<script lang="ts">
  import { onMount } from 'svelte'
  import Icon from '../../ui/Icon.svelte'
  import type { Background, ViewerState } from './viewer.svelte'
  let { viewer, onPortrait }: { viewer: ViewerState; onPortrait: () => void } = $props()
  let backgroundButton: HTMLButtonElement | undefined = $state()
  let popover: HTMLDivElement | undefined = $state()
  let paletteOpen = $state(false)
  let popoverStyle = $state('')
  const swatches: { key: Background; title: string }[] = [
    { key: 'default', title: 'Default dark' }, { key: 'black', title: 'Black' },
    { key: 'white', title: 'White' }, { key: 'skyblue', title: 'Sky blue' },
  ]
  onMount(() => {
    const outside = (event: PointerEvent) => { if (!backgroundButton?.parentElement?.contains(event.target as Node) && !popover?.contains(event.target as Node)) paletteOpen = false }
    const resize = () => positionPopover()
    window.addEventListener('pointerdown', outside)
    window.addEventListener('resize', resize)
    return () => { window.removeEventListener('pointerdown', outside); window.removeEventListener('resize', resize) }
  })
  $effect(() => {
    if (!paletteOpen) return
    const escape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      event.preventDefault()
      event.stopPropagation()
      event.stopImmediatePropagation()
      paletteOpen = false
    }
    window.addEventListener('keydown', escape, true)
    return () => window.removeEventListener('keydown', escape, true)
  })
  function positionPopover() {
    const button = backgroundButton?.getBoundingClientRect()
    const height = popover?.getBoundingClientRect().height
    if (!button || !height) return
    const panelRight = backgroundButton?.closest<HTMLElement>('[data-ui="viewer-left"]')?.getBoundingClientRect().right
    const top = Math.max(8, button.bottom - height)
    popoverStyle = `left: ${(panelRight ?? button.right) + 6}px; top: ${top}px`
  }
  function togglePalette() {
    paletteOpen = !paletteOpen
    if (paletteOpen) requestAnimationFrame(positionPopover)
  }
</script>

<div class="tools" data-ui="controls">
  <section class="group"><span class="cap">Camera</span><div class="grid" class:three={viewer.spots.length > 0}>
    <button title="Reset view (R)" onclick={() => viewer.resetView()}><Icon name="rotate-ccw" /><span>Reset</span></button>
    <button class:active={viewer.follow} aria-pressed={viewer.follow} title="Toggle follow camera" onclick={() => viewer.toggleFollow()}><Icon name="crosshair" /><span>Follow {viewer.follow ? 'On' : 'Off'}</span></button>
    {#if viewer.spots.length}<button class:active={viewer.fitMode !== 'off'} title="Dating scenes: Fit Off / On / Snap" onclick={() => viewer.cycleFit()}><Icon name="maximize" /><span>Fit {viewer.fitMode === 'snap' ? 'Snap' : viewer.fitMode === 'on' ? 'On' : 'Off'}</span></button>{/if}
  </div></section>
  <section class="group"><span class="cap">Capture</span><div class="grid">
    <button title="Export high-resolution PNG snapshot" onclick={() => viewer.snapshot()}><Icon name="camera" /><span>Snapshot</span></button>
    <button title="Set as costume portrait; dashed 4:5 guide shows while hovered" onclick={onPortrait} onmouseenter={() => (viewer.portraitGuide = true)} onmouseleave={() => (viewer.portraitGuide = false)} onfocus={() => (viewer.portraitGuide = true)} onblur={() => (viewer.portraitGuide = false)}><Icon name="image" /><span>Portrait</span></button>
  </div></section>
  <section class="group"><span class="cap">View</span><div class="grid">
    <button class:active={viewer.playbackBar} aria-pressed={viewer.playbackBar} title="Show or hide playback bar" onclick={() => viewer.togglePlaybackBar()}><Icon name="panel-bottom" /><span>Playback bar</span></button>
    <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
    <div class="palette" role="group" aria-label="Background controls">
      <button bind:this={backgroundButton} aria-expanded={paletteOpen} aria-label="Background color" title="Background color" onclick={togglePalette}><span class="current" class:default={viewer.background === 'default'} class:black={viewer.background === 'black'} class:white={viewer.background === 'white'} class:skyblue={viewer.background === 'skyblue'} class:custom={viewer.background === 'custom'}></span><span>Background</span></button>
      {#if paletteOpen}<div bind:this={popover} class="popover" style={popoverStyle} role="group" aria-label="Background choices">
        {#each swatches as sw (sw.key)}<button class="swatch" class:chosen={viewer.background === sw.key} aria-label={sw.title} title={sw.title} onclick={() => { viewer.background = sw.key; paletteOpen = false }}><span class={sw.key}></span></button>{/each}
        <label class="swatch custom" class:chosen={viewer.background === 'custom'} title="Custom color"><span class="rainbow"></span><input type="color" bind:value={viewer.customBackground} oninput={() => (viewer.background = 'custom')} aria-label="Custom background color" /></label>
      </div>{/if}
    </div>
  </div></section>
</div>

<style>
  .tools { position: relative; flex: none; display: flex; flex-direction: column; gap: 7px; padding: 0.5rem; border-top: 1px solid var(--panel-line, var(--border-subtle)); }
  .group { display: flex; flex-direction: column; gap: 3px; }
  .cap { font-size: var(--fs-xs); font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: var(--text-dim); }
  .grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 4px; }
  .grid.three { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .grid > button, .palette > button { min-width: 0; min-height: 42px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2px; color: var(--text-muted); background: transparent; border: 0; border-radius: var(--radius-md); font-size: var(--fs-xs); }
  .grid button:hover, .grid button:focus-visible, .grid button.active, .palette > button:hover, .palette > button:focus-visible { color: var(--primary); background: var(--selected-bg); }
  .palette { position: static; width: 100%; }
  .palette > button { width: 100%; }
  .current { width: 14px; height: 14px; border: 1px solid var(--border-focus); border-radius: 50%; }
  .default { background: radial-gradient(circle, var(--viewport-1), var(--viewport-2)); }
  .black { background: var(--bg-dark); }.white { background: var(--text-main); }.skyblue { background: var(--cat-idle); }
  /* The rainbow gradient is a deliberate raw-colour exception, retained from the original custom swatch. */
  .rainbow, .current.custom { background: conic-gradient(#ff0055, #ff9900, #ffea00, #00ff66, #00ffff, #0066ff, #9900ff, #ff0055); }
  /* no border at all under the rainbow: a transparent rounded border leaves light seams at its edge (box-sizing keeps it 14px) */
  .current.custom { border: 0; }
  .popover { position: fixed; z-index: 1000; display: flex; flex-direction: column; gap: 5px; padding: 7px; background: var(--surface-2); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); box-shadow: var(--shadow-card); }
  .swatch { position: relative; width: 26px; height: 26px; padding: 3px; background: transparent; border: 1px solid var(--border-subtle); border-radius: 50%; }
  .swatch span { display: block; width: 100%; height: 100%; border-radius: 50%; }
  .swatch.chosen { border-color: var(--primary); }
  .swatch.custom input { position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0; cursor: pointer; }
  .swatch.custom .rainbow { pointer-events: none; }
</style>
