/**
 * Where the camera should look. Illustrations often carry thin beams, sparkles or glow far from the character, so a plain
 * union of every attachment frames a tiny character in a big empty view. Instead the subject is the area-weighted bulk of
 * the visible attachments: each side of the frame is trimmed by a small share of the visual mass, but big parts are never cut.
 */
import { isBackgroundSlot } from './spine'

export interface Rect { minX: number; maxX: number; minY: number; maxY: number }
export interface Box extends Rect {
  /** Visual mass: true covered area x opacity (additive glows count a tenth). */
  weight: number
  /** Covered area as a share of the bounding box: low for long diagonal slivers. */
  fill: number
  /** A full-screen backdrop rather than part of the subject. */
  giant: boolean
}

const BLEND_ADDITIVE = 1

/** Area actually covered by the attachment: the sum of its triangles, or the quad of a region. */
function coveredArea(attachment: any, vertices: Float32Array): number {
  const triangleArea = (a: number, b: number, c: number) =>
    Math.abs((vertices[b * 2] - vertices[a * 2]) * (vertices[c * 2 + 1] - vertices[a * 2 + 1]) - (vertices[c * 2] - vertices[a * 2]) * (vertices[b * 2 + 1] - vertices[a * 2 + 1])) / 2
  const triangles: ArrayLike<number> | undefined = attachment.triangles
  if (triangles?.length) {
    let area = 0
    for (let i = 0; i + 2 < triangles.length; i += 3) area += triangleArea(triangles[i], triangles[i + 1], triangles[i + 2])
    return area
  }
  return vertices.length >= 8 ? triangleArea(0, 1, 2) + triangleArea(0, 2, 3) : 0
}

/** World vertices of an attachment (any kind that can be placed), or null when it cannot be computed. */
function worldVertices(slot: any, attachment: any): Float32Array | null {
  try {
    if (attachment.worldVerticesLength) {
      const vertices = new Float32Array(attachment.worldVerticesLength)
      attachment.computeWorldVertices(slot, 0, attachment.worldVerticesLength, vertices, 0, 2)
      return vertices
    }
    const vertices = new Float32Array(8)
    attachment.computeWorldVertices(slot, vertices, 0, 2)
    return vertices
  } catch {
    return null
  }
}

function extent(vertices: Float32Array): Rect | null {
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity
  for (let i = 0; i < vertices.length; i += 2) {
    const x = vertices[i], y = vertices[i + 1]
    if (!Number.isFinite(x) || !Number.isFinite(y)) continue
    minX = Math.min(minX, x); maxX = Math.max(maxX, x); minY = Math.min(minY, y); maxY = Math.max(maxY, y)
  }
  return minX > maxX ? null : { minX, maxX, minY, maxY }
}

/**
 * Some dating illustrations park several scenes in one skeleton and cover all but one with opaque black masks: the game's
 * camera only ever sees the gap between the masks. That gap is the largest grid cell (cut at the masks' edges) no mask covers.
 */
function openWindow(masks: Rect[]): Rect | null {
  if (!masks.length) return null
  const xs = [...new Set(masks.flatMap((m) => [m.minX, m.maxX]))].sort((a, b) => a - b)
  const ys = [...new Set(masks.flatMap((m) => [m.minY, m.maxY]))].sort((a, b) => a - b)
  let best: Rect | null = null, bestArea = 0
  for (let i = 0; i + 1 < xs.length; i++) {
    for (let j = 0; j + 1 < ys.length; j++) {
      const cell = { minX: xs[i], maxX: xs[i + 1], minY: ys[j], maxY: ys[j + 1] }
      if (masks.some((m) => m.minX <= cell.minX && m.maxX >= cell.maxX && m.minY <= cell.minY && m.maxY >= cell.maxY)) continue
      const area = (cell.maxX - cell.minX) * (cell.maxY - cell.minY)
      if (area > bestArea) { best = cell; bestArea = area }
    }
  }
  return best
}

/**
 * World boxes of the visible, non-background attachments of the skeleton's current pose. Spine clipping attachments mask
 * everything up to their end slot (scenes are often composed with parts parked outside a picture frame), so boxes are
 * cut to the active clip and dropped when nothing of them remains inside.
 */
export function attachmentBoxes(skeleton: any): Box[] {
  const boxes = collectBoxes(skeleton, true)
  // a scene whose every piece is named like scenery (Scheherazade's `C_BG_..`) has no subject by those rules: take what is drawn, whatever it is called
  return boxes.length ? boxes : collectBoxes(skeleton, false)
}

function collectBoxes(skeleton: any, skipScenery: boolean): Box[] {
  const boxes: Box[] = []
  const masks: Rect[] = []
  let clip: { rect: Rect | null; end: unknown } | null = null
  for (const slot of skeleton?.drawOrder ?? skeleton?.slots ?? []) {
    const attachment = slot.getAttachment?.()
    if (attachment && attachment.endSlot !== undefined && typeof attachment.computeWorldVertices === 'function') {
      const vertices = worldVertices(slot, attachment)
      clip = { rect: vertices ? extent(vertices) : null, end: attachment.endSlot }
    } else if (attachment && typeof attachment.computeWorldVertices === 'function'
      && !(skipScenery && isBackgroundSlot(slot.data?.name ?? '')) && !(slot.color && slot.color.a <= 0)
      && !(skipScenery && isBackgroundSlot((attachment.name ?? '').toLowerCase())) && !(attachment.color && attachment.color.a <= 0)) {
      const vertices = worldVertices(slot, attachment)
      const own = vertices && extent(vertices)
      if (own) {
        const width = own.maxX - own.minX, height = own.maxY - own.minY
        let visible = own
        if (clip?.rect) {
          visible = {
            minX: Math.max(own.minX, clip.rect.minX), maxX: Math.min(own.maxX, clip.rect.maxX),
            minY: Math.max(own.minY, clip.rect.minY), maxY: Math.min(own.maxY, clip.rect.maxY),
          }
        }
        if (visible.minX < visible.maxX && visible.minY < visible.maxY) {
          const opacity = (slot.color?.a ?? 1) * (attachment.color?.a ?? 1) * (skeleton.color?.a ?? 1)
          const glow = slot.data?.blendMode === BLEND_ADDITIVE ? 0.1 : 1
          const area = coveredArea(attachment, vertices) * (((visible.maxX - visible.minX) * (visible.maxY - visible.minY)) / Math.max(width * height, 1))
          boxes.push({
            ...visible, weight: Math.max(area, 1) * opacity * glow,
            fill: width * height > 0 ? Math.min(area / ((visible.maxX - visible.minX) * (visible.maxY - visible.minY)), 1) : 1,
            giant: width > 1500 && height > 900,
          })
        }
      }
    }
    else if (attachment && typeof attachment.computeWorldVertices === 'function' && /black/i.test(slot.data?.name ?? '') && (slot.color?.a ?? 1) >= 0.99) {
      const vertices = worldVertices(slot, attachment)
      const rect = vertices && extent(vertices)
      if (rect) masks.push(rect)
    }
    if (clip && slot.data === clip.end) clip = null
  }
  const open = skipScenery ? openWindow(masks) : null
  return open ? boxes.filter((b) => b.maxX > open.minX && b.minX < open.maxX && b.maxY > open.minY && b.minY < open.maxY) : boxes
}

/**
 * Extent of the dense part of one axis. Every box spreads its mass evenly over its extent, which gives a density profile;
 * the ends of the axis whose density stays below `tau` of the typical (mass-weighted median) density are cut off. The
 * median, not the peak, so a pile of small overlapping layers cannot make everything else look sparse.
 */
function denseRange(boxes: Box[], axis: 'x' | 'y', tau: number): [number, number] {
  const lo = (b: Box) => (axis === 'x' ? b.minX : b.minY)
  const hi = (b: Box) => Math.max(axis === 'x' ? b.maxX : b.maxY, lo(b) + 1)
  // Sweep over the box edges: the density changes by +/- weight/extent at each one.
  const events = boxes.flatMap((b) => {
    const rate = b.weight / (hi(b) - lo(b))
    return [[lo(b), rate], [hi(b), -rate]] as [number, number][]
  }).sort((a, b) => a[0] - b[0])
  const points: number[] = []
  const segments: { density: number; mass: number }[] = []
  let density = 0
  for (let i = 0; i < events.length; i++) {
    density += events[i][1]
    const next = events[i + 1]
    if (points[points.length - 1] !== events[i][0]) points.push(events[i][0])
    if (!next || next[0] === events[i][0]) continue
    segments.push({ density: Math.max(density, 0), mass: Math.max(density, 0) * (next[0] - events[i][0]) })
    points.push(next[0])
  }
  const byDensity = [...segments].sort((a, b) => a.density - b.density)
  const half = segments.reduce((sum, s) => sum + s.mass, 0) / 2
  let seen = 0
  let typical = byDensity[byDensity.length - 1].density
  for (const segment of byDensity) {
    seen += segment.mass
    if (seen >= half) { typical = segment.density; break }
  }
  const floor = typical * tau
  const first = segments.findIndex((s) => s.density >= floor)
  const last = segments.length - 1 - [...segments].reverse().findIndex((s) => s.density >= floor)
  return [points[first], points[last + 1]]
}

export interface SubjectOptions {
  /** Ends of an axis thinner than this fraction of the typical density are trimmed (default 5%). */
  tau?: number
  /** A compact part carrying at least this share of the total mass is always kept whole (default 4%). */
  keep?: number
}

/** Beams, streaks and slivers: long and narrow, or mostly empty inside their bounding box. */
const isThin = (b: Box) => {
  const w = b.maxX - b.minX, h = b.maxY - b.minY
  return Math.min(w, h) < 0.12 * Math.max(w, h) || b.fill < 0.3
}

/** The area to frame: the dense bulk of the boxes, plus every substantial compact part in full. Null when nothing is visible. */
export function subjectRect(all: Box[], { tau = 0.05, keep = 0.04 }: SubjectOptions = {}): Rect | null {
  const boxes = all.some((b) => !b.giant) ? all.filter((b) => !b.giant) : all
  if (!boxes.length) return null
  const [minX, maxX] = denseRange(boxes, 'x', tau)
  const [minY, maxY] = denseRange(boxes, 'y', tau)
  let rect: Rect = { minX, maxX, minY, maxY }
  const total = boxes.reduce((sum, b) => sum + b.weight, 0)
  for (const box of boxes) if (box.weight >= total * keep && !isThin(box)) rect = unionRect(rect, box)
  return rect.minX < rect.maxX && rect.minY < rect.maxY ? rect : null
}

export function unionRect(a: Rect, b: Rect): Rect {
  return { minX: Math.min(a.minX, b.minX), maxX: Math.max(a.maxX, b.maxX), minY: Math.min(a.minY, b.minY), maxY: Math.max(a.maxY, b.maxY) }
}

export const rectCenter = (r: Rect) => ({ x: (r.minX + r.maxX) / 2, y: (r.minY + r.maxY) / 2 })

/** Camera zoom (world units per pixel) that fits `rect` into the viewport with a small margin on every side. */
export function fitRect(rect: Rect, viewportW: number, viewportH: number, margin = 0.05): number {
  const w = Math.max(rect.maxX - rect.minX, 1), h = Math.max(rect.maxY - rect.minY, 1)
  return Math.max(w / Math.max(viewportW * (1 - 2 * margin), 1), h / Math.max(viewportH * (1 - 2 * margin), 1))
}

/** Zoom that makes the rect fill the view's height (dating pictures are vertical, so no black bars above and below); a very wide one is not cropped by more than a quarter. */
export function fitHeight(rect: Rect, viewportW: number, viewportH: number): number {
  const w = Math.max(rect.maxX - rect.minX, 1), h = Math.max(rect.maxY - rect.minY, 1)
  return Math.max(h / Math.max(viewportH, 1), (0.75 * w) / Math.max(viewportW, 1))
}

/**
 * The heaviest group of boxes that touch each other (within `gap` world units). Cutscenes park alternate pieces away from the
 * picture; a thumbnail should show the picture, not the whole spread.
 */
export function mainCluster(boxes: Box[], gap = 40): Box[] {
  const parent = boxes.map((_, i) => i)
  const find = (i: number): number => (parent[i] === i ? i : (parent[i] = find(parent[i])))
  boxes.forEach((a, i) => boxes.forEach((b, j) => {
    if (j > i && a.minX - gap <= b.maxX && b.minX - gap <= a.maxX && a.minY - gap <= b.maxY && b.minY - gap <= a.maxY) parent[find(i)] = find(j)
  }))
  const weights = new Map<number, number>()
  boxes.forEach((b, i) => weights.set(find(i), (weights.get(find(i)) ?? 0) + b.weight))
  const best = [...weights.entries()].sort((x, y) => y[1] - x[1])[0]?.[0]
  return boxes.filter((_, i) => find(i) === best)
}

/**
 * The picture in a drawn frame. Modded scenes put extra pictures (a pose menu, a second scene) beside it, so a plain bounding
 * box of everything filled would take them in. `filled` is a W*H mask. Filled pixels are grouped into clusters (cells of `cell`
 * pixels, joined across gaps of `gap` cells); the picture is the biggest cluster holding a touch point (pixel coordinates), plus
 * nearby ones that hold touch points too; with no touch points it is the largest cluster. Returns the box of the chosen clusters in pixels (max exclusive), or null when nothing is filled.
 */
export function pictureBox(filled: Uint8Array, W: number, H: number, points: { x: number; y: number }[], cell = 6, gap = 2): { x0: number; x1: number; y0: number; y1: number } | null {
  const cw = Math.ceil(W / cell), ch = Math.ceil(H / cell)
  const count = new Int32Array(cw * ch)
  const lo = new Int32Array(cw * ch * 2).fill(1 << 30), hi = new Int32Array(cw * ch * 2).fill(-1)
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      if (!filled[y * W + x]) continue
      const i = Math.floor(y / cell) * cw + Math.floor(x / cell)
      count[i]++
      lo[i * 2] = Math.min(lo[i * 2], x); lo[i * 2 + 1] = Math.min(lo[i * 2 + 1], y)
      hi[i * 2] = Math.max(hi[i * 2], x + 1); hi[i * 2 + 1] = Math.max(hi[i * 2 + 1], y + 1)
    }
  }
  const label = new Int32Array(cw * ch).fill(-1)
  const clusters: { x0: number; x1: number; y0: number; y1: number; area: number; points: number }[] = []
  for (let start = 0; start < count.length; start++) {
    if (!count[start] || label[start] >= 0) continue
    const id = clusters.length, c = { x0: 1 << 30, x1: -1, y0: 1 << 30, y1: -1, area: 0, points: 0 }
    const queue = [start]
    label[start] = id
    while (queue.length) {
      const i = queue.pop()!, cx = i % cw, cy = Math.floor(i / cw)
      c.area += count[i]
      c.x0 = Math.min(c.x0, lo[i * 2]); c.y0 = Math.min(c.y0, lo[i * 2 + 1]); c.x1 = Math.max(c.x1, hi[i * 2]); c.y1 = Math.max(c.y1, hi[i * 2 + 1])
      for (let dy = -gap; dy <= gap; dy++) {
        for (let dx = -gap; dx <= gap; dx++) {
          const nx = cx + dx, ny = cy + dy
          if (nx < 0 || ny < 0 || nx >= cw || ny >= ch) continue
          const n = ny * cw + nx
          if (count[n] && label[n] < 0) { label[n] = id; queue.push(n) }
        }
      }
    }
    clusters.push(c)
  }
  if (!clusters.length) return null
  const slack = cell * gap
  for (const c of clusters) c.points = points.filter((q) => q.x >= c.x0 - slack && q.x <= c.x1 + slack && q.y >= c.y0 - slack && q.y <= c.y1 + slack).length
  // The anchor is the biggest cluster holding a touch point (else the biggest cluster); other clusters with touch points join it only
  // when they sit close to it (a picture split by black bands), not when they are far away (a mod's spots parked beside the scene).
  const big = (list: typeof clusters) => list.reduce((a, b) => (b.area > a.area ? b : a))
  const anchor = big(clusters.some((c) => c.points) ? clusters.filter((c) => c.points) : clusters)
  const reach = 0.35 * Math.max(anchor.x1 - anchor.x0, anchor.y1 - anchor.y0)
  const near = (c: (typeof clusters)[number]) => c.x0 - anchor.x1 <= reach && anchor.x0 - c.x1 <= reach && c.y0 - anchor.y1 <= reach && anchor.y0 - c.y1 <= reach
  const chosen = clusters.filter((c) => c === anchor || (c.points && near(c)))
  return { x0: Math.min(...chosen.map((c) => c.x0)), x1: Math.max(...chosen.map((c) => c.x1)), y0: Math.min(...chosen.map((c) => c.y0)), y1: Math.max(...chosen.map((c) => c.y1)) }
}
