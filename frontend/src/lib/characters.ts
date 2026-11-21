/** Roster rules: counts per character, search, ordering, and validating a new character. */
import type { Character } from './api'

export const OTHERS = 'Others'

export interface RosterRow {
  name: string
  count: number
  image_url: string
  costume_id: string
  /** In the roster file (false for 'Others' and names that only exist in the library index). */
  known: boolean
}

export type RosterSort = 'mods' | 'name'

const needle = (text: string) => text.trim().toLowerCase()

/**
 * Roster rows with the number of mods each character has in the library. 'Others' (unmatched mods) is listed when it
 * has mods, and a character that only appears in the library index still shows up so its mods stay reachable.
 */
export function rosterRows(characters: Character[], counts: Record<string, number>, query = '', sort: RosterSort = 'mods'): RosterRow[] {
  const rows: RosterRow[] = characters.map((c) => ({
    name: c.name, count: counts[c.name] ?? 0, image_url: c.image_url, costume_id: c.costume_id, known: true,
  }))
  const known = new Set(characters.map((c) => c.name))
  for (const [name, count] of Object.entries(counts)) {
    if (!known.has(name) && count > 0) rows.push({ name, count, image_url: '', costume_id: '', known: false })
  }
  const q = needle(query)
  const byName = new Map(characters.map((c) => [c.name, c]))
  const matches = (row: RosterRow) => {
    if (!q) return true
    const c = byName.get(row.name)
    return [row.name, row.costume_id, ...(c?.aliases ?? []), ...Object.values(c?.costumes ?? {})].some((t) => needle(t).includes(q))
  }
  const compare = (a: RosterRow, b: RosterRow) => a.name.localeCompare(b.name)
  // While searching, a character whose own name matches comes before one that only matches through an alias.
  const rank = (row: RosterRow) => (!q ? 0 : needle(row.name).startsWith(q) ? 0 : needle(row.name).includes(q) ? 1 : 2)
  const order = sort === 'name' ? compare : (a: RosterRow, b: RosterRow) => b.count - a.count || compare(a, b)
  return rows.filter(matches).sort((a, b) => rank(a) - rank(b) || order(a, b))
}

export const totalMods = (counts: Record<string, number>) => Object.values(counts).reduce((sum, n) => sum + n, 0)

/** Accept "060301" or "char060301"; empty is allowed (the server then has no portrait to build). */
export function normalizeCostumeId(input: string): string | null {
  const text = input.trim().toLowerCase().replace(/^char/, '')
  if (!text) return ''
  return /^\d{4,6}$/.test(text) ? text : null
}

export type CharacterProblem = 'no-name' | 'bad-costume' | 'bad-image'

export function characterProblems(draft: { name: string; costume_id: string; image_url: string }): CharacterProblem[] {
  const problems: CharacterProblem[] = []
  if (!draft.name.trim()) problems.push('no-name')
  if (normalizeCostumeId(draft.costume_id) === null) problems.push('bad-costume')
  if (draft.image_url.trim() && !/^https?:\/\//i.test(draft.image_url.trim())) problems.push('bad-image')
  return problems
}

/** Case-insensitive: adding "alec" updates the existing "Alec" instead of making a second entry. */
export const findCharacter = (characters: Character[], name: string): Character | undefined =>
  characters.find((c) => c.name.toLowerCase() === name.trim().toLowerCase())
