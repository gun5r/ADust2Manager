/** Spine preview helpers: file picking, asset URLs, animation choice and auto-framing bounds. */

export interface SpineFiles {
  atlas?: string
  skeleton?: string
  json?: string
  pngs: string[]
}

/** `skeleton` picks the atlas of that skeleton (same name) when a folder holds several skeletons. */
export function pickSpineFiles(files: string[], skeletonFile?: string): SpineFiles {
  const lower = (f: string) => f.toLowerCase()
  const atlases = files.filter((f) => lower(f).endsWith('.atlas') || lower(f).endsWith('.atlas.txt'))
  const stem = skeletonFile?.replace(/\.(skel|json)(\.bytes)?$/i, '').toLowerCase()
  const atlas = atlases.find((f) => lower(f).replace(/\.atlas(\.txt)?$/, '') === stem) ?? atlases[0]
  const skeleton = files.find((f) => lower(f).endsWith('.skel') || lower(f).endsWith('.skel.bytes'))
  const json = files.find((f) => lower(f).endsWith('.json'))
  return { atlas, skeleton, json, pngs: files.filter((f) => lower(f).endsWith('.png')) }
}

/** Same encoding the Python side expects in /api/mod-assets/{folder_b64}/... (urlsafe base64, no padding). */
export function encodeFolder(folderPath: string): string {
  const bytes = new TextEncoder().encode(folderPath)
  let binary = ''
  for (const byte of bytes) binary += String.fromCharCode(byte)
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

/** `maxTexture` asks the server for a PNG shrunk to about that many pixels on its longest side (portrait rendering only). */
export const assetUrl = (folderPath: string, file: string, maxTexture = 0): string =>
  `/api/mod-assets/${encodeFolder(folderPath)}/${encodeURIComponent(file)}${maxTexture ? `?max=${maxTexture}` : ''}`

const IDLE_PRIORITY = [/^idle$/i, /idle/i, /^loop$/i, /loop/i, /^motion$/i, /^m01$/i, /^dating/i]

export function cutSequence(names: string[]): string[] {
  const clips = names.filter((n) => /^cut_?\d+$/i.test(n) || /cutscene_?\d+$/i.test(n))
  const order = (n: string) => parseInt(n.replace(/\D/g, ''), 10) || 0
  return clips.length > 1 ? clips.sort((a, b) => order(a) - order(b)) : []
}

/** Animation to start with: a full cutscene sequence, else idle/loop/motion, else the first clip. */
export function defaultPlayback(names: string[]): { sequence: string[]; animation: string | null } {
  const sequence = cutSequence(names)
  const priority = IDLE_PRIORITY.map((pattern) => names.find((n) => pattern.test(n))).find(Boolean) ?? null
  if (sequence.length && (!priority || sequence.includes(priority))) return { sequence, animation: null }
  return { sequence: [], animation: priority ?? names[0] ?? null }
}

export function isBackgroundSlot(name: string): boolean {
  if (!name) return false
  const n = name.toLowerCase()
  return (
    n.startsWith('bg') || n.startsWith('bk') || n.startsWith('env') ||
    ['_bg', ' bg', 'background', 'backdrop', 'stage', 'room', 'wall', 'scene', 'ground', 'floor', 'frame', 'window',
      'gradient', 'overlay', 'back_', 'water', 'sky', 'shadow'].some((part) => n.includes(part))
  )
}

/** A dating scene split over skeletons named `..._<phase>.skel` (the game's own scenes, e.g. illust_dating22_1 and _2): phase -> file. */
export function skeletonParts(files: string[]): Map<number, string> {
  const parts = new Map<number, string>()
  for (const f of files) {
    const m = /_(\d+)\.skel(\.bytes)?$/i.exec(f)
    if (m) parts.set(Number(m[1]), f)
  }
  return parts.size > 1 ? parts : new Map()
}
