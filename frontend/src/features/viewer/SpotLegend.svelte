<script lang="ts">
  import type { HotspotKind } from '../../lib/dating'
  import type { ViewerState } from './viewer.svelte'
  import { COLOURS } from './spotMarkers'
  let { viewer }: { viewer: ViewerState } = $props()

  const MEANING: Record<HotspotKind, string> = {
    touch: 'Touch: tap it',
    follow: 'Hold: press and keep pressing, it follows the finger',
    drag: 'Drag: pull it along',
    hidden: 'Hidden: only works after another spot',
    gyro: 'Tilt: the phone is tilted in the game, use the Tilt button',
  }
  const ORDER: HotspotKind[] = ['touch', 'follow', 'drag', 'hidden', 'gyro']
  // only what the phase on screen has
  const kinds = $derived.by(() => {
    const here = viewer.spots.filter((s) => s.phase === viewer.phase)
    const present = new Set((here.length ? here : viewer.spots).map((s) => s.kind))
    return ORDER.filter((k) => present.has(k))
  })
</script>

{#if viewer.prefs.legendOn && kinds.length}
  <div class="legend" data-ui="spot-legend" role="note" aria-label="What the spot colours mean">
    <button class="close" title="Hide the legend (the Legend button in the touch menu shows it again)" aria-label="Hide the legend" onclick={() => (viewer.prefs.legendOn = false)}>Hide</button>
    <ul>
      {#each kinds as kind (kind)}
        <li><i style:background="rgb({COLOURS[kind]})"></i>{MEANING[kind]}</li>
      {/each}
      {#if viewer.prefs.guide !== 'off'}<li><i class="guide"></i>Guide: the next spot to touch</li>{/if}
    </ul>
  </div>
{/if}

<style>
  .legend { position: absolute; left: 12px; bottom: 12px; z-index: 3; max-width: min(20rem, 45%); padding: 6px 10px; font-size: var(--fs-xs); color: var(--text-main); background: var(--scrim-soft); border: 0; border-radius: 8px; backdrop-filter: blur(4px); }
  ul { margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 3px; }
  li { display: flex; align-items: center; gap: 0.5rem; }
  i { flex-shrink: 0; width: 10px; height: 10px; border-radius: 50%; box-shadow: 0 0 5px currentColor; }
  i.guide { background: transparent; border: 2px solid rgb(253, 224, 71); box-sizing: border-box; }
  .close { position: absolute; top: -9px; right: 6px; padding: 0 0.45rem; font-size: var(--fs-xs); font-weight: 700; color: var(--text-muted); background: var(--surface-2); border: 1px solid var(--tint-4); border-radius: 6px; opacity: 0; pointer-events: none; transition: opacity 0.12s; }
  .legend:hover .close, .close:focus-visible { opacity: 1; pointer-events: auto; }
  .close:hover { border-color: var(--primary); color: var(--text-main); }
</style>
