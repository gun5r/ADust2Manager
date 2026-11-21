<script lang="ts">
  import { CATEGORY_ICON } from '../../lib/categoryIcons'
  import CategoryPills from '../library/CategoryPills.svelte'
  import StatusTabs from '../library/StatusTabs.svelte'
  import type { StatusFilter } from '../../lib/filters'
  import Icon from '../../ui/Icon.svelte'
  import { characterPortraits } from '../../lib/portraits'
  import type { CategoryFilter, IndexMod } from '../../lib/classify'
  import { cancelPrefetchIntent, prefetchOnIntent } from '../../lib/prefetch'
  import type { Character } from '../../lib/api'
  import type { CharacterGroup } from '../../lib/grouping'
  import { byType } from '../../lib/viewerNav'
  import { modKey } from '../../lib/selection'
  import Avatar from '../../ui/Avatar.svelte'
  import PanelTabs from '../../ui/PanelTabs.svelte'
  import type { ViewerState } from './viewer.svelte'

  let { viewer, groups, roster, installed, selected, selectedCount, installedCount, uninstalledCount, category, onCategory, status, onStatus, onPick, onToggleSelect, packs = false }: {
    viewer: ViewerState
    groups: CharacterGroup[]
    roster: Character[]
    installed: Set<string>
    selected: Set<string>
    selectedCount: number
    installedCount: number
    uninstalledCount: number
    /** The same category / installed filters as the main window (one state, owned by the library). */
    category: CategoryFilter
    onCategory: (key: CategoryFilter) => void
    status: StatusFilter
    onStatus: (value: StatusFilter) => void
    onPick: (mod: IndexMod) => void
    onToggleSelect: (mod: IndexMod) => void
    /** Listing other multi-mod packs: no category pills, batch filters, file list or batch selection. */
    packs?: boolean
  } = $props()

  const imageOf = (name: string) => characterPortraits(roster.find((c) => c.name === name))
  const isInstalled = (m: IndexMod) => installed.has(m.name) || (m.id !== undefined && installed.has(m.id))
  /** Two views like the multimod panel: the selected character's costumes and mods, or the list of characters to pick another. */
  let view = $state<'costumes' | 'characters'>('costumes')
  /** The character on show: the picked one, else the previewed mod's. If the filters leave it without mods it stays picked (empty message) instead of jumping to another. */
  const wanted = $derived(viewer.expanded ?? viewer.mod?.character ?? groups[0]?.name ?? null)
  const current = $derived(groups.find((g) => g.name === wanted) ?? null)
  const pick = (name: string) => { viewer.expanded = name; view = 'costumes' }
  let scroller: HTMLDivElement | undefined = $state()
  $effect(() => {
    void viewer.mod?.folder_path
    void view
    void current?.name
    queueMicrotask(() => scroller?.querySelector('.mod.active, .crow.current')?.scrollIntoView({ block: 'nearest' }))
  })
  const label = (group: CharacterGroup, section: CharacterGroup['sections'][number]) => section.title.replace(`${group.name} - `, '')
</script>

<aside class="side" data-ui="viewer-right">
  <div class="characters">
    <PanelTabs label="Characters panel" value={view} onChange={(id) => (view = id as 'costumes' | 'characters')}
               tabs={[{ id: 'costumes', label: 'Costumes', icon: 'layout-grid' }, { id: 'characters', label: 'Characters', icon: 'users'}]} />
    {#if !packs}
    <div class="cats stat"><StatusTabs {status} {onStatus} installed={installedCount} uninstalled={uninstalledCount} selected={selectedCount} /></div>
    <div class="cats"><CategoryPills {category} {onCategory} /></div>
    {/if}
    {#if view === 'characters'}
      <div class="search">
        <span class="mag"><Icon name="search" size={13} /></span>
        <input type="text" placeholder="Search character..." bind:value={viewer.browserQuery} />
        <button class="reset" title="Reset search" aria-label="Reset search" onclick={() => (viewer.browserQuery = '')}><Icon name="x" size={13} /></button>
      </div>
    {/if}
    <div class="scroller" bind:this={scroller}>
      {#if view === 'characters'}
        {#each groups as group (group.name)}
          {@const picked = group.mods.filter((m) => selected.has(modKey(m))).length}
          <div class="crow" class:current={current?.name === group.name} role="button" tabindex="0" onclick={() => pick(group.name)} onkeydown={(e) => e.key === 'Enter' && pick(group.name)}>
            <span class="av"><Avatar name={group.name} urls={imageOf(group.name)} variant="card" /></span>
            <span class="cname" title={group.name}>{group.name}</span>
            {#if picked}<span class="badge picked" title="{picked} selected for batch">{picked}</span>{/if}
            <span class="badge" title="{group.mods.length} total mods">{group.mods.length}</span>
            <span class="chev">▶</span>
          </div>
        {:else}
          <span class="none">{viewer.browserQuery ? `No characters match "${viewer.browserQuery}".` : 'No mods found in this category.'}</span>
        {/each}
      {:else if current}
        <div class="who">
          <span class="av big"><Avatar name={current.name} urls={imageOf(current.name)} variant="card" /></span>
          <span class="wname" title={current.name}>{current.name}</span>
          <span class="badge" title="{current.mods.length} total mods">{current.mods.length}</span>
        </div>
        {#each current.sections as section (section.key)}
          <div class="csec">
          {#if current.name !== 'Others'}
            <div class="sep"><span class="stitle">{label(current, section)}</span><span class="line"></span></div>
          {/if}
          {#each byType(section.mods) as tg (tg.key)}
          <div class="tsep" style:--c="var(--cat-{tg.key})"><span>{tg.name}</span><i></i></div>
          {#each tg.mods as mod (modKey(mod))}
            <div class="mod" class:active={(packs ? viewer.pack : viewer.mod)?.folder_path === mod.folder_path} role="button" tabindex="0" title={packs ? 'Open this pack' : mod.is_multi ? 'A multimod: pick it to open the multimod selector' : 'Double-click to toggle batch selection'}
                 onpointerenter={() => prefetchOnIntent(mod)} onpointerleave={cancelPrefetchIntent} onclick={() => onPick(mod)} ondblclick={() => !packs && !mod.is_multi && onToggleSelect(mod)} onkeydown={(e) => e.key === 'Enter' && onPick(mod)}>
              <span class="mname" title={mod.name}>{mod.name}</span>
              {#if mod.is_multi && !packs}<span class="multitag" title="A multimod: opens the multimod selector">MULTI</span>{/if}
              <span class="marks">
                {#if isInstalled(mod)}<span class="mini ok" title="Installed"><Icon name="check" size={11} /></span>{/if}
                {#if selected.has(modKey(mod))}<span class="mini batch" title="Selected for Batch">●</span>{/if}
              </span>
            </div>
          {/each}
          {/each}
          </div>
        {/each}
      {:else}
        <div class="who">
          <span class="av big"><Avatar name={wanted ?? ''} urls={imageOf(wanted ?? '')} variant="card" /></span>
          <span class="wname" title={wanted ?? ''}>{wanted ?? 'No character'}</span>
        </div>
        <span class="none">{wanted ? `${wanted} has no mods with these filters.` : 'No mods match these filters.'}</span>
      {/if}
    </div>
  </div>

  {#if !packs}
  <div class="files" class:open={viewer.filesOpen}>
    <div class="files-head" role="button" tabindex="0" title="Click to show/hide Mod Files" onclick={() => (viewer.filesOpen = !viewer.filesOpen)} onkeydown={(e) => e.key === 'Enter' && (viewer.filesOpen = !viewer.filesOpen)}>
      <span class="ftitle"><Icon name="file-text" size={13} /> MOD FILES ( {viewer.mod?.files.length ?? 0} )</span>
      <span class="fchev">{viewer.filesOpen ? '▼' : '▲'}</span>
    </div>
    {#if viewer.filesOpen}
      <div class="flist">
        {#each viewer.mod?.files ?? [] as file}
          {@const ext = (file.split('.').pop() ?? '').toLowerCase()}
          <div class="file {ext}"><span class="ext">.{ext}</span><span class="fname" title={file}>{file}</span></div>
        {/each}
      </div>
    {/if}
  </div>
  {/if}
</aside>

<style>
  .multitag { flex-shrink: 0; padding: 0 5px; font-size: var(--fs-xs); font-weight: 800; color: var(--cat-multi); background: color-mix(in srgb, var(--cat-multi) 15%, transparent); border: 1px solid color-mix(in srgb, var(--cat-multi) 40%, transparent); border-radius: 4px; }
  .side { width: 265px; flex: 0 0 auto; display: flex; flex-direction: column; min-height: 0; background: transparent; border-left: 1px solid var(--panel-line, var(--border-subtle)); }
  .characters { flex: 1; min-height: 0; display: flex; flex-direction: column; }
  .mag { position: absolute; left: 1.05rem; top: 50%; transform: translateY(-50%); display: flex; color: var(--text-dim); pointer-events: none; z-index: 1; }
  .search { position: relative; display: flex; gap: 0.35rem; align-items: center; padding: 0.5rem 0.55rem 0.4rem; flex-shrink: 0; }
  .search input { flex: 1; min-width: 0; height: 26px; padding: 0 0.55rem 0 1.7rem; font-size: var(--fs-sm); color: var(--text-main); background: color-mix(in srgb, var(--surface-2) 85%, transparent); border: 1px solid var(--border-subtle); border-radius: 5px; outline: none; }
  .search input:focus { border-color: var(--primary); }
  .reset { width: 26px; height: 26px; font-size: var(--fs-sm); color: var(--text-muted); background: var(--tint-2); border: 1px solid var(--border-subtle); border-radius: 5px; }
  .reset:hover { color: var(--danger-text); border-color: color-mix(in srgb, var(--danger) 45%, transparent); }
  .cats { padding: 0.45rem 0.5rem; flex-shrink: 0; }
  .cats.stat { padding-bottom: 0; }
  .scroller { flex: 1; min-height: 0; overflow-y: auto; padding: 0.45rem; display: flex; flex-direction: column; gap: 0.15rem; }
  .crow { display: flex; align-items: center; gap: 0.5rem; padding: 0.4rem 0.55rem; border-radius: var(--radius-md); cursor: pointer; flex-shrink: 0; }
  .crow:hover { background: var(--tint-2); }
  .crow.current { background: var(--selected-bg); box-shadow: inset 2px 0 0 var(--primary); }
  .av { width: 26px; height: 26px; flex-shrink: 0; color: var(--text-muted); font-weight: 700; border-radius: 50%; overflow: hidden; border: 0; background: var(--surface-3); font-size: var(--fs-xs); }
  .av.big { width: 34px; height: 34px; }
  .av :global(.avatar) { border-radius: 50%; font-size: var(--fs-xs); }
  .cname { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: var(--fs-md); font-weight: 600; }
  .badge { flex-shrink: 0; padding: 1px 6px; font-size: var(--fs-xs); font-weight: 700; color: var(--text-muted); background: var(--tint-3); border-radius: 10px; }
  .badge.picked { color: var(--on-primary); background: var(--primary-solid); }
  .chev { flex-shrink: 0; font-size: var(--fs-xs); color: var(--text-muted); }
  .who { display: flex; align-items: center; gap: 0.55rem; padding: 0.3rem 0.35rem 0.5rem; flex-shrink: 0; }
  .wname { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: var(--fs-lg); font-weight: 700; color: var(--text-main); }
  .csec { display: flex; flex-direction: column; flex-shrink: 0; }
  .sep { position: sticky; top: -0.45rem; z-index: 1; display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem 0.55rem 0.45rem; margin-top: 0.5rem; background: var(--panel-fill, var(--surface-2)); border-left: 3px solid var(--primary); border-radius: 0 var(--radius-sm) var(--radius-sm) 0; }
  .stitle { font-size: var(--fs-lg); font-weight: 700; letter-spacing: 0.01em; color: var(--text-main); white-space: nowrap; }
  .line { display: none; }
  .tsep { display: flex; align-items: center; gap: 0.5rem; padding: 0.4rem 0.6rem 0.15rem; font-size: var(--fs-xs); font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--text-main); }
  .tsep i { flex: 1; height: 2px; border-radius: 2px; background: color-mix(in srgb, var(--c) 70%, transparent); }
  .mod { display: flex; align-items: center; justify-content: space-between; gap: 0.35rem; padding: 0.35rem 0.5rem; font-size: var(--fs-sm); font-weight: 500; color: var(--text-muted); border-radius: 5px; cursor: pointer; flex-shrink: 0; }
  .mod:hover { background: var(--tint-2); color: var(--text-main); }
  .mod.active { background: var(--selected-bg); color: var(--text-main); font-weight: 600; }
  .mname { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .marks { display: flex; gap: 3px; flex-shrink: 0; }
  .mini { font-size: var(--fs-xs); font-weight: 800; }
  .mini.ok { color: var(--ok-text); } .mini.batch { color: var(--primary); }
  .none { padding: 0.75rem; text-align: center; font-size: var(--fs-sm); color: var(--text-dim); }
  .files { flex-shrink: 0; background: transparent; border-top: 1px solid var(--panel-line, var(--border-subtle)); display: flex; flex-direction: column; max-height: 40%; }
  .files-head { display: flex; align-items: center; justify-content: space-between; padding: 0.45rem 0.65rem; letter-spacing: 0.04em; cursor: pointer; font-size: var(--fs-sm); font-weight: 700; color: var(--text-dim); }
  .ftitle { display: flex; gap: 0.35rem; } .fchev { font-size: var(--fs-xs); }
  .flist { overflow-y: auto; display: flex; flex-direction: column; gap: 0.3rem; padding: 0.45rem; }
  .file { display: flex; align-items: center; gap: 0.35rem; padding: 0.3rem 0.5rem; font-size: var(--fs-sm); background: var(--tint-1); border-radius: 4px; }
  .ext { font-weight: 700; opacity: 0.85; flex-shrink: 0; }
  .fname { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .file { color: var(--text-muted); }
  @media (max-width: 1100px) { .side { width: 220px; } }
  @media (max-width: 760px) { .side { display: none; } }
</style>
