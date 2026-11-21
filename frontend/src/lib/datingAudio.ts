/** Dating-scene sound plans: the game plays an FMOD event per touch animation; the server hands us each event's layers. */
export interface SoundLayer {
  /** Seconds after the animation starts. */
  start: number
  /** How long it plays (seconds, 0 = the whole clip), and where in the clip it starts (samples). */
  length: number
  trim: number
  /** Linear gain (instrument volume plus its track buses) and the random level variation (dB, plus or minus). */
  gain: number
  jitter_db: number
  /** Playback rate (pitch) and the fades at the start and end of the played part (seconds). */
  rate: number
  fade_in: number
  fade_out: number
  /** Probability (0-1) that the instrument plays at all. */
  chance: number
  /** `one`: pick one of the clips at random; `all`: play them together. */
  pick: 'one' | 'all'
  clips: string[]
}

export interface SoundManifest {
  animations: Record<string, { sfx?: SoundLayer[]; voice?: Record<string, SoundLayer[]> }>
}

/** `mix1_05_1`, `Mix_1_5_1` and `mix1_5_1` are one animation (same rule as core/dating_audio.py anim_key). */
export function animKey(name: string): string {
  const key = name.trim().toLowerCase().replace(/^(mix|motion|montion)_?/, (_m, prefix: string) => (prefix === 'mix' ? 'mix' : 'motion'))
  return key.replace(/\d+/g, (digits) => String(Number(digits)))
}

/** The key of `spot`'s sound for `variant`: that variant, the spot's single clip, or else its first numbered variant (a spot whose variants play at random sounds the same for any). */
function variantKey(manifest: SoundManifest, spot: string, variant: string | undefined): string | null {
  const have = (key: string) => (manifest.animations[key] ? key : null)
  const numbered = Object.keys(manifest.animations).filter((k) => k.startsWith(`${spot}_`) && /^\d+$/.test(k.slice(spot.length + 1))).sort((a, b) => Number(a.split('_').pop()) - Number(b.split('_').pop()))
  return (variant && have(`${spot}_${variant}`)) || have(spot) || numbered[0] || null
}

/** Layers to play when an animation starts: its effect event (or the one `soundFrom` says it reuses, or that of another variant of its spot), plus its voice line in the chosen language when the scene has one. */
export function layersFor(manifest: SoundManifest | null | undefined, animation: string, voice: string | null, soundFrom: Record<string, string[]> = {}): SoundLayer[] {
  if (!manifest) return []
  const of = (key: string) => [...(manifest.animations[key]?.sfx ?? []), ...(voice ? (manifest.animations[key]?.voice?.[voice] ?? []) : [])]
  const key = animKey(animation)
  const own = of(key)
  if (own.length) return own
  const parsed = /^(mix|motion)(\d+)_(\d+)(?:_(.+))?$/.exec(key)
  if (!parsed) return []
  const spot = `${parsed[1]}${parsed[2]}_${parsed[3]}`, variant = parsed[4]
  const sources = soundFrom[spot] ?? [spot]
  return sources.flatMap((source) => { const found = variantKey(manifest, source, variant); return found ? of(found) : [] })
}

/** The clips a layer plays this time (empty when its trigger chance fails). */
export function clipsToPlay(layer: SoundLayer, random: () => number = Math.random): string[] {
  if (!layer.clips.length || random() >= layer.chance) return []
  return layer.pick === 'one' ? [layer.clips[Math.floor(random() * layer.clips.length)]] : layer.clips
}
