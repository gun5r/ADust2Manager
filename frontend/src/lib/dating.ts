/**
 * Dating-scene interaction rules, read from the skeleton itself: hotspots are bones named
 * `point{phase}_{id}_{touch|touch_follow|drag|touch_hidden}[n]`, reactions are animations `mix{phase}_{id}_{variant}`
 * and the resting poses are `idle{phase}`.
 */
export type HotspotKind = 'touch' | 'follow' | 'drag' | 'hidden' | 'gyro'

/** One spot's rules as the game stores them (generated/dating_rules.json, from the original scene). */
import type { GaugeRule, SpotGauge } from './gauge'
import overrides from './datingOverrides.json'

export interface SpotRule {
  bone: string
  phase: number
  id: number
  kind: 'touch' | 'drag'
  anims: string[]
  random: boolean
  /** Played when the action stops (pointer released). */
  stop?: string
  /** Played when the action completes; with `next` the scene then moves to the next phase. */
  motion?: string
  next: boolean
  /** Continuous clicks allowed before the spot stops reacting (0 = unlimited), and the pause that ends a run of clicks. */
  clickMax: number
  clickReset: number
  longPress?: { type: number; threshold: number; loop: string[]; fail: string[]; success: string[] }
  /** Drags with a destination: `[x, y, width, height]` in the spot bone's parent space; reaching it completes the action. */
  dest?: [number, number, number, number]
  /** Where the finger of a drag may go, `[x, y, width, height]` around its centre; drags that end a phase without a `dest` (Scheherazade's thighs) are done when they reach it. */
  area?: [number, number, number, number]
  /** `[width, height]` of the spot's touchable rectangle (world units). */
  size?: [number, number]
  /** The tool (skin) this spot belongs to; absent = 0, the bare hand. */
  tool?: number
  /** Present when the spot is tied to the phase's score gauge (see lib/gauge.ts). */
  gauge?: SpotGauge
}

export interface SceneRules {
  groups: { group: number; idle: string; switch: string; gauge?: GaugeRule; tools?: { id: number; skin: string }[] }[]
  spots: SpotRule[]
  /** From the overrides (not the game's data): where a phase-ending spot (`<phase>_<id>`) leads, and the spots (or clips) whose sounds a clip plays. */
  nextPhase?: Record<string, number>
  soundFrom?: Record<string, string[]>
}

export interface Hotspot {
  bone: string
  phase: number
  id: number
  kind: HotspotKind
  /** Reaction animations that exist in the skeleton, in variant order. */
  reactions: string[]
  /** Hold-style spots (some scenes): `mix{p}_{id}_loop` plays while the spot is held, `mix{p}_{id}_end` on release. */
  loop?: string
  end?: string
  /** The game's own rules for this spot, when the scene is known (the naming convention above is the fallback). */
  rule?: SpotRule
}

const BONE = /^point(\d+)_(\d+)_(touch_hidden|touch_follow|touch|drag|gyro)/i
const KIND: Record<string, HotspotKind> = { touch: 'touch', touch_follow: 'follow', drag: 'drag', touch_hidden: 'hidden', gyro: 'gyro' }

export function parseHotspots(bones: string[], animations: string[]): Hotspot[] {
  const reactionsOf = (phase: number, id: number) =>
    animations.filter((a) => new RegExp(`^mix${phase}_0*${id}_\\d+$`, 'i').test(a)).sort((a, b) => Number(a.split('_').pop()) - Number(b.split('_').pop()))
  const named = (phase: number, id: number, suffix: string) =>
    animations.find((a) => new RegExp(`^mix${phase}_0*${id}_${suffix}`, 'i').test(a))
  const found = new Map<string, Hotspot>()
  for (const bone of bones) {
    const m = BONE.exec(bone)
    if (!m) continue
    const phase = Number(m[1]), id = Number(m[2]), key = `${phase}_${id}`
    // Several bones can belong to one spot (`point1_5_drag`, `point1_5_drag2`): the plain one is the hit position.
    if (!found.has(key) || bone.length < found.get(key)!.bone.length) found.set(key, { bone, phase, id, kind: KIND[m[3].toLowerCase()], reactions: reactionsOf(phase, id), loop: named(phase, id, 'loop'), end: named(phase, id, 'end') })
  }
  return [...found.values()].sort((a, b) => a.phase - b.phase || a.id - b.id)
}

export const phasesOf = (spots: Hotspot[]): number[] => [...new Set(spots.map((s) => s.phase))].sort((a, b) => a - b)

/** The resting animation of a phase: `idle{phase}`, else the first idle-like one. */
export const idleFor = (phase: number, animations: string[]): string | null =>
  animations.find((a) => a.toLowerCase() === `idle${phase}`) ?? animations.find((a) => /^idle/i.test(a)) ?? null

/** Taps cycle through a spot's variants (`_1`, `_2`, `_3`…). */
export const nextReaction = (spot: Hotspot, taps: number): string | null => spot.reactions.length ? spot.reactions[taps % spot.reactions.length] : null

/** Radius (world units) of the "fixed" zones: small enough that neighbouring spots rarely share a point. */
export const FIXED_RADIUS = 45
/** A zone this big (world units) covers the whole picture: it is hit last and drawn as a small marker. */
export const HUGE_ZONE = 2000

/** Touchable size `[width, height]` of a spot in world units: the game's own rectangle, else a square of twice the fallback radius. */
export function spotSize(spot: Hotspot, radius: number): [number, number] {
  const size = spot.rule?.size
  return size && size[0] >= 20 && size[1] >= 20 ? size : [2 * radius, 2 * radius]
}

/** Area of the shape a spot is touched in: a box for drag handles, an ellipse for touch zones. */
export function spotArea(spot: Hotspot, radius: number): number {
  const [w, h] = spotSize(spot, radius)
  return spot.kind === 'drag' ? w * h : (Math.PI / 4) * w * h
}

/**
 * Every spot whose zone holds the point, nearest centre first. Zones overlap a lot (in newer scenes half of all points are in two
 * or more, the game's own sizes), and no simple rule (nearest centre, smallest zone, topmost in the game's hierarchy) makes every
 * spot reachable: measured over all 22 scenes, nearest centre leaves the fewest spots hard to hit (12%), so it is the default and
 * `skip` walks down the list for the spots behind it. Spots the skeleton cannot react to are ignored.
 */
export function hotspotsAt<T extends Hotspot>(spots: { spot: T; x: number; y: number }[], x: number, y: number, radius: number, fixed = 0, scale = 1): T[] {
  const hits: { spot: T; d: number }[] = []
  for (const s of spots) {
    if (!s.spot.reactions.length && !s.spot.loop && !s.spot.rule?.motion && !s.spot.rule?.next) continue
    const [w, h] = fixed ? [2 * fixed, 2 * fixed] : spotSize(s.spot, radius).map((v) => v * scale)
    const nx = (s.x - x) / (w / 2), ny = (s.y - y) / (h / 2)  // drag handles are boxes, touch zones ellipses (as drawn); fixed zones are circles
    if (s.spot.kind === 'drag' && !fixed ? Math.max(Math.abs(nx), Math.abs(ny)) > 1 : nx * nx + ny * ny > 1) continue
    hits.push({ spot: s.spot, d: Math.hypot(s.x - x, s.y - y) })
  }
  // a zone that covers the whole picture (Wilhelmina's 5000 x 5000, Justia's 2500) only takes what no smaller zone wants
  const huge = (s: Hotspot) => Number(Math.max(...spotSize(s, radius)) >= HUGE_ZONE)
  return hits.sort((a, b) => huge(a.spot) - huge(b.spot) || a.d - b.d).map((h) => h.spot)
}

/** The spot a point touches: the nearest one, or with `skip` the one behind it (Shift+click cycles through the overlapping spots). */
export function hotspotAt<T extends Hotspot>(spots: { spot: T; x: number; y: number }[], x: number, y: number, radius: number, skip = 0, fixed = 0, scale = 1): T | null {
  const hits = hotspotsAt(spots, x, y, radius, fixed, scale)
  return hits.length ? hits[skip % hits.length] : null
}

/** A spot's rule (by bone, else by phase and id), with only the clips the skeleton has: a mod may lack some. No playable clip and no ending: the spot stays without a rule. */
function matchRule(spot: Hotspot, rules: SceneRules, have: Set<string>): Hotspot {
  const rule = rules.spots.find((r) => r.bone === spot.bone) ?? rules.spots.find((r) => r.phase === spot.phase && r.id === spot.id)
  if (!rule) return spot
  const anims = rule.anims.filter((a) => have.has(a))
  // a spot whose mix clips a mod lacks can still end the phase through its motion clip (Tyr's spot 10, Olivier's 15-17), or just move the scene on (Scheherazade's gyro spot)
  return anims.length || rule.motion || rule.next ? { ...spot, rule: { ...rule, anims }, reactions: anims } : spot
}

/**
 * The game's data does not always name the clip that ends a phase (Teresse's spot 37), but the skeleton holds it as motion<phase>_<id>.
 * A touch that ends its phase through it plays that clip ALONE, with no reaction clip: its mix clip is another part of the scene, and
 * played first it looked like the wrong animation. So such a spot is not "live" for the legend and has no reaction sound.
 */
function nameEnding(spot: Hotspot, have: Set<string>): Hotspot {
  const rule = spot.rule
  if (!rule?.next || rule.motion) return spot
  const motion = `motion${rule.phase}_${rule.id}`
  if (!have.has(motion)) return spot
  const alone = spot.kind === 'touch'
  return { ...spot, rule: { ...rule, motion, anims: alone ? [] : rule.anims }, reactions: alone ? [] : spot.reactions }
}

/** A drag that ends a phase without a clip of its own plays its twin's (Scheherazade's thighs 11 and 12: only 12 has motion2_12). */
function borrowTwinMotion(spots: Hotspot[]): Hotspot[] {
  return spots.map((spot) => {
    const rule = spot.rule
    if (!rule?.next || rule.motion || spot.kind !== 'drag') return spot
    const twin = spots.find((o) => o.phase === spot.phase && o.kind === 'drag' && o.rule?.next && o.rule.motion)
    return twin ? { ...spot, rule: { ...rule, motion: twin.rule!.motion } } : spot
  })
}

/**
 * A phase-ending spot that still has no motion clip gets the clip of its phase that no spot owns: Dalvi's skeleton holds motion1_3 ..
 * motion6_3 while her ending spots are numbered 1 or 2, so the name never matches. A clip belongs to a spot when its number is that of
 * one of the phase's spots (motion5_29 is spot 29's) or when a spot already plays it; exactly one clip left over is taken, else none.
 */
function unclaimedMotion(spots: Hotspot[], have: Set<string>): Hotspot[] {
  const clips = [...have].filter((n) => /^motion\d+_\d+$/.test(n))
  const claimed = new Set(spots.flatMap((s) => (s.rule?.motion ? [s.rule.motion] : [])))
  return spots.map((spot) => {
    const rule = spot.rule
    if (!rule?.next || rule.motion) return spot
    const free = clips.filter((c) => c.startsWith(`motion${spot.phase}_`) && !claimed.has(c) && !spots.some((o) => o.phase === spot.phase && c === `motion${spot.phase}_${o.rule?.id ?? o.id}`))
    return free.length === 1 ? { ...spot, rule: { ...rule, motion: free[0] } } : spot
  })
}

/** Attach the game's rules to the spots found in the skeleton, then fill in the endings the data leaves unsaid. */
export function attachRules(spots: Hotspot[], rules: SceneRules | null | undefined, animations: string[]): Hotspot[] {
  if (!rules) return spots
  const have = new Set(animations)
  return unclaimedMotion(borrowTwinMotion(spots.map((spot) => nameEnding(matchRule(spot, rules, have), have))), have)
}

/** The scene's own knowledge that the game's data lacks (lib/datingOverrides.json), laid over its rules. */
export function withOverrides(scene: string | null, rules: SceneRules): SceneRules {
  const key = scene?.match(/^illust_dating\d+/i)?.[0].toLowerCase()
  return { ...rules, ...(key ? (overrides as Record<string, Partial<SceneRules>>)[key] : undefined) }
}

/** The phase a finished ending action goes to: the scene's own branch, else the next phase, else (the last phase) the one before it. */
export function phaseAfter(rules: SceneRules | null, spot: Hotspot, phases: number[]): number | undefined {
  const branch = rules?.nextPhase?.[`${spot.phase}_${spot.rule?.id ?? spot.id}`]
  return branch ?? phases.find((n) => n > spot.phase) ?? phases.filter((n) => n < spot.phase).pop()
}

/** Where a scene-ending drag has to get to: its destination, else the middle of its area. */
export const dragGoal = (rule: SpotRule | undefined): readonly number[] | undefined => rule?.dest ?? (rule && (rule.next || rule.motion) ? rule.area : undefined)

/**
 * A scene-ending drag the game gives no destination or area for (Dalvi's drags): it ends the phase when it is let go after being pulled
 * this far (world units): about 60% of its touchable box, never less than 150. A press that barely moves is just a press.
 */
export const dragTravel = (rule: SpotRule | undefined): number => Math.max(150, 0.6 * Math.max(0, ...(rule?.size ?? [])))

/**
 * The clips of one stage of a staged long press (Yuri's spot 1 has 20: hold clip mix1_1_loop<n>, success clip mix1_1_long<n>).
 * `stage` counts from 0 and stays on the last stage once the run is complete; `last` says whether another stage follows.
 */
export function longPressStage(press: NonNullable<SpotRule['longPress']>, stage: number): { index: number; loop?: string; success?: string; fail?: string; last: boolean } {
  const at = <T,>(list: T[], i: number): T | undefined => list[Math.min(i, list.length - 1)]
  const index = Math.max(0, Math.min(stage, Math.max(press.success.length, 1) - 1))
  return { index, loop: at(press.loop, index), success: at(press.success, index), fail: at(press.fail, index), last: index >= press.success.length - 1 }
}

/** The picture of a tool button: the game's toolbar icons are numbered from 1 and tool id 0 (the bare hand) is icon 1 (the server cuts them out of the game's atlas). */
export const toolIconUrl = (toolId: number): string => `/api/dating-tool-icon/${toolId + 1}`

export interface TapState { taps: number; lastAt: number }

/**
 * The reaction a tap plays under the game's rules: taps within `clickReset` seconds of the previous one continue the
 * sequence of the spot's animations (`random` picks one instead), a pause starts it again, and after `clickMax`
 * continuous clicks the spot is silent until the pause. Without a rule the variants simply cycle.
 */
export function chooseReaction(spot: Hotspot, state: TapState, now: number, random: () => number = Math.random): { anim: string | null; state: TapState } {
  const rule = spot.rule
  if (!rule) return { anim: nextReaction(spot, state.taps), state: { taps: state.taps + 1, lastAt: now } }
  const continuous = state.taps > 0 && (now - state.lastAt) / 1000 < (rule.clickReset || 1)
  const taps = continuous ? state.taps : 0
  if (rule.clickMax > 0 && taps >= rule.clickMax) return { anim: null, state }
  const list = rule.anims
  const anim = rule.kind === 'drag' ? list[0] : rule.random ? list[Math.floor(random() * list.length)] : list[Math.min(taps, list.length - 1)]
  return { anim: anim ?? null, state: { taps: taps + 1, lastAt: now } }
}
