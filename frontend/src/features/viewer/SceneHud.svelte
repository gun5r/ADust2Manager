<script lang="ts">
  import type { ViewerState } from './viewer.svelte'
  import { toolIconUrl } from '../../lib/dating'
  let { viewer }: { viewer: ViewerState } = $props()
  /** Tool ids whose icon could not be loaded (no internet on first use, older game): their button shows the text instead. */
  let brokenIcons = $state(new Set<number>())
  const percent = $derived(viewer.gauge ? Math.min(100, (viewer.gauge.score / Math.max(viewer.gauge.max, 1)) * 100) : 0)
</script>

<!-- Always on screen (the touch menu may be hidden): the phase's gauge down the right edge, its tools in the bottom right corner -->
{#if viewer.gauge}
  <div class="gauge" data-ui="gauge" title="Score gauge {Math.floor(viewer.gauge.score)} / {viewer.gauge.max}: touches fill it, spots work only inside their range, the full spots appear at the top" role="meter" aria-valuenow={Math.floor(viewer.gauge.score)} aria-valuemax={viewer.gauge.max} aria-label="Score gauge">
    <div class="fill" style:height="{percent}%"></div>
    {#each [25, 50, 75] as tick}<i class="tick" style:bottom="{tick}%"></i>{/each}
  </div>
  <div class="reading" data-ui="gauge-reading" aria-hidden="true">{Math.floor(viewer.gauge.score)}<small>/{viewer.gauge.max}</small></div>
{/if}
{#if viewer.tools.length > 1 || (viewer.tools.length === 1 && viewer.tools[0].id !== 0) || viewer.tilts.length > 0}
  <div class="tools" data-ui="tools" role="group" aria-label="Tool">
    {#each viewer.tools.length > 1 || viewer.tools[0]?.id !== 0 ? viewer.tools : [] as t (t.id)}
      <button class:active={viewer.tool === t.id} class:guided={viewer.prefs.guide !== 'off' && viewer.guideTool === t.id} aria-pressed={viewer.tool === t.id} title="Tool {t.id === 0 ? 'Hand' : t.id}: changes the skin and which spots can be used" onclick={() => viewer.setTool(t.id)}>{#if brokenIcons.has(t.id)}{t.id === 0 ? 'Hand' : t.id}{:else}<img class="icon" src={toolIconUrl(t.id)} alt={t.id === 0 ? 'Hand' : `Tool ${t.id}`} draggable="false" onerror={() => (brokenIcons = new Set(brokenIcons).add(t.id))} />{/if}</button>
    {/each}
    {#each viewer.tilts as tilt (tilt.id)}
      <button class:guided={viewer.prefs.guide !== 'off' && viewer.guideTilts.includes(tilt.id)} title="Tilt the phone: the game's gyro spots cannot be done with a pointer, this plays their reaction (with any tool in hand)" aria-label={tilt.label} onclick={() => viewer.tilt(tilt.id)}>{#if tilt.tool === null || brokenIcons.has(tilt.tool)}{tilt.label}{:else}<img class="icon" src={toolIconUrl(tilt.tool)} alt="" draggable="false" onerror={() => (brokenIcons = new Set(brokenIcons).add(tilt.tool ?? 0))} />{#if tilt.label !== 'Tilt'}<b>{tilt.label.slice(-1)}</b>{/if}{/if}</button>
    {/each}
  </div>
{/if}

<style>
  .gauge { position: absolute; right: 10px; top: 40px; bottom: 90px; width: 12px; z-index: 3; display: flex; align-items: flex-end; border-radius: 6px; background: color-mix(in srgb, var(--surface-2) 45%, transparent); border: 1px solid rgba(255, 255, 255, 0.22); overflow: hidden; pointer-events: none; }
  .tick { position: absolute; left: 0; right: 0; height: 1px; background: rgba(255, 255, 255, 0.35); }
  .reading { position: absolute; right: 6px; top: 14px; z-index: 3; min-width: 20px; padding: 1px 6px; font: 700 var(--fs-sm) var(--font-mono, monospace); text-align: center; color: var(--text-main); background: color-mix(in srgb, var(--surface-2) 45%, transparent); border: 1px solid rgba(255, 255, 255, 0.22); border-radius: 8px; pointer-events: none; }
  .reading small { font-weight: 500; opacity: 0.65; }
  .fill { width: 100%; background: linear-gradient(0deg, var(--primary), var(--cat-dating)); opacity: 0.85; transition: height 0.15s linear; }
  .tools { position: absolute; right: 12px; bottom: 14px; z-index: 3; display: flex; gap: 8px; }
  .tools button { position: relative; display: grid; place-items: center; width: 62px; height: 50px; padding: 0 0.4rem; font-size: var(--fs-lg); font-weight: 700; color: var(--text-main); background: color-mix(in srgb, var(--surface-2) 40%, transparent); border: 1px solid rgba(255, 255, 255, 0.28); border-radius: 12px; opacity: 0.5; }
  .tools button:hover { opacity: 0.9; border-color: var(--primary); }
  .tools button .icon { display: block; width: 38px; height: 38px; object-fit: contain; pointer-events: none; }
  .tools button b { position: absolute; right: 5px; bottom: 2px; font-size: var(--fs-xs); }
  .tools button.guided { opacity: 1; border-color: var(--warn-text); box-shadow: 0 0 12px var(--warn-text); animation: guided 1.1s ease-in-out infinite; }
  @keyframes guided { 50% { box-shadow: 0 0 2px var(--warn-text); } }
  .tools button.active { opacity: 0.75; background: rgba(var(--primary-rgb), 0.4); border-color: var(--primary); }
</style>
