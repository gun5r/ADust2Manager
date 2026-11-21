<script lang="ts">
  /** A picture shown large over everything, inside a dialog. Any click, or Escape, closes only the picture: the dialog below stays open. */
  let { src, alt = '', onClose }: { src: string; alt?: string; onClose: () => void } = $props()

  // Capture phase: Escape must not reach the dialog's own handler, which would close the dialog too.
  function onKey(e: KeyboardEvent) {
    if (e.key !== 'Escape') return
    e.preventDefault()
    e.stopImmediatePropagation()
    onClose()
  }
  function focus(node: HTMLElement) {
    node.focus({ preventScroll: true })
  }
</script>

<svelte:window onkeydowncapture={onKey} />

<!-- svelte-ignore a11y_click_events_have_key_events -->
<div class="shade" role="dialog" aria-modal="true" aria-label="Large picture" tabindex="-1" use:focus onclick={(e) => { e.stopPropagation(); onClose() }}>
  <img {src} {alt} />
</div>

<style>
  .shade { position: fixed; inset: 0; z-index: 200; display: grid; place-items: center; padding: 2rem; cursor: zoom-out; background: rgba(0, 0, 0, 0.82); outline: none; }
  img { height: min(62vh, 640px); max-width: 90vw; object-fit: contain; border-radius: var(--radius-md); box-shadow: 0 20px 60px rgba(0, 0, 0, 0.7); background: color-mix(in srgb, var(--surface-2) 90%, transparent); }
</style>
