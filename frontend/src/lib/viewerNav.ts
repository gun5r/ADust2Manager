/** Viewer navigation rules (ported from classic): the right-hand character browser and the keyboard stepping. */
import type { Character } from './api'
import { CATEGORIES, effectiveCategory, type CategoryFilter, type IndexMod } from './classify'
import { groupByCharacter, OTHERS, type CharacterGroup } from './grouping'
import { filterMods, type StatusFilter } from './filters'

export interface BrowserFilters {
  category: CategoryFilter
  status: StatusFilter
  query: string
}

/** Inside a costume the mods are split by type, so idles, skills and dating scenes do not mix. */
export function byType(mods: IndexMod[]) {
  const by = new Map<string, IndexMod[]>()
  for (const m of mods) { const c = effectiveCategory(m); const k = CATEGORIES.some(({ key }) => key === c) ? c : 'other'; by.set(k, [...(by.get(k) ?? []), m]) }
  return CATEGORIES.filter(({ key }) => by.has(key)).map(({ key, heading }) => ({ key, name: heading, mods: by.get(key)! }))
}
/** A character's mods in the order the right panel lists them (costume by costume, type by type): what W / S walk through. */
export const listOrder = (group: CharacterGroup | null | undefined): IndexMod[] => (group?.sections ?? []).flatMap((s) => byType(s.mods).flatMap((t) => t.mods))

/** Characters (with their sorted mods) shown in the viewer's right sidebar after every filter. */
export function browserGroups(
  mods: IndexMod[], roster: Character[], installed: Set<string>, selected: Set<string>, filters: BrowserFilters,
): CharacterGroup[] {
  const groups = groupByCharacter(filterMods(mods, installed, filters.status, filters.category, selected), roster)
  const query = filters.query.trim().toLowerCase()
  if (!query) return groups
  // Name matches only; those that start with the query come first, "Others" last.
  return groups
    .filter((g) => g.name.toLowerCase().includes(query))
    .sort((a, b) => {
      const aStarts = a.name.toLowerCase().startsWith(query), bStarts = b.name.toLowerCase().startsWith(query)
      if (aStarts !== bStarts) return aStarts ? -1 : 1
      if (a.name === OTHERS) return 1
      if (b.name === OTHERS) return -1
      return a.name.localeCompare(b.name, undefined, { sensitivity: 'base' })
    })
}

const wrap = (index: number, size: number) => (index + size) % size

/** Top of the list of the previous/next character (Q / E, PgUp / PgDn). */
export function adjacentCharacter(groups: CharacterGroup[], currentCharacter: string | null, direction: -1 | 1): IndexMod | null {
  if (!groups.length) return null
  const current = Math.max(0, groups.findIndex((g) => g.name === currentCharacter))
  return listOrder(groups[wrap(current + direction, groups.length)])[0] ?? null
}

/** W / S: the previous/next mod in the character's list; past the end it wraps to the other end of the same character, never into another one. */
export function stepWithin(groups: CharacterGroup[], currentCharacter: string | null, currentPath: string | null, direction: -1 | 1): IndexMod | null {
  const list = listOrder(groups.find((g) => g.name === currentCharacter) ?? groups[0])
  if (!list.length) return null
  const index = list.findIndex((m) => m.folder_path === currentPath)
  if (index < 0) return list[direction > 0 ? 0 : list.length - 1]
  return list[wrap(index + direction, list.length)]
}

/** Linear previous/next over the whole list, wrapping around (← and →). */
export function linearStep(mods: IndexMod[], currentPath: string | null, delta: -1 | 1): IndexMod | null {
  if (!mods.length) return null
  const index = Math.max(0, mods.findIndex((m) => m.folder_path === currentPath))
  return mods[wrap(index + delta, mods.length)]
}

export function cycleCategory(current: CategoryFilter, direction: -1 | 1): CategoryFilter {
  const keys = CATEGORIES.map(({ key }) => key) // the filter bar's six, not "all"
  const index = keys.findIndex((key) => key === current)
  if (index < 0) return direction > 0 ? keys[0] : keys[keys.length - 1] // no category chosen: start from either end
  return keys[wrap(index + direction, keys.length)]
}

/** Packs listing: the open pack's character first (its other packs are the likeliest comparison), the rest as given. */
export const characterFirst = (groups: CharacterGroup[], character: string | null | undefined): CharacterGroup[] =>
  [...groups.filter((g) => g.name === character), ...groups.filter((g) => g.name !== character)]
