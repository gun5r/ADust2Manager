/**
 * Imperative wrapper around the Spine 4.1 player (global `spine`, loaded from /static/libs): loading, playback, the
 * follow/zoom/pan camera, layer hiding, click-to-motion and snapshots. It holds no UI state; ViewerState mirrors it.
 */
import { findMotionAnimation, followFilterStep, isIdleAnimationName, type FollowFilter } from '../../lib/follow'
import { hitsSkeleton, screenToWorld } from '../../lib/hit'
import { setSlotHidden } from '../../lib/layers'
import { attachmentBoxes, fitRect, mainCluster, rectCenter, subjectRect } from '../../lib/framing'
import { FitCamera, type CameraView } from './fitCamera'
import { DatingSession, type SessionHooks } from './datingSession'
import type { SpineCamera, SpinePlayer } from './spineTypes'
import { keepIdleAttachments } from './fadeAttachments'
import { isBlank } from './isBlank'
import { adaptRuntime, ensureSpine, SPINE_MISSING } from './spineRuntime'
import { prefetchMod } from '../../lib/prefetch'
import { assetUrl, defaultPlayback, pickSpineFiles } from '../../lib/spine'

declare const spine: any

export interface Clip { name: string; duration: number }

export interface Hooks extends SessionHooks {
  ready(clips: Clip[]): void
  error(message: string): void
  /** The playing clip changed (a single clip name, or null while a sequence plays). */
  animation(name: string | null): void
}

export interface LoadTarget { folder_path: string; files: string[] }

export class SpineController {
  player: SpinePlayer | null = null
  follow = true
  speed = 1
  loop = true
  paused = false
  hidden = new Set<string>()
  current: string | null = null

  private view: CameraView = { frame: { x: 0, y: 0, zoom: 1 }, zoomScale: 1, panX: 0, panY: 0 }
  /** The Fit of dating scenes (see fitCamera.ts); the viewer switches it through `fit.enabled` and `fit.snap`. */
  readonly fit = new FitCamera({
    view: this.view,
    player: () => this.player,
    stage: () => this.stage,
    generation: () => this.generation,
    phase: () => this.sim.phase,
    hotspots: () => this.sim.hotspots,
    rules: () => this.sim.rules,
    animationNames: () => this.animationNames,
    dragging: () => this.sim.dragging,
    applyCamera: (camera) => this.applyCamera(camera),
    reframe: () => this.reframe(),
  })
  private ticks = 0
  private generation = 0
  private pending: SpinePlayer | null = null
  private stage: HTMLElement | undefined

  /** The touch simulation of a dating scene (see datingSession.ts). */
  readonly sim: DatingSession

  constructor(private hooks: Hooks) {
    this.sim = new DatingSession({
      player: () => this.player,
      animationNames: () => this.animationNames,
      current: () => this.current,
      paused: () => this.paused,
      wake: () => { this.paused = false; this.player!.paused = false; this.player!.play?.() },
      expectNewPhase: () => this.fit.expectNewPhase(),
      playIdle: (name) => this.play(name),
      motionPlaying: (name) => { this.player!.animationState.timeScale = this.speed; this.current = name; this.hooks.animation(name) },
    }, hooks)
  }

  get zoomPercent(): number {
    return Math.round(this.view.zoomScale * 100)
  }

  get clips(): Clip[] {
    return (this.player?.skeleton?.data?.animations ?? []).map((a) => ({ name: a.name, duration: a.duration }))
  }

  dispose(): void {
    this.generation++
    try {
      this.player?.dispose?.()
    } catch (e) {
      console.warn('Spine dispose failed (ignored):', e)
    }
    try {
      this.pending?.dispose?.() // a player still loading has no `success` yet: release its WebGL context here
    } catch (e) {
      console.warn('Spine dispose failed (ignored):', e)
    }
    this.pending = null
    this.player = null
    this.current = null
    this.sim.dispose()
    if (this.stage) this.stage.innerHTML = ''
  }

  load(stage: HTMLElement, target: LoadTarget, options: { skeleton?: string; premultipliedAlpha: boolean; quiet?: boolean; maxTexture?: number }): void {
    this.dispose()
    this.stage = stage
    this.fit.reset()
    this.followFilter = undefined
    this.resetCamera()
    const generation = this.generation
    const files = pickSpineFiles(target.files, options.skeleton)
    const binary = options.skeleton ? /\.skel(\.bytes)?$/i.test(options.skeleton) : Boolean(files.skeleton)
    const skeletonFile = options.skeleton ?? files.skeleton ?? files.json
    if (typeof spine === 'undefined' || !spine.SpinePlayer) return void ensureSpine().then((ok) => (ok ? this.load(stage, target, options) : this.hooks.error(SPINE_MISSING))) // the player script is missing: fetch it once more, else tell the user what to do
    if (!files.atlas || !skeletonFile) return this.hooks.error(`Missing atlas (${files.atlas ?? 'none'}) or skeleton (${skeletonFile ?? 'none'}).`)

    // options.premultipliedAlpha means the TEXTURES already are premultiplied (the PMA toggle); otherwise convert them as they upload
    adaptRuntime()
    spine.GLTexture.PREMULTIPLY_ON_UPLOAD = !options.premultipliedAlpha
    prefetchMod(target, options.maxTexture) // fetch the files in parallel right away; the player would load them one after another
    const rawDataURIs: Record<string, string> = {}
    // The player looks a texture up by the path it builds from the atlas URL (folder URL + page name), so that is the key to override.
    const base = assetUrl(target.folder_path, '')
    for (const png of files.pngs) rawDataURIs[png] = rawDataURIs[png.replace(/\.png$/i, '')] = assetUrl(target.folder_path, png, options.maxTexture)
    if (options.maxTexture) for (const png of files.pngs) rawDataURIs[base + png] = assetUrl(target.folder_path, png, options.maxTexture)
    const config: Record<string, unknown> = {
      atlasUrl: assetUrl(target.folder_path, files.atlas, options.maxTexture),
      rawDataURIs,
      alpha: true,
      backgroundColor: '#00000000',
      showControls: false,
      showLoading: !options.quiet, // off-screen renders: no spinner and logo fading over the first frame
      preserveDrawingBuffer: true,
      premultipliedAlpha: true, // the pipeline is always premultiplied; straight-alpha textures are premultiplied on upload (see PREMULTIPLY_ON_UPLOAD)
      viewport: { padLeft: 0, padRight: 0, padTop: 50, padBottom: 50, transitionTime: 0, animations: {} },
      update: (p: SpinePlayer, delta: number) => this.updateCamera(p, delta),
      success: (p: SpinePlayer) => {
        if (generation !== this.generation) return p.dispose?.()
        this.pending = null
        this.player = p
        p.config.showLoading = false // the loading logo fades out over the first seconds, drawn on top of the picture and with its own camera
        ;(stage as any).__player = p // debugging and e2e profiling (e2e/profile-viewer.mjs)
        ;(stage as any).__controller = this
        p.animationState.data.defaultMix = 0
        const clips = this.clips
        this.sim.loaded()
        this.fit.loaded()
        this.hooks.ready(clips)
        if (!clips.length) this.hooks.error('No animation clips in this skeleton.')
      },
      error: (failed: any, reason: unknown) => {
        if (generation !== this.generation) return
        try { failed?.dispose?.() } catch { /* a player that failed to load may be half built */ }
        if (binary && files.json && config.binaryUrl) {
          // The binary skeleton failed to parse: retry once with the JSON skeleton.
          delete config.binaryUrl
          config.jsonUrl = assetUrl(target.folder_path, files.json)
          stage.innerHTML = ''
          try { this.pending = new spine.SpinePlayer(stage, config) } catch (e) { this.hooks.error(String(e)) }
          return
        }
        this.hooks.error(String(reason))
      },
    }
    if (binary) config.binaryUrl = assetUrl(target.folder_path, skeletonFile)
    else config.jsonUrl = assetUrl(target.folder_path, skeletonFile)
    try {
      this.pending = new spine.SpinePlayer(stage, config)
    } catch (e) {
      this.hooks.error(String(e))
    }
  }

  // ---- playback ---------------------------------------------------------------------------------------------

  play(name: string): void {
    const p = this.player
    if (!p) return
    this.paused = false
    p.paused = false
    p.play?.()
    p.animationState.data.defaultMix = 0
    p.skeleton.setToSetupPose()
    p.animationState.clearTracks() // drops any reaction layered over the previous clip
    this.sim.clearLayers()
    p.animationState.setAnimation(0, name, this.loop)
    p.animationState.timeScale = this.speed
    p.animationState.apply(p.skeleton)
    p.skeleton.updateWorldTransform()
    this.current = name
    this.hooks.animation(name)
    this.reframeSoon()
  }

  /** Cut clips play once in order and the last one loops. */
  playSequence(clips: string[]): void {
    const p = this.player
    if (!p || !clips.length) return
    this.paused = false
    p.paused = false
    p.play?.()
    p.animationState.data.defaultMix = 0
    p.skeleton.setToSetupPose()
    const state = p.animationState
    state.clearTracks()
    state.setAnimation(0, clips[0], clips.length === 1 ? this.loop : false)
    clips.slice(1, -1).forEach((clip) => state.addAnimation(0, clip, false, 0))
    if (clips.length > 1) state.addAnimation(0, clips[clips.length - 1], true, 0)
    state.timeScale = this.speed
    state.apply(p.skeleton)
    p.skeleton.updateWorldTransform()
    this.current = clips[0]
    this.hooks.animation(null)
    this.reframeSoon()
  }

  togglePause(): boolean {
    const p = this.player
    if (!p) return this.paused
    this.paused = !this.paused
    p.paused = this.paused
    if (this.paused) p.pause?.()
    else p.play?.()
    p.animationState.timeScale = this.paused ? 0 : this.speed
    return this.paused
  }

  setSpeed(speed: number): void {
    this.speed = speed
    if (this.player && !this.paused) this.player.animationState.timeScale = speed
  }

  setLoop(loop: boolean): void {
    this.loop = loop
    const track = this.player?.animationState?.getCurrent(0)
    if (track) track.loop = loop
  }

  /** Click on the character: play its reaction clip once, then go back to the idle clip. */
  playMotionOnce(): boolean {
    const p = this.player
    if (!p || p.paused) return false
    const state = p.animationState
    const current = state.getCurrent(0)
    if (!current?.animation || !isIdleAnimationName(current.animation.name) || current.next) return false
    const motion = findMotionAnimation(this.clips.map((c) => c.name))
    if (!motion) return false
    const idle = current.animation.name
    const duration = state.data.skeletonData.findAnimation(motion)?.duration ?? 0
    const entry = state.setAnimation(0, motion, false)
    state.addAnimation(0, idle, true, duration)
    this.current = motion
    this.hooks.animation(motion)
    if (entry) entry.listener = { complete: () => { this.current = idle; this.hooks.animation(idle) } }
    return true
  }

  // ---- layers -----------------------------------------------------------------------------------------------

  setLayerHidden(name: string, hidden: boolean): void {
    if (hidden) this.hidden.add(name)
    else this.hidden.delete(name)
    setSlotHidden(this.player?.skeleton?.findSlot?.(name), hidden)
  }

  // ---- camera -----------------------------------------------------------------------------------------------

  private resetCamera(): void {
    this.view.zoomScale = 1
    this.view.panX = this.view.panY = 0
  }

  private get animationNames(): string[] {
    return this.clips.map((c) => c.name)
  }

  resetView(): void {
    this.resetCamera()
    this.reframe()
  }

  /** Frame the character: centre it and fit it as large as the view allows (see lib/framing.ts for what counts as the subject). */
  reframe(): void {
    const p = this.player
    const camera = p?.sceneRenderer?.camera
    if (!camera) return
    p.skeleton.updateWorldTransform()
    const rect = subjectRect(attachmentBoxes(p.skeleton))
    if (!rect) return
    const center = rectCenter(rect)
    this.view.frame = { x: center.x, y: center.y, zoom: fitRect(rect, camera.viewportWidth, camera.viewportHeight) }
    this.followFilter = undefined // the filter starts again from the new frame
    this.applyCamera(camera)
    p.drawFrame?.(false)
  }

  /** The pose at t=0 is not representative, so frame again once a few frames have run (the Fit of dating scenes does it its own way). */
  private reframeSoon(): void {
    this.fit.reframeSoon(this.sim.interact)
  }

  /** Frame the scene again (the Fit button was switched). */
  refit(): void {
    this.fit.refit(this.sim.interact)
  }

  private followFilter: FollowFilter | undefined
  private followDt = 0

  toggleFollow(): boolean {
    this.follow = !this.follow
    if (this.follow) this.reframe()
    return this.follow
  }

  private applyCamera(camera: SpineCamera): void {
    const zoom = this.view.frame.zoom / this.view.zoomScale
    camera.position.x = this.view.frame.x + this.view.panX * zoom
    camera.position.y = this.view.frame.y + this.view.panY * zoom
    camera.zoom = zoom
    camera.update()
  }

  private updateCamera(p: SpinePlayer, delta: number): void {
    const camera = p?.sceneRenderer?.camera
    // Animations keep resetting slot colours, so hidden layers are re-applied every frame.
    for (const name of this.hidden) setSlotHidden(p.skeleton?.findSlot?.(name), true)
    this.sim.update(p, delta)
    keepIdleAttachments(p)
    if (!camera) return
    if (this.fit.probing) return this.applyCamera(camera) // filledRect is drawing a probe frame at its own camera
    this.followDt += delta || 0.016
    if (this.follow && p.skeleton && ++this.ticks % 2 === 0) {
      const rect = subjectRect(attachmentBoxes(p.skeleton))
      if (rect) {
        const c = rectCenter(rect), dt = this.followDt
        const step = followFilterStep(this.followFilter, this.view.frame, { x: c.x, y: c.y, zoom: fitRect(rect, camera.viewportWidth, camera.viewportHeight) }, camera.viewportHeight * this.view.frame.zoom, dt)
        this.followFilter = step.filter
        this.view.frame.x = step.camera.x
        this.view.frame.y = step.camera.y
        this.view.frame.zoom = step.camera.zoom
      }
      this.followDt = 0
    }
    this.fit.advance(delta || 0.016)
    this.applyCamera(camera)
    if (this.stage) this.sim.draw(this.stage, camera)
  }

  /** Wheel zooms, drag pans 1:1 in screen pixels, a click on the character plays its motion. Returns the cleanup. */
  attachInteraction(node: HTMLElement, onZoom: () => void): () => void {
    let dragging = false, moved = false, startX = 0, startY = 0, lastX = 0, lastY = 0
    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      const before = this.view.frame.zoom / this.view.zoomScale
      this.view.zoomScale = Math.max(0.05, Math.min(this.view.zoomScale * (e.deltaY < 0 ? 1.15 : 0.87), 35))
      // Keep the world point under the cursor fixed: shift the pan by the cursor's offset from the view centre.
      const box = node.querySelector('canvas')?.getBoundingClientRect() ?? node.getBoundingClientRect()
      const after = this.view.frame.zoom / this.view.zoomScale
      this.view.panX += (e.clientX - (box.left + box.width / 2)) * (before - after) / after
      this.view.panY -= (e.clientY - (box.top + box.height / 2)) * (before - after) / after
      onZoom()
    }
    const onDown = (e: MouseEvent) => {
      if (e.button !== 0 || this.sim.pointerDown(e.clientX, e.clientY, e.shiftKey, node)) return
      dragging = true; moved = false
      startX = lastX = e.clientX; startY = lastY = e.clientY
    }
    const onMove = (e: MouseEvent) => {
      if (this.sim.pointerMove(e.clientX, e.clientY, e.shiftKey, node) || !dragging) return
      this.view.panX -= e.clientX - lastX
      this.view.panY += e.clientY - lastY
      lastX = e.clientX; lastY = e.clientY
      if (Math.hypot(e.clientX - startX, e.clientY - startY) > 6) moved = true
    }
    const onUp = (e: MouseEvent) => {
      if (this.sim.pointerUp() || !dragging) return
      dragging = false
      const canvas = node.querySelector('canvas')
      const p = this.player
      if (moved || !canvas || !p) return
      const world = screenToWorld(p.sceneRenderer?.camera, canvas.getBoundingClientRect(), e.clientX, e.clientY)
      if (!this.sim.hotspots.length && world && hitsSkeleton(p.skeleton, this.hidden, world.x, world.y)) this.playMotionOnce()
    }
    node.addEventListener('wheel', onWheel, { passive: false })
    node.addEventListener('mousedown', onDown)
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
    return () => {
      node.removeEventListener('wheel', onWheel)
      node.removeEventListener('mousedown', onDown)
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
  }

  /**
   * PNG of the loaded mod's second animation frame (the first is sometimes broken), framed on the character. `crop` keeps only
   * the upper part (idle sprites are full body). The player must be loaded; it is frozen afterwards.
   */
  async portrait(crop: boolean, keep: number, at = 1 / 30): Promise<Blob | null> {
    const p = this.player, camera = p?.sceneRenderer?.camera
    if (!p || !camera) return null
    const names = this.clips.map((c) => c.name)
    const choice = defaultPlayback(names)
    if (!choice.animation && !choice.sequence.length) return null
    this.follow = false
    if (choice.sequence.length) {
      // A cutscene builds its picture in its intro clips (the loop alone is mostly empty): run them, then take the frame after the loop starts.
      this.playSequence(choice.sequence)
      const intro = choice.sequence.slice(0, -1).reduce((sum, n) => sum + (p.skeleton.data.findAnimation(n)?.duration ?? 0), 0)
      for (let t = 0; t < intro; t += 1 / 30) p.animationState.update(1 / 30)
      p.animationState.update(at)
    } else {
      this.play(choice.animation!)
      p.animationState.update(at)
    }
    // Scenes that fade in or reveal their picture later are blank on the second frame: keep advancing until something is drawn.
    for (const step of [0, 0.5, 1, 2]) {
      if (step) p.animationState.update(step)
      p.animationState.apply(p.skeleton)
      p.skeleton.updateWorldTransform()
      let rect = subjectRect(mainCluster(attachmentBoxes(p.skeleton)))
      if (!rect) continue
      if (crop) rect = { ...rect, minY: rect.maxY - (rect.maxY - rect.minY) * keep }
      const center = rectCenter(rect)
      this.view.frame = { x: center.x, y: center.y, zoom: fitRect(rect, camera.viewportWidth, camera.viewportHeight, 0.06) }
      this.applyCamera(camera)
      p.paused = true
      p.drawFrame?.(false)
      if (!isBlank(p.canvas as HTMLCanvasElement)) return new Promise((resolve) => (p.canvas as HTMLCanvasElement).toBlob(resolve, 'image/png'))
      p.paused = false
    }
    return null
  }

  /** What the player shows right now, as a 4:5 window in the middle of the view (320x400): the user pans, zooms and pauses first. */
  async captureFrame(): Promise<Blob | null> {
    const p = this.player, camera = p?.sceneRenderer?.camera
    if (!p || !camera) return null
    const canvas = p.canvas as HTMLCanvasElement
    p.drawFrame?.(false)
    const vw = camera.viewportWidth, vh = camera.viewportHeight
    const width = Math.min(vw, vh * 0.8)
    const ratio = canvas.width / vw
    const out = document.createElement('canvas')
    out.width = 320
    out.height = 400
    out.getContext('2d')?.drawImage(canvas, ((vw - width) / 2) * ratio, 0, width * ratio, canvas.height, 0, 0, 320, 400)
    return new Promise((resolve) => out.toBlob(resolve, 'image/png'))
  }

  snapshot(fileName: string): void {
    const canvas = this.player?.canvas as HTMLCanvasElement | undefined
    if (!canvas) return
    this.player?.drawFrame?.(false)
    canvas.toBlob((blob) => {
      if (!blob) return
      const link = document.createElement('a')
      link.href = URL.createObjectURL(blob)
      link.download = `${fileName.replace(/[^a-zA-Z0-9_-]/g, '_')}_snapshot.png`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      setTimeout(() => URL.revokeObjectURL(link.href), 2000)
    }, 'image/png')
  }
}
