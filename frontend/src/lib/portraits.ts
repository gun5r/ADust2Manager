/** Portraits: which mods get a generated thumbnail, how it is framed, and where costume / mod portraits are served. */
import { costumeSortInfo, effectiveCategory, type IndexMod } from './classify'

/** Idle, cutscene and dating mods get a generated portrait; illustrations and the rest still show in Costume mode with a placeholder. Packs have no skeleton of their own. */
export const portraitEligible = (mod: IndexMod): boolean => !mod.is_multi && ['idle', 'cut', 'dating'].includes(effectiveCategory(mod))

/** Idle sprites are full-body: the portrait keeps the upper part. Illustrations and cutscenes keep the whole picture. */
export const cropsBody = (mod: IndexMod): boolean => effectiveCategory(mod) === 'idle'

/** Share of the character's height (from the top) kept in an idle portrait. */
export const IDLE_CROP = 0.6

export const costumePortraitUrl = (costumeId: string): string => `/api/portraits/costume/${costumeId}.png`
export const modPortraitUrl = (folder: string, version: number): string => `/api/portraits/mod?folder=${encodeURIComponent(folder)}&v=${version}`

export interface CostumeEntry {
  key: string
  /** 6-digit costume id, or '' for illustrations / mods that name no costume. */
  costumeId: string
  /** Every id the card's mods use, to find a portrait when the first has none. */
  costumeIds: string[]
  title: string
  /** The character's illustrations, which sit in their own section of the mod box. */
  illustrations: boolean
  mods: IndexMod[]
}

/** Costume cards of a character group, in the list's order (every mod appears, portrait or not; a section without mods is a costume nobody made a mod for, shown when the setting asks for it).
 *  The game gives some costumes two ids (e.g. the idle under one, the cutscene under another) with the same name: they are one card. */
export function costumeEntries(sections: { key: string; title: string; isIllustrations: boolean; costumeId?: string; mods: IndexMod[] }[]): CostumeEntry[] {
  const out: CostumeEntry[] = []
  for (const s of sections) {
    const mods = s.mods
    const costumeId = s.costumeId ?? (mods[0] ? costumeSortInfo(mods[0]).costumeId : '')
    const twin = s.title && !s.isIllustrations ? out.find((e) => e.title === s.title && !e.illustrations) : undefined
    if (twin) {
      twin.mods.push(...mods)
      if (costumeId && !twin.costumeIds.includes(costumeId)) twin.costumeIds.push(costumeId)
    } else out.push({ key: s.key, costumeId, costumeIds: costumeId ? [costumeId] : [], title: s.title, illustrations: s.isIllustrations, mods: [...mods] })
  }
  return out
}

/** Mod counts shown on a costume card: idle, cutscenes, and everything else (illustrations included). */
export function categoryCounts(mods: IndexMod[]): { idle: number; cut: number; rest: number } {
  const idle = mods.filter((m) => effectiveCategory(m) === 'idle').length
  const cut = mods.filter((m) => effectiveCategory(m) === 'cut').length
  return { idle, cut, rest: mods.length - idle - cut }
}

/** The mod box of a costume: Idle on top, Cutscenes in the middle, the rest last. Illustrations are a section of their own and need no heading. */
export function modSections(entry: CostumeEntry): { title: string; mods: IndexMod[] }[] {
  if (entry.illustrations) {
    const dating = entry.mods.filter((m) => effectiveCategory(m) === 'dating')
    // illustrations need no heading; dating scenes sharing the box get one so the two stay apart
    return dating.length && dating.length < entry.mods.length
      ? [{ title: 'Dating', mods: dating }, { title: 'Illustrations', mods: entry.mods.filter((m) => !dating.includes(m)) }]
      : [{ title: '', mods: entry.mods }]
  }
  const of = (...cats: string[]) => entry.mods.filter((m) => cats.includes(effectiveCategory(m)))
  const idle = of('idle'), cut = of('cut'), dating = of('dating')
  const extras = entry.mods.filter((m) => ![...idle, ...cut, ...dating].includes(m))
  return [{ title: 'Idle', mods: idle }, { title: 'Skills', mods: cut }, { title: 'Dating', mods: dating }, { title: 'Extras', mods: extras }].filter((s) => s.mods.length)
}

/** A character's portrait candidates: the local costume portraits of its costumes (the id of its listed image first), best guess first. */
export function characterPortraits(c: { image_url?: string; costume_id?: string; costumes?: Record<string, string> } | undefined): string[] {
  if (!c) return []
  const first = (c.image_url ?? '').match(/char(\d+)/i)?.[1] ?? c.costume_id ?? ''
  const ids = [first, ...Object.keys(c.costumes ?? {}).sort()].filter((id, i, all) => id && all.indexOf(id) === i)
  return ids.slice(0, 6).map(costumePortraitUrl)
}
