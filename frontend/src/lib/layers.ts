/** Viewer layer list: which slots an animation touches, and how hiding a layer changes its colour (ported from classic). */

interface Colorish { r: number; g: number; b: number; a: number }
export interface SlotLike {
  data: { name: string; attachmentName?: string | null; color?: Colorish; darkColor?: Colorish }
  attachment?: { name?: string } | null
  color: Colorish
  darkColor?: Colorish | null
  bone?: unknown
}
export interface SkeletonLike {
  drawOrder?: SlotLike[]
  slots?: SlotLike[]
  bones?: unknown[]
  data?: { findAnimation?: (name: string) => { timelines?: { slotIndex?: number; boneIndex?: number }[] } | null }
  findSlot?: (name: string) => SlotLike | null
}

const hasArt = (s: SlotLike) => Boolean(s.attachment || s.data?.attachmentName)

/** Slots drawn by (or animated in) `animName`, in draw order. Without an animation: every slot that has artwork. */
export function slotsForAnimation(skeleton: SkeletonLike | null | undefined, animName?: string | null): SlotLike[] {
  if (!skeleton) return []
  const drawOrder = skeleton.drawOrder?.length ? skeleton.drawOrder : (skeleton.slots ?? [])
  const anim = animName ? skeleton.data?.findAnimation?.(animName) : null
  if (!anim) return drawOrder.filter((s) => s && hasArt(s))

  const slotIndexes = new Set<number>()
  const boneIndexes = new Set<number>()
  for (const timeline of anim.timelines ?? []) {
    if (typeof timeline.slotIndex === 'number' && timeline.slotIndex >= 0) slotIndexes.add(timeline.slotIndex)
    if (typeof timeline.boneIndex === 'number' && timeline.boneIndex >= 0) boneIndexes.add(timeline.boneIndex)
  }
  const slots = skeleton.slots ?? []
  if (boneIndexes.size && skeleton.bones) {
    slots.forEach((slot, index) => {
      if (slot?.attachment && slot.bone) {
        const bone = skeleton.bones!.indexOf(slot.bone)
        if (bone !== -1 && boneIndexes.has(bone)) slotIndexes.add(index)
      }
    })
  }
  return drawOrder.filter((s) => s && (hasArt(s) || slotIndexes.has(slots.indexOf(s))))
}

export interface LayerRow {
  name: string
  /** The attachment's own name when it differs from the slot name. */
  tag: string
}

/** Top-most layer first, like the classic list. */
export function layerRows(slots: SlotLike[]): LayerRow[] {
  return [...slots].reverse().map((slot) => {
    const attachment = slot.attachment ? (slot.attachment.name ?? '') : (slot.data.attachmentName ?? '')
    return { name: slot.data.name, tag: attachment && attachment !== slot.data.name ? attachment : '' }
  })
}

export function filterLayers(rows: LayerRow[], query: string): LayerRow[] {
  const needle = query.trim().toLowerCase()
  return needle ? rows.filter((row) => row.name.toLowerCase().includes(needle)) : rows
}

/** Hide a slot (alpha 0) or restore its authored colour. */
export function setSlotHidden(slot: SlotLike | null | undefined, hidden: boolean): void {
  if (!slot) return
  if (hidden) {
    slot.color.a = 0
    if (slot.darkColor) slot.darkColor.a = 0
    return
  }
  const authored = slot.data?.color
  slot.color.r = authored?.r ?? 1
  slot.color.g = authored?.g ?? 1
  slot.color.b = authored?.b ?? 1
  slot.color.a = authored && typeof authored.a === 'number' ? authored.a : 1
  if (slot.darkColor && slot.data?.darkColor) slot.darkColor.a = typeof slot.data.darkColor.a === 'number' ? slot.data.darkColor.a : 0
}

export function countVisible(rows: LayerRow[], hidden: Set<string>): number {
  return rows.filter((row) => !hidden.has(row.name)).length
}

/** The classic "All" button: show everything if anything is hidden, otherwise hide everything. */
export const nextAllHidden = (rows: LayerRow[], hidden: Set<string>): boolean => !rows.some((row) => hidden.has(row.name))
