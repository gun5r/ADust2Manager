/** Reads, from the skeleton itself, which spot brings which other spot on screen, and picks the spot the touch guide points at (lib/guide.ts). */
import { attachmentBoxes, type Rect } from '../../lib/framing'
import { idleFor, type Hotspot } from '../../lib/dating'
import { guideTarget, type Reveals } from '../../lib/guide'
import type { SpineAnimation, SpinePlayer, SpineSkeleton } from './spineTypes'

declare const spine: any

interface PhaseMap { reveals: Reveals; art: Rect }

export class SceneGuide {
  private phases = new Map<number, PhaseMap>()

  constructor(private scene: { player: () => SpinePlayer | null; hotspots: () => Hotspot[]; animations: () => string[] }) {}

  /** A new skeleton or new rules: the maps are read again. */
  reset(): void { this.phases.clear() }

  /** The placed spot to point at (one of `placed`, spots of `phase` that can be used now), or null. */
  target<T extends { spot: Hotspot; x: number; y: number }>(phase: number, placed: T[], usable: (spot: Hotspot) => boolean): T | null {
    const map = this.map(phase)
    if (!map) return null
    const { minX, maxX, minY, maxY } = map.art
    const bone = guideTarget(placed.map(({ spot, x, y }) => ({ bone: spot.bone, id: spot.id, ends: !!spot.rule?.next, usable: usable(spot), onScreen: spot.kind === 'gyro' || x >= minX && x <= maxX && y >= minY && y <= maxY })), map.reveals)
    return placed.find((p) => p.spot.bone === bone) ?? null
  }

  /** Does touching `from` bring `to` on screen? */
  reveals(phase: number, from: string, to: string): boolean {
    return this.map(phase)?.reveals.get(from)?.includes(to) ?? false
  }

  private map(phase: number): PhaseMap | null {
    const cached = this.phases.get(phase)
    if (cached) return cached
    const built = this.build(phase)
    if (built) this.phases.set(phase, built)
    return built
  }

  /** Apply each reaction of every spot, over the phase's idle pose, to a scratch skeleton and note which other spots end up on screen. */
  private build(phase: number): PhaseMap | null {
    const player = this.scene.player()
    if (!player?.skeleton) return null
    const spots = this.scene.hotspots().filter((h) => h.phase === phase)
    if (!spots.some((s) => s.rule?.next)) return null // no way out of this phase (the last one, or a scene without rules)
    const data = player.skeleton.data
    const scratch = new spine.Skeleton(data)
    const idle = data.findAnimation(idleFor(phase, this.scene.animations()) ?? '')
    const pose = (clip: SpineAnimation | null, time: number) => {
      scratch.setToSetupPose()
      idle?.apply(scratch, 0, 0, true, [], 1, spine.MixBlend.setup, spine.MixDirection.mixIn)
      clip?.apply(scratch, time, time, false, [], 1, spine.MixBlend.replace, spine.MixDirection.mixIn)
      scratch.updateWorldTransform()
    }
    pose(null, 0)
    const art = this.artOf(scratch) ?? this.artOf(player.skeleton)
    if (!art) return null
    const visible = () => spots.filter((s) => {
      const bone = scratch.findBone(s.bone)
      return bone && bone.worldX >= art.minX && bone.worldX <= art.maxX && bone.worldY >= art.minY && bone.worldY <= art.maxY
    }).map((s) => s.bone)
    const resting = new Set(visible())
    const reveals: Reveals = new Map()
    for (const spot of spots) {
      const brought = new Set<string>()
      for (const name of [...spot.reactions, spot.rule?.stop]) {
        const clip = name ? data.findAnimation(name) : null
        if (!clip) continue
        const step = Math.max(0.15, clip.duration / 25)
        for (let time = 0; time <= clip.duration; time += step) {
          pose(clip, time)
          visible().forEach((bone) => bone !== spot.bone && !resting.has(bone) && brought.add(bone))
        }
      }
      if (brought.size) reveals.set(spot.bone, [...brought])
    }
    return { reveals, art }
  }

  /** The picture's extent: its drawn attachments, else (a phase that draws nothing yet) its bones; widened because the game parks spots
   * thousands of units away, while one at the edge of the picture (Justia's, just past its right side) is still on screen. */
  private artOf(skeleton: SpineSkeleton): Rect | null {
    const boxes = attachmentBoxes(skeleton)
    const points = boxes.length ? [] : skeleton.bones.filter((b) => !/^point/i.test(b.data.name)).map((b) => ({ x: b.worldX, y: b.worldY }))
    const xs = [...boxes.flatMap((b) => [b.minX, b.maxX]), ...points.map((p) => p.x)], ys = [...boxes.flatMap((b) => [b.minY, b.maxY]), ...points.map((p) => p.y)]
    if (!xs.length) return null
    const bounds = { minX: Math.min(...xs), maxX: Math.max(...xs), minY: Math.min(...ys), maxY: Math.max(...ys) }
    const margin = 0.2 * Math.max(bounds.maxX - bounds.minX, bounds.maxY - bounds.minY)
    return { minX: bounds.minX - margin, maxX: bounds.maxX + margin, minY: bounds.minY - margin, maxY: bounds.maxY + margin }
  }
}
