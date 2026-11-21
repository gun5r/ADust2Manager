/**
 * The Fit camera of dating scenes: it finds the picture by drawing the skeleton and looking at which pixels are filled (the boxes of
 * its attachments include pieces parked far away), and shows it filling the view's height. The first fit of a mod jumps (the stage
 * stays hidden until it is done), the fits of the other phases are worked out in the background on a spare skeleton so a phase
 * change sets its camera at once, and only later corrections within a phase glide.
 */
import { attachmentBoxes, fitHeight, fitRect, pictureBox, rectCenter, subjectRect, type Rect } from '../../lib/framing'
import { idleFor, phasesOf, type Hotspot, type SceneRules } from '../../lib/dating'

declare const spine: any

/** The camera values the viewer owns: the framed position and zoom, and the user's wheel zoom and pan on top of them. */
export interface CameraView {
  frame: { x: number; y: number; zoom: number }
  zoomScale: number
  panX: number
  panY: number
}

/** What the fit reads from, and asks of, the viewer. */
export interface FitHost {
  view: CameraView
  player(): any
  stage(): HTMLElement | undefined
  generation(): number
  phase(): number
  hotspots(): Hotspot[]
  rules(): SceneRules | null
  animationNames(): string[]
  dragging(): boolean
  applyCamera(camera: any): void
  /** The plain framing of the subject (used before the fit is known, and when the Fit is off). */
  reframe(): void
}

export class FitCamera {
  /** Fit On/Off and Snap (jump instead of gliding), as chosen in the viewer footer. */
  enabled = true
  snap = false
  /** True while a probe frame is being drawn: the player's per-frame update must keep the probe's camera. */
  probing = false
  private fitted = false
  /** A freshly loaded scene or a new phase: it appears already fitted, so the stage stays hidden until the first fit is done. */
  private fresh = false
  /** The picture of this mod cannot be found (Scheherazade draws nothing the Fit can measure): nothing is hidden waiting for a fit that never comes. */
  private unfittable = false
  private timers: ReturnType<typeof setTimeout>[] = []
  private glide: { from: CameraView['frame']; to: CameraView['frame']; t: number } | null = null
  private cache = new Map<number, Rect>()
  private cacheStarted = false

  constructor(private host: FitHost) {}

  /** A new mod is loading. */
  reset(): void {
    this.cache.clear()
    this.cacheStarted = false
    this.unfittable = false
    this.reveal()
  }

  /** The player is ready: the first fit of this mod is still to come. */
  loaded(): void {
    this.fitted = false
    this.fresh = true
  }

  /** The scene changes phase: the new phase appears already fitted too. */
  expectNewPhase(): void {
    this.fresh = true
  }

  reveal(on = true): void {
    const stage = this.host.stage()
    if (stage) stage.style.visibility = on ? '' : 'hidden'
  }

  /** The pose at t=0 is not representative, so frame again once a few frames have run. */
  reframeSoon(interact: boolean): void {
    const generation = this.host.generation()
    this.timers.forEach(clearTimeout)
    if (!(this.enabled && interact)) {
      this.fresh = false
      this.host.reframe()
      this.timers = [setTimeout(() => generation === this.host.generation() && this.host.reframe(), 200)]
      return
    }
    const cached = this.fitted && this.cache.get(this.host.phase()) // a phase worked out beforehand: no waiting, no blink
    if (cached) { this.apply(cached); this.fresh = false } else this.host.reframe()
    if (this.fresh && !this.unfittable) this.reveal(false)
    this.timers = [120, 700].map((ms, i) => setTimeout(() => {
      if (generation !== this.host.generation()) return
      this.fit((i === 0 && !this.fitted) || this.snap || this.fresh)
      if (i === 1) {
        const first = this.fresh
        this.fresh = false
        this.reveal()
        if (first && !this.cacheStarted) { this.cacheStarted = true; this.cachePhases(generation) }
      }
    }, ms))
  }

  /** Frame the scene again (the Fit button was switched). */
  refit(interact: boolean): void {
    this.fitted = false
    this.reframeSoon(interact)
  }

  /** Per frame: move the camera along an unfinished glide. */
  advance(delta: number): void {
    const g = this.glide
    if (!g) return
    g.t = Math.min(1, g.t + delta / 0.7)
    const e = g.t * g.t * (3 - 2 * g.t) // ease in and out
    const frame = this.host.view.frame
    frame.x = g.from.x + (g.to.x - g.from.x) * e
    frame.y = g.from.y + (g.to.y - g.from.y) * e
    frame.zoom = Math.exp(Math.log(g.from.zoom) + (Math.log(g.to.zoom) - Math.log(g.from.zoom)) * e)
    if (g.t >= 1) this.glide = null
  }

  /** Find the picture of the live phase and show it filling the view's height; the manual pan and zoom are put back. */
  private fit(jump: boolean): void {
    const view = this.host.view, camera = this.host.player()?.sceneRenderer?.camera
    if (!camera) return
    const rect = this.pictureRect(this.host.phase())
    if (!rect) { this.unfittable = true; return this.reveal() }
    this.cache.set(this.host.phase(), rect)
    const c = rectCenter(rect), zoom = fitHeight(rect, camera.viewportWidth, camera.viewportHeight)
    const base = view.frame.zoom / view.zoomScale
    const same = view.zoomScale === 1 && !view.panX && !view.panY && Math.abs(Math.log(zoom / base)) < 0.03 && Math.hypot(c.x - view.frame.x, c.y - view.frame.y) < base * 12
    this.fitted = true
    if (same) return this.reveal()
    view.frame = { ...view.frame, zoom: base }
    view.zoomScale = 1
    view.panX = view.panY = 0
    if (jump) { view.frame = { x: c.x, y: c.y, zoom }; this.reveal() }
    else this.glide = { from: { ...view.frame }, to: { x: c.x, y: c.y, zoom }, t: 0 }
  }

  /** The camera that shows `rect` as the Fit does, set at once. */
  private apply(rect: Rect): void {
    const view = this.host.view, camera = this.host.player()?.sceneRenderer?.camera
    if (!camera) return
    const c = rectCenter(rect)
    view.frame = { x: c.x, y: c.y, zoom: fitHeight(rect, camera.viewportWidth, camera.viewportHeight) }
    view.zoomScale = 1
    view.panX = view.panY = 0
  }

  /** The picture of the phase as it is posed now, in world units. */
  private pictureRect(phase: number): Rect | null {
    const p = this.host.player()
    p.skeleton.updateWorldTransform()
    const union = attachmentBoxes(p.skeleton).reduce<Rect | null>((u, b) => u ? { minX: Math.min(u.minX, b.minX), maxX: Math.max(u.maxX, b.maxX), minY: Math.min(u.minY, b.minY), maxY: Math.max(u.maxY, b.maxY) } : { ...b }, null)
    let rect = this.filledRect(union, phase)
    if (rect) rect = this.filledRect(rect, phase) // a second look, now at a size where the picture fills the view
    return rect ?? subjectRect(attachmentBoxes(p.skeleton))
  }

  /**
   * Work out where the picture of every other phase is while the scene sits idle, so a phase change can set its camera at once
   * (no hidden moment, no glide). Each phase is posed on a spare skeleton and drawn and read back inside one task, so nothing of
   * it reaches the screen.
   */
  private cachePhases(generation: number): void {
    const todo = phasesOf(this.host.hotspots()).filter((n) => !this.cache.has(n))
    const next = () => {
      const phase = todo.shift()
      const p = this.host.player()
      if (phase === undefined || generation !== this.host.generation() || !p || this.host.dragging()) return
      const anim = p.skeleton.data.findAnimation(idleFor(phase, this.host.animationNames()) ?? '')
      if (anim) {
        const real = p.skeleton, wasPaused = p.paused
        try {
          const scratch = new spine.Skeleton(real.data)
          scratch.setToSetupPose()
          const skin = this.host.rules()?.groups.find((g) => g.group === phase)?.tools?.find((t) => t.id === 0)?.skin
          if (skin && real.data.findSkin(skin)) { scratch.setSkinByName(skin); scratch.setSlotsToSetupPose() }
          anim.apply(scratch, 0.12, 0.12, true, [], 1, spine.MixBlend.setup, spine.MixDirection.mixIn)
          scratch.updateWorldTransform()
          p.skeleton = scratch
          p.paused = true // the player must not apply the running animation to the spare skeleton
          const rect = this.pictureRect(phase)
          if (rect) this.cache.set(phase, rect)
        } catch (e) {
          console.warn('Fit of a phase could not be worked out (ignored):', e)
        } finally {
          p.skeleton = real
          p.paused = wasPaused
        }
      }
      setTimeout(next, 40)
    }
    setTimeout(next, 0)
  }

  /** The box of what is drawn (filled, not black: opaque black masks hide the other panels of the skeleton) when the camera shows `view`, as world units. */
  private filledRect(area: Rect | null, phase: number): Rect | null {
    const p = this.host.player(), camera = p?.sceneRenderer?.camera
    if (!p || !camera || !area) return null
    const view = this.host.view
    const keep = { frame: { ...view.frame }, zoomScale: view.zoomScale, panX: view.panX, panY: view.panY }
    try {
      const c = rectCenter(area)
      view.frame = { x: c.x, y: c.y, zoom: fitRect(area, camera.viewportWidth, camera.viewportHeight, 0.02) }
      this.probing = true
      view.zoomScale = 1
      view.panX = view.panY = 0
      this.host.applyCamera(camera)
      p.drawFrame?.(false)
      const canvas = p.canvas as HTMLCanvasElement
      const W = 384, H = Math.max(1, Math.round((384 * canvas.height) / canvas.width))
      const probe = document.createElement('canvas')
      probe.width = W
      probe.height = H
      const ctx = probe.getContext('2d', { willReadFrequently: true })
      if (!ctx) return null
      ctx.drawImage(canvas, 0, 0, W, H)
      const px = ctx.getImageData(0, 0, W, H).data
      const filled = new Uint8Array(W * H)
      for (let i = 0; i < W * H; i++) filled[i] = px[i * 4 + 3] > 40 && px[i * 4] + px[i * 4 + 1] + px[i * 4 + 2] > 36 ? 1 : 0
      const w = camera.viewportWidth * view.frame.zoom, h = camera.viewportHeight * view.frame.zoom
      const worldX = (x: number) => view.frame.x + (x / W - 0.5) * w, worldY = (y: number) => view.frame.y - (y / H - 0.5) * h
      // the touch spots of the live phase mark the real picture (a mod may park other pictures beside it)
      const points = this.host.hotspots().filter((s) => s.phase === phase).flatMap((s) => {
        const bone = p.skeleton.findBone(s.bone)
        return bone ? [{ x: ((bone.worldX + p.skeleton.x - view.frame.x) / w + 0.5) * W, y: (0.5 - (bone.worldY + p.skeleton.y - view.frame.y) / h) * H }] : []
      })
      const box = pictureBox(filled, W, H, points)
      return box ? { minX: worldX(box.x0), maxX: worldX(box.x1), minY: worldY(box.y1), maxY: worldY(box.y0) } : null
    } finally {
      this.probing = false
      view.frame = keep.frame
      view.zoomScale = keep.zoomScale
      view.panX = keep.panX
      view.panY = keep.panY
      this.host.applyCamera(camera)
    }
  }
}
