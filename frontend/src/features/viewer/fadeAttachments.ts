/**
 * A reaction clip ends by fading out over a short empty animation. While it fades, Spine still applies the clip's attachment keys
 * (a face swapped for an expression, hidden faces left hidden) over the idle, and the idle's own faces only come back when the fade
 * is over: for those 150 ms the head is gone (Sylvia, any touch). The game does not show that gap, so while a layer fades the slots it
 * keys go back to what the idle shows (or the setup attachment where the idle does not key them).
 */
import type { SpinePlayer, SpineTimeline, SpineTrackEntry } from './spineTypes'

declare const spine: { AttachmentTimeline: abstract new (...args: never[]) => SpineTimeline; MixBlend: { setup: unknown }; MixDirection: { mixIn: unknown } }

/** The slots a clip keys attachments of. */
function attachmentSlots(timelines: SpineTimeline[]): number[] {
  return timelines.filter((t) => t instanceof spine.AttachmentTimeline && t.slotIndex !== undefined).map((t) => t.slotIndex!)
}

export function keepIdleAttachments(player: SpinePlayer | null): void {
  if (!player) return
  const { animationState: state, skeleton } = player
  const idle = state.tracks[0]
  if (!idle?.animation) return
  const fading = state.tracks.filter((entry, track): entry is SpineTrackEntry => track > 0 && !!entry?.mixingFrom && entry.animation?.name === '<empty>')
  if (!fading.length) return
  // slots another reaction layer keeps keying (the idle is what we restore to, so it does not count) (Teresse: spot 36 takes the bottles over from spot 29) are that layer's
  const live = new Set(state.tracks.flatMap((entry, track) => (track > 0 && entry?.animation && entry.animation.name !== '<empty>' && !fading.includes(entry) ? attachmentSlots(entry.animation.timelines) : [])))
  const slots = new Set<number>()
  for (const entry of fading) {
    for (let from = entry.mixingFrom; from; from = from.mixingFrom) {
      for (const index of attachmentSlots(from.animation?.timelines ?? [])) if (!live.has(index)) slots.add(index)
    }
  }
  for (const index of slots) {
    const slot = skeleton.slots[index]
    slot.setAttachment(slot.data.attachmentName ? skeleton.getAttachment(index, slot.data.attachmentName) : null)
  }
  const time = idle.getAnimationTime()
  for (const timeline of idle.animation.timelines) {
    if (timeline instanceof spine.AttachmentTimeline && timeline.slotIndex !== undefined && slots.has(timeline.slotIndex)) timeline.apply(skeleton, time, time, [], 1, spine.MixBlend.setup, spine.MixDirection.mixIn)
  }
}
