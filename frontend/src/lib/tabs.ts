/** Folder tab rules: unique ids and paths, never zero tabs, ordering, and which scans a change requires. */
import type { FolderTab } from './api'

export const COLORS = ['#38bdf8', '#10b981', '#8b5cf6', '#f59e0b', '#f43f5e', '#3b82f6', '#14b8a6', '#ef4444']

export const samePath = (a: string, b: string) => {
  const n = (p: string) => p.trim().replace(/\\/g, '/').replace(/\/+$/, '').toLowerCase()
  return n(a) === n(b)
}

export const defaultName = (tabs: FolderTab[]) => `${tabs.length + 1}Batch`

export function createTab(draft: Omit<FolderTab, 'id'>, tabs: FolderTab[]): FolderTab {
  return { ...draft, name: draft.name.trim() || defaultName(tabs), path: draft.path.trim(), id: `tab_${Date.now()}_${tabs.length}` }
}

export type TabProblem = 'no-path' | 'duplicate-path'

/** Problems that block saving. A missing folder on disk is only a warning, so it is checked separately. */
export function tabProblems(draft: Pick<FolderTab, 'path'>, tabs: FolderTab[], editingId?: string): TabProblem[] {
  const problems: TabProblem[] = []
  if (!draft.path.trim()) problems.push('no-path')
  else if (tabs.some((t) => t.id !== editingId && samePath(t.path, draft.path))) problems.push('duplicate-path')
  return problems
}

export const updateTab = (tabs: FolderTab[], id: string, patch: Partial<FolderTab>): FolderTab[] =>
  tabs.map((t) => (t.id === id ? { ...t, ...patch, path: (patch.path ?? t.path).trim(), name: (patch.name ?? t.name).trim() || t.name } : t))

/** Remove a tab (any, the last one too: with no folder the manager has nothing to work on until one is added). */
export function removeTab(tabs: FolderTab[], id: string, activeId: string): { tabs: FolderTab[]; activeId: string } {
  if (!tabs.some((t) => t.id === id)) return { tabs, activeId }
  const index = tabs.findIndex((t) => t.id === id)
  const rest = tabs.filter((t) => t.id !== id)
  return { tabs: rest, activeId: activeId !== id ? activeId : rest.length ? rest[Math.min(index, rest.length - 1)].id : '' }
}

export function moveTab(tabs: FolderTab[], id: string, delta: -1 | 1): FolderTab[] {
  const from = tabs.findIndex((t) => t.id === id)
  const to = from + delta
  if (from < 0 || to < 0 || to >= tabs.length) return tabs
  const copy = [...tabs]
  ;[copy[from], copy[to]] = [copy[to], copy[from]]
  return copy
}

/** Does saving `after` need a rescan of this tab (new tab, or its folder/multi flag changed)? */
export function needsScan(before: FolderTab | undefined, after: FolderTab): boolean {
  return !before || !samePath(before.path, after.path) || Boolean(before.is_multi_folder) !== Boolean(after.is_multi_folder)
}

export const forceMultiMap = (tabs: FolderTab[]): Record<string, boolean> =>
  Object.fromEntries(tabs.filter((t) => t.path).map((t) => [t.path, Boolean(t.is_multi_folder)]))
