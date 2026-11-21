/** Library grouping: character -> costume section -> mods, exactly as the classic list shows it. */
import type { Character } from './api'
import { costumeName, costumeSortInfo, effectiveCategory, type IndexMod } from './classify'

export const OTHERS = 'Others'
/** The groups that never have a portrait (mods nobody matched, and the game's non-player characters): their cards say the name instead. */
const NO_PORTRAIT = [OTHERS, 'NPCs']
export const neverHasPortrait = (name: string): boolean => NO_PORTRAIT.includes(name)

export interface Section {
  key: string
  title: string
  isIllustrations: boolean
  /** The costume this section is, '' for the loose illustrations of a character whose costumes are unknown. */
  costumeId: string
  mods: IndexMod[]
}

export interface CharacterGroup {
  name: string
  mods: IndexMod[]
  sections: Section[]
}

/** Character names, alphabetical with "Others" last. */
export function characterOrder(names: Iterable<string>): string[] {
  return [...names].sort((a, b) => (a === OTHERS ? 1 : b === OTHERS ? -1 : a.localeCompare(b, undefined, { sensitivity: 'base' })))
}

/**
 * The costume a mod is listed under. Idle and cutscene mods name theirs; a dating scene belongs to the costume the website links
 * it to; anything else of the character (illustrations, story art) goes to its first costume. '' when the character has none known.
 */
export function costumeIdFor(mod: IndexMod, character: Character | undefined): string {
  const own = costumeSortInfo(mod).costumeId
  if (own) return own
  const ids = Object.keys(character?.costumes ?? {})
  if (!ids.length) return ''
  if (effectiveCategory(mod) === 'dating') {
    const scene = (mod.asset_key ?? '').toLowerCase().match(/illust_dating\d+/)?.[0]
    const linked = scene ? character?.dating?.[scene] : undefined
    if (linked && character?.costumes[linked]) return linked
  }
  return ids[0]
}

const compare = (a: string, b: string, numeric = false) => a.localeCompare(b, undefined, { sensitivity: 'base', numeric })

/** Per costume: idle, cutscenes, dating, extras; inside that by asset, then name. Sorts a copy. */
function sortWithinCharacter(mods: IndexMod[], costumes: Map<IndexMod, string>): IndexMod[] {
  const info = new Map(mods.map((m) => [m, costumeSortInfo(m)]))
  const key = (m: IndexMod) => (costumes.get(m) ? `costume_${costumes.get(m)}` : 'z_illustrations')
  return [...mods].sort((a, b) => {
    const x = info.get(a)!, y = info.get(b)!
    if (key(a) !== key(b)) return compare(key(a), key(b), true)
    if (x.catRank !== y.catRank) return x.catRank - y.catRank
    if (x.assetKey !== y.assetKey && x.assetKey !== 'unknown' && y.assetKey !== 'unknown') return compare(x.assetKey, y.assetKey)
    return compare(a.name ?? '', b.name ?? '')
  })
}

export function groupByCharacter(mods: IndexMod[], roster: Character[]): CharacterGroup[] {
  const byCharacter = new Map<string, IndexMod[]>()
  for (const mod of mods) {
    const name = mod.character || OTHERS
    byCharacter.set(name, [...(byCharacter.get(name) ?? []), mod])
  }
  return characterOrder(byCharacter.keys()).map((name) => {
    const character = roster.find((c) => c.name === name)
    const costumes = new Map(byCharacter.get(name)!.map((m) => [m, name === OTHERS ? '' : costumeIdFor(m, character)]))
    const sorted = sortWithinCharacter(byCharacter.get(name)!, costumes)
    const sections: Section[] = []
    for (const mod of sorted) {
      let key = '', title = '', illust = false
      const costumeId = costumes.get(mod) ?? ''
      if (name === OTHERS) {
        key = 'others'
      } else {
        illust = !costumeId
        key = illust ? 'illustrations' : `costume_${costumeId}`
        const label = costumeName(roster, name, costumeId)
        title = illust ? `${name} - Illustrations` : label ? `${name} - ${label}` : `${name} - Costume ${costumeId}`
      }
      const last = sections.at(-1)
      if (last && last.key === key) last.mods.push(mod)
      else sections.push({ key, title, isIllustrations: illust, costumeId, mods: [mod] })
    }
    return { name, mods: sorted, sections }
  })
}

/** Every roster character with every costume it has; those without mods are empty groups and sections (the "show all characters" setting). */
export function withEmptyCharacters(groups: CharacterGroup[], roster: Character[]): CharacterGroup[] {
  const byName = new Map(groups.map((g) => [g.name, g]))
  for (const c of roster) {
    const g = byName.get(c.name) ?? { name: c.name, mods: [], sections: [] }
    const have = new Set(g.sections.map((s) => s.key))
    const missing: Section[] = Object.entries(c.costumes ?? {}).filter(([id]) => !have.has(`costume_${id}`))
      .map(([id, label]) => ({ key: `costume_${id}`, title: label ? `${c.name} - ${label}` : `${c.name} - Costume ${id}`, isIllustrations: false, costumeId: id, mods: [] }))
    const sections = [...g.sections, ...missing].sort((a, b) => Number(a.isIllustrations) - Number(b.isIllustrations) || compare(a.key, b.key, true))
    byName.set(c.name, { ...g, sections })
  }
  return characterOrder(byName.keys()).map((name) => byName.get(name)!)
}

/** Layout constants measured from the classic list (px). They only seed the virtual list; real heights replace them once rendered. */
export const LAYOUT = { groupChrome: 2 + 17.6 + 43, row: 54.73, separator: 28.19 + 4.8, rowGap: 7.2, groupGap: 13.6 }

export function estimateGroupHeight(group: CharacterGroup): number {
  const separators = group.name === OTHERS ? 0 : group.sections.length
  const children = separators + group.mods.length
  if (children === 0) return LAYOUT.groupChrome
  return LAYOUT.groupChrome + separators * LAYOUT.separator + group.mods.length * LAYOUT.row + (children - 1) * LAYOUT.rowGap
}
