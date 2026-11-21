/** The touch menu's preferences of the dating simulator (not the scene's own state): one shape, one set of defaults, one reader. */
export type GuideStyle = 'off' | 'on' | 'alt'

export interface TouchPrefs {
  soundOn: boolean
  voiceOn: boolean
  /** Master volume of the dating sounds (the game's own mix is not reproduced exactly, so it is adjustable). */
  soundVolume: number
  spotsOn: boolean
  /** Hide the markers while a reaction plays. */
  spotsIdle: boolean
  spotStyle: 'numbers' | 'dots' | 'plain'
  /** Every zone one small fixed circle. */
  spotsFixed: boolean
  /** Only the spot under the pointer is drawn. */
  spotsHover: boolean
  spotScale: number
  spotOpacity: number
  /** Opaque markers (they hide the art behind them). */
  spotsSolid: boolean
  guide: GuideStyle
  legendOn: boolean
}

export const DEFAULT_PREFS: TouchPrefs = {
  soundOn: true, voiceOn: true, soundVolume: 0.8,
  spotsOn: true, spotsIdle: false, spotStyle: 'dots', spotsFixed: false, spotsHover: false, spotScale: 1, spotOpacity: 1, spotsSolid: false,
  guide: 'on', legendOn: true,
}

const LIMITS: Partial<Record<keyof TouchPrefs, [number, number]>> = { soundVolume: [0, 1.5], spotScale: [0.25, 1.5], spotOpacity: [0.1, 1] }
// 'dots' remains the saved glow style; the touch menu labels it Alt.
const CHOICES: Partial<Record<keyof TouchPrefs, string[]>> = { spotStyle: ['numbers', 'dots', 'plain'], guide: ['off', 'on', 'alt'] }

/** Saved preferences, each value kept only when it is of the right kind and inside its range; anything else is the default. */
export function readPrefs(saved: unknown): TouchPrefs {
  const from = (saved && typeof saved === 'object' ? saved : {}) as Record<string, unknown>
  const out: Record<string, unknown> = { ...DEFAULT_PREFS }
  for (const [key, fallback] of Object.entries(DEFAULT_PREFS)) {
    const value = from[key], limit = LIMITS[key as keyof TouchPrefs], choices = CHOICES[key as keyof TouchPrefs]
    if (typeof value !== typeof fallback) continue
    if (limit && ((value as number) < limit[0] || (value as number) > limit[1])) continue
    if (choices && !choices.includes(value as string)) continue
    out[key] = value
  }
  return out as unknown as TouchPrefs
}
