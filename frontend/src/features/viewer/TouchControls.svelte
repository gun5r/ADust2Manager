<script lang="ts">
  import Icon from '../../ui/Icon.svelte'
  import type { ViewerState } from './viewer.svelte'
  let { viewer }: { viewer: ViewerState } = $props()
  let lastGuideStyle = $state<'on' | 'alt'>('on')
  // the style the guide returns to when it is switched back on
  $effect(() => { if (viewer.prefs.guide !== 'off') lastGuideStyle = viewer.prefs.guide })
</script>

{#if !viewer.interact}
  <!-- Simulate is off (footer button): no menu -->
{:else if !viewer.menuOpen}
  <button class="ghost" data-ui="touch-menu-open" title="Open the touch menu" onclick={() => (viewer.menuOpen = true)}>Menu</button>
{:else}
<div class="touch" data-ui="touch-controls" role="group" aria-label="Dating scene touch controls">
  <button class="main" title="Hide this menu (a small Menu button stays)" onclick={() => (viewer.menuOpen = false)}>Hide</button>
  {#if true}
    <div class="group" title="Scene phase (idle pose and live spots)">
      <span class="cap">Scene</span>
      <div class="seg phases" style:--cols={Math.min(viewer.phases.length, 5)}>{#each viewer.phases as n}<button class:active={viewer.phase === n} onclick={() => viewer.setPhase(n)}>P{n}</button>{/each}</div>
    </div>
    {#if viewer.audio?.available}
      <div class="group">
        <span class="cap">Sound</span>
        {#if viewer.audio.cached}
          <div class="seg" title="Sound and voice controls">
            <button class:active={viewer.prefs.soundOn} aria-pressed={viewer.prefs.soundOn} title={viewer.prefs.soundOn ? 'Turn sound off' : 'Play the sounds the game plays with each touch'} onclick={() => { viewer.prefs.soundOn = !viewer.prefs.soundOn; if (!viewer.prefs.soundOn) viewer.stopSounds() }}>{viewer.prefs.soundOn ? 'On' : 'Off'}</button>
            {#if viewer.audio.voice?.length}
              <button class:active={viewer.prefs.voiceOn} aria-pressed={viewer.prefs.voiceOn} title={viewer.prefs.voiceOn ? 'Turn voice lines off' : 'Turn voice lines on'} onclick={() => (viewer.prefs.voiceOn = !viewer.prefs.voiceOn)}>{viewer.prefs.voiceOn ? 'Voice' : 'No voice'}</button>
            {/if}
          </div>
        {:else}
          <button class="dl" disabled={viewer.audioBusy} title="Download this scene's sounds from the game servers (kept in the dating audio cache)" onclick={() => viewer.downloadAudio()}>
            {#if viewer.audioBusy}Downloading…{:else}<Icon name="download" size={12} /> Audio (~{Math.max(1, Math.round(viewer.audio.download_mb ?? 1))} MB){/if}
          </button>
        {/if}
        {#if viewer.audio.cached}
          <label class="vol" title="Volume of the dating sounds ({Math.round(viewer.prefs.soundVolume * 100)}%)">
            <span>Volume</span>
            <input type="range" min="0" max="1.5" step="0.05" value={viewer.prefs.soundVolume} aria-label="Dating sound volume" oninput={(e) => viewer.setSoundVolume(Number(e.currentTarget.value))} />
          </label>
        {/if}
        {#if viewer.audioError}<span class="err" title={viewer.audioError}>Download failed</span>{/if}
      </div>
    {:else if viewer.audio}
      <span class="err" title="Tools > Dating > Simulator Data > Update from phone adds the sounds of scenes that came with a game update">No sounds for this scene yet</span>
    {/if}
    <div class="group">
      <span class="cap" title="The highlighted spot is the one a click triggers. Zones overlap, as in the game: Shift+click takes the next spot under the pointer">Spots</span>
      <!-- Spots visibility, reaction hiding, and hover filtering -->
      <div class="seg">
        <button class:active={viewer.prefs.spotsOn} aria-pressed={viewer.prefs.spotsOn} title={viewer.prefs.spotsOn ? 'Hide the touch spots' : 'Show the touch spots'} onclick={() => viewer.setSpotsOn(!viewer.prefs.spotsOn)}>{viewer.prefs.spotsOn ? 'On' : 'Off'}</button>
        <button class:active={viewer.prefs.spotsIdle} aria-pressed={viewer.prefs.spotsIdle} title="Hide the spots and the guide while a reaction plays" onclick={() => viewer.toggleSpotsIdle()}>Hide</button>
        <button class:active={viewer.prefs.spotsHover} aria-pressed={viewer.prefs.spotsHover} title="Hide the spots; each one shows only while the pointer is over it" onclick={() => viewer.toggleSpotsHover()}>Hover</button>
      </div>
      <!-- Areas, glow dots, and plain dots are exclusive styles. -->
      <div class="seg">
        <button class:active={viewer.prefs.spotStyle === 'numbers'} aria-pressed={viewer.prefs.spotStyle === 'numbers'} title="Each spot as its area, with its number" onclick={() => viewer.setSpotStyle('numbers')}>Areas</button>
        <button class:active={viewer.prefs.spotStyle === 'plain'} aria-pressed={viewer.prefs.spotStyle === 'plain'} title="A small dot per spot without the surrounding glow; an arrow shows which way a drag goes, a ring that it goes any way" onclick={() => viewer.setSpotStyle('plain')}>Dots</button>
        <button class:active={viewer.prefs.spotStyle === 'dots'} aria-pressed={viewer.prefs.spotStyle === 'dots'} title="Dots with a soft glow over each spot's zone" onclick={() => viewer.setSpotStyle('dots')}>Alt</button>
      </div>
      <div class="vol" title="Size of the spots as a share of the game's own size ({Math.round(viewer.prefs.spotScale * 100)}%)">
        <button class="fx" class:active={viewer.prefs.spotsFixed} aria-pressed={viewer.prefs.spotsFixed} title="Fixed: every spot a small fixed circle (shown and touched), so neighbouring spots hardly overlap; off: the game's own sizes, set by the slider" onclick={() => viewer.toggleSpotsFixed()}>{viewer.prefs.spotsFixed ? 'Fixed' : 'Size'}</button>
        <input type="range" min="0.25" max="1.5" step="0.05" value={viewer.prefs.spotScale} disabled={viewer.prefs.spotsFixed} aria-label="Spot size" oninput={(e) => viewer.setSpotScale(Number(e.currentTarget.value))} />
      </div>
      <div class="vol" title="How see-through the spots are ({Math.round(viewer.prefs.spotOpacity * 100)}% opaque)">
        <button class="fx" class:active={viewer.prefs.spotsSolid} aria-pressed={viewer.prefs.spotsSolid} title="Fixed: every spot completely opaque, even where it hides the animation behind it (for reading the spots, not for playing); off: see-through as the slider says" onclick={() => viewer.toggleSpotsSolid()}>{viewer.prefs.spotsSolid ? 'Fixed' : 'Opacity'}</button>
        <input type="range" min="0.1" max="1" step="0.05" value={viewer.prefs.spotOpacity} disabled={viewer.prefs.spotsSolid} aria-label="Spot opacity" oninput={(e) => viewer.setSpotOpacity(Number(e.currentTarget.value))} />
      </div>
    </div>
    <div class="group">
      <span class="cap" title="A circle over the spot to touch next to take the scene on to the next phase; after a missed touch it points at the way on from where the scene is">Guide</span>
      <div class="seg" title={viewer.gauge ? 'Not available in scenes with a score gauge yet' : 'Show or hide the guide; choose the standard or Alt style'}>
        <button class:active={viewer.prefs.guide !== 'off'} aria-pressed={viewer.prefs.guide !== 'off'} disabled={!!viewer.gauge} onclick={() => viewer.setGuide(viewer.prefs.guide === 'off' ? lastGuideStyle : 'off')}>{viewer.prefs.guide === 'off' ? 'Off' : 'On'}</button>
        <button class:active={viewer.prefs.guide === 'alt'} aria-pressed={viewer.prefs.guide === 'alt'} disabled={!!viewer.gauge} onclick={() => viewer.setGuide(viewer.prefs.guide === 'alt' ? 'on' : 'alt')}>Alt</button>
      </div>
      <span class="cap">Legend</span>
      <div class="seg" title="The list at the bottom left that says what each spot colour means">
        <button class:active={viewer.prefs.legendOn} aria-pressed={viewer.prefs.legendOn} onclick={() => (viewer.prefs.legendOn = true)}>Show</button>
        <button class:active={!viewer.prefs.legendOn} aria-pressed={!viewer.prefs.legendOn} onclick={() => (viewer.prefs.legendOn = false)}>Hide</button>
      </div>
    </div>
  {/if}
</div>
{/if}

<style>
  .ghost { position: absolute; top: 12px; left: 12px; z-index: 3; padding: 0.3rem 0.7rem; font-size: var(--fs-sm); font-weight: 700; color: rgba(203, 213, 225, 0.8); background: color-mix(in srgb, var(--surface-2) 35%, transparent); border: 1px solid var(--border-subtle); border-radius: 8px; opacity: 0.6; }
  .ghost:hover { opacity: 1; border-color: var(--primary); }
  /* fixed width: the menu looks the same for 2 or 7 phases; only the phase buttons adapt */
  .touch { width: 152px; position: absolute; top: 12px; left: 12px; z-index: 3; display: flex; flex-direction: column; align-items: flex-start; gap: 6px; padding: 6px; background: var(--scrim-soft); border: 0; border-radius: 10px; }
  .main { width: 100%; padding: 0.35rem 0.7rem; font-size: var(--fs-sm); font-weight: 700; color: var(--text-muted); background: var(--tint-2); border: 0; border-radius: 8px; white-space: nowrap; }
  .main:hover { background: var(--tint-4); }
  .group { display: flex; flex-direction: column; gap: 3px; width: 100%; }
  .cap { font-size: var(--fs-xs); font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: var(--text-muted); }
  .dl { width: 100%; padding: 0.25rem 0.55rem; font-size: var(--fs-sm); font-weight: 700; color: var(--primary); background: var(--selected-bg); border: 1px solid rgba(var(--primary-rgb), 0.35); border-radius: 8px; white-space: nowrap; }
  .dl:disabled { opacity: 0.6; cursor: progress; }
  .err { font-size: var(--fs-xs); color: var(--danger-text); }
  .vol { display: flex; align-items: center; gap: 0.4rem; width: 100%; font-size: var(--fs-xs); color: var(--text-muted); }
  .vol > span, .fx { flex: 0 0 3.9rem; }
  .fx { width: 3.9rem; padding: 0.1rem 0.4rem; font-size: var(--fs-xs); font-weight: 700; color: var(--text-muted); background: var(--tint-2); border: 0; border-radius: 6px; }
  .fx.active { background: var(--primary-solid); color: var(--on-primary); }
  .vol input { flex: 1 1 0; width: 0; min-width: 0; accent-color: var(--primary); }
  /* every row: equal buttons sharing the full width */
  .seg { width: 100%; display: grid; grid-auto-flow: column; grid-auto-columns: minmax(0, 1fr); gap: 2px; padding: 2px; background: var(--tint-2); border: 0; border-radius: 8px; }
  /* phases wrap every 5 inside the same block: later rows keep the same column width and 2px gap, so they read as one grid */
  .seg.phases { grid-auto-flow: row; grid-template-columns: repeat(var(--cols), minmax(0, 1fr)); }
  .seg button { min-width: 0; overflow: hidden; text-overflow: ellipsis; padding: 0.15rem 0.2rem; font-size: var(--fs-sm); font-weight: 600; color: var(--text-muted); border-radius: 5px; white-space: nowrap; }
  .seg button:hover { color: var(--text-main); }
  .seg button:disabled { opacity: 0.4; cursor: not-allowed; }
  .seg button.active { background: var(--primary-solid); color: var(--on-primary); font-weight: 700; }
</style>
