/** The Spine player is a script the page loads at start; when that went wrong (a hiccup, a damaged copy in the browser's cache) it is fetched again once. */
declare const spine: any

export const SPINE_MISSING = 'The Spine player did not load, so nothing can be previewed. Reload the page (F5); if this message comes back, do a hard reload that skips the browser cache: Ctrl+Shift+R (Ctrl+F5 on Windows and Linux, Cmd+Shift+R on Mac).'

let retry: Promise<boolean> | null = null

/** Spine 4.2 wants a Physics mode with every updateWorldTransform; our calls predate that, so the missing one means "update". Idempotent. */
export function adaptRuntime(): void {
  const proto = typeof spine !== 'undefined' ? spine.Skeleton?.prototype : undefined
  if (!proto || proto.adustPhysics) return
  const original = proto.updateWorldTransform
  proto.updateWorldTransform = function (physics?: unknown) { return original.call(this, physics ?? spine.Physics?.update) }
  proto.adustPhysics = true
}

export function ensureSpine(): Promise<boolean> {
  const ready = () => typeof spine !== 'undefined' && !!spine.SpinePlayer
  if (ready()) return Promise.resolve(true)
  retry ??= new Promise<boolean>((resolve) => {
    const script = document.createElement('script')
    script.src = `/static/libs/spine-player.js?retry=${Date.now()}`
    script.onload = () => resolve(ready())
    script.onerror = () => resolve(false)
    document.head.appendChild(script)
  }).finally(() => { retry = null })
  return retry
}
