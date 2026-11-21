import type { Character, Mod } from './api'
import { effectiveCategory, type IndexMod } from './classify'
import { groupByCharacter } from './grouping'

export const modKey = (mod: Pick<Mod, 'folder_path' | 'name'>) => `${mod.folder_path}\u0000${mod.name}`

const TYPE_LABEL: Record<string, string> = { idle: 'Idle', cut: 'Skill', dating: 'Dating', illust: 'Illustration', multi: 'Multi', other: 'Other' }
/** "Aquila - Sealed Desires = Idle" for each mod: its costume heading and what kind of mod it is (so a selection reads without the file names). */
export function selectionLabels(mods: IndexMod[], roster: Character[]): Map<string, string> {
  const out = new Map<string, string>()
  for (const g of groupByCharacter(mods, roster)) for (const sec of g.sections) for (const m of sec.mods) {
    const kind = TYPE_LABEL[effectiveCategory(m)] ?? 'Other'
    out.set(modKey(m), sec.title ? `${sec.title} = ${kind}` : `${g.name} = ${kind}`)
  }
  return out
}
