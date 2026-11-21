/** Queue orchestration: persistence, concurrent preparation, and the assemble-then-transfer pipeline. */
import type { PrepareRequest, QueueJob, TransferRequest } from './api'
import { detectConflicts, foldersOf, groupByBundle, isActive, namesOf, restoreJob, type Conflict } from './queue'

export const MAX_PREPARE_CONCURRENCY = 3
export const TRANSFER_BATCH = 5

export interface RunnerApi {
  queueState(): Promise<{ queue: QueueJob[]; issues: { mod_name?: string; issue?: string }[] }>
  saveQueue(queue: QueueJob[]): Promise<unknown>
  prepare(request: PrepareRequest): Promise<{ success: boolean; data?: QueueJob['prepared_data']; error?: string; cancelled?: boolean }>
  cancelPrepare(jobId: string, folder: string): Promise<unknown>
  transfer(request: TransferRequest): Promise<{ success: boolean; error?: string }>
  toggleInstalled(modName: string, installed: boolean): Promise<unknown>
}

export type TransferOutcome =
  | { status: 'done'; transferred: number }
  | { status: 'conflicts'; conflicts: Conflict[] }
  | { status: 'nothing' }
  | { status: 'error'; message: string }

export class QueueRunner {
  jobs: QueueJob[] = []
  transferring = false
  private preparing = 0
  private saveTimer: ReturnType<typeof setTimeout> | undefined

  constructor(
    private api: RunnerApi,
    private onChange: () => void,
    private log: (message: string, level?: string) => void = () => {},
    private saveDelay = 400,
  ) {}

  async load(): Promise<void> {
    const state = await this.api.queueState()
    this.jobs = state.queue.map(restoreJob)
    if (state.issues.length) this.log(`Restored queue: ${state.issues.length} mod(s) have missing files.`, 'warning')
    this.changed(false)
    this.pump()
  }

  /** Queue jobs; folders that are already queued, preparing or ready are skipped. Returns how many were added. */
  add(newJobs: QueueJob[]): number {
    const taken = new Set(this.jobs.filter(isActive).flatMap(foldersOf))
    const fresh = newJobs.filter((job) => !taken.has(job.mod_folder))
    this.jobs.push(...fresh)
    this.changed()
    this.pump()
    return fresh.length
  }

  private pump(): void {
    while (this.preparing < MAX_PREPARE_CONCURRENCY) {
      const job = this.jobs.find((j) => j.status === 'queued')
      if (!job) break
      this.preparing++
      void this.prepare(job)
    }
  }

  private async prepare(job: QueueJob): Promise<void> {
    job.status = 'preparing'
    job.progress = 25
    job.progress_text = 'Downloading and preparing assets…'
    this.changed(false)
    try {
      const request: PrepareRequest = { mod_folder: job.mod_folder, quality: job.quality, job_id: job.id }
      if (job.mod_folders?.length) request.mod_folders = job.mod_folders
      const result = await this.api.prepare(request)
      if (job.cancelled || !this.jobs.includes(job)) return
      if (!result.success || !result.data) {
        if (result.cancelled) return
        throw new Error(result.error || 'Preparation failed')
      }
      Object.assign(job, { status: 'prepared', progress: 100, progress_text: 'Ready to transfer', error: null, prepared_data: result.data })
      this.log(`Prepared ${job.mod_name}`, 'success')
    } catch (error) {
      if (job.cancelled || !this.jobs.includes(job)) return
      const message = error instanceof Error ? error.message : String(error)
      Object.assign(job, { status: 'failed_prepare', error: message, progress: 0, progress_text: `Preparation failed: ${message}` })
      this.log(`Preparation failed for ${job.mod_name}: ${message}`, 'error')
    } finally {
      this.preparing = Math.max(0, this.preparing - 1)
      this.changed()
      this.pump()
    }
  }

  cancel(id: string): void {
    const job = this.jobs.find((j) => j.id === id)
    if (!job) return
    if (job.status === 'preparing') void this.api.cancelPrepare(job.id, job.mod_folder).catch(() => {})
    job.cancelled = true
    job.status = 'cancelled'
    job.progress_text = 'Cancelled'
    this.changed()
  }

  retry(id: string): void {
    const job = this.jobs.find((j) => j.id === id)
    if (!job || !['failed_prepare', 'failed_transfer', 'cancelled'].includes(job.status)) return
    const transferOnly = job.status === 'failed_transfer' && job.prepared_data
    Object.assign(job, {
      status: transferOnly ? 'prepared' : 'queued',
      cancelled: false,
      error: null,
      progress: transferOnly ? 100 : 0,
      progress_text: transferOnly ? 'Ready to transfer' : 'Waiting to prepare…',
    })
    this.changed()
    this.pump()
  }

  remove(id: string): void {
    const job = this.jobs.find((j) => j.id === id)
    if (job?.status === 'preparing') this.cancel(id)
    this.jobs = this.jobs.filter((j) => j.id !== id)
    this.changed()
  }

  clear(kind: 'done' | 'failed' | 'waiting' | 'ready'): void {
    const match: Record<typeof kind, QueueJob['status'][]> = {
      done: ['completed'], failed: ['failed_prepare', 'failed_transfer', 'cancelled'], waiting: ['queued'], ready: ['prepared'],
    }
    this.jobs = this.jobs.filter((j) => !match[kind].includes(j.status))
    this.changed()
  }

  /** Keep one of several jobs that replace the same asset; the others leave the queue. */
  resolveConflict(conflict: Conflict, keepId: string): void {
    for (const job of conflict.jobs) if (job.id !== keepId) this.remove(job.id)
  }

  /**
   * Upload every prepared job. Jobs for different assets in one bundle are first assembled into a single bundle
   * (separate uploads would overwrite each other). Assembly failure stops everything; nothing is uploaded.
   */
  async transfer(deviceId: string): Promise<TransferOutcome> {
    if (this.transferring) return { status: 'nothing' }
    for (const job of this.jobs.filter((j) => j.status === 'prepared' && !j.prepared_data?.repacked_path)) {
      Object.assign(job, { status: 'failed_transfer', error: 'Missing prepared bundle file path. Retry preparation.' })
    }
    const ready = this.jobs.filter((j) => j.status === 'prepared')
    this.changed()
    if (!ready.length) return { status: 'nothing' }

    const conflicts = detectConflicts(ready)
    const groups = groupByBundle(ready)
    if (conflicts.length || groups.some((g) => g.hasConflict)) return { status: 'conflicts', conflicts }

    this.transferring = true
    try {
      const queue: QueueJob[] = []
      for (const group of groups) {
        if (!group.needsAssembly) {
          queue.push(...group.jobs)
          continue
        }
        const head = await this.assemble(group.jobs)
        if (typeof head === 'string') return { status: 'error', message: head }
        queue.push(head)
      }
      this.log(`Transferring ${queue.length} bundle(s) in batches of ${TRANSFER_BATCH}…`, 'start')
      for (let i = 0; i < queue.length; i += TRANSFER_BATCH) {
        await Promise.all(queue.slice(i, i + TRANSFER_BATCH).map((job) => this.send(job, deviceId)))
      }
      return { status: 'done', transferred: queue.filter((j) => j.status === 'completed').length }
    } finally {
      this.transferring = false
      this.changed()
    }
  }

  /** Merge several prepared jobs into the first one. Returns the merged job, or an error message. */
  private async assemble(jobs: QueueJob[]): Promise<QueueJob | string> {
    const [head, ...rest] = jobs
    const folders = [...new Set(jobs.flatMap(foldersOf))]
    const names = [...new Set(jobs.flatMap(namesOf))]
    const replaced = [...new Set(jobs.flatMap((j) => j.replaces_installed_mods ?? []))]
    const before = { ...head }
    this.log(`Assembling ${jobs.length} mods that share bundle ${head.prepared_data?.bundle_hash.slice(0, 8)}…`, 'info')
    Object.assign(head, { status: 'preparing', progress: 50, progress_text: `Assembling ${jobs.length} shared mods…` })
    this.changed(false)
    try {
      const result = await this.api.prepare({
        mod_folder: folders[0], mod_folders: folders, quality: head.prepared_data?.quality || head.quality, job_id: head.id,
      })
      if (!result.success || !result.data) throw new Error(result.error || 'Shared bundle assembly failed')
      Object.assign(head, {
        prepared_data: result.data, mod_folders: folders, mod_names: names,
        replaces_installed_mods: replaced.length ? replaced : head.replaces_installed_mods,
        mod_name: `${names[0]} (+ ${names.length - 1} assembled mods)`,
        status: 'prepared', progress: 100, progress_text: 'Ready to transfer (assembled)',
      })
      for (const job of rest) Object.assign(job, { status: 'completed', progress: 100, progress_text: `Assembled with ${head.mod_name} ✓` })
      return head
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      Object.assign(head, before, { status: 'prepared', error: message, progress_text: 'Assembly failed; retry transfer' })
      this.log(`Transfer stopped: ${message}. Shared mods must be assembled before uploading.`, 'error')
      return message
    }
  }

  private async send(job: QueueJob, deviceId: string): Promise<void> {
    const data = job.prepared_data
    if (!data) {
      Object.assign(job, { status: 'failed_transfer', error: 'Missing prepared bundle data. Retry preparation.' })
      return
    }
    Object.assign(job, { status: 'transferring', progress: 50, progress_text: 'Pushing to phone via ADB…' })
    this.changed(false)
    try {
      const result = await this.api.transfer({
        device_id: deviceId, bundle_name: data.bundle_name, bundle_hash: data.bundle_hash,
        repacked_path: data.repacked_path, mod_name: job.mod_name, mod_folder: job.mod_folder,
        ...(job.mod_names?.length ? { mod_names: job.mod_names } : {}),
      })
      if (!result.success) throw new Error(result.error || 'ADB transfer failed')
      Object.assign(job, { status: 'completed', progress: 100, progress_text: 'Installed on phone ✓', error: null })
      this.log(`Installed on phone: ${job.mod_name}`, 'success')
      await this.unmarkReplaced(job)
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      Object.assign(job, { status: 'failed_transfer', error: message, progress_text: `Transfer error: ${message}` })
      this.log(`Transfer failed for ${job.mod_name}: ${message}`, 'error')
    } finally {
      this.changed()
    }
  }

  /** The upload replaced these installed mods' assets, so they are no longer active on the phone. */
  private async unmarkReplaced(job: QueueJob): Promise<void> {
    const installedNow = new Set(namesOf(job))
    for (const name of job.replaces_installed_mods ?? []) {
      if (!name || installedNow.has(name)) continue
      try {
        await this.api.toggleInstalled(name, false)
        this.log(`Marked "${name}" as no longer installed (replaced by ${job.mod_name}).`, 'info')
      } catch {
        this.log(`Could not un-mark replaced mod "${name}".`, 'warning')
      }
    }
  }

  /** Save, then reload so the server re-checks every job (e.g. after cached bundles were deleted). */
  async revalidate(): Promise<void> {
    await this.flush()
    await this.load()
  }

  /** Flush a pending save immediately (used by tests and before unloading). */
  async flush(): Promise<void> {
    clearTimeout(this.saveTimer)
    await this.api.saveQueue(this.jobs.map(({ ...job }) => job))
  }

  private changed(persist = true): void {
    this.onChange()
    if (!persist) return
    clearTimeout(this.saveTimer)
    this.saveTimer = setTimeout(() => void this.flush().catch(() => this.log('Could not save the queue', 'warning')), this.saveDelay)
  }
}
