<script lang="ts">
  import type { ViewerState } from './viewer.svelte'
  import Icon from '../../ui/Icon.svelte'
  let { viewer }: { viewer: ViewerState } = $props()
  // Closed by default: the slot names are for modders, the animation list and the canvas matter more. The choice is remembered.
  const KEY = 'adust2.viewerLayersOpen'
  const saved = (() => { try { return localStorage.getItem(KEY) === '1' } catch { return false } })()
  let open = $state(saved)
  function toggle() {
    open = !open
    try { localStorage.setItem(KEY, open ? '1' : '0') } catch { /* private window: the panel simply starts closed next time */ }
  }
</script>

<div class="sub" class:open>
  <div class="header">
    <button class="title" aria-expanded={open} title={open ? 'Hide the layer list' : 'Show the layer list'} onclick={toggle}>
      <Icon name={open ? 'chevron-up' : 'chevron-down'} size={13} />
      <span>Layers ({viewer.layers.length ? `${viewer.visibleLayerCount} / ${viewer.layers.length}` : 0})</span>
    </button>
    {#if open}
      <div class="buttons">
        <button class="text-xs" title="Toggle Show/Hide All Layers" onclick={() => viewer.toggleAllLayers()}>All</button>
        <button class="text-xs" title="Reset all layers to visible" onclick={() => viewer.resetLayers()}>Reset</button>
      </div>
    {/if}
  </div>
  {#if open}
    <div class="search"><input type="text" placeholder="Filter layers..." bind:value={viewer.layerQuery} /></div>
    <div class="list" data-ui="layers">
      {#each viewer.visibleLayers as row (row.name)}
        {@const hidden = viewer.hidden.has(row.name)}
        <div class="row" class:hidden role="button" tabindex="0" title="Slot: {row.name} (Click to {hidden ? 'enable' : 'disable'})"
             onclick={() => viewer.toggleLayer(row.name)} onkeydown={(e) => e.key === 'Enter' && viewer.toggleLayer(row.name)}>
          <span class="light" class:off={hidden}></span>
          <span class="name" title={row.name}>{row.name}</span>
          {#if row.tag}<span class="tag" title={row.tag}>{row.tag}</span>{/if}
        </div>
      {:else}
        <span class="empty">{viewer.layers.length ? 'No layer matches.' : 'No animation running'}</span>
      {/each}
    </div>
  {/if}
</div>

<style>
  .sub { display: flex; flex-direction: column; min-height: 0; flex: 0 0 auto; background: transparent; border-bottom: 1px solid var(--panel-line, var(--border-subtle)); }
  .sub.open { height: 320px; }
  .header { display: flex; align-items: center; padding: 0.5rem 0.75rem; font-size: var(--fs-sm); font-weight: 700; letter-spacing: 0.08em;
    text-transform: uppercase; color: var(--text-dim); flex-shrink: 0; }
  .title { display: flex; align-items: center; gap: 0.4rem; color: inherit; text-transform: inherit; letter-spacing: inherit; font: inherit; }
  .title:hover { color: var(--text-main); }
  .buttons { margin-left: auto; display: flex; gap: 0.35rem; align-items: center; }
  .text-xs { padding: 2px 6px; font-size: var(--fs-xs); font-weight: 400; color: var(--text-muted); background: transparent; border: 1px solid var(--border-subtle);
    border-radius: 4px; text-transform: none; letter-spacing: 0; }
  .text-xs:hover { color: var(--primary); border-color: rgba(var(--primary-rgb), 0.4); }
  .search { padding: 0.2rem 0.5rem 0.4rem; flex-shrink: 0; }
  .search input { width: 100%; height: 22px; padding: 4px 8px; font-size: var(--fs-sm); color: var(--text-main); background: color-mix(in srgb, var(--surface-2) 60%, transparent); border: 1px solid var(--border-subtle); border-radius: 8px; outline: none; }
  .search input:focus { border-color: var(--primary); }
  .list { flex: 1; min-height: 0; overflow-y: auto; padding: 0.35rem; display: flex; flex-direction: column; gap: 3px; }
  .row { display: flex; align-items: center; gap: 0.4rem; padding: 0.3rem 0.55rem; font-size: var(--fs-sm); background: transparent; border: 0;
    border-radius: 6px; cursor: pointer; flex-shrink: 0; transition: background 0.12s; }
  .row:hover { background: var(--tint-2); }
  .row.hidden { opacity: 0.55; }
  .row.hidden .name { text-decoration: line-through; color: var(--text-dim); }
  .light { width: 9px; height: 9px; margin: 0 3px; flex-shrink: 0; border-radius: 50%; background: var(--primary-solid); border: 0; box-shadow: none; }
  .light.off { background: transparent; border-color: #6b6b6b; }
  .name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-family: var(--font-mono); font-size: var(--fs-xs); }
  .tag { flex-shrink: 0; max-width: 74px; padding: 1px 4px; font-size: var(--fs-xs); color: var(--text-muted); background: var(--tint-2); border-radius: 3px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-family: var(--font-mono); }
  .empty { padding: 1rem; text-align: center; font-size: var(--fs-sm); color: var(--text-dim); }
</style>
