import { categoryCounts } from './portraits'
import { isInstalled, type IndexMod } from './classify'

export interface ModBadges { idle: number; cut: number; rest: number; installed: number; queued: number }

/** Every number shown on a character or costume portrait, worked out in one place: mods by category, installed ones, ones in the queue. */
export function modBadges(mods: IndexMod[], installed: Set<string>, queuedFolders: Set<string>): ModBadges {
  return {
    ...categoryCounts(mods),
    installed: mods.filter((m) => isInstalled(m, installed)).length,
    queued: mods.filter((m) => queuedFolders.has(m.folder_path)).length,
  }
}
