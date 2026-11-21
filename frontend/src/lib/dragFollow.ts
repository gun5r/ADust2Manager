/** Geometry of dragging a dating-scene spot: the spot's bone follows the finger, limited in reach, and a drag with a
 *  destination rectangle (the scene-ending ones) completes when the point lands inside it. */

/** Keep an offset within `max` of the start. */
export function clampOffset(dx: number, dy: number, max: number): { dx: number; dy: number } {
  const length = Math.hypot(dx, dy)
  return length > max && length > 0 ? { dx: (dx / length) * max, dy: (dy / length) * max } : { dx, dy }
}

/** Is the point inside a `[x, y, width, height]` rectangle centred on (x, y)? */
export const insideRect = (x: number, y: number, rect: readonly number[]): boolean =>
  Math.abs(x - rect[0]) <= rect[2] / 2 && Math.abs(y - rect[1]) <= rect[3] / 2

/** One frame of the spring-back after release: the offset shrinks exponentially; `done` once it is negligible. */
export function springBack(dx: number, dy: number, dt: number, rate = 14): { dx: number; dy: number; done: boolean } {
  const keep = Math.exp(-Math.max(0, dt) * rate)
  const next = { dx: dx * keep, dy: dy * keep }
  return { ...next, done: Math.hypot(next.dx, next.dy) < 0.5 }
}

/**
 * Did the point travel (nearly) all the way from its rest position `start` to the destination rectangle, heading roughly
 * towards it? The rectangle itself is small and moves with its parent while the press clip plays, so landing in it exactly
 * is not asked for: 90% of the way along the line, within a 35% sideways drift, or beyond.
 */
export function reachedDestination(start: readonly [number, number], dest: readonly number[], point: readonly [number, number]): boolean {
  const dx = dest[0] - start[0], dy = dest[1] - start[1], length = Math.hypot(dx, dy)
  if (length < 1) return insideRect(point[0], point[1], dest)
  const vx = point[0] - start[0], vy = point[1] - start[1]
  const along = (vx * dx + vy * dy) / length, sideways = Math.abs(vx * dy - vy * dx) / length
  return along >= 0.9 * length && sideways <= 0.35 * length
}
