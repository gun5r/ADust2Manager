<script lang="ts">
  import { onMount } from 'svelte'
  import Icon from '../../ui/Icon.svelte'
  import type { ViewerState } from './viewer.svelte'
  let { viewer, dating, visible }: { viewer: ViewerState; dating: boolean; visible: boolean } = $props()
  let time = $state(0), duration = $state(0)
  const speeds = [0.5, 1, 1.5, 2]
  function changeSpeed(event: MouseEvent) {
    const index = speeds.indexOf(viewer.speed)
    const direction = event.shiftKey ? -1 : 1
    viewer.setSpeed(speeds[(index + direction + speeds.length) % speeds.length])
  }
  function seek(value: number) { viewer.seekPlayback(value); time = value }
  function format(value: number) { return value.toFixed(1) }
  onMount(() => {
    let frame = 0
    const update = () => { ({ time, duration } = viewer.playbackTime()); frame = requestAnimationFrame(update) }
    frame = requestAnimationFrame(update)
    return () => cancelAnimationFrame(frame)
  })
</script>

{#if viewer.playbackBar}
  <div class="bar" class:visible class:dating data-ui="playback-bar" role="group" aria-label="Animation playback" onpointerdown={(e) => e.stopPropagation()}>
    <button aria-label={viewer.paused ? 'Play (P)' : 'Pause (P)'} title={viewer.paused ? 'Play (P)' : 'Pause (P)'} onclick={() => viewer.togglePause()}><Icon name={viewer.paused ? 'play' : 'pause'} size={14} /></button>
    <input class="timeline" type="range" min="0" max={duration || 1} step="0.01" value={Math.min(time, duration || 1)} aria-label="Clip position" oninput={(e) => seek(Number(e.currentTarget.value))} />
    <span class="readout">{format(time)} / {format(duration)} s</span>
    <button class:on={viewer.loop} aria-label="Loop" aria-pressed={viewer.loop} title="Loop (L)" onclick={() => viewer.toggleLoop()}><Icon name="repeat" size={14} /></button>
    <button aria-label={`Playback speed ${viewer.speed}×`} title="Playback speed (click: faster, Shift+click: slower)" onclick={changeSpeed}>{viewer.speed}×</button>
  </div>
{/if}

<style>
  .bar { position: absolute; z-index: 5; left: 50%; bottom: 12px; transform: translate(-50%, 4px); width: min(460px, calc(100% - 32px)); min-height: 30px; box-sizing: border-box; display: flex; align-items: center; gap: 6px; padding: 3px 6px; color: var(--text-main); background: var(--scrim-soft); border-radius: var(--radius-md); backdrop-filter: blur(5px); opacity: 0; pointer-events: none; transition: opacity 0.18s ease, transform 0.18s ease; }
  .bar.visible, .bar:focus-within { opacity: 1; transform: translate(-50%, 0); pointer-events: auto; }
  .bar.dating { bottom: var(--dating-playback-bottom, 10.75rem); left: calc(50% - 6px); width: min(460px, calc(100% - 48px)); }
  button { height: 24px; flex: none; padding: 0 5px; display: inline-flex; align-items: center; justify-content: center; color: var(--text-main); background: transparent; border: 0; border-radius: 5px; font: inherit; }
  button:hover, button:focus-visible, button.on { color: var(--primary); background: var(--selected-bg); }
  .timeline { min-width: 40px; flex: 1; height: 3px; accent-color: var(--primary); cursor: pointer; }
  .readout { white-space: nowrap; font: var(--fs-sm) var(--font-mono); color: var(--text-main); }
  button { cursor: pointer; }
</style>
