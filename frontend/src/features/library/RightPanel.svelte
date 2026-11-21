<script lang="ts">
  import type { CategoryFilter } from '../../lib/classify'
  import { BADGE_STYLE, type BadgeKind } from '../../lib/categoryIcons'
  import CategoryPills from './CategoryPills.svelte'
  import StatusTabs from './StatusTabs.svelte'
  import Icon from '../../ui/Icon.svelte'
  import Badge from '../../ui/Badge.svelte'
  import type { IndexMod } from '../../lib/classify'
  import type { FilterCounts, StatusFilter } from '../../lib/filters'

  let { templates, template, status, category, counts, detected, selected, selectedMods = [], selectedLabel = (m: IndexMod) => m.name, onRemove = () => {}, installedCount, showLegend, onHideLegend, listMode, onListMode, onTemplate, onLoad, onSave, onSaveInstalled, onDelete, onStatus, onCategory, onReset, onSelectAll, onDeselectAll, onPrepare }: {
    templates: string[]
    template: string
    status: StatusFilter
    category: CategoryFilter
    counts: FilterCounts
    detected: number
    selected: number
    selectedMods?: IndexMod[]
    /** The short "Character - Costume = Type" line of a selected mod (the list shows it unless File Names is on). */
    selectedLabel?: (mod: IndexMod) => string
    onRemove?: (mod: IndexMod) => void
    onTemplate: (name: string) => void
    onLoad: () => void
    onSave: () => void
    onSaveInstalled: () => void
    installedCount: number
    showLegend: boolean
    listMode: boolean
    onListMode: () => void
    onHideLegend: () => void
    onDelete: () => void
    onStatus: (value: StatusFilter) => void
    onCategory: (value: CategoryFilter) => void
    onReset: () => void
    onSelectAll: () => void
    onDeselectAll: () => void
    onPrepare: () => void
  } = $props()

  /** The legend is fixed: it shows what each badge is, with # where the number goes. */
  const LEGEND: BadgeKind[] = ['idle', 'cut', 'rest', 'installed', 'queued']
  const LEGEND_LABEL: Record<BadgeKind, string> = { idle: 'Idle', cut: 'Skills', rest: 'Others', installed: 'Installed', queued: 'In queue' }
  const filtered = $derived(status !== 'all' || category !== 'all')
  let tplOpen = $state(false)
  let fileNames = $state(false)
</script>

<aside class="panel" data-ui="right-panel">
  <div class="seg" role="group" aria-label="Library view">
    <button class:on={!listMode} aria-pressed={!listMode} title="Costume portraits" onclick={onListMode}><Icon name="layout-grid" size={14} /> Costumes</button>
    <button class:on={listMode} aria-pressed={listMode} aria-label="List Mode" title="Show the plain mod list instead of the costume portraits" onclick={onListMode}><Icon name="list" size={14} /> List</button>
  </div>

  <section class="section">
    <div class="head"><span class="title">Filter</span>{#if filtered}<button class="link" onclick={onReset}>Reset Filters</button>{/if}</div>
    <StatusTabs {status} {onStatus} installed={counts.installed} uninstalled={counts.uninstalled} {selected} />
    <CategoryPills {category} {onCategory} />
  </section>

  <section class="section">
    <button class="disclose" aria-expanded={tplOpen} onclick={() => (tplOpen = !tplOpen)}>
      <span class="title">Templates</span><Icon name={tplOpen ? 'chevron-up' : 'chevron-down'} size={14} />
    </button>
    {#if tplOpen}
      <div class="row">
        <select value={template} onchange={(e) => onTemplate(e.currentTarget.value)} aria-label="Template">
          <option value="">-- Select Template --</option>
          {#each templates as name}<option value={name}>{name}</option>{/each}
        </select>
        <button class="btn" onclick={onLoad} title="Select the mods of the chosen template">Load</button>
        {#if template}<button class="btn danger" onclick={onDelete} title="Delete this template" aria-label="Delete this template"><Icon name="trash-2" size={14} /></button>{/if}
      </div>
      <div class="row">
        <button class="btn grow" disabled={installedCount === 0} onclick={onSaveInstalled} title="Save every mod marked as installed ({installedCount}) as a template"><Icon name="hard-drive" size={14} /> Save installed</button>
        <button class="btn grow" onclick={onSave} title="Save currently selected mods as a reusable template"><Icon name="save" size={14} /> Save</button>
      </div>
    {/if}
  </section>

  <section class="section picked" data-ui="selected-list">
    <div class="head"><span class="title">Selected</span>{#if selectedMods.length}<button class="link names" aria-pressed={fileNames} title={fileNames ? 'Show the costume and type of each selected mod' : 'Show the file names of the selected mods'} onclick={() => (fileNames = !fileNames)}>File Names</button>{/if}</div>
    {#if selectedMods.length}
      <ul>
        {#each selectedMods as mod (mod.folder_path + mod.name)}
          <li><span class="nm" title={mod.name}>{fileNames ? mod.name : selectedLabel(mod)}</span>
            <button class="rm" title="Remove from selection" aria-label="Remove {mod.name} from selection" onclick={() => onRemove(mod)}><Icon name="x" size={12} /></button></li>
        {/each}
      </ul>
    {:else}<div class="empty"><Icon name="list-checks" size={26} /><span class="et">No mods selected</span><span>Click mods, or use Select All</span></div>{/if}
  </section>

  <div class="bottom">
    {#if showLegend}
      <div class="legend" data-ui="legend" aria-label="Legend of the colours and numbers">
        <button class="hide" title="Hide this legend (it can be shown again in Settings / Tools > Settings)" aria-label="Hide the legend" onclick={onHideLegend}><Icon name="x" size={12} /> Hide</button>
        <div class="ltitle">Color badges</div>
        <div class="lgrid">
          {#each LEGEND as kind}
            <div class="lrow" title="# {BADGE_STYLE[kind].label}"><Badge {kind} n="#" /><span>{LEGEND_LABEL[kind]}</span></div>
          {/each}
        </div>
      </div>
    {/if}
    <div class="sel">
      <span><strong>{selected}</strong> selected <em>of {detected}</em></span>
      <span class="links"><button class="link" onclick={onSelectAll}>Select All</button><button class="link" disabled={selected === 0} onclick={onDeselectAll}>Deselect All</button></span>
    </div>
    <button class="prepare" disabled={selected === 0} onclick={onPrepare}><Icon name="rocket" size={16} /> Prepare for Install</button>
  </div>
</aside>

<style>
  .panel { display: flex; flex-direction: column; gap: 1.35rem; min-height: 0; padding: 0.9rem; overflow-y: auto; background: var(--surface-1);
    border: 1px solid var(--border-subtle); border-radius: var(--radius-md); }
  .section { display: flex; flex-direction: column; gap: 0.55rem; }
  .head { display: flex; align-items: center; justify-content: space-between; min-height: 18px; }
  .title { font-size: var(--fs-sm); font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--text-muted); }
  .names { margin-right: auto; margin-left: 0.6rem; } .names[aria-pressed='true'] { color: var(--primary); }
  .link { font-size: var(--fs-sm); font-weight: 600; color: var(--text-muted); } .link:hover:not(:disabled) { color: var(--primary); } .link:disabled { opacity: 0.4; cursor: default; }

  .seg { display: grid; grid-template-columns: 1fr 1fr; padding: 3px; gap: 3px; background: var(--surface-1); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); }
  .seg button { display: inline-flex; align-items: center; justify-content: center; gap: 0.4rem; padding: 0.4rem 0; font-size: var(--fs-md); font-weight: 600; color: var(--text-muted); border-radius: var(--radius-sm); }
  .seg button:hover { color: var(--text-main); }
  .seg button.on { color: var(--text-main); background: var(--tint-3); }

  .disclose { display: flex; align-items: center; justify-content: space-between; color: var(--text-muted); } .disclose:hover { color: var(--text-main); }
  .row { display: flex; gap: 0.4rem; }
  select { flex: 1; min-width: 0; padding: 0.4rem 0.6rem; font-size: var(--fs-md); background: var(--surface-1); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); color: var(--text-main); outline: none; }
  select:focus { border-color: var(--primary); }
  .btn { display: inline-flex; align-items: center; justify-content: center; gap: 0.4rem; padding: 0.4rem 0.75rem; font-size: var(--fs-sm); font-weight: 600; color: var(--text-main); background: var(--tint-2);
    border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); white-space: nowrap; }
  .btn:hover:not(:disabled) { background: var(--tint-3); border-color: var(--tint-4); }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .grow { flex: 1 1 0; min-width: 0; padding-inline: 0.5rem; overflow: hidden; text-overflow: ellipsis; }
  .danger { flex: none; padding-inline: 0.65rem; } .danger:hover:not(:disabled) { background: color-mix(in srgb, var(--danger) 20%, transparent); border-color: color-mix(in srgb, var(--danger) 50%, transparent); }

  /* selection + the one primary action sit at the bottom of the panel */
  .picked { flex: 1 1 8rem; min-height: 6rem; }
  .picked ul { flex: 1; min-height: 0; margin: 0; padding: 0; list-style: none; overflow-y: auto; display: flex; flex-direction: column; gap: 2px; }
  .picked li { display: flex; align-items: flex-start; gap: 0.4rem; padding: 0.15rem 0.3rem 0.15rem 0.5rem; font-size: var(--fs-sm); color: var(--text-main); border-radius: var(--radius-sm); }
  .picked li:hover { background: var(--tint-2); }
  .nm { flex: 1; min-width: 0; overflow: hidden; overflow-wrap: anywhere; display: -webkit-box; -webkit-line-clamp: 2; line-clamp: 2; -webkit-box-orient: vertical; }
  .rm { flex: none; display: inline-flex; padding: 0.2rem; color: var(--text-dim); border-radius: var(--radius-sm); } .rm:hover { color: var(--danger-text); background: var(--tint-3); }
  .empty { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 0.3rem; text-align: center; font-size: var(--fs-sm); color: var(--text-dim); }
  .empty .et { font-size: var(--fs-md); font-weight: 600; color: var(--text-muted); }
  .bottom { margin-top: auto; display: flex; flex-direction: column; gap: 0.6rem; }
  .sel { display: flex; flex-direction: column; align-items: flex-start; gap: 0.3rem; font-size: var(--fs-md); color: var(--text-muted); }
  .sel strong { color: var(--text-main); } .sel em { font-style: normal; color: var(--text-dim); }
  .links { display: flex; gap: 0.75rem; }
  .legend { position: relative; display: flex; flex-direction: column; gap: 0.3rem; padding: 0.45rem 0.6rem; font-size: var(--fs-sm); color: var(--text-muted); background: var(--tint-1); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); }
  .ltitle { font-size: var(--fs-xs); font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: var(--text-dim); }
  .lgrid { display: grid; grid-template-columns: 1fr 1fr; gap: 0.3rem 0.5rem; }
  .lrow { display: flex; align-items: center; gap: 0.4rem; white-space: nowrap; }
  .lrow > :first-child { flex: none; }
  .hide { position: absolute; top: 0.4rem; right: 0.4rem; display: inline-flex; align-items: center; gap: 0.25rem; padding: 0.15rem 0.5rem; font-size: var(--fs-xs); font-weight: 600; color: var(--text-main); background: color-mix(in srgb, var(--surface-2) 90%, transparent); border: 1px solid var(--border-subtle); border-radius: var(--radius-full); opacity: 0; pointer-events: none; transition: opacity 0.12s; }
  .legend:hover .hide, .hide:focus-visible { opacity: 1; pointer-events: auto; }
  .hide:hover { border-color: var(--primary); }
  .prepare { display: inline-flex; align-items: center; justify-content: center; gap: 0.5rem; padding: 0.7rem 1rem; font-size: var(--fs-md); font-weight: 700; color: var(--on-primary); border-radius: var(--radius-md); background: var(--primary-solid); transition: background 0.15s; }
  .prepare:hover:not(:disabled) { background: var(--primary-solid-hover); }
  .prepare:disabled { opacity: 0.4; cursor: not-allowed; }
</style>
