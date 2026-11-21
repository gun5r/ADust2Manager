import type { IndexMod } from './classify'

/** A mod with textures or an atlas but no skeleton (.skel / .json) cannot be previewed or prepared until one is added. */
export function lacksSkeleton(mod: IndexMod): boolean {
  if (mod.is_multi || mod.has_json_anim) return false
  const files = (mod.files ?? []).map((f) => f.toLowerCase())
  return files.some((f) => /\.(atlas|png)$/.test(f)) && !files.some((f) => /\.(skel|skel\.bytes|json)$/.test(f))
}
