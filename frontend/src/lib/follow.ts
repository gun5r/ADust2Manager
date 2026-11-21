/** Animation-name rules and the follow-camera easing used by the viewer (ported from classic updateSpineCamera). */

export const isIdleAnimationName = (name: string | null | undefined): boolean => {
  if (!name) return false
  const n = name.toLowerCase()
  return n === 'idle' || n.startsWith('idle') || n.includes('idle') || n === 'stand' || n === 'loop'
}

export const isMotionAnimationName = (name: string | null | undefined): boolean => {
  if (!name) return false
  const n = name.toLowerCase()
  return n === 'motion' || n.startsWith('motion') || n === 'touch' || n === 'action' || n.startsWith('m01') || n.startsWith('m1')
}

export const followForScene = (dating: boolean, remembered: boolean | undefined): boolean => dating ? false : remembered ?? true

/** The click-to-play reaction clip: exactly "motion" if present, otherwise the first motion-like clip. */
export function findMotionAnimation(names: string[]): string | null {
  return names.find((n) => n.toLowerCase() === 'motion') ?? names.find(isMotionAnimationName) ?? null
}

export interface FollowFilter { x: number; y: number; z: number; zooming: boolean }

/**
 * The follow camera without wiggle. The subject's centre and size change with every pose, so they are low-pass filtered first (a
 * slow time constant averages a whole motion cycle), and the camera then only moves when the filtered target is more than a small
 * dead zone away, easing toward the edge of that zone, so what is left of the sway never reaches the screen. The zoom works the same
 * way (it only starts to change past 12% and stops near the target), and a jump larger than the view (a scene cut) snaps.
 * `viewWorld` is the height of the view in world units; zoom is world units per pixel.
 */
export function followFilterStep(
  filter: FollowFilter | undefined,
  camera: { x: number; y: number; zoom: number },
  target: { x: number; y: number; zoom: number },
  viewWorld: number,
  dt: number,
): { filter: FollowFilter; camera: { x: number; y: number; zoom: number } } {
  dt = Math.min(Math.max(dt, 0), 0.1)
  const logTarget = Math.log(target.zoom)
  if (!filter || Math.hypot(target.x - filter.x, target.y - filter.y) > viewWorld * 0.8) {
    return { filter: { x: target.x, y: target.y, z: logTarget, zooming: false }, camera: { ...target } }
  }
  const a = 1 - Math.exp(-dt / 0.6)
  const f = { x: filter.x + (target.x - filter.x) * a, y: filter.y + (target.y - filter.y) * a, z: filter.z + (logTarget - filter.z) * a, zooming: filter.zooming }
  const out = { ...camera }
  const dx = f.x - camera.x, dy = f.y - camera.y, dist = Math.hypot(dx, dy), dead = viewWorld * 0.035
  if (dist > dead) {
    const move = ((dist - dead) / dist) * Math.min(1, dt * 3)
    out.x += dx * move
    out.y += dy * move
  }
  const dz = f.z - Math.log(camera.zoom)
  f.zooming = f.zooming ? Math.abs(dz) > 0.03 : Math.abs(dz) > 0.12
  if (f.zooming) out.zoom = camera.zoom * Math.exp(dz * Math.min(1, dt * 1.5))
  return { filter: f, camera: out }
}
