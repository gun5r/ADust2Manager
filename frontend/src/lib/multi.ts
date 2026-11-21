/** Multi-variant packs: choosing variants without picking two that replace the same asset. */
import type { Mod, PackCategory, PackVariant, PreparedVariant } from './api'

const keysOf = (variant: Pick<PackVariant, 'asset_keys' | 'asset_key'>): string[] =>
  (variant.asset_keys?.length ? variant.asset_keys : [variant.asset_key]).filter((k) => k && k !== 'unknown').map((k) => k.toLowerCase())

/** Does picking `variant` clash with any of `chosen` (same game asset)? */
export const clashes = (chosen: PackVariant[], variant: PackVariant): PackVariant[] => {
  const wanted = new Set(keysOf(variant))
  return chosen.filter((c) => c.full_path !== variant.full_path && keysOf(c).some((k) => wanted.has(k)))
}

/** Toggle a variant. Picking one removes any chosen variant for the same asset (only one can be active). */
export function toggleVariant(chosen: PackVariant[], variant: PackVariant): PackVariant[] {
  if (chosen.some((c) => c.full_path === variant.full_path)) return chosen.filter((c) => c.full_path !== variant.full_path)
  const clash = new Set(clashes(chosen, variant).map((c) => c.full_path))
  return [...chosen.filter((c) => !clash.has(c.full_path)), variant]
}

export const allVariants = (categories: PackCategory[]): PackVariant[] =>
  categories.flatMap((c) => c.options.flatMap((o) => o.variants))

export function filterCategories(categories: PackCategory[], query: string): PackCategory[] {
  const needle = query.trim().toLowerCase()
  if (!needle) return categories
  const matches = (v: PackVariant) => `${v.name} ${v.asset_key} ${v.files.join(' ')}`.toLowerCase().includes(needle)
  return categories
    .map((c) => ({ ...c, options: c.options.map((o) => ({ ...o, variants: o.variants.filter(matches) })).filter((o) => o.variants.length) }))
    .filter((c) => c.options.length)
}

/** A variant folder as a Mod-like object so the Spine preview can play it. */
export const variantAsMod = (variant: PackVariant, character: string): Mod => ({
  name: variant.name, folder_name: variant.name, folder_path: variant.full_path, category: variant.category,
  character, asset_key: variant.asset_key, asset_keys: variant.asset_keys, is_multi: false,
  png_files: variant.files.filter((f) => f.toLowerCase().endsWith('.png')), files: variant.files,
  texture_count: variant.files.filter((f) => f.toLowerCase().endsWith('.png')).length,
})

/** Server-prepared variants as Mods ready for the normal queue flow. */
export const preparedAsMod = (item: PreparedVariant): Mod => ({
  name: item.name, folder_name: item.variant_name, folder_path: item.folder_path, category: 'other',
  character: item.character, asset_key: item.asset_key, asset_keys: item.asset_keys, is_multi: false, source_folder: item.source_folder,
  png_files: item.files.filter((f) => f.toLowerCase().endsWith('.png')), files: item.files,
  texture_count: item.files.filter((f) => f.toLowerCase().endsWith('.png')).length,
})

export const splitPath = (full: string): [string, string] => {
  const i = Math.max(full.lastIndexOf('/'), full.lastIndexOf('\\'))
  return [full.slice(0, i), full.slice(i + 1)]
}
