/**
 * Warm the browser's caches for a mod's Spine files before the viewer asks for them: the files are fetched in parallel
 * (the player itself loads atlas, then textures, then skeleton one after another) and the textures are decoded ahead of
 * time. Used on hover, for the neighbouring mods while one is open, and at the start of every load.
 */
import { assetUrl, pickSpineFiles } from './spine'

const KEEP = 6
/** Recently warmed mods; holding the Image objects keeps their decoded pixels around for the real load. */
const warmed = new Map<string, HTMLImageElement[]>()

export function prefetchMod(mod: { folder_path: string; files: string[] }, maxTexture = 0): void {
  if (typeof Image === 'undefined') return
  const key = maxTexture ? `${mod.folder_path}|${maxTexture}` : mod.folder_path
  if (warmed.has(key)) {
    const images = warmed.get(key)!
    warmed.delete(key)
    warmed.set(key, images) // most recently used
    return
  }
  const files = pickSpineFiles(mod.files)
  for (const file of [files.atlas, files.skeleton ?? files.json]) {
    if (file) fetch(assetUrl(mod.folder_path, file, file === files.atlas ? maxTexture : 0)).catch(() => {})
  }
  const images = files.pngs.map((png) => {
    const image = new Image()
    image.decoding = 'async'
    image.src = assetUrl(mod.folder_path, png, maxTexture)
    image.decode().catch(() => {})
    return image
  })
  warmed.set(key, images)
  while (warmed.size > KEEP) warmed.delete(warmed.keys().next().value!)
}

/** Forget a mod (its files changed, e.g. after merging) so the next prefetch fetches fresh data. */
export const forgetPrefetch = (folderPath: string): void => void warmed.delete(folderPath)

let intent: ReturnType<typeof setTimeout> | undefined

/** Prefetch only when the pointer rests on something for a moment, so sweeping across a list does not fetch every mod. */
export function prefetchOnIntent(mod: { folder_path: string; files: string[] }, delay = 150): void {
  clearTimeout(intent)
  intent = setTimeout(() => prefetchMod(mod), delay)
}

export const cancelPrefetchIntent = (): void => clearTimeout(intent)
