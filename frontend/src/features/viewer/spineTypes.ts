/** The parts of the Spine 4.1 runtime (global `spine`, patched player in /static/libs) that the viewer touches, so the code around it is typed and can be tested with plain objects. */

export interface SpineColor { r: number; g: number; b: number; a: number }

export interface SpinePoint { x: number; y: number }

export interface SpineBone {
  data: { name: string; x: number; y: number }
  parent: SpineBone | null
  x: number
  y: number
  worldX: number
  worldY: number
  setToSetupPose(): void
  localToWorld(point: SpinePoint): void
  worldToLocal(point: SpinePoint): void
}

export interface SpineSlot {
  data: { name: string; attachmentName: string | null; index: number; blendMode: number; color?: SpineColor; darkColor?: SpineColor }
  attachment?: { name?: string } | null
  color: SpineColor
  darkColor?: SpineColor | null
  getAttachment(): SpineAttachment | null
  setAttachment(attachment: SpineAttachment | null): void
}

export interface SpineAttachment { name: string; endSlot?: unknown; computeWorldVertices?: unknown }

export interface SpineTimeline { slotIndex?: number; boneIndex?: number; frames: Float32Array | number[]; attachmentNames?: (string | null)[]; getFrameEntries?(): number; apply(...args: unknown[]): void }

export interface SpineAnimation { name: string; duration: number; timelines: SpineTimeline[]; apply(skeleton: SpineSkeleton, lastTime: number, time: number, loop: boolean, events: unknown[], alpha: number, blend: unknown, direction: unknown): void }

export interface SpineSkeletonData {
  bones: { name: string }[]
  animations: SpineAnimation[]
  findAnimation(name: string): SpineAnimation | null
  findSkin(name: string): unknown
}

export interface SpineSkeleton {
  data: SpineSkeletonData
  bones: SpineBone[]
  slots: SpineSlot[]
  drawOrder?: SpineSlot[]
  findBone(name: string): SpineBone | null
  findSlot(name: string): SpineSlot | null
  getAttachment(slotIndex: number, name: string): SpineAttachment | null
  setToSetupPose(): void
  setSlotsToSetupPose(): void
  setSkinByName(name: string): void
  updateWorldTransform(): void
}

export interface SpineTrackEntry {
  animation: SpineAnimation | null
  mixingFrom: SpineTrackEntry | null
  trackTime: number
  animationEnd: number
  next?: SpineTrackEntry | null
  loop: boolean
  listener: { complete?: () => void } | null
  getAnimationTime(): number
  isComplete?(): boolean
}

export interface SpineAnimationState {
  tracks: (SpineTrackEntry | null | undefined)[]
  timeScale: number
  data: { defaultMix: number; skeletonData: SpineSkeletonData }
  getCurrent(track: number): SpineTrackEntry | null
  setAnimation(track: number, name: string, loop: boolean): SpineTrackEntry
  addAnimation(track: number, name: string, loop: boolean, delay: number): SpineTrackEntry
  addEmptyAnimation(track: number, mixDuration: number, delay: number): SpineTrackEntry
  setEmptyAnimation(track: number, mixDuration: number): SpineTrackEntry
  clearTrack(track: number): void
  clearTracks(): void
  apply(skeleton: SpineSkeleton): void
  update(delta: number): void
}

export interface SpineCamera { viewportWidth: number; viewportHeight: number; zoom: number; position: SpinePoint; update(): void }

export interface SpinePlayer {
  skeleton: SpineSkeleton
  animationState: SpineAnimationState
  sceneRenderer?: { camera: SpineCamera }
  canvas: HTMLCanvasElement
  paused: boolean
  config: { showLoading: boolean }
  play?(): void
  pause?(): void
  drawFrame?(draw: boolean): void
  dispose?(): void
}
