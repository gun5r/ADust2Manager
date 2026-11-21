/**
 * The touch simulation of a dating scene on top of a loaded Spine player: which phase is live, the tool in use, the spots, what a press
 * plays and where an action leads, the score gauge, the drags, the markers and the touch guide. The controller owns the player and the
 * camera and hands it over through `SessionHost`; the viewer hears about it through `SessionHooks` (events) and `SimState` (a snapshot
 * published whenever one of its fields changes).
 */
import { screenToWorld } from '../../lib/hit'
import { isIdleAnimationName } from '../../lib/follow'
import { clampOffset, reachedDestination, springBack } from '../../lib/dragFollow'
import { attachRules, chooseReaction, dragGoal, dragTravel, longPressStage, phaseAfter, FIXED_RADIUS, hotspotAt, idleFor, parseHotspots, phasesOf, type Hotspot, type SceneRules, type SpotRule, type TapState } from '../../lib/dating'
import { afterClick, autoStep, crossed, startScore, usable, type GaugeRule } from '../../lib/gauge'
import { DragDirections } from './dragDirections'
import type { SpineBone, SpineCamera, SpinePlayer, SpineTrackEntry } from './spineTypes'
import { SceneGuide } from './sceneGuide'
import { GuideMarker, SpotMarkers, type GuideStyle } from './spotMarkers'

/** What the viewer mirrors from the session besides the events: it changes rarely, so it is published as a whole. */
export interface SimState {
  tool: number
  /** The phase's score gauge (null: none). */
  gauge: { score: number; max: number } | null
  /** What the guide wants pressed instead of a spot: a tool button (its id) or tilt buttons (the ids of their gyro spots). */
  guideTool: number | null
  guideTilts: number[]
}

export interface SessionHooks {
  /** A spot started a reaction clip: its sounds should play now. */
  reaction?(animation: string, spot: Hotspot, kind: 'tap' | 'press' | 'release'): void
  /** A spot's animation ended early (let go, interrupted, replaced): the sounds it started should end. */
  released?(spot: Hotspot): void
  /** The scene moved to another phase by itself (a spot's action ended with a state change). */
  phase?(phase: number): void
  state?(state: SimState): void
}

/** What the session needs from the controller that owns the player. */
export interface SessionHost {
  player(): SpinePlayer | null
  animationNames(): string[]
  current(): string | null
  paused(): boolean
  /** Make sure the player runs (a touch wakes a paused one). */
  wake(): void
  /** The camera of a phase is not known yet: its first frame is hidden until it is fitted. */
  expectNewPhase(): void
  /** Play a clip on the main track (the idle of a phase). */
  playIdle(name: string): void
  /** A scene-ending motion is now the clip on the main track. */
  motionPlaying(name: string): void
}

interface SpotHandle { track: number; entry: SpineTrackEntry; spot: Hotspot; timer?: ReturnType<typeof setTimeout>; held?: boolean; done?: boolean; down?: boolean }

/** A spot whose bone follows the finger (drags, and touch-follow spots) until it springs back after release. */
interface DragState { handle: SpotHandle; bone: SpineBone; pointer: { x: number; y: number }; origin: { x: number; y: number }; dx: number; dy: number; max: number; returning: boolean }

/** How long a spot's layer stays when the spot it brought in is pressed, so what it shows does not blink out before the new clip shows it. */
const HANDOVER_MS = 300

export class DatingSession {
  hotspots: Hotspot[] = []
  interact = false
  phase = 1
  tool = 0
  rules: SceneRules | null = null

  /** Markers: shown at all, only while the scene idles, numbered areas or small dots, every zone one small fixed circle, only the one under the pointer. */
  spotsOn = true
  spotsIdle = false
  spotStyle: 'numbers' | 'dots' | 'plain' = 'numbers'
  spotsFixed = false
  spotsHover = false
  /** Size of the game's zones (not the fixed ones) as a share, how opaque the markers are, and whether they hide what is behind them. */
  spotScale = 1
  spotOpacity = 1
  spotsSolid = false
  /** The touch guide (a circle over the next spot to touch; off while the phase has a score gauge). */
  guide: GuideStyle = 'off'
  hitRadius = 80

  /** `locked`: the scene-ending action is running (its clip, then the motion): the spots are gone and presses do nothing until the next phase starts. */
  private action: 'open' | 'locked' = 'open'
  private taps = new Map<string, TapState>()
  /** Staged long presses (Yuri's spot 1: 20 stages): the stage the next hold of a spot starts with. */
  private stages = new Map<string, number>()
  private drag: DragState | null = null
  /** The spot being pressed right now (its release is still to come). */
  private grabbed: SpotHandle | null = null
  /** Tracks whose clip ended with the spot bones displaced (hidden spots revealed): the game keeps that pose. */
  private heldTracks = new Set<number>()
  /** Which spot's clip is on a reaction track (to end its sounds when another spot takes over). */
  private spotOnTrack = new Map<number, Hotspot>()
  private gaugeRule: GaugeRule | null = null
  private score = 0
  private chains = new Map<string, ReturnType<typeof setTimeout>>()
  private handovers = new Set<ReturnType<typeof setTimeout>>()
  private poseCache = new Map<string, 'hold' | 'reset' | 'none'>()
  private toolSets = new Map<string, Set<number>>()
  private markers = new SpotMarkers()
  private guideMarker = new GuideMarker()
  private sceneGuide: SceneGuide
  private dragDirections = new DragDirections()
  /** The spot a press at the pointer would trigger (highlighted, so overlapping zones are not a guess). */
  private hover: string | null = null
  private altDepth = 0
  private published: SimState | null = null
  private guideTool: number | null = null
  private guideTilts: number[] = []

  constructor(private host: SessionHost, private hooks: SessionHooks) {
    this.sceneGuide = new SceneGuide({ player: () => host.player(), hotspots: () => this.hotspots, animations: () => host.animationNames() })
  }

  private get player(): SpinePlayer | null { return this.host.player() }

  /** The player, for the work that only makes sense with one loaded. */
  private get live(): SpinePlayer {
    const player = this.host.player()
    if (!player) throw new Error('No player is loaded')
    return player
  }

  /** Whether presses reach the spots. */
  get canTouch(): boolean { return this.action === 'open' }

  get dragging(): boolean { return !!this.drag }

  // ---- loading ------------------------------------------------------------------------------------------------

  /** The skeleton is ready: read its spots (matched against the game's rules when they are known). */
  loaded(): void {
    this.loadedSpots()
    this.taps.clear()
    this.stages.clear()
  }

  /** The player is going away (a new load, or the viewer closed). */
  dispose(): void {
    for (const t of [...this.chains.values(), ...this.handovers]) clearTimeout(t)
    this.chains.clear()
    this.handovers.clear()
    this.action = 'open'
    this.grabbed = null
    this.markers = new SpotMarkers() // the old overlay went with the stage
    this.guideMarker = new GuideMarker()
    this.sceneGuide.reset()
    this.hotspots = []
  }

  /** The game's rules for the scene on screen (loaded after the skeleton): re-match every spot against them. */
  setRules(rules: SceneRules | null): void {
    this.rules = rules
    this.toolSets.clear()
    this.resetGauge()
    this.sceneGuide.reset()
    if (!this.player) return
    this.dragDirections.clear()
    this.loadedSpots()
    if (this.interact) this.setTool(this.defaultTool()) // the rules arrive after the first frame: the phase's first tool (and its skin) was not known yet
  }

  /** Read the spots of the skeleton, matched against the rules. */
  private loadedSpots(): void {
    const names = this.host.animationNames()
    this.hotspots = attachRules(parseHotspots(this.live.skeleton.data.bones.map((b) => b.name), names), this.rules, names)
  }

  /** The main clip was replaced by another (a clip picked from the list): whatever a spot had layered or dragged is dropped. */
  clearLayers(): void {
    this.endDrag(true)
    this.heldTracks.clear()
  }

  // ---- phases and tools -----------------------------------------------------------------------------------------

  setInteract(on: boolean): void {
    this.interact = on
    if (on) this.setPhase(this.phase)
  }

  /** Phase = which idle pose is shown and which spots are live. */
  setPhase(phase: number): void {
    this.phase = phase
    const idle = idleFor(phase, this.host.animationNames())
    if (this.interact && idle) {
      this.host.expectNewPhase()
      this.host.playIdle(idle)
      const group = this.rules?.groups.find((g) => g.group === phase)
      if (group?.switch && this.host.animationNames().includes(group.switch)) { // the transition clip into this phase, then its idle
        const state = this.live.animationState
        state.setAnimation(0, group.switch, false)
        state.addAnimation(0, idle, true, 0)
      }
    }
    this.action = 'open'
    this.setTool(this.defaultTool())
    this.resetGauge()
  }

  /** Tilting the phone (the game's gyro spots, which a pointer cannot do): the one asked for, else the one the guide points at, else the phase's first. */
  tilt(id?: number): void {
    const spots = this.allSpots().filter(({ spot }) => spot.kind === 'gyro' && (spot.reactions.length || spot.rule?.motion || spot.rule?.next))
    const chosen = (id !== undefined && spots.find(({ spot }) => (spot.rule?.id ?? spot.id) === id)) || this.sceneGuide.target(this.phase, spots, () => true) || spots.find(({ spot }) => spot.rule?.next) || spots[0]
    if (!chosen || !this.canTouch) return
    if (!this.toolsOf(chosen.spot).has(this.tool)) this.setTool(chosen.spot.rule?.tool ?? 0) // the phone can be tilted with any tool in hand
    const handle = this.react(chosen.spot)
    if (handle) this.release(handle)
  }

  /** The hand, or the first tool of the phase when the hand is not one of its tools (some phases only have spots for a tool). */
  private defaultTool(): number {
    const ids = this.rules?.groups.find((g) => g.group === this.phase)?.tools?.map((t) => t.id) ?? []
    return !ids.length || ids.includes(0) ? 0 : ids[0]
  }

  /** Pick the tool of the phase: its skin is applied, and only spots of that tool can be used. */
  setTool(id: number): void {
    this.tool = id
    this.publish()
    const p = this.player
    const group = this.rules?.groups.find((g) => g.group === this.phase)
    const skin = group?.tools?.find((t) => t.id === id)?.skin
    const data = p?.skeleton?.data
    if (p && data && skin && data.findSkin(skin)) {
      p.skeleton.setSkinByName(skin)
      p.skeleton.setSlotsToSetupPose()
      p.animationState.apply(p.skeleton)
    }
  }

  // ---- gauge ---------------------------------------------------------------------------------------------------

  private resetGauge(): void {
    const g = this.rules?.groups.find((x) => x.group === this.phase)?.gauge
    this.gaugeRule = g?.on ? g : null
    this.score = this.gaugeRule ? startScore(this.gaugeRule) : 0
    this.publish()
  }

  /** Move the score (a click, or the gauge's own change), play the motions it crossed, and tell the viewer. */
  private setScore(next: number, spot?: Hotspot): void {
    const g = this.gaugeRule
    if (!g || next === this.score) return
    const before = this.score
    this.score = next
    for (const m of crossed(before, next, g.motions)) {
      if (!this.host.animationNames().includes(m.MixAnimationName)) continue
      const from = spot ?? { bone: 'gauge', phase: this.phase, id: 0, kind: 'touch', reactions: [m.MixAnimationName] } as Hotspot
      this.play1(8, m.MixAnimationName, from, 'tap')
      this.live.animationState.addEmptyAnimation(8, 0.15, 0)
    }
    this.publish()
  }

  /** Tell the viewer when one of the mirrored values changed (the gauge counts whole points). */
  private publish(): void {
    const gauge = this.gaugeRule ? { score: this.score, max: this.gaugeRule.min.y } : null
    const next: SimState = { tool: this.tool, gauge, guideTool: this.guideTool, guideTilts: this.guideTilts }
    const was = this.published
    if (was && was.tool === next.tool && was.guideTool === next.guideTool && was.guideTilts.join() === next.guideTilts.join() && Math.floor(was.gauge?.score ?? -1) === Math.floor(gauge?.score ?? -1) && !was.gauge === !gauge) return
    this.hooks.state?.((this.published = next))
  }

  // ---- spots ---------------------------------------------------------------------------------------------------

  /** Whether a spot can be used now: it belongs to the tool in use, and the score is inside its gauge range. */
  private spotActive(spot: Hotspot): boolean {
    const rule = spot.rule
    if (!rule) return true
    if (!this.toolsOf(spot).has(this.tool)) return false
    return !this.gaugeRule || usable(rule.gauge, this.score)
  }

  /** The tools a spot exists for: variants of one spot share its phase and id (`point1_5_touch`, `point1_5_touch_tool21`). */
  private toolsOf(spot: Hotspot): Set<number> {
    const id = spot.rule?.id ?? spot.id // a gyro bone's name says 0, the game's rule has its real id (Eclipse's point3_0_gyro is spot 22)
    const key = `${spot.phase}_${id}`
    let set = this.toolSets.get(key)
    if (!set) {
      set = new Set((this.rules?.spots ?? []).filter((r) => r.phase === spot.phase && r.id === id).map((r) => r.tool ?? 0))
      if (!set.size) set.add(0)
      this.toolSets.set(key, set)
    }
    return set
  }

  private place(spots: Hotspot[]) {
    const skeleton = this.player?.skeleton
    if (!skeleton) return []
    return spots.flatMap((spot) => {
      const bone = skeleton.findBone(spot.bone)
      return bone ? [{ spot, x: bone.worldX as number, y: bone.worldY as number }] : []
    })
  }

  /** The spots of the current phase a press can trigger now, with their position in world units (bone origin). */
  private usableSpots() {
    return this.place(this.hotspots.filter((h) => h.phase === this.phase && h.kind !== 'gyro' && this.spotActive(h)))
  }

  /** Every spot of the current phase whatever the tool, gyro spots included (what the guide and the tilt buttons work with). */
  private allSpots() {
    return this.place(this.hotspots.filter((h) => h.phase === this.phase))
  }

  /** World position of a screen point (the finger), for dragging; the origin when the camera is not ready. */
  private worldAt(clientX: number, clientY: number, node: HTMLElement): { x: number; y: number } {
    const canvas = node.querySelector('canvas')
    return (canvas && screenToWorld(this.player?.sceneRenderer?.camera, canvas.getBoundingClientRect(), clientX, clientY)) || { x: 0, y: 0 }
  }

  /** The spot under the pointer; `skip` > 0 picks one of the spots behind it (Shift+click through overlapping zones). */
  private spotAt(clientX: number, clientY: number, node: HTMLElement, skip = 0): Hotspot | null {
    const canvas = node.querySelector('canvas')
    const world = canvas && screenToWorld(this.player?.sceneRenderer?.camera, canvas.getBoundingClientRect(), clientX, clientY)
    return world ? hotspotAt(this.usableSpots(), world.x, world.y, this.hitRadius, skip, this.spotsFixed ? FIXED_RADIUS : 0, this.spotScale) : null
  }

  // ---- pointer ---------------------------------------------------------------------------------------------------

  /** A press on the stage: true when a spot took it (the controller then does not pan). */
  pointerDown(clientX: number, clientY: number, shift: boolean, node: HTMLElement): boolean {
    if (this.grabbed) { // a press while another spot is still held (the release was missed): that one ends first
      if (!this.grabbed.done) this.release(this.grabbed)
      this.grabbed = null
    }
    if (!this.interact || !this.hotspots.length || !this.canTouch) return false
    // Shift+click goes to the next spot under the pointer: overlapping zones would otherwise hide some spots
    const spot = this.spotAt(clientX, clientY, node, shift ? ++this.altDepth : (this.altDepth = 0))
    if (!spot) return false
    const handle = this.react(spot)
    if (handle) {
      this.grabbed = handle
      if (spot.kind === 'drag' || spot.kind === 'follow') this.beginDrag(handle, this.worldAt(clientX, clientY, node))
    }
    return true
  }

  /** The pointer moved: true while a spot is held (the controller then does not pan). */
  pointerMove(clientX: number, clientY: number, shift: boolean, node: HTMLElement): boolean {
    if (this.interact && this.hotspots.length && !this.grabbed && this.canTouch) this.hover = this.spotAt(clientX, clientY, node, shift ? this.altDepth + 1 : 0)?.bone ?? null
    if (!this.grabbed) return false
    if (!this.grabbed.done) this.moveDrag(this.worldAt(clientX, clientY, node))
    return true
  }

  /** The pointer was let go: true when it ended the press of a spot. */
  pointerUp(): boolean {
    if (!this.grabbed) return false
    if (!this.grabbed.done) this.release(this.grabbed) // the rest of the reaction plays out over the idle, which never stopped
    this.grabbed = null
    return true
  }

  // ---- reactions -------------------------------------------------------------------------------------------------

  private play1(track: number, animation: string, spot: Hotspot, kind: 'tap' | 'press' | 'release', loop = false): SpineTrackEntry {
    const entry = this.live.animationState.setAnimation(track, animation, loop)
    this.spotOnTrack.set(track, spot)
    this.hooks.reaction?.(animation, spot, kind)
    return entry
  }

  /**
   * What a clip does to the spot bones (`point*`) by its last frame: `hold` = leaves them displaced (a clip that reveals the
   * hidden spots: the game keeps that pose so they stay usable), `reset` = moves them back, `none` = does not touch them.
   */
  private poseEffect(animation: string): 'hold' | 'reset' | 'none' {
    const cached = this.poseCache.get(animation)
    if (cached) return cached
    let result: 'hold' | 'reset' | 'none' = 'none'
    const data = this.player?.skeleton?.data
    const clip = data?.findAnimation(animation)
    for (const timeline of clip?.timelines ?? []) {
      if (timeline.boneIndex === undefined || !timeline.constructor.name.startsWith('Translate') || !/^point/i.test(data!.bones[timeline.boneIndex].name)) continue
      const step = timeline.getFrameEntries!(), frames = timeline.frames, last = frames.length - step
      const displaced = [...frames.slice(last + 1, last + step)].some((v) => Math.abs(v) > 1)
      if (displaced) { result = 'hold'; break }
      result = 'reset'
    }
    this.poseCache.set(animation, result)
    return result
  }

  /** Fade a spot's layer out (its sounds end with it). When the spot being pressed was brought in by it (Teresse 29 -> 36) the layer stays a moment. */
  private endTrack(track: number, mix: number, successor?: Hotspot): void {
    const state = this.player?.animationState, current = state?.getCurrent(track), spot = this.spotOnTrack.get(track)
    if (state && successor && spot && this.sceneGuide.reveals(spot.phase, spot.bone, successor.bone)) {
      const timer = setTimeout(() => {
        this.handovers.delete(timer)
        if (state.getCurrent(track) === current) state.setEmptyAnimation(track, mix)
      }, HANDOVER_MS)
      this.handovers.add(timer)
    } else state?.setEmptyAnimation(track, mix)
    if (spot) this.hooks.released?.(spot)
  }

  /** A clip that moves the spot bones replaces the pose another spot left held: every held layer but `keep`'s ends. */
  private releaseHeldExcept(keep: number, successor: Hotspot): void {
    for (const track of this.heldTracks) if (track !== keep) this.endTrack(track, 0.15, successor)
    this.heldTracks.clear()
    this.heldTracks.add(keep)
  }

  /** A clip hides the hidden spots again: every held layer ends. */
  private releaseAllHeld(): void {
    for (const track of this.heldTracks) this.endTrack(track, 0.15)
    this.heldTracks.clear()
  }

  /** The reaction clip of `spot` leads into its motion and, when the rules say so, the next phase: nothing may cut it short now. */
  private endsWith(entry: SpineTrackEntry, spot: Hotspot, lock = true): void {
    if (lock && spot.rule?.next) this.action = 'locked'
    entry.listener = { complete: () => this.afterAction(spot) }
  }

  /**
   * Layer the spot's reaction over the looping idle (reactions only key a part of the skeleton: playing one on the idle's
   * own track would freeze every other bone). Which clip plays follows the game's rules for the spot (see chooseReaction).
   * Returns a handle when the pointer-up still matters (drag, follow, hold, release clip, long press).
   */
  private react(spot: Hotspot): SpotHandle | null {
    const p = this.player
    if (!p) return null
    const key = `${spot.phase}_${spot.id}`
    if (!spot.reactions.length && (spot.rule?.motion || spot.rule?.next)) {
      this.afterAction(spot) // no mix clip in this mod: the game still runs the spot's motion and moves on
      return null
    }
    const chosen = chooseReaction(spot, this.taps.get(key) ?? { taps: 0, lastAt: 0 }, performance.now())
    this.taps.set(key, chosen.state)
    if (this.gaugeRule && chosen.anim) this.setScore(afterClick(this.score, this.gaugeRule, spot.rule?.gauge, chosen.state.taps - 1), spot)
    const rule = spot.rule
    const stageKey = `${spot.phase}_${spot.id}`
    const stage = rule?.longPress ? longPressStage(rule.longPress, this.stages.get(stageKey) ?? 0) : undefined
    const hold = spot.loop ?? stage?.loop
    if (!chosen.anim && !hold) return null
    const state = p.animationState, track = 1 + (spot.id % 8)
    // A run of clicks (Olivier's spot 8: ten clips that fill a meter) is not a press: its end clip plays when the run breaks off early
    const chain = !!rule?.stop && rule.clickMax > 0 && rule.kind === 'touch' && !hold
    this.cancelOtherSpots(track, spot)
    this.host.wake()
    // Whatever kind of spot it is, a clip that moves the spot bones replaces the pose another spot left held (two full poses layered on
    // different tracks fight over the body: Tyr phase 3, spot 9 held, then a drag on spot 2 broke the arms)
    if (this.poseEffect(chosen.anim ?? hold!) !== 'none') this.releaseHeldExcept(track, spot)
    let entry
    if (hold) {
      // Hold style: the start clip (if any), then the held loop until release.
      entry = chosen.anim ? this.play1(track, chosen.anim, spot, 'press') : this.play1(track, hold, spot, 'press', true)
      if (chosen.anim) state.addAnimation(track, hold, true, 0)
    } else if (spot.kind === 'drag') {
      // The press clip plays normally and its last frame stays while the finger is down (the release clip follows).
      entry = this.play1(track, chosen.anim!, spot, 'press')
      this.heldTracks.delete(track)
    } else {
      entry = this.play1(track, chosen.anim!, spot, rule?.stop && !chain ? 'press' : 'tap')
      const effect = this.poseEffect(chosen.anim!)
      if (effect === 'hold') this.releaseHeldExcept(track, spot) // the pose stays (hidden spots stay revealed) until another state replaces it
      else {
        state.addEmptyAnimation(track, 0.15, 0)
        this.heldTracks.delete(track)
        if (effect === 'reset') this.releaseAllHeld()
      }
      if (!rule?.stop && (rule?.motion || rule?.next)) this.endsWith(entry, spot, !rule.longPress)
    }
    if (chain) {
      clearTimeout(this.chains.get(key))
      const taps = this.taps.get(key)!.taps
      if (taps >= rule!.clickMax && (rule!.motion || rule!.next)) { // the run is complete: its last clip ends the action (motion, next phase)
        this.endsWith(entry, spot)
        return null
      }
      this.chains.set(key, setTimeout(() => {
        this.chains.delete(key)
        if (taps >= rule!.clickMax) return // a full run stays as it is (the clips it revealed stay revealed)
        this.play1(track, rule!.stop!, spot, 'tap')
        state.addEmptyAnimation(track, 0.15, 0)
      }, (rule!.clickReset || 1) * 1000))
    }
    const handle: SpotHandle = { track, entry, spot, down: true }
    const press = rule?.longPress
    if (press?.success.length && press.threshold > 0) {
      // Held long enough: the long-press clip takes over.
      handle.timer = setTimeout(() => { handle.timer = undefined; handle.held = true; this.runStage(handle, stageKey, press, stage!.index) }, press.threshold * 1000)
    }
    return spot.kind === 'drag' || spot.kind === 'follow' || hold || (rule?.stop && !chain) || handle.timer ? handle : null
  }

  /** A spot was pressed: the reactions of the other spots end (the game plays one touch reaction at a time), but a held pose stays. */
  private cancelOtherSpots(track: number, pressed: Hotspot): void {
    const state = this.player?.animationState
    if (!state) return
    for (let t = 1; t <= 8; t++) {
      if (t === track || this.heldTracks.has(t) || !state.getCurrent(t)) continue
      this.endTrack(t, 0.1, pressed)
    }
  }

  /** The pointer let go: finish what the spot started (release/stop/end clip), spring the bone back, fade the layer out. */
  private release(h: SpotHandle): void {
    const state = this.player?.animationState
    if (!state) return
    if (h.timer) clearTimeout(h.timer)
    h.down = false
    this.hooks.released?.(h.spot) // sounds of the press end now; a release clip's own sounds start below
    this.endDrag(false)
    const { track, spot } = h
    const rule = spot.rule
    if (h.held) return
    if (spot.loop || rule?.longPress?.loop.length) {
      const end = spot.end ?? rule?.stop ?? rule?.longPress?.fail[0]
      if (end) this.play1(track, end, spot, 'release')
      state.addEmptyAnimation(track, 0.15, 0)
    } else if (spot.kind === 'drag') {
      const second = rule?.stop ?? spot.reactions[1]
      if (second) {
        const pressing = h.entry
        const left = pressing?.animation ? pressing.animationEnd - pressing.getAnimationTime() : 0
        // A long press clip (Olivier's runs 16 s) must not outlive the finger: the release clip takes over at once.
        if (left > 1) state.setAnimation(track, second, false)
        else state.addAnimation(track, second, false, 0)
        this.hooks.reaction?.(second, spot, 'release')
      }
      state.addEmptyAnimation(track, 0.15, 0)
    } else if (rule?.stop) {
      this.play1(track, rule.stop, spot, 'release')
      state.addEmptyAnimation(track, 0.15, 0)
    }
  }

  /**
   * One stage of a long press: its success clip plays through in full (a release does not cut it short, so what it brings on screen
   * can still be pressed). A staged press (more than one stage) goes on with the next stage while the pointer is still down; the stage after
   * the last complete one is where the next hold starts.
   */
  private runStage(h: SpotHandle, key: string, press: NonNullable<SpotRule['longPress']>, stage: number): void {
    const state = this.player?.animationState
    const clip = longPressStage(press, stage)
    if (!state || !clip.success) return
    const entry = this.play1(h.track, clip.success, h.spot, 'tap')
    state.addEmptyAnimation(h.track, 0.15, 0)
    if (press.success.length < 2) return
    entry.listener = { complete: () => {
      this.stages.set(key, clip.index + 1)
      if (h.down && !clip.last) this.runStage(h, key, press, clip.index + 1)
    } }
  }

  // ---- bone-follow drags -----------------------------------------------------------------------------------------

  /** Start moving the spot's bone with the finger. Reach is the distance to the destination (scene-ending drags) or a fixed 600. */
  private beginDrag(handle: SpotHandle, pointer: { x: number; y: number }): void {
    const bone = this.player?.skeleton?.findBone(handle.spot.bone)
    if (!bone) return
    this.endDrag(true)
    const origin = { x: bone.worldX as number, y: bone.worldY as number }
    let max = 600
    const dest = dragGoal(handle.spot.rule)
    if (dest && bone.parent) {
      const world = { x: dest[0], y: dest[1] }
      bone.parent.localToWorld(world)
      max = Math.hypot(world.x - origin.x, world.y - origin.y) * 1.1
    }
    this.drag = { handle, bone, pointer, origin, dx: 0, dy: 0, max, returning: false }
  }

  private moveDrag(pointer: { x: number; y: number }): void {
    const drag = this.drag
    if (!drag || drag.returning) return
    const offset = clampOffset(pointer.x - drag.pointer.x, pointer.y - drag.pointer.y, drag.max)
    drag.dx = offset.dx
    drag.dy = offset.dy
  }

  /** Stop following: spring back to rest (or snap, when `immediate`). */
  private endDrag(immediate: boolean): void {
    const drag = this.drag
    if (!drag) return
    if (immediate) {
      drag.bone.setToSetupPose()
      this.player?.skeleton?.updateWorldTransform()
      this.drag = null
    } else drag.returning = true
  }

  /** Every frame, after the animation has been applied: put the dragged bone where the finger is and let the constraints follow. */
  private applyDrag(p: SpinePlayer, delta: number): void {
    const drag = this.drag
    if (!drag || !p.skeleton) return
    if (drag.returning) {
      const next = springBack(drag.dx, drag.dy, delta || 0.016)
      drag.dx = next.dx
      drag.dy = next.dy
      if (next.done) {
        drag.bone.setToSetupPose()
        p.skeleton.updateWorldTransform()
        this.drag = null
        return
      }
    }
    const point = { x: drag.origin.x + drag.dx, y: drag.origin.y + drag.dy }
    const parent = drag.bone.parent
    if (parent) parent.worldToLocal(point)
    drag.bone.x = point.x
    drag.bone.y = point.y
    p.skeleton.updateWorldTransform()
    const rule = drag.handle.spot.rule
    const goal = dragGoal(rule), moving = !drag.returning && goal && (rule?.motion || rule?.next)
    if (moving && reachedDestination([drag.bone.data.x, drag.bone.data.y], goal, [point.x, point.y])) this.completeDrag(drag)
    // a phase-ending drag the game gives no destination for is done as soon as it is pulled far enough: straight to the transition, no release clip
    else if (!drag.returning && !goal && rule?.next && Math.hypot(drag.dx, drag.dy) >= dragTravel(rule)) this.completeDrag(drag)
  }

  /** The point reached its destination: end the press layer cleanly (no frozen leftovers), then the action's motion and next phase. */
  private completeDrag(drag: DragState): void {
    const { handle } = drag
    handle.done = true
    this.hooks.released?.(handle.spot)
    this.player?.animationState?.setEmptyAnimation(handle.track, 0.1)
    drag.returning = true
    this.afterAction(handle.spot)
  }

  /** An action ran its course: play its motion clip (if the scene has it), then move on to the next phase when the rules say so. */
  private afterAction(spot: Hotspot): void {
    const rule = spot.rule, state = this.player?.animationState
    if (!rule || !state) return
    if (rule.next) this.action = 'locked'
    const goNext = () => {
      if (!rule.next) return
      // where the scene goes (see phaseAfter); with nowhere to go the idle takes over again
      const target = phaseAfter(this.rules, spot, phasesOf(this.hotspots))
      if (target === undefined) {
        const idle = idleFor(spot.phase, this.host.animationNames())
        this.action = 'open'
        if (idle) this.host.playIdle(idle)
        return
      }
      this.setPhase(target)
      this.hooks.phase?.(target)
    }
    if (rule.motion && this.host.animationNames().includes(rule.motion)) {
      if (rule.next) {
        // A scene-ending motion replaces the whole pose (it keys about as many bones as the idle): layered over the looping idle on a spare
        // track it only moved part of the body, which left the face and the rest of the pose fighting the idle. Its last frame stays up
        // until the next phase's idle replaces it (fading out first showed the old idle).
        for (let t = 1; t <= 8; t++) state.clearTrack(t)
        this.heldTracks.clear()
        this.player.skeleton.setToSetupPose()
        const entry = this.play1(0, rule.motion, spot, 'tap')
        // Show the clip's first frame now: this can run after the frame's animations were applied, and the frame would otherwise be drawn in the bare setup pose (a one-frame flash)
        state.update(0)
        state.apply(this.player.skeleton)
        this.player.skeleton.updateWorldTransform()
        this.host.motionPlaying(rule.motion)
        entry.listener = { complete: goNext }
        return
      }
      const entry = this.play1(1, rule.motion, spot, 'tap')
      state.addEmptyAnimation(1, 0.15, 0)
      entry.listener = { complete: goNext }
    } else goNext()
  }

  // ---- every frame ---------------------------------------------------------------------------------------------

  /** After the animations were applied: the dragged bone, and the gauge's own change. */
  update(p: SpinePlayer, delta: number): void {
    this.applyDrag(p, delta)
    if (this.gaugeRule && this.interact && !this.host.paused() && delta) this.setScore(autoStep(this.score, this.gaugeRule, delta))
  }

  /** Is anything other than the idle pose playing (a layered reaction, or a non-idle clip picked from the list)? */
  private busy(): boolean {
    const tracks = this.player?.animationState?.tracks ?? []
    return !!this.drag || !isIdleAnimationName(this.host.current()) || tracks.slice(1).some((t) => t?.animation && t.animation.name !== '<empty>' && !t.isComplete?.())
  }

  /** Keep the markers and the guide over the spots of the current phase. */
  draw(stage: HTMLElement, camera: SpineCamera): void {
    if (!(this.spotsOn || this.guide !== 'off' || this.markers.count || this.guideMarker.shown)) return
    const hideDuringReaction = this.spotsIdle && this.busy() // Hide: spots and guide go away together while a reaction plays
    const hidden = !this.interact || !this.spotsOn || !this.canTouch || hideDuringReaction
    const spots = hidden ? [] : this.usableSpots().filter(({ spot }) => !this.spotsHover || spot.bone === this.hover)
    const next = this.interact && this.guide !== 'off' && !this.gaugeRule && this.canTouch && !hideDuringReaction
      ? this.sceneGuide.target(this.phase, this.allSpots(), (spot) => this.toolsOf(spot).has(this.tool)) : null
    // not on the picture: the way on needs another tool, or the phone tilted (their buttons are lit instead)
    const tilts = next?.spot.kind === 'gyro'
    // every tilt that ends the phase is lit (Eclipse's two both lead on), not only the one the guide would pick
    const id = (s: Hotspot) => s.rule?.id ?? s.id
    this.guideTilts = tilts ? this.allSpots().filter(({ spot }) => spot.kind === 'gyro' && spot.rule?.next).map(({ spot }) => id(spot)) : []
    this.guideTool = next && !tilts && !this.toolsOf(next.spot).has(this.tool) ? (next.spot.rule?.tool ?? 0) : null
    this.publish()
    this.guideMarker.draw(stage, camera, next && this.guideTool === null && !tilts ? { bone: next.spot.bone, x: next.x, y: next.y } : null, this.guide)
    this.markers.draw(stage, camera, spots, {
      opacity: this.spotOpacity, solid: this.spotsSolid, hitRadius: this.hitRadius, fixed: this.spotsFixed, scale: this.spotScale, dots: this.spotStyle === 'dots', plain: this.spotStyle === 'plain',
      hover: this.hover, grabbed: this.drag && !this.drag.returning ? this.drag.handle.spot.bone : null, direction: (spot) => this.dragDirections.of(this.player, spot),
    })
  }
}
