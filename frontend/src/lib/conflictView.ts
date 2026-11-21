/** Shape the conflict resolver dialog shows, built from either kind of conflict (selection or queue). */
import type { IndexMod } from './classify'
import type { Conflict, SelectionConflict } from './queue'

/** `folder`: the folder that holds the mod's portrait (a variant's own folder for variants of a multimod). */
export interface ConflictOption { id: string; name: string; folder?: string; badges?: { text: string; tone: 'src' | 'cache' | 'multi' | 'ok' | 'plain' }[] }
export interface ConflictGroup {
  key: string
  character: string
  options: ConflictOption[]
  /** Name of another mod already on the phone for this asset (selection conflicts only). */
  installed: string | null
  /** Folder of that installed mod (its portrait), when known. */
  installedFolder?: string | null
  queue: boolean
}

export const fromSelection = (conflicts: SelectionConflict<IndexMod>[]): ConflictGroup[] =>
  conflicts.map((c) => ({
    key: c.assetKey,
    character: c.items[0].character,
    installed: c.installed?.name ?? null,
    installedFolder: c.installed?.folder_path ?? null,
    queue: false,
    options: c.items.map((m) => ({ id: m.folder_path, name: m.name, folder: (m as { source_folder?: string }).source_folder ?? m.folder_path, badges: [{ text: `${m.files.filter((f) => f.toLowerCase().endsWith('.png')).length || 1} textures`, tone: 'plain' as const }] })),
  }))

export const fromQueue = (conflicts: Conflict[]): ConflictGroup[] =>
  conflicts.map((c) => ({
    key: c.assetKey,
    character: c.jobs[0].character,
    installed: null,
    queue: true,
    options: c.jobs.map((j) => ({
      id: j.id,
      name: j.mod_name,
      folder: j.portrait_folder || j.mod_folder,
      badges: [
        j.category === 'multi' ? { text: 'Multi View', tone: 'multi' as const } : j.id.startsWith('job_cache_') ? { text: 'Cached', tone: 'cache' as const } : { text: 'Mod List', tone: 'src' as const },
        { text: j.status === 'prepared' ? 'Ready' : j.status, tone: 'ok' as const },
      ],
    })),
  }))
