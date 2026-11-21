/**
 * The score gauge some dating phases have (scenes 14, 15, 16, 19, 22). What the game's data says: a score between min and max starts at
 * `start`; each click of a spot adds the spot's `Scores[click]`; the score changes by itself by `-decay` per second while it is
 * inside the auto-change limits; a spot with its own gauge is usable only while the score is inside its range (so the ten spots at
 * one place in Olivier's phase 2 are really three: low, high and full); motions are played when the score crosses a threshold.
 * What happens when the gauge is full is not in the data: it only makes the "full" spots (range max..max) usable.
 */
export interface Range { x: number; y: number }
export interface GaugeMotion { Score: number; MixAnimationName: string; VoiceSoundEventName?: string; SFXSoundEventName?: string; IsCanPlayWhenIncreaseScore: number; IsCanPlayWhenDecreaseScore: number }
export interface GaugeRule { on: boolean; min: Range; start: number; decay: number; limit?: Range; motions: GaugeMotion[] }
export interface SpotGauge { IsOn: number; InteractableMinMaxRange: Range; Scores: number[]; LongPressFailScore?: number; LongPressSuccessScore?: number }

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v))

export const startScore = (g: GaugeRule): number => clamp(g.start, g.min.x, g.min.y)

/** The score `dt` seconds later with no touches: it moves only while inside the limits and stays inside them. */
export function autoStep(score: number, g: GaugeRule, dt: number): number {
  if (!g.decay) return score
  const limit = g.limit ?? g.min
  if (score < limit.x || score > limit.y) return score
  return clamp(score - g.decay * dt, limit.x, limit.y)
}

/** A click: the spot's score for this click of the run (the last entry repeats), kept between min and max. */
export function afterClick(score: number, g: GaugeRule, spot: SpotGauge | undefined, click: number): number {
  const scores = spot?.Scores ?? []
  const add = scores.length ? scores[Math.min(click, scores.length - 1)] : 0
  return clamp(score + add, g.min.x, g.min.y)
}

/** Whether a spot can be used at this score (spots without a gauge always can). */
export function usable(spot: SpotGauge | undefined, score: number): boolean {
  if (!spot?.IsOn) return true
  const s = Math.floor(score + 1e-6)
  return s >= spot.InteractableMinMaxRange.x && s <= spot.InteractableMinMaxRange.y
}

/** Motions whose threshold the score just crossed (upwards or downwards, where they allow it). */
export function crossed(from: number, to: number, motions: GaugeMotion[]): GaugeMotion[] {
  return motions.filter((m) => m.MixAnimationName && ((to > from && from < m.Score && to >= m.Score && m.IsCanPlayWhenIncreaseScore) || (to < from && from > m.Score && to <= m.Score && m.IsCanPlayWhenDecreaseScore)))
}
