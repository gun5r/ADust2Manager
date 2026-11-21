export interface Mod {
  id?: string
  asset_keys?: string[]
  name: string
  folder_name: string
  folder_path: string
  category: string
  character: string
  asset_key: string
  is_multi: boolean
  png_files: string[]
  files: string[]
  texture_count: number
  /** A variant prepared out of a multimod: the variant's own folder, which holds its portrait. */
  source_folder?: string
}

export interface FolderTab {
  id: string
  name: string
  path: string
  color?: string
  /** Legacy flag the classic UI honours when scanning: treat the folder's subfolders as multi-variant packs. */
  is_multi_folder?: boolean
}

/** Shared with the classic UI (config.settings); unknown keys are preserved. */
export interface Settings {
  /** Colour theme (Settings > Appearance): 'graphite' (default) or 'black'. */
  theme?: 'graphite' | 'black'
  expand_console_default?: boolean
  auto_expand_on_install?: boolean
  auto_mark_installed?: boolean
  isolated_character_list?: boolean
  /** The colour legend under Prepare for Install in the main list (on unless switched off). */
  show_legend?: boolean
  /** Costume mode (clusters): fill every row completely, cutting a character's costumes between rows when needed (on unless switched off). */
  costume_wrap?: boolean
  /** The options row above the costume list (Mod view, size sliders, Hide Options); on unless hidden. */
  costume_options?: boolean
  /** The preview's panels take the canvas colour, without outlines, so it looks like one surface (on unless switched off). */
  seamless_viewer?: boolean
  /** Roster and Costume mode also list the characters and costumes that have no mods yet (greyed out). Off unless switched on. */
  show_empty_characters?: boolean
  /** Icons on the portrait badges (on unless switched off: then plain coloured badges with the number). */
  badge_icons?: boolean
  /** Troubleshooting: the textures of the previews are premultiplied already (washed-out or dark edges otherwise). */
  pma_textures?: boolean
  /** Repack several mods at once (faster, much heavier on the PC). Off: downloads overlap, repacking is one at a time. */
  turbo_mode?: boolean
  [key: string]: unknown
}

export interface CacheBucket {
  bytes: number
  formatted: string
  files: number
}

export interface CacheStats {
  total_bytes: number
  total_formatted: string
  originals: CacheBucket
  catalogs: CacheBucket
  repacked: CacheBucket
  thumbnails: CacheBucket
  audio: CacheBucket
}

export interface CachedBundle {
  id: string
  folder_name: string
  mod_name: string
  mod_names?: string[]
  mod_folder: string
  mod_folders?: string[]
  bundle_name: string
  bundle_hash: string
  repacked_path: string
  size_bytes: number
  size_str: string
  modified_time: number
  quality: string
  asset_key?: string
  asset_keys?: string[]
  asset_stem?: string
  files?: string[]
  character?: string
  category?: string
  is_broken: boolean
  broken_reason?: string
}

export interface Config {
  mods_dir: string
  quality?: string
  settings?: Settings
  folder_tabs: FolderTab[]
  active_tab_id: string
  installed_mods: string[]
  templates?: Record<string, Record<string, string[]>>
}

export interface ModPage {
  total: number
  offset: number
  limit: number
  mods: Mod[]
}

export type Facets = Record<'character' | 'category' | 'root', Record<string, number>>

export interface ModQuery {
  q: string
  character: string
  category: string
  root: string
  sort: string
}

async function json<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  if (!response.ok) {
    // FastAPI answers {"detail": "..."}: show that text when there is one.
    const detail = await response.json().then((b) => (typeof b?.detail === 'string' ? b.detail : ''), () => '')
    throw new Error(detail || `${response.status} ${url}`)
  }
  return response.json()
}

const post = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'content-type': 'application/json' },
  body: JSON.stringify(body),
})

export const buildModsUrl = (query: ModQuery, offset: number, limit: number): string => {
  const params = new URLSearchParams({ sort: query.sort, offset: String(offset), limit: String(limit) })
  for (const key of ['q', 'character', 'category', 'root'] as const) if (query[key]) params.set(key, query[key])
  return `/api/mods?${params}`
}

import type { SceneRules } from './dating'
import type { SoundManifest } from './datingAudio'

/** Sounds of a dating scene (downloaded on demand): what the server knows about it. */
export interface DatingAudio {
  available: boolean
  cached: boolean
  /** Voice languages present in the downloaded plans. */
  voice?: string[]
  animations?: number
  download_mb?: number
}

export const datingClipUrl = (scene: string, name: string): string =>
  `/api/dating-audio/${encodeURIComponent(scene)}/clip/${encodeURIComponent(name)}`

export interface Mascot {
  id: string
  mod_name: string
  character: string
  layer: 'above' | 'below'
  draggable: boolean
  locked: boolean
  click_through: boolean
  scale: number
  opacity: number
  status: string
}

export interface MascotLaunch {
  mod_name: string
  folder_path: string
  asset_stem: string
  category: string
  character: string
  files: string[]
  default_animation: string
  is_multi?: boolean
  variant_path?: string
}

export interface MascotDiagnostics { has_pyside6: boolean; has_pyqt6: boolean }

export const thumbUrl = (mod: Mod, size = 256): string | null =>
  mod.png_files?.length
    ? `/api/mods/thumb?${new URLSearchParams({ folder: mod.folder_path, file: mod.png_files[0], size: String(size) })}`
    : null

export interface PreparedData {
  bundle_name: string
  bundle_hash: string
  repacked_path: string
  quality: string
  asset_key?: string
  asset_keys?: string[]
  mod_folder: string
  mod_folders?: string[]
  mod_name: string
  mod_names?: string[]
  files?: string[]
  asset_stem?: string
}

export type JobStatus =
  | 'queued' | 'preparing' | 'prepared' | 'transferring' | 'completed' | 'failed_prepare' | 'failed_transfer' | 'cancelled'

/** Same shape the classic UI persists in /api/queue/state, so both UIs share one queue. */
export interface QueueJob {
  id: string
  mod_folder: string
  files: string[]
  asset_key: string
  asset_keys: string[]
  mod_folders: string[] | null
  mod_name: string
  mod_names: string[] | null
  character: string
  category: string
  quality: string
  status: JobStatus
  progress: number
  progress_text: string
  error: string | null
  prepared_data: PreparedData | null
  replaces_installed_mods?: string[] | null
  cancelled?: boolean
  /** Folder that holds this mod's portrait when it differs from `mod_folder` (a variant of a multimod). */
  portrait_folder?: string | null
}

export interface PrepareRequest {
  mod_folder: string
  mod_folders?: string[]
  quality: string
  job_id: string
}

export interface TransferRequest {
  device_id: string
  bundle_name: string
  bundle_hash: string
  repacked_path: string
  mod_name: string
  mod_names?: string[]
  mod_folder: string
}

export interface SharedMod {
  name: string
  folder_path: string
  character: string
  category: string
  asset_key: string
  files?: string[]
  source?: string
  source_folder?: string
}

export interface SharedBundleGroup {
  bundle_hash: string
  new_mods: SharedMod[]
  queue_mods: SharedMod[]
  installed_mods: SharedMod[]
  total_mods_count: number
}

/** A backup of an original game bundle on the phone (made before a mod overwrote it). */
export interface PhoneBackup { bundle_name: string; bundle_hash: string; size: number; modified: number }

export interface Device {
  id: string
  status: string
  model?: string
  game_installed: boolean
}

export interface PreviewImage {
  name: string
  rel_path: string
  full_path: string
}

/** A picture in a pack that is not a skin (preview, guide, comparison). */
export interface PackPreview extends PreviewImage {
  folder: string
}

export interface PackVariant {
  id: string
  name: string
  stem: string
  category: string
  rel_path: string
  full_path: string
  files: string[]
  asset_keys: string[]
  asset_key: string
}

export interface PackOption {
  id: string
  name: string
  rel_path: string
  full_path: string
  category: string
  previews: PreviewImage[]
  variants: PackVariant[]
}

export interface PackCategory {
  id: string
  name: string
  rel_path: string
  full_path: string
  previews: PreviewImage[]
  options: PackOption[]
}

export interface PreparedVariant {
  name: string
  folder_path: string
  source_folder?: string
  character: string
  variant_name: string
  asset_keys: string[]
  files: string[]
  asset_stem: string
  asset_key: string
}

export interface DuplicateSide {
  folder_path: string
  name: string
  file_count: number
  size_bytes?: number
}

export interface ExactDuplicate {
  name: string
  mod1: DuplicateSide
  mod2: DuplicateSide
  different_names: boolean
}

export interface NameCollision {
  name: string
  suggested_name: string
  mod1: DuplicateSide
  mod2: DuplicateSide
}

export interface Character {
  name: string
  costume_id: string
  image_url: string
  aliases: string[]
  costumes: Record<string, string>
  /** Dating scene (`illust_dating<N>`) -> id of the costume it belongs to. */
  dating?: Record<string, string>
}

export const api = {
  config: () => json<Config>('/api/config'),
  datingRules: (scene: string) => json<SceneRules>(`/api/dating-rules/${encodeURIComponent(scene)}`),
  datingManifest: (scene: string) => json<SoundManifest>(`/api/dating-audio/${encodeURIComponent(scene)}/manifest`),
  datingAudio: (scene: string) => json<DatingAudio>(`/api/dating-audio/${encodeURIComponent(scene)}`),
  downloadDatingAudio: (scene: string) => json<DatingAudio>(`/api/dating-audio/${encodeURIComponent(scene)}/download`, { method: 'POST' }),
  datingDataInfo: () => json<DatingInfo>('/api/tools/dating-data'),
  downloadDatingSounds: () => json<{ downloaded: number[]; failed: number[] } & DatingInfo>('/api/tools/dating-data/sounds', { method: 'POST' }),
  datingScenes: () => json<{ scenes: { scene: string; number: number; character: string | null; costume: string | null }[] }>('/api/tools/dating-scenes'),
  downloadDatingScene: (scene: string, root: string) => json<{ folders: string[]; root: string }>('/api/tools/dating-scene', post({ scene, root })),
  deleteCharacters: () => json<{ count: number; costumes: number; updated_at: number | null; portraits: number }>('/api/tools/characters', { method: 'DELETE' }),
  deleteDatingData: () => json<DatingInfo>('/api/tools/dating-data', { method: 'DELETE' }),
  updateDatingDataFromApk: (path: string) => json<{ scenes: number; spots: number; costumes: number; matched: number; unmatched: number[] }>('/api/tools/dating-data/update-apk', post({ path })),
  updateDatingData: () => json<{ scenes: number; spots: number; costumes: number; matched: number; unmatched: number[] }>('/api/tools/dating-data/update', { method: 'POST' }),
  mascots: () => json<{ mascots: Mascot[] }>('/api/dmascot/list'),
  launchMascot: (body: MascotLaunch) => json<{ mascot: Mascot }>('/api/dmascot/launch', post(body)),
  updateMascot: (id: string, patch: Partial<Mascot>) => json<{ mascot: Mascot }>(`/api/dmascot/update/${id}`, post(patch)),
  closeMascot: (id: string) => json<{ status: string }>(`/api/dmascot/close/${id}`, { method: 'POST' }),
  resetMascots: () => json<{ status: string }>('/api/dmascot/reset', { method: 'POST' }),
  mascotDiagnostics: () => json<MascotDiagnostics>('/api/dmascot/diagnostics'),
  mascotKwinRule: () => json<{ status: string; message: string }>('/api/dmascot/install-kwin-rule', { method: 'POST' }),
  facets: () => json<Facets>('/api/mods/facets'),
  mods: (query: ModQuery, offset: number, limit: number) => json<ModPage>(buildModsUrl(query, offset, limit)),
  scanAll: (dirs: string[], forceMulti: Record<string, boolean> = {}) =>
    json<{ count: number }>('/api/scan_all', post({ mods_dirs: dirs, force_multi_map: forceMulti })),
  saveTabs: (folder_tabs: FolderTab[], active_tab_id: string) =>
    json<{ config: Config }>('/api/tabs/save', post({ folder_tabs, active_tab_id })),
  openFolder: (path: string) => json<{ status: string }>('/api/folders/open', post({ path })),
  pickFolder: (start: string) => json<{ path: string | null }>('/api/folders/pick', post({ start })),
  checkFolder: (path: string) =>
    json<{ path: string; exists: boolean; is_dir: boolean; readable: boolean }>(`/api/folders/check?${new URLSearchParams({ path })}`),
  toggleInstalled: (modName: string, installed: boolean) =>
    json<{ installed_mods: string[] }>('/api/mod/toggle-installed', post({ mod_name: modName, installed })),
  updateConfig: (patch: { quality?: string; settings?: Settings }) => json<{ config: Config }>('/api/config', post(patch)),
  cacheInfo: () => json<CacheStats>('/api/cache-info'),
  cachedBundles: () => json<{ mods: CachedBundle[] }>('/api/cache/repacked-mods'),
  deleteCachedBundle: (folder_name: string) => json<{ deleted: string }>('/api/cache/repacked-mods/delete', post({ folder_name })),
  clearCache: (request: { clear_originals: boolean; clear_repacked: boolean; clear_catalogs: boolean; clear_thumbs: boolean; clear_audio?: boolean }) =>
    json<{ result: { freed_formatted: string; deleted_count: number; updated_stats: CacheStats } }>('/api/cache-clear', post(request)),
  checkDuplicates: () =>
    json<{ exact_duplicates: ExactDuplicate[]; name_collisions: NameCollision[]; folder_tabs: FolderTab[] }>(
      '/api/mods/check-duplicates',
      post({ mods_dirs: [] }),
    ),
  deleteFolders: (folder_paths: string[]) =>
    json<{ deleted: string[]; failed: { path: string; error: string }[] }>('/api/mod/delete-folders', post({ folder_paths })),
  renameFolder: (folder_path: string, new_name: string) =>
    json<{ new_path: string; new_name: string }>('/api/mod/rename-folder', post({ folder_path, new_name })),
  characters: () => json<{ characters: Character[] }>('/api/characters'),
  quit: () => json<{ status: string }>('/api/quit', { method: 'POST', headers: { 'X-ADust2': '1' } }),
  acknowledgeActivity: () => json<{ status: string }>('/api/activity/acknowledge', { method: 'POST' }),
  /** Work that only runs in the browser (rendering portraits) reports itself, so the status bar shows it too. No id starts a task. */
  reportTask: (task: { id?: number; title?: string; detail?: string; progress?: number; state?: 'running' | 'done' | 'error' | 'cancelled'; error?: string }) =>
    json<{ id: number }>('/api/activity/report', post(task)),
  modHealth: (folder: string) => json<{ damaged: { file: string; reason: string }[] }>(`/api/mods/health?folder=${encodeURIComponent(folder)}`),
  spine42Scan: () => json<Spine42Scan>('/api/tools/spine42'),
  spine42Update: () => json<Spine42Result>('/api/tools/spine42/update', post({})),
  adbInfo: () => json<{ found: boolean; path: string }>('/api/tools/adb'),
  installAdb: () => json<{ found: boolean; path: string }>('/api/tools/adb/install', { method: 'POST' }),
  portraitsInfo: () => json<{ count: number; bytes: number; updated_at: number | null }>('/api/tools/portraits'),
  deletePortraits: () => json<{ count: number; bytes: number; updated_at: number | null }>('/api/tools/portraits', { method: 'DELETE' }),
  charactersInfo: () => json<{ count: number; costumes: number; updated_at: number | null; portraits: number }>('/api/tools/characters'),
  updateCharacters: () => json<{ added: number; updated: number; total: number; count: number; costumes: number; updated_at: number | null; portraits: number; portrait_error: string }>('/api/tools/characters/update', { method: 'POST' }),
  modsIndex: () => json<{ mods: unknown[] }>('/api/mods/index'),
  mergeSpine: (mod_folder: string) => json<{ message: string }>('/api/mod/merge-spine', post({ mod_folder })),
  revertMerge: (mod_folder: string) => json<{ message: string }>('/api/mod/revert-merge', post({ mod_folder })),
  skeletonDonors: (folder: string) => json<{ donors: SkeletonDonor[] }>(`/api/mod/skeleton-donors?folder=${encodeURIComponent(folder)}`),
  fixSkeleton: (folder: string, donor_folder?: string) => json<{ message: string; file: string }>('/api/mod/fix-skeleton', post({ folder, donor_folder })),
  phoneBackups: (deviceId: string) => json<{ backups: PhoneBackup[] }>(`/api/backups?${new URLSearchParams({ device_id: deviceId })}`),
  restoreBackup: (device_id: string, b: PhoneBackup) => json<{ message: string }>('/api/restore', post({ device_id, bundle_name: b.bundle_name, bundle_hash: b.bundle_hash })),
  deleteBackup: (device_id: string, b: PhoneBackup) => json<{ message: string }>('/api/backups/delete', post({ device_id, bundle_name: b.bundle_name, bundle_hash: b.bundle_hash })),
  skeletonScan: () => json<{ mods: SkeletonCase[] }>('/api/mods/skeleton-scan'),
  saveTemplate: (tab_id: string, template_name: string, mod_names: string[]) =>
    json<{ templates: Record<string, Record<string, string[]>> }>('/api/templates/save', post({ tab_id, template_name, mod_names })),
  deleteTemplate: (tab_id: string, template_name: string) =>
    json<{ templates: Record<string, Record<string, string[]>> }>('/api/templates/delete', post({ tab_id, template_name })),
  multiTree: (folderPath: string, modName: string) =>
    json<{ categories: PackCategory[]; previews?: PackPreview[]; error?: string }>(
      `/api/multi/tree?${new URLSearchParams({ folder_path: folderPath, mod_name: modName })}`,
    ),
  prepareSelections: (variants: { full_path: string; name: string; character: string }[], modName: string, quality: string) =>
    json<{ items: PreparedVariant[] }>('/api/multi/prepare-selections', post({ variants, mod_name: modName, quality })),
  installedMods: () => json<{ mods: Mod[]; missing: string[] }>('/api/mods/installed'),
  devices: () => json<{ devices: Device[] }>('/api/devices'),
  queueState: () => json<{ queue: QueueJob[]; issues: { mod_name?: string; issue?: string }[] }>('/api/queue/state'),
  saveQueue: (queue: QueueJob[]) => json<{ status: string }>('/api/queue/state', post({ queue })),
  prepare: (request: PrepareRequest) =>
    json<{ success: boolean; data?: PreparedData; error?: string; cancelled?: boolean }>('/api/mod/prepare', post(request)),
  cancelPrepare: (job_id: string, mod_folder: string) =>
    json<{ cancelled: boolean }>('/api/mod/cancel-prepare', post({ job_id, mod_folder })),
  transfer: (request: TransferRequest) => json<{ success: boolean; error?: string }>('/api/mod/transfer', post(request)),
  checkShared: (request: {
    mod_folders: string[]
    installed_mod_names: string[]
    queue_mod_folders: string[]
    quality: string
  }) =>
    json<{ has_shared: boolean; bundle_groups: Record<string, SharedBundleGroup> }>(
      '/api/mods/check-shared-bundles',
      post(request),
    ),
}

/** Mod skeletons by Spine version: the game runs 4.2, so 4.1 ones (v41) need converting. */
export interface Spine42Scan { total: number; v41: number; v42: number; other: number; folders: number }
export interface Spine42Result { checked: number; updated: number; failed: { file: string; error: string }[]; counts: Spine42Scan }

export interface SkeletonDonor {
  name: string
  folder_path: string
  skeleton: string
  category: string
  mtime: number
}

/** A mod without a skeleton and the mods that could lend one. */
export interface SkeletonCase {
  name: string
  folder_path: string
  asset_key: string
  donors: SkeletonDonor[]
}

export interface DatingInfo {
  files: number
  bytes: number
  updated_at: number | null
  /** Scenes the touch rules know, those with sounds, and the dating scenes of the library the data does not know yet. */
  scenes: number
  with_sounds: number
  scene_numbers: number[]
  new_scenes: number[]
}
