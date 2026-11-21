import { datingClipUrl } from './api'
import { clipsToPlay, type SoundLayer, type SoundManifest } from './datingAudio'

/** Sounds started by one animation; `stop` fades them out (a drag that is let go ends its event). */
export interface Playback {
  stop(fadeSeconds?: number): void
}

/** WebAudio playback of dating-scene sound plans: clips are decoded once; each layer plays its part of the clip with the
 *  instrument's level, pitch and fades at its offset from the animation start. */
export class SoundPlayer {
  private context: AudioContext | null = null
  private master: GainNode | null = null
  private buffers = new Map<string, Promise<AudioBuffer | null>>()
  private active = new Set<{ source: AudioBufferSourceNode; gain: GainNode }>()
  volume = 1

  private ctx(): AudioContext {
    if (!this.context) {
      this.context = new AudioContext()
      this.master = this.context.createGain()
      this.master.gain.value = this.volume
      this.master.connect(this.context.destination)
    }
    return this.context
  }

  setVolume(volume: number) {
    this.volume = volume
    if (this.master) this.master.gain.value = volume
  }

  private buffer(scene: string, clip: string): Promise<AudioBuffer | null> {
    const key = `${scene}/${clip}`
    let found = this.buffers.get(key)
    if (!found) {
      found = fetch(datingClipUrl(scene, clip)).then((r) => (r.ok ? r.arrayBuffer() : Promise.reject(new Error(String(r.status))))).then((data) => this.ctx().decodeAudioData(data)).catch(() => null)
      this.buffers.set(key, found)
    }
    return found
  }

  /** Fetch and decode every clip of the scene ahead of time, a few at a time, so the first touch has no delay. */
  async preload(scene: string, manifest: SoundManifest, voice: string | null) {
    const clips = new Set<string>()
    for (const entry of Object.values(manifest.animations)) {
      for (const layer of [...(entry.sfx ?? []), ...(voice ? (entry.voice?.[voice] ?? []) : [])]) layer.clips.forEach((c) => clips.add(c))
    }
    const queue = [...clips]
    await Promise.all(Array.from({ length: 4 }, async () => { for (let c = queue.pop(); c; c = queue.pop()) await this.buffer(scene, c) }))
  }

  /** Start the layers now; returns a handle that can fade them out early. */
  play(scene: string, layers: SoundLayer[], random: () => number = Math.random): Playback {
    const ctx = this.ctx()
    if (ctx.state === 'suspended') void ctx.resume()
    const origin = ctx.currentTime
    const mine = new Set<{ source: AudioBufferSourceNode; gain: GainNode }>()
    let stopped = false
    for (const layer of layers) {
      for (const clip of clipsToPlay(layer, random)) {
        void this.buffer(scene, clip).then((buffer) => {
          if (!buffer || stopped) return
          const when = Math.max(ctx.currentTime, origin + layer.start)
          const offset = Math.min(buffer.duration, layer.trim / buffer.sampleRate)
          // The played part is `length` of timeline time; with a pitch change it covers rate x as much of the clip.
          const wanted = layer.length > 0 ? layer.length : (buffer.duration - offset) / layer.rate
          const length = Math.min(wanted, (buffer.duration - offset) / layer.rate)
          if (length <= 0) return
          const level = layer.gain * 10 ** (((random() * 2 - 1) * layer.jitter_db) / 20)
          const source = ctx.createBufferSource(), gain = ctx.createGain()
          source.buffer = buffer
          source.playbackRate.value = layer.rate
          const fadeIn = Math.min(Math.max(layer.fade_in, 0.004), length), fadeOut = Math.min(layer.fade_out, length - fadeIn)
          gain.gain.setValueAtTime(0, when)
          gain.gain.linearRampToValueAtTime(level, when + fadeIn)
          if (fadeOut > 0) { gain.gain.setValueAtTime(level, when + length - fadeOut); gain.gain.linearRampToValueAtTime(0, when + length) }
          source.connect(gain).connect(this.master ?? ctx.destination)
          const entry = { source, gain }
          this.active.add(entry); mine.add(entry)
          source.onended = () => { this.active.delete(entry); mine.delete(entry) }
          source.start(when, offset, length * layer.rate)
        })
      }
    }
    return {
      stop: (fade = 0.12) => {
        stopped = true
        for (const { source, gain } of mine) {
          try {
            const now = ctx.currentTime
            gain.gain.cancelScheduledValues(now)
            gain.gain.setValueAtTime(gain.gain.value, now)
            gain.gain.linearRampToValueAtTime(0, now + fade)
            source.stop(now + fade + 0.02)
          } catch { /* already finished */ }
        }
      },
    }
  }

  stop() {
    for (const { source } of this.active) try { source.stop() } catch { /* already finished */ }
    this.active.clear()
  }
}
