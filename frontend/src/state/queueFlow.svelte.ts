/** Everything between "Prepare for Install" and the phone: conflict checks, shared bundles, the cache list and transfer. */
import { api, type CachedBundle, type Config, type Device, type SharedBundleGroup, type SharedMod } from '../lib/api'
import type { IndexMod } from '../lib/classify'
import {
  detectSelectionConflicts, foldersOf, isActive, isQueuedFromCache, jobFromCached, newJob, resolveSelection,
  type Conflict, type SelectionConflict,
} from '../lib/queue'
import type { QueueRunner } from '../lib/runner'

interface Host {
  config: Config | null
  devices: Device[]
  runner: QueueRunner
  log(message: string, level?: string): void
  refreshConfig(): Promise<void>
  clearSelection(): void
}

export class QueueFlow {
  open = $state(false)
  cached = $state<CachedBundle[]>([])
  cacheQuery = $state('')
  cacheError = $state('')
  transferMessage = $state('')
  /** Number of conflict / shared-bundle checks in flight (they can take a few seconds): shown as a toast. */
  checks = $state(0)
  /** Selected mods that clash with each other or with installed mods (asked before queueing). */
  conflictPrompt = $state<{ mods: IndexMod[]; conflicts: SelectionConflict<IndexMod>[] } | null>(null)
  /** Mods whose game bundle also holds installed mods (asked before queueing). */
  sharedPrompt = $state<{ mods: IndexMod[]; groups: SharedBundleGroup[]; replaces: Record<string, string[]>; cached?: CachedBundle[] } | null>(null)
  /** Ready jobs that replace the same asset (asked before transferring). */
  queueConflicts = $state<Conflict[] | null>(null)

  constructor(private host: Host) {}

  // Getters, not $derived: field initialisers run before the constructor stores `host`.
  get deviceId() {
    return this.host.devices.find((d) => d.status === 'device')?.id ?? ''
  }

  get visibleCached() {
    const q = this.cacheQuery.trim().toLowerCase()
    if (!q) return this.cached
    return this.cached.filter((m) => [m.mod_name, m.bundle_name, m.folder_name].some((s) => s?.toLowerCase().includes(q)))
  }

  show() {
    this.open = true
    void this.loadCached()
  }

  private autoShow() {
    if (this.host.config?.settings?.auto_expand_on_install === true) this.show()
  }

  // ---- queueing ----------------------------------------------------------------------------------------------

  /** Step 1: conflicts inside the selection or with installed mods (asks the user), then step 2. */
  async queueMods(mods: IndexMod[]) {
    if (!mods.length || !this.host.config) return
    this.autoShow()
    this.host.log(`Checking ${mods.length} mod(s) for conflicts and shared game bundles before preparing…`)
    this.checks++
    try {
      try {
        const { mods: installed } = await api.installedMods()
        const found = detectSelectionConflicts(mods, installed)
        if (found.length) return void (this.conflictPrompt = { mods, conflicts: found })
      } catch (e) {
        this.host.log(`Installed-mod conflict check skipped: ${e}`, 'warning')
      }
      await this.checkShared(mods, {})
    } finally {
      this.checks--
    }
  }

  resolveSelectionConflicts(choices: Record<string, string>) {
    const prompt = this.conflictPrompt
    if (!prompt) return
    this.conflictPrompt = null
    const resolved = resolveSelection(prompt.mods, prompt.conflicts, choices)
    const skipped = prompt.mods.length - resolved.mods.length
    if (skipped) this.host.log(`Conflict resolution skipped ${skipped} mod(s).`)
    void this.checkShared(resolved.mods, resolved.replaces)
  }

  /** Step 2: does the game bundle also hold installed mods? If so, offer to rebuild them together. */
  private async checkShared(mods: IndexMod[], replaces: Record<string, string[]>) {
    const config = this.host.config
    if (!mods.length || !config) return
    const replaced = new Set(Object.values(replaces).flat())
    this.checks++
    try {
      const check = await api.checkShared({
        mod_folders: mods.map((m) => m.folder_path),
        installed_mod_names: config.installed_mods.filter((n) => !replaced.has(n)),
        queue_mod_folders: this.host.runner.jobs.filter(isActive).flatMap(foldersOf),
        quality: config.quality || 'HD',
      })
      // Installed companions already new or queued are rebuilt together anyway; only the others need a decision.
      const accounted = new Set([...mods.map((m) => m.folder_path), ...this.host.runner.jobs.filter(isActive).flatMap(foldersOf)])
      const groups = Object.values(check.bundle_groups ?? {}).filter((g) => g.installed_mods.some((m) => !accounted.has(m.folder_path)))
      if (check.has_shared && groups.length) return void (this.sharedPrompt = { mods, groups, replaces })
    } catch (e) {
      this.host.log(`Shared bundle check skipped: ${e}`, 'warning')
    } finally {
      this.checks--
    }
    this.enqueue(mods, [], replaces)
  }

  enqueue(mods: IndexMod[], extra: SharedMod[], replaces: Record<string, string[]>) {
    const quality = this.host.config?.quality || 'HD'
    const cached = this.sharedPrompt?.cached ?? []
    const added = this.host.runner.add([
      ...cached.map((c) => jobFromCached(c)),
      ...mods.map((m) => newJob(m, quality, replaces[m.folder_path])),
      ...extra.map((m) => newJob(m, quality)),
    ])
    this.host.log(`Added ${added} mod(s) to the processing queue.`)
    this.host.clearSelection()
    this.sharedPrompt = null
  }

  // ---- transfer ----------------------------------------------------------------------------------------------

  async transfer() {
    this.transferMessage = ''
    this.queueConflicts = null
    if (!this.deviceId) return void (this.transferMessage = 'No phone connected. Connect it with USB debugging enabled, then press Check ADB.')
    // Mods in one game bundle replace each other when uploaded separately, so the ones still preparing may belong with the ready ones.
    const pending = this.host.runner.jobs.filter((j) => j.status === 'queued' || j.status === 'preparing').length
    if (pending && !confirm(`${pending} mod(s) are still preparing.\n\nMods that share a game bundle with the ready ones (for example other dating mods) are only installed together if you wait for them. Transfer the ready mods now anyway?`)) return
    const outcome = await this.host.runner.transfer(this.deviceId)
    if (outcome.status === 'conflicts') this.queueConflicts = outcome.conflicts
    else if (outcome.status === 'error') this.transferMessage = outcome.message
    else if (outcome.status === 'nothing') this.transferMessage = 'Nothing is ready to transfer.'
    else await this.host.refreshConfig()
  }

  /** Keep the chosen job of each conflicting group; the others leave the queue. */
  resolveQueueConflicts(choices: Record<string, string>) {
    for (const conflict of this.queueConflicts ?? []) this.host.runner.resolveConflict(conflict, choices[conflict.assetKey] ?? conflict.jobs[0].id)
    this.queueConflicts = null
  }

  // ---- cache of prepared bundles -----------------------------------------------------------------------------

  async loadCached() {
    try {
      this.cached = (await api.cachedBundles()).mods
      this.cacheError = ''
    } catch {
      this.cacheError = 'Failed to load cached mods'
    }
  }

  isCachedQueued = (item: CachedBundle) => isQueuedFromCache(this.host.runner.jobs, item)

  async addCached(item: CachedBundle) {
    if (this.isCachedQueued(item)) return this.host.log(`"${item.mod_name}" is already ready in the queue.`)
    await this.addFromCache([item])
  }

  async addAllCached() {
    const fresh = this.visibleCached.filter((m) => !m.is_broken && !this.isCachedQueued(m))
    if (!fresh.length) return this.host.log('Every cached mod is already in the queue.')
    await this.addFromCache(fresh)
  }

  /** Cached bundles join the queue like new mods do: when their game bundle also holds installed mods, the same question is asked first. */
  private async addFromCache(items: CachedBundle[]) {
    const config = this.host.config
    const folders = items.flatMap((c) => (c.mod_folders?.length ? c.mod_folders : [c.mod_folder])).filter(Boolean)
    const add = () => {
      this.host.runner.add(items.map((c) => jobFromCached(c)))
      this.host.log(items.length === 1 ? `Added "${items[0].mod_name}" from the cache.` : `Added ${items.length} cached mod(s) to the queue.`)
    }
    if (!config || !folders.length) return add()
    this.checks++
    try {
      const active = this.host.runner.jobs.filter(isActive).flatMap(foldersOf)
      const check = await api.checkShared({ mod_folders: folders, installed_mod_names: config.installed_mods, queue_mod_folders: active, quality: config.quality || 'HD' })
      const accounted = new Set([...folders, ...active])
      const groups = Object.values(check.bundle_groups ?? {}).filter((g) => g.installed_mods.some((m) => !accounted.has(m.folder_path)))
      if (check.has_shared && groups.length) return void (this.sharedPrompt = { mods: [], groups, replaces: {}, cached: items })
    } catch (e) {
      this.host.log(`Shared bundle check skipped: ${e}`, 'warning')
    } finally {
      this.checks--
    }
    add()
  }

  async deleteCached(item: CachedBundle) {
    if (!confirm(`Delete the prepared files of "${item.mod_name}" from the cache?`)) return
    try {
      await api.deleteCachedBundle(item.folder_name)
      this.host.log(`Deleted "${item.mod_name}" from the cache.`, 'success')
      await this.loadCached()
      await this.host.runner.revalidate()
    } catch (e) {
      this.host.log(`Could not delete "${item.mod_name}": ${e}`, 'error')
    }
  }
}
