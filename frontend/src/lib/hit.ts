/** Click hit-testing against Spine attachments, so clicking the character (not the backdrop) can trigger its motion clip. */
import { isBackgroundSlot } from './spine'

export function pointInPolygon(px: number, py: number, v: ArrayLike<number>): boolean {
  let inside = false
  for (let i = 0, j = v.length - 2; i < v.length; j = i, i += 2) {
    const xi = v[i], yi = v[i + 1], xj = v[j], yj = v[j + 1]
    if (yi > py !== yj > py && px < ((xj - xi) * (py - yi)) / (yj - yi) + xi) inside = !inside
  }
  return inside
}

export function pointInTriangle(px: number, py: number, ax: number, ay: number, bx: number, by: number, cx: number, cy: number): boolean {
  const d1 = (px - bx) * (ay - by) - (ax - bx) * (py - by)
  const d2 = (px - cx) * (by - cy) - (bx - cx) * (py - cy)
  const d3 = (px - ax) * (cy - ay) - (cx - ax) * (py - ay)
  return !((d1 < 0 || d2 < 0 || d3 < 0) && (d1 > 0 || d2 > 0 || d3 > 0))
}

/** Screen position -> world position for the player's orthographic camera. */
export function screenToWorld(camera: any, rect: { left: number; top: number; width: number; height: number }, clientX: number, clientY: number) {
  if (!camera || rect.width <= 0 || rect.height <= 0) return null
  const nx = ((clientX - rect.left) / rect.width) * 2 - 1
  const ny = 1 - 2 * ((clientY - rect.top) / rect.height)
  return { x: nx * (camera.viewportWidth / 2) * camera.zoom + camera.position.x, y: ny * (camera.viewportHeight / 2) * camera.zoom + camera.position.y }
}

/** Is the world point on a visible, non-background attachment of the skeleton (topmost first)? */
export function hitsSkeleton(skeleton: any, hidden: Set<string>, x: number, y: number): boolean {
  if (!skeleton || (skeleton.color && skeleton.color.a <= 0)) return false
  const drawOrder = skeleton.drawOrder || skeleton.slots || []
  for (let i = drawOrder.length - 1; i >= 0; i--) {
    const slot = drawOrder[i]
    if (!slot) continue
    const name = slot.data?.name ?? ''
    if (isBackgroundSlot(name) || (slot.color && slot.color.a <= 0) || hidden.has(name)) continue
    const attachment = slot.getAttachment?.()
    if (!attachment || (attachment.color && attachment.color.a <= 0)) continue
    try {
      if (!attachment.uvs) continue // bounding boxes, clipping, paths and points are not drawn
      if (attachment.triangles) {
        // Mesh (it also has a `region`, so it must be tested before the region case)
        const count = attachment.worldVerticesLength || 0
        if (!count) continue
        const vertices = new Float32Array(count)
        attachment.computeWorldVertices(slot, 0, count, vertices, 0, 2)
        const triangles = attachment.triangles
        for (let t = 0; t + 2 < triangles.length; t += 3) {
          const a = triangles[t] * 2, b = triangles[t + 1] * 2, c = triangles[t + 2] * 2
          if (pointInTriangle(x, y, vertices[a], vertices[a + 1], vertices[b], vertices[b + 1], vertices[c], vertices[c + 1])) return true
        }
      } else {
        const vertices = new Float32Array(8)
        attachment.computeWorldVertices(slot, vertices, 0, 2)
        if (pointInPolygon(x, y, vertices)) return true
      }
    } catch {
      /* keep testing the remaining attachments */
    }
  }
  return false
}
