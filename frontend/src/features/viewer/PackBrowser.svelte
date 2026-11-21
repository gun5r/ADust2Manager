<script lang="ts">
  import Icon from '../../ui/Icon.svelte'
  import { assetUrl } from '../../lib/spine'
  import { splitPath } from '../../lib/multi'
  import { clashes } from '../../lib/multi'
  import type { ViewerState } from './viewer.svelte'

  let { viewer }: { viewer: ViewerState } = $props()
  const isChosen = (path: string) => viewer.chosen.some((c) => c.full_path === path)
</script>

<aside class="side" data-ui="pack-browser">
  <div class="search">
    <input type="search" placeholder="Filter variants…" bind:value={viewer.packQuery} />
    <button class="reset" title="Clear filter" aria-label="Clear filter" onclick={() => (viewer.packQuery = '')}><Icon name="x" size={13} /></button>
  </div>
  <div class="tree">
    {#if viewer.packLoading}<p class="none">Reading pack…</p>{/if}
    {#if viewer.packError}<p class="none err">{viewer.packError}</p>{/if}
    {#each viewer.visibleCategories as category (category.id)}
      <button class="sep cat" onclick={() => (viewer.collapsed[category.id] = !viewer.collapsed[category.id])}>
        <span class="light"></span><span class="stitle">{category.name}</span><span class="line"></span><span class="chev" class:open={!viewer.collapsed[category.id]}>▶</span>
      </button>
      {#if !viewer.collapsed[category.id]}
        {#each category.options as option (option.id)}
          {#if category.options.length > 1}<div class="sep opt"><span class="light"></span><span class="stitle">{option.name}</span><span class="line"></span></div>{/if}
          {#each option.variants as variant (variant.full_path)}
            {@const clash = !isChosen(variant.full_path) && clashes(viewer.chosen, variant).length > 0}
            <div class="variant" class:active={viewer.variant?.full_path === variant.full_path} class:chosen={isChosen(variant.full_path)}>
              <button class="pick" title="{variant.name} (double-click, Space or the Select button to choose it for install)" onclick={() => viewer.pickVariant(variant)} ondblclick={() => viewer.toggleChosen(variant)}>
                <span class="name">{variant.name}</span>
                <small>{variant.asset_key}</small>
              </button>
              {#if isChosen(variant.full_path)}<span class="chosen" title="Chosen for install">Selected</span>{/if}
              {#if clash}<span class="clash" title="Picking this replaces another chosen variant for the same asset">replaces</span>{/if}
            </div>
          {/each}
        {/each}
      {/if}
    {:else}
      {#if !viewer.packLoading}<p class="none">No variants match.</p>{/if}
    {/each}
  </div>

  <div class="files" class:open={viewer.previewsOpen}>
    <div class="files-head" role="button" tabindex="0" title="Click to show/hide the pack's preview pictures" onclick={() => (viewer.previewsOpen = !viewer.previewsOpen)} onkeydown={(e) => e.key === 'Enter' && (viewer.previewsOpen = !viewer.previewsOpen)}>
      <span class="ftitle"><Icon name="images" size={13} /> PREVIEWS ( {viewer.packPreviews.length} )</span>
      <span class="fchev">{viewer.previewsOpen ? '▼' : '▲'}</span>
    </div>
    {#if viewer.previewsOpen}
      <div class="flist">
        {#each viewer.packPreviews as pic, i (pic.full_path)}
          {@const [dir, file] = splitPath(pic.full_path)}
          {#if i === 0 || viewer.packPreviews[i - 1].folder !== pic.folder}
            <div class="sep"><span class="light"></span><span class="stitle" title={pic.folder}>{pic.folder || 'Pack root'}</span><span class="line"></span></div>
          {/if}
          <button class="pic" class:active={viewer.shownPreview === pic.full_path} title={viewer.shownPreview === pic.full_path ? 'Click again to clear the preview' : pic.rel_path}
                  onclick={() => viewer.togglePreview(pic.full_path)}>
            <img src={assetUrl(dir, file)} alt="" loading="lazy" />
            <span class="pname">{pic.name}</span>
          </button>
        {:else}
          <p class="none">This pack has no preview pictures.</p>
        {/each}
      </div>
    {/if}
  </div>
</aside>

<style>
  .side { width: 265px; flex: 0 0 auto; display: flex; flex-direction: column; min-height: 0; background: transparent; border-left: 0; }
  .search { display: flex; gap: 0.35rem; align-items: center; padding: 0.5rem 0.55rem 0.4rem; flex-shrink: 0; }
  .search input { flex: 1; min-width: 0; height: 26px; padding: 0 0.55rem; font-size: var(--fs-sm); color: var(--text-main); background: color-mix(in srgb, var(--surface-2) 85%, transparent); border: 1px solid var(--border-subtle); border-radius: 5px; outline: none; }
  .search input:focus { border-color: var(--primary); }
  .reset { width: 26px; height: 26px; font-size: var(--fs-sm); color: var(--text-muted); background: var(--tint-2); border: 1px solid var(--border-subtle); border-radius: 5px; }
  .reset:hover { color: var(--danger-text); border-color: color-mix(in srgb, var(--danger) 45%, transparent); }
  .tree { flex: 1; min-height: 0; overflow-y: auto; padding: 0.45rem; display: flex; flex-direction: column; gap: 2px; }
  .sep { display: flex; align-items: center; gap: 0.5rem; width: 100%; padding: 0.3rem 0.65rem; margin: 0.25rem 0 0.15rem; background: var(--panel-fill, var(--surface-1)); text-align: left; }
  .cat { position: sticky; top: 0; z-index: 1; cursor: pointer; }
  .light { display: none; }
  .stitle { min-width: 0; overflow: hidden; text-overflow: ellipsis; font-size: var(--fs-md); font-weight: 750; letter-spacing: 0.02em; color: var(--text-muted); white-space: nowrap; }
  .line { flex: 1; min-width: 12px; height: 1px; background: var(--border-subtle); }
  .opt .stitle { font-size: var(--fs-xs); color: var(--text-muted); } .opt .light { width: 5px; height: 5px; }
  .chev { font-size: var(--fs-xs); color: var(--text-muted); transition: transform 0.15s ease; } .chev.open { transform: rotate(90deg); }
  .variant { display: flex; align-items: center; gap: 0.4rem; padding: 0 0.4rem 0 0.7rem; border-radius: 5px; }
  .variant:hover { background: var(--tint-2); }
  .variant.chosen { box-shadow: inset 3px 0 0 var(--ok-text); background: color-mix(in srgb, var(--ok) 10%, transparent); }
  .chosen { flex-shrink: 0; padding: 0 5px; font-size: var(--fs-xs); font-weight: 700; color: var(--ok-text); background: color-mix(in srgb, var(--ok) 12%, transparent); border: 1px solid color-mix(in srgb, var(--ok) 35%, transparent); border-radius: 4px; }
  .variant.active { background: var(--selected-bg); }
  .pick { flex: 1; min-width: 0; display: flex; flex-direction: column; text-align: left; padding: 0.35rem 0.1rem; color: var(--text-muted); }
  .active .pick { color: var(--text-main); font-weight: 600; }
  .name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: var(--fs-sm); }
  small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-family: var(--font-mono); font-size: var(--fs-xs); color: var(--text-dim); }
  .clash { flex-shrink: 0; padding: 0 5px; font-size: var(--fs-xs); font-weight: 700; color: var(--warn-text); background: color-mix(in srgb, var(--warn) 12%, transparent); border: 1px solid color-mix(in srgb, var(--warn) 30%, transparent); border-radius: 4px; }
  .none { padding: 0.75rem; text-align: center; font-size: var(--fs-sm); color: var(--text-dim); }
  .err { color: var(--warning); }
  .files { flex-shrink: 0; background: transparent; border-top: 1px solid var(--panel-line, var(--border-subtle)); display: flex; flex-direction: column; max-height: 45%; }
  .files-head { display: flex; align-items: center; justify-content: space-between; padding: 0.45rem 0.65rem; letter-spacing: 0.04em; cursor: pointer; font-size: var(--fs-sm); font-weight: 700; color: var(--text-dim); }
  .ftitle { display: flex; gap: 0.35rem; } .fchev { font-size: var(--fs-xs); }
  .flist { overflow-y: auto; display: flex; flex-direction: column; gap: 0.3rem; padding: 0.45rem; }
  .pic { display: flex; align-items: center; gap: 0.5rem; padding: 0.3rem; text-align: left; color: var(--text-muted); background: var(--tint-1); border: 1px solid transparent; border-radius: 4px; }
  .pic:hover { background: var(--tint-3); }
  .pic.active { background: var(--selected-bg); border-color: var(--primary); color: var(--text-main); }
  .pic img { width: 44px; height: 44px; flex-shrink: 0; object-fit: cover; border-radius: 3px; background: #000; }
  .pname { min-width: 0; display: flex; flex-direction: column; overflow: hidden; font-size: var(--fs-sm); }
  .pname { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  @media (max-width: 1100px) { .side { width: 220px; } }
  @media (max-width: 760px) { .side { display: none; } }
</style>
