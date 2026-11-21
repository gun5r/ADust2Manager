<script lang="ts">
  import Icon from '../../ui/Icon.svelte'
  import type { FolderTab } from '../../lib/api'

  let { tabs, activeId, syncView, scanning, onSelect, onSync, onScan, onAdd, onEdit, onRemove, onOpen }: {
    tabs: FolderTab[]
    activeId: string
    syncView: boolean
    scanning: boolean
    onSelect: (id: string) => void
    onSync: () => void
    onScan: () => void
    onAdd: () => void
    onEdit: (tab: FolderTab) => void
    onRemove: (tab: FolderTab) => void
    /** Double-click: show the folder in the file manager. */
    onOpen: (tab: FolderTab) => void
  } = $props()

  let scroller = $state<HTMLElement>()
  let fadeL = $state(false), fadeR = $state(false)
  function measure() {
    const el = scroller
    if (!el) return
    fadeL = el.scrollLeft > 1
    fadeR = el.scrollLeft + el.clientWidth < el.scrollWidth - 1
  }
  function wheel(e: WheelEvent) {
    if (!scroller || e.shiftKey || Math.abs(e.deltaY) <= Math.abs(e.deltaX)) return
    scroller.scrollLeft += e.deltaY
    e.preventDefault()
  }
  $effect(() => {
    if (!scroller) return
    const ro = new ResizeObserver(measure)
    ro.observe(scroller)
    return () => ro.disconnect()
  })
  $effect(() => {
    void tabs.length
    const id = syncView ? '' : activeId
    queueMicrotask(() => {
      scroller?.querySelector<HTMLElement>(id ? '.tab.active' : '.add')?.scrollIntoView({ block: 'nearest', inline: 'nearest' })
      measure()
    })
  })
</script>

<section class="bar" data-ui="tabs">
  <div class="pinned">
    <button class="scan" class:busy={scanning} disabled={scanning || tabs.length === 0} title={syncView ? 'Scan every mod folder for new, changed and removed mods' : 'Scan this folder for new, changed and removed mods'} onclick={onScan}>
      <Icon name="refresh-cw" size={14} />
      <span class="txt stack"><span class:off={scanning}>Scan Mods</span><span class:off={!scanning}>Scanning…</span></span>
    </button>
    <button class="sync chrome-toggle" class:on={syncView} aria-pressed={syncView} aria-label="Show All" title="Show All: list the mods of every folder together" onclick={onSync}>
      <Icon name="layers" size={14} />
      <span class="txt">Show All</span>
    </button>
  </div>
  <div class="divider"></div>
  <div class="tabs" class:fade-l={fadeL} class:fade-r={fadeR} bind:this={scroller} onscroll={measure} onwheel={wheel}>
    {#each tabs as tab (tab.id)}
      <div class="tab" class:active={!syncView && tab.id === activeId} class:colored={!!tab.color}
           style={tab.color ? `--accent: ${tab.color}; --glow: ${tab.color}40` : ''}
           role="tab" tabindex="0" aria-selected={!syncView && tab.id === activeId}
           onclick={() => onSelect(tab.id)} ondblclick={() => onOpen(tab)} onkeydown={(e) => e.key === 'Enter' && onSelect(tab.id)}>
        <span class="icon"><Icon name="folder" size={15} color={tab.color || 'currentColor'} /></span>
        <span class="name" title={tab.path ? `${tab.path}\nDouble-click to open this folder` : 'No path set'}>{tab.name}</span>
        <div class="actions">
          <button class="mini edit" title="Configure tab (name, location, color)" aria-label="Edit {tab.name}" onclick={(e) => { e.stopPropagation(); onEdit(tab) }}>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>
          </button>
          <button class="mini close" title="Remove tab from manager" aria-label="Remove {tab.name}" onclick={(e) => { e.stopPropagation(); onRemove(tab) }}>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
          </button>
        </div>
      </div>
    {/each}
  </div>
  <button class="add" aria-label="Add a folder to the manager" title="Add a folder to the manager" onclick={onAdd}>
    <Icon name="plus" size={14} />
    <span>New Folder</span>
  </button>
</section>

<style>
  /* one flat row: no container box, the buttons and tabs are quiet until hovered or active */
  .bar { display: flex; align-items: center; gap: 0.35rem; padding: 0; margin-bottom: 0.7rem; flex-shrink: 0; }
  .pinned { display: flex; gap: 0.2rem; flex-shrink: 0; }
  .sync, .scan { height: 34px; display: inline-flex; align-items: center; justify-content: center; gap: 0.45rem; padding: 0 0.8rem; font-size: var(--fs-md); font-weight: 600; white-space: nowrap; border-radius: var(--radius-sm); flex-shrink: 0; color: var(--text-muted); border: 0; transition: background 0.12s, color 0.12s; }
  .sync:hover, .scan:hover:not(:disabled) { background: var(--tint-2); color: var(--text-main); }
  /* both labels share one cell, so the button keeps the width of the longer one */
  .stack { display: inline-grid; justify-items: center; } .stack > span { grid-area: 1 / 1; } .stack > .off { visibility: hidden; }
  .sync.on { border: 0; } /* Show All keeps its tint while on, without the outline */
  .scan:disabled { opacity: 0.4; cursor: default; }
  .scan.busy :global(svg) { animation: spin 0.9s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
  @media (max-width: 900px) { .txt { display: none; } .sync, .scan { padding: 0; width: 34px; } }
  .divider { width: 1px; height: 18px; margin: 0 0.3rem; background: var(--border-subtle); flex-shrink: 0; }
  .tabs { flex: 1; min-width: 0; display: flex; gap: 0.2rem; overflow-x: auto; padding: 4px 2px; margin: -4px 0; scrollbar-width: none; }
  .tabs::-webkit-scrollbar { display: none; }
  .tabs.fade-r { mask-image: linear-gradient(to right, #000 calc(100% - 36px), transparent); }
  .tabs.fade-l { mask-image: linear-gradient(to left, #000 calc(100% - 36px), transparent); }
  .tabs.fade-l.fade-r { mask-image: linear-gradient(to right, transparent, #000 36px, #000 calc(100% - 36px), transparent); }
  .tab { height: 34px; flex-shrink: 0; display: flex; align-items: center; gap: 0.45rem; position: relative; padding: 0 0.75rem; border-radius: var(--radius-sm); font-size: var(--fs-md); font-weight: 600; color: var(--text-muted); cursor: pointer; user-select: none; transition: background 0.12s, color 0.12s; }
  .tab:hover { background: var(--tint-2); color: var(--text-main); }
  .tab.active { background: var(--tint-3); color: var(--text-main); }
  .tab:hover, .tab:focus-within { padding-right: 3.5rem; }
  .tab.colored { box-shadow: inset 0 -2px 0 var(--accent); }
  .name { flex: 1 1 auto; min-width: 0; max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .actions { position: absolute; right: 3px; top: 50%; transform: translateY(-50%); display: flex; align-items: center; gap: 2px; padding-left: 8px; border-radius: var(--radius-sm); background: var(--surface-3); opacity: 0; pointer-events: none; transition: opacity 0.12s; }
  .tab:hover .actions, .tab:focus-within .actions { opacity: 1; pointer-events: auto; }
  .tab:focus-visible { outline-offset: -2px; }
  @media (hover: none) {
    .tab:hover, .tab:focus-within { padding-right: 0.75rem; }
    .actions { opacity: 1; pointer-events: auto; position: static; transform: none; padding: 0; background: none; }
  }
  .mini { width: 20px; height: 20px; display: inline-flex; align-items: center; justify-content: center; color: var(--text-muted); border-radius: 4px; }
  .edit:hover { background: var(--tint-3); color: var(--text-main); }
  .close:hover { background: color-mix(in srgb, var(--danger) 25%, transparent); color: var(--danger); }
  .add { height: 34px; flex-shrink: 0; display: inline-flex; align-items: center; gap: 0.35rem; padding: 0 0.7rem; font-size: var(--fs-md); font-weight: 600; color: var(--text-dim); border-radius: var(--radius-sm); }
  .add:hover { background: var(--tint-2); color: var(--text-main); }
  @media (max-width: 1100px) { .add span { display: none; } .add { width: 34px; justify-content: center; padding: 0; } }
</style>
