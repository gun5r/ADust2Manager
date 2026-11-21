/** Pure queue rules: job creation, conflict detection and bundle grouping (ported from the classic ConflictSystem). */
import type { CachedBundle, JobStatus, Mod, QueueJob, SharedMod } from './api'

export const ACTIVE: JobStatus[] = ['queued', 'preparing', 'prepared']
export const DEAD: JobStatus[] = ['cancelled', 'failed_prepare', 'failed_transfer', 'completed']

let counter = 0
const jobId = () => `job_${Date.now()}_${(counter++).toString(36)}${Math.random().toString(36).slice(2, 6)}`

type Queueable = Pick<Mod, 'name' | 'folder_path' | 'asset_key' | 'character' | 'category'> &
  Partial<Pick<Mod, 'files' | 'source_folder'>> & { asset_keys?: string[] }

export function newJob(mod: Queueable | SharedMod, quality: string, replaces: string[] = []): QueueJob {
  const asset_keys = 'asset_keys' in mod && mod.asset_keys ? mod.asset_keys : []
  return {
    id: jobId(),
    mod_folder: mod.folder_path,
    files: mod.files ?? [],
    asset_key: (mod.asset_key || '').toLowerCase(),
    asset_keys,
    mod_folders: null,
    mod_name: mod.name,
    mod_names: null,
    character: mod.character || 'Others',
    category: mod.category || 'other',
    quality,
    status: 'queued',
    progress: 0,
    progress_text: 'Waiting to prepare…',
    error: null,
    prepared_data: null,
    replaces_installed_mods: replaces.length ? replaces : null,
    cancelled: false,
    portrait_folder: (mod as { source_folder?: string }).source_folder ?? null,
  }
}

/** A job interrupted by closing the app resumes from the nearest safe state. */
export function restoreJob(job: QueueJob): QueueJob {
  const status: JobStatus = job.status === 'preparing' ? 'queued' : job.status === 'transferring' ? 'prepared' : job.status
  return { ...job, status: status || 'queued', cancelled: false }
}

export const isActive = (job: QueueJob) => ACTIVE.includes(job.status)

export function assetKeysOf(job: QueueJob): string[] {
  const prepared = job.prepared_data?.asset_keys
  const keys = prepared?.length ? prepared : job.asset_keys
  const list = keys?.length ? keys : [job.prepared_data?.asset_key || job.asset_key]
  return [...new Set(list.filter(Boolean).map((k) => k.toLowerCase()))]
}

export function bundleIdOf(job: QueueJob): string | null {
  const hash = job.prepared_data?.bundle_hash?.trim()
  if (hash) return hash.toLowerCase()
  const name = job.prepared_data?.bundle_name?.trim()
  return name ? name.toLowerCase() : null
}

export interface Conflict {
  assetKey: string
  jobs: QueueJob[]
}

/** Active jobs that replace the same game asset: only one of them can win. */
export function detectConflicts(jobs: QueueJob[]): Conflict[] {
  const groups = new Map<string, QueueJob[]>()
  for (const job of jobs.filter(isActive)) {
    for (const key of assetKeysOf(job)) {
      if (key === 'unknown') continue
      const members = groups.get(key) ?? []
      if (!members.includes(job)) members.push(job)
      groups.set(key, members)
    }
  }
  return [...groups].filter(([, members]) => members.length > 1).map(([assetKey, members]) => ({ assetKey, jobs: members }))
}

export interface BundleGroup {
  hash: string | null
  jobs: QueueJob[]
  /** Several different assets target one bundle: they must be assembled into a single upload. */
  needsAssembly: boolean
  /** Two jobs in the group replace the same asset. */
  hasConflict: boolean
}

export function groupByBundle(jobs: QueueJob[]): BundleGroup[] {
  const byBundle = new Map<string, QueueJob[]>()
  const loose: QueueJob[] = []
  for (const job of jobs) {
    const id = bundleIdOf(job)
    if (!id) loose.push(job)
    else byBundle.set(id, [...(byBundle.get(id) ?? []), job])
  }
  const groups: BundleGroup[] = [...byBundle].map(([hash, members]) => ({
    hash,
    jobs: members,
    needsAssembly: members.length > 1,
    hasConflict: detectConflicts(members).length > 0,
  }))
  return [...groups, ...loose.map((job) => ({ hash: null, jobs: [job], needsAssembly: false, hasConflict: false }))]
}

export const foldersOf = (job: QueueJob) => job.mod_folders?.length ? job.mod_folders : [job.mod_folder]
export const namesOf = (job: QueueJob) => job.mod_names?.length ? job.mod_names : [job.mod_name]

export function summarize(jobs: QueueJob[]) {
  const count = (...statuses: JobStatus[]) => jobs.filter((j) => statuses.includes(j.status)).length
  return {
    waiting: count('queued', 'preparing'),
    ready: count('prepared'),
    transferring: count('transferring'),
    done: count('completed'),
    failed: count('failed_prepare', 'failed_transfer'),
  }
}

type Selectable = Pick<Mod, 'name' | 'folder_path' | 'asset_key'> & { asset_keys?: string[] }

/** A selected or installed mod's game assets (lowercased, 'unknown' dropped). */
export function modAssetKeys(mod: Selectable): string[] {
  const keys = mod.asset_keys?.length ? mod.asset_keys : [mod.asset_key]
  return [...new Set(keys.filter(Boolean).map((k) => k.toLowerCase()).filter((k) => k !== 'unknown'))]
}

export interface SelectionConflict<T extends Selectable = Selectable> {
  assetKey: string
  /** Selected mods that replace this asset. */
  items: T[]
  /** A different mod already installed for this asset, if any. */
  installed: Selectable | null
}

/**
 * Conflicts inside a selection about to be queued: several selected mods for one asset, or a selected mod for an
 * asset that another installed mod already provides. Re-installing the same mod is not a conflict.
 */
export function detectSelectionConflicts<T extends Selectable>(mods: T[], installed: Selectable[]): SelectionConflict<T>[] {
  const groups = new Map<string, T[]>()
  for (const mod of mods) {
    for (const key of modAssetKeys(mod)) {
      const members = groups.get(key) ?? []
      if (!members.includes(mod)) members.push(mod)
      groups.set(key, members)
    }
  }
  const result: SelectionConflict<T>[] = []
  for (const [assetKey, items] of groups) {
    const other = installed.find(
      (im) => modAssetKeys(im).includes(assetKey) && !items.some((it) => it.folder_path === im.folder_path || it.name === im.name),
    )
    if (items.length > 1 || other) result.push({ assetKey, items, installed: other ?? null })
  }
  return result
}

export const KEEP_INSTALLED = '__keep_installed__'
export const SKIP_ALL = '__skip__'

/**
 * Apply per-asset choices (a mod's folder_path, KEEP_INSTALLED or SKIP_ALL). A mod rejected in any conflict is
 * dropped; a chosen mod that beats an installed one records it in `replaces` (it is un-marked after the upload).
 */
export function resolveSelection<T extends Selectable>(
  mods: T[], conflicts: SelectionConflict<T>[], choices: Record<string, string>,
): { mods: T[]; replaces: Record<string, string[]> } {
  const rejected = new Set<string>()
  const replaces: Record<string, string[]> = {}
  for (const conflict of conflicts) {
    const choice = choices[conflict.assetKey] ?? conflict.items[0].folder_path
    const chosen = conflict.items.find((it) => it.folder_path === choice)
    for (const item of conflict.items) if (item !== chosen) rejected.add(item.folder_path)
    if (chosen && conflict.installed) {
      replaces[chosen.folder_path] = [...new Set([...(replaces[chosen.folder_path] ?? []), conflict.installed.name])]
    }
  }
  const kept = mods.filter((m) => !rejected.has(m.folder_path))
  return { mods: kept, replaces: Object.fromEntries(Object.entries(replaces).filter(([path]) => !rejected.has(path))) }
}

/** A prepared bundle already on disk becomes a job that is ready to transfer (no preparation needed). */
export function jobFromCached(item: CachedBundle): QueueJob {
  const keys = item.asset_keys?.length ? item.asset_keys : []
  const assetKey = (item.asset_key && item.asset_key !== 'unknown' ? item.asset_key : keys[0] ?? '').toLowerCase()
  return {
    id: jobId().replace('job_', 'job_cache_'),
    mod_folder: item.mod_folder || '',
    files: item.files ?? [],
    asset_key: assetKey,
    asset_keys: keys,
    mod_folders: item.mod_folders?.length ? item.mod_folders : null,
    mod_name: item.mod_name,
    mod_names: item.mod_names?.length ? item.mod_names : null,
    character: item.character || 'Others',
    category: item.category || 'other',
    quality: item.quality,
    status: 'prepared',
    progress: 100,
    progress_text: 'Ready to transfer (from cache)',
    error: null,
    prepared_data: {
      bundle_name: item.bundle_name,
      bundle_hash: item.bundle_hash,
      repacked_path: item.repacked_path,
      quality: item.quality,
      asset_key: assetKey,
      asset_keys: keys,
      mod_folder: item.mod_folder || '',
      mod_folders: item.mod_folders?.length ? item.mod_folders : undefined,
      mod_name: item.mod_name,
      files: item.files ?? [],
      asset_stem: item.asset_stem || item.mod_name,
    },
    replaces_installed_mods: null,
    cancelled: false,
  }
}

export const isQueuedFromCache = (jobs: QueueJob[], item: CachedBundle): boolean =>
  jobs.some((j) => j.status === 'prepared' && (j.prepared_data?.repacked_path === item.repacked_path || j.mod_name === item.mod_name))
