/** Which way each drag spot goes, worked out once per skeleton (the dots style draws it as an arrow). */
import { dragGoal, type Hotspot } from '../../lib/dating'
import type { SpinePlayer } from './spineTypes'

declare const spine: any

type Direction = { x: number; y: number } | null

export class DragDirections {
  private cache = new Map<string, Direction>()

  clear(): void { this.cache.clear() }

  /** Toward its destination (scene-ending drags), else where its press clip moves the spot's bone; null = any direction. */
  of(player: SpinePlayer | null, spot: Hotspot): Direction {
    if (this.cache.has(spot.bone)) return this.cache.get(spot.bone)!
    let dir: Direction = null
    const bone = player?.skeleton?.findBone(spot.bone)
    const dest = dragGoal(spot.rule)
    if (bone && dest && bone.parent) {
      const world = { x: dest[0], y: dest[1] }
      bone.parent.localToWorld(world)
      dir = { x: world.x - bone.worldX, y: world.y - bone.worldY }
    } else if (player && spot.reactions[0]) {
      const data = player.skeleton.data, anim = data.findAnimation(spot.reactions[0])
      if (anim) {
        const scratch = new spine.Skeleton(data)
        scratch.setToSetupPose()
        scratch.updateWorldTransform()
        const b = scratch.findBone(spot.bone)
        if (b) {
          const start = { x: b.worldX as number, y: b.worldY as number }
          anim.apply(scratch, 0, anim.duration, false, [], 1, spine.MixBlend.setup, spine.MixDirection.mixIn)
          scratch.updateWorldTransform()
          dir = { x: b.worldX - start.x, y: b.worldY - start.y }
        }
      }
    }
    if (dir && Math.hypot(dir.x, dir.y) < 25) dir = null // hardly moves: the finger goes anywhere
    if (dir) { const n = Math.hypot(dir.x, dir.y); dir = { x: dir.x / n, y: dir.y / n } }
    this.cache.set(spot.bone, dir)
    return dir
  }
}
