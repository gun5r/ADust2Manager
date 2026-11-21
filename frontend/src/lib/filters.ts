/** Library filtering exactly as the classic UI composes it: folder tab, then install status and category. */
import type { FolderTab } from './api'
import { modBadges } from './badges'
import { modKey } from './selection'
import { inCategory, isInstalled, type CategoryFilter, type IndexMod } from './classify'

export type StatusFilter = 'all' | 'installed' | 'uninstalled' | 'selected'

export const tabRoot = (tab: Pick<FolderTab, 'path'>) => tab.path.trim().replace(/[\\/]+$/, '')

/** Mods of the active folder tab, or of every folder in Sync View. */
export function modsOfTab(mods: IndexMod[], tab: FolderTab | undefined, syncView: boolean): IndexMod[] {
  if (!tab) return [] // no folder, no mods
  if (syncView) return mods
  const root = tabRoot(tab)
  return mods.filter((m) => (m.root ?? '').replace(/[\\/]+$/, '') === root)
}

export const filterMods = (mods: IndexMod[], installed: Set<string>, status: StatusFilter, category: CategoryFilter, selected: Set<string> = new Set()): IndexMod[] =>
  mods.filter((m) => {
    const isIn = isInstalled(m, installed)
    if (status === 'installed' && !isIn) return false
    if (status === 'uninstalled' && isIn) return false
    if (status === 'selected' && !selected.has(modKey(m))) return false
    return inCategory(m, category)
  })

export interface FilterCounts {
  total: number
  installed: number
  uninstalled: number
}

export function filterCounts(mods: IndexMod[], installed: Set<string>): FilterCounts {
  const installedCount = mods.filter((m) => isInstalled(m, installed)).length
  return { total: mods.length, installed: installedCount, uninstalled: mods.length - installedCount }
}

/** The classic roster lists a character when it has at least one mod after the status and category filters. */
export function rosterEntries(groups: { name: string; mods: IndexMod[] }[], installed: Set<string>, query: string, queuedFolders: Set<string> = new Set()) {
  const needle = query.trim().toLowerCase()
  return groups
    .filter((g) => !needle || g.name.toLowerCase().includes(needle))
    .map((g) => ({ name: g.name, count: g.mods.length, ...modBadges(g.mods, installed, queuedFolders) }))
}
