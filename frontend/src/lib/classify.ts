/**
 * Mod classification used by the library list, ported from the classic UI (getEffectiveCategory, isModInCategory,
 * getModCostumeSortInfo, sortCharacterMods, getCharacterCostumeName). Keep the rules identical: users rely on them.
 */
import type { Character } from './api'

export interface IndexMod {
  id?: string
  name: string
  folder_name?: string
  folder_path: string
  root?: string
  character: string
  category: string
  asset_key: string
  asset_keys?: string[]
  asset_stem?: string
  is_multi: boolean
  has_backup?: boolean
  has_json_anim?: boolean
  texture_count: number
  files: string[]
}

export type Category = 'idle' | 'cut' | 'illust' | 'dating' | 'multi' | 'other'

export function effectiveCategory(mod: IndexMod): Category {
  if (mod.is_multi) return 'multi'
  const files = (mod.files ?? []).join(' ').toLowerCase()
  const assetKey = (mod.asset_key ?? '').toLowerCase()
  const stem = (mod.asset_stem ?? '').toLowerCase()
  const name = (mod.name ?? '').toLowerCase()
  const folder = (mod.folder_path ?? mod.folder_name ?? '').toLowerCase()
  const combined = `${stem} ${assetKey} ${name} ${files} ${folder}`

  // Dating means the mod file really is illust_dating*; "char123 + dating" in a name does not count.
  const isDating = /illust_dating\d*/i.test(files) || /illust_dating\d*/i.test(assetKey) || /illust_dating\d*/i.test(stem) || /illust_dating\d*/i.test(name)
  if (isDating) return 'dating'
  if (combined.includes('specialillust')) return 'illust'
  if (/\b(cut|cutscene|skill|combat|ultimate|burst)\b|_cut\b|cut_/i.test(name) || files.includes('cutscene')) return 'cut'
  if (/\b(idle|lobby|field|standby)\b|_idle\b|idle_/i.test(name) || /char\d+/i.test(files) || /char\d+/i.test(name) || /char\d+/i.test(assetKey)) return 'idle'

  // Last resort: trust the scanner's category, but never a dating/illust claim that the strict rules reject.
  const stored = (mod.category ?? 'other').toLowerCase()
  const hasChar = /char\d+/i.test(files) || /char\d+/i.test(assetKey)
  if (stored === 'dating') return hasChar ? 'idle' : 'other'
  if (stored === 'illust' && !combined.includes('specialillust')) return hasChar ? 'idle' : 'other'
  return (['idle', 'cut', 'illust', 'dating', 'multi', 'other'].includes(stored) ? stored : 'other') as Category
}

export type CategoryFilter = 'all' | 'idle' | 'cut' | 'dating' | 'illust' | 'multi' | 'other'

/** The categories in the order the filter bar and the preview's lists show them: the key, the filter button's name and the heading of its list. */
export const CATEGORIES = [
  { key: 'idle', label: 'Idle', heading: 'Idles' }, { key: 'cut', label: 'Skills', heading: 'Skills' }, { key: 'dating', label: 'Dating', heading: 'Dating' },
  { key: 'illust', label: 'Illust', heading: 'Illustrations' }, { key: 'other', label: 'Others', heading: 'Others' }, { key: 'multi', label: 'Multi', heading: 'Multi' },
] as const satisfies readonly { key: CategoryFilter; label: string; heading: string }[]

export function inCategory(mod: IndexMod, filter: CategoryFilter): boolean {
  if (filter === 'all') return true
  const category = effectiveCategory(mod)
  if (filter === 'multi') return mod.is_multi || category === 'multi'
  if (filter === 'other') return !['idle', 'cut', 'dating', 'illust', 'multi'].includes(category) || category === 'other'
  return category === filter
}

export interface CostumeSortInfo {
  costumeKey: string
  costumeId: string
  catRank: number
  assetKey: string
  name: string
}

export function costumeSortInfo(mod: IndexMod): CostumeSortInfo {
  const assetKey = (mod.asset_key ?? '').toLowerCase()
  const combined = `${assetKey} ${(mod.name ?? '').toLowerCase()} ${(mod.folder_path ?? mod.folder_name ?? '').toLowerCase()} ${(mod.files ?? []).join(' ').toLowerCase()}`
  const match = combined.match(/char(\d{4,6})/i)
  const category = effectiveCategory(mod)
  return {
    costumeKey: match ? `costume_${match[1]}` : 'z_illustrations',
    costumeId: match ? match[1] : '',
    catRank: category === 'idle' ? 1 : category === 'cut' ? 2 : category === 'dating' ? 3 : 4,
    assetKey: assetKey || 'unknown',
    name: mod.name ?? '',
  }
}

const compare = (a: string, b: string, numeric = false) => a.localeCompare(b, undefined, { sensitivity: 'base', numeric })

/** Per costume: idles, cutscenes, dating, others; inside that by asset, then name. Sorts a copy. */
export function sortCharacterMods(mods: IndexMod[]): IndexMod[] {
  const info = new Map(mods.map((m) => [m, costumeSortInfo(m)]))
  return [...mods].sort((a, b) => {
    const x = info.get(a)!, y = info.get(b)!
    if (x.costumeKey !== y.costumeKey) return compare(x.costumeKey, y.costumeKey, true)
    if (x.catRank !== y.catRank) return x.catRank - y.catRank
    if (x.assetKey !== y.assetKey && x.assetKey !== 'unknown' && y.assetKey !== 'unknown') return compare(x.assetKey, y.assetKey)
    return compare(a.name ?? '', b.name ?? '')
  })
}

export function costumeName(roster: Character[], character: string, costumeId: string): string | null {
  const info = roster.find((c) => c.name === character)
  if (!info?.costumes || !costumeId) return null
  const clean = String(costumeId).replace(/^char/i, '')
  if (info.costumes[clean]) return info.costumes[clean]
  const unpadded = clean.replace(/^0+/, '')
  for (const [key, value] of Object.entries(info.costumes)) if (key.replace(/^0+/, '') === unpadded) return value
  return null
}

export const isInstalled = (mod: IndexMod, installed: Set<string>) => installed.has(mod.name) || (mod.id !== undefined && installed.has(mod.id))
