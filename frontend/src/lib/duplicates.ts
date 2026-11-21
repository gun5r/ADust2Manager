/** Duplicate inspector rules: which configured folder a copy lives in, and safe bulk "keep this folder" plans. */
import type { ExactDuplicate, FolderTab } from './api'

const norm = (p: string) => p.replace(/\\/g, '/').replace(/\/+$/, '')

/** The configured folder that contains `path` (the deepest one if tabs are nested). */
export function tabOf(path: string, tabs: FolderTab[]): FolderTab | null {
  const target = norm(path)
  let best: FolderTab | null = null
  for (const tab of tabs) {
    const root = norm(tab.path)
    if (root && (target === root || target.startsWith(root + '/')) && (!best || root.length > norm(best.path).length)) best = tab
  }
  return best
}

export interface KeepPlan {
  tab: FolderTab
  /** Copies outside `tab` whose twin lives inside it. */
  deletePaths: string[]
}

/**
 * For each folder, "keep everything here": delete the copies of its mods that live in other folders. A pair is only
 * part of a plan when exactly one side is inside the folder, so a plan can never delete both copies of a mod.
 */
export function keepPlans(duplicates: ExactDuplicate[], tabs: FolderTab[]): KeepPlan[] {
  const targets = new Map<string, Set<string>>()
  const add = (tab: FolderTab, path: string) => targets.set(tab.id, (targets.get(tab.id) ?? new Set()).add(path))
  for (const dup of duplicates) {
    const t1 = tabOf(dup.mod1.folder_path, tabs), t2 = tabOf(dup.mod2.folder_path, tabs)
    if (t1 && t1.id !== t2?.id) add(t1, dup.mod2.folder_path)
    if (t2 && t2.id !== t1?.id) add(t2, dup.mod1.folder_path)
  }
  return tabs
    .filter((tab) => targets.has(tab.id))
    .map((tab) => ({ tab, deletePaths: [...targets.get(tab.id)!] }))
    .sort((a, b) => b.deletePaths.length - a.deletePaths.length)
}

/** Pairs still valid after some folders were deleted (a pair needs both copies on disk). */
export const withoutDeleted = <T extends { mod1: { folder_path: string }; mod2: { folder_path: string } }>(pairs: T[], deleted: string[]): T[] => {
  const gone = new Set(deleted.map(norm))
  return pairs.filter((p) => !gone.has(norm(p.mod1.folder_path)) && !gone.has(norm(p.mod2.folder_path)))
}

export function formatBytes(bytes: number | undefined): string {
  if (bytes === undefined) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`
}
