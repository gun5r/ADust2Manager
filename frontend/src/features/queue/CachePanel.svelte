<script lang="ts">
  import Icon from '../../ui/Icon.svelte'
  import type { AppState } from '../../state/app.svelte'
  import type { CachedBundle } from '../../lib/api'

  let { app }: { app: AppState } = $props()
  // svelte-ignore state_referenced_locally
  const flow = app.flow
  const total = $derived(flow.cached.length)
  const shown = $derived(flow.visibleCached.length)
  const kind = (m: CachedBundle) =>
    m.asset_stem && m.asset_stem !== m.mod_name && m.asset_stem !== m.folder_name ? m.asset_stem
      : m.asset_key && m.asset_key !== 'unknown' && m.asset_key !== m.mod_name ? m.asset_key
      : m.bundle_hash ? m.bundle_hash.slice(0, 8) : m.folder_name.slice(-8)
</script>

<aside class="sidebar" data-ui="queue-cache">
  <div class="head">
    <div class="title">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path><polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline><line x1="12" y1="22.08" x2="12" y2="12"></line></svg>
      <span>Cache Ready ({flow.cacheQuery.trim() ? `${shown}/${total}` : total})</span>
    </div>
    <div class="head-actions">
      <button class="btn secondary" title="Refresh Cached Mods" aria-label="Refresh Cached Mods" onclick={() => flow.loadCached()}><Icon name="refresh-cw" size={14} /></button>
    </div>
  </div>
  <div class="search"><input type="text" placeholder="Filter cached mods..." bind:value={flow.cacheQuery} /></div>
  <div class="list">
    {#if flow.cacheError}
      <div class="empty err">{flow.cacheError}</div>
    {:else if shown === 0}
      <div class="empty">
        {#if flow.cacheQuery.trim()}No cached mods match "{flow.cacheQuery.trim()}"{:else}No prepared mods yet.{/if}
      </div>
    {/if}
    {#each flow.visibleCached as m (m.id)}
      {#if m.is_broken}
        <div class="card broken">
          <span class="name err"><Icon name="triangle-alert" size={14} color="var(--warn-text)" /> {m.mod_name}</span>
          <div class="meta wrap"><span class="chip bad">Corrupted / Missing Data</span><span class="reason">{m.broken_reason || 'Corrupted bundle'}</span></div>
          <button class="del full" title="Delete corrupted files from cache" onclick={() => flow.deleteCached(m)}><Icon name="trash-2" size={14} /> <span>Delete Broken Cache</span></button>
        </div>
      {:else}
        {@const queued = flow.isCachedQueued(m)}
        <div class="card">
          <span class="name">{m.mod_name}</span>
          <div class="meta col">
            <div class="row"><span class="chip">{m.character || 'Others'}</span><span class="dot">•</span><span class="muted"><Icon name="hard-drive" size={12} /> {m.size_str}</span></div>
            <span class="kind" title="Mod file type / Asset Key: {m.asset_stem || m.asset_key || ''}"><Icon name="file-text" size={12} /> {kind(m)}</span>
          </div>
          <div class="actions">
            <button class="install" class:queued title={queued ? 'Already added to transfer queue' : 'Add prepared files directly to transfer list'} onclick={() => flow.addCached(m)}>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"></path><path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"></path><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"></path><path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"></path></svg>
              <Icon name={queued ? 'check' : 'plus'} size={12} /><span>{queued ? 'In Queue' : 'Install'}</span>
            </button>
            <button class="del" title="Delete from cache" onclick={() => flow.deleteCached(m)}>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
              <span>Delete</span>
            </button>
          </div>
        </div>
      {/if}
    {/each}
  </div>
</aside>

<style>
  .sidebar { --zone: var(--zone-cache); display: flex; flex-direction: column; min-height: 0; height: 100%; background: var(--surface-panel); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); overflow: hidden; }
  .head { display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; padding: 0.75rem 0.9rem; background: transparent; border-bottom: 1px solid var(--border-subtle); flex-shrink: 0; }
  .title { white-space: nowrap; display: flex; align-items: center; gap: 0.45rem; font-weight: 700; font-size: var(--fs-md); color: var(--text-main); }
  .title :global(svg) { color: var(--zone); }
  .head-actions { display: flex; align-items: center; gap: 0.4rem; }
  .btn { white-space: nowrap; display: inline-flex; align-items: center; gap: 0.5rem; line-height: normal; padding: 0.55rem 1rem; font-size: var(--fs-md); min-height: 38px; font-weight: 600; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle); color: var(--text-main); }
  .secondary { background: var(--tint-2); }
  .secondary:hover { background: var(--tint-3); border-color: var(--tint-4); }
  .search { padding: 0.5rem 0.75rem; background: rgba(0, 0, 0, 0.2); border-bottom: 1px solid var(--border-subtle); flex-shrink: 0; }
  .search input { width: 100%; height: 27.2px; padding: 0.35rem 0.65rem; font-size: var(--fs-sm); line-height: normal; color: var(--text-main); background: var(--tint-1); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); outline: none; transition: all 0.2s ease; }
  .search input:focus { border-color: var(--primary); background: var(--tint-2); box-shadow: none; }
  .list { flex: 1; min-height: 0; overflow-y: auto; padding: 0.75rem; display: flex; flex-direction: column; gap: 0.5rem; }
  .empty { padding: 1.5rem 0.5rem; text-align: center; font-size: var(--fs-md); color: var(--text-dim); }
  .err { color: var(--danger); }
  .card { display: flex; flex-direction: column; gap: 0.45rem; padding: 0.6rem 0.75rem; background: var(--tint-1); border: 1px solid var(--border-subtle); border-left: 3px solid color-mix(in srgb, var(--zone) 80%, transparent); border-radius: var(--radius-sm); transition: all 0.2s ease; flex-shrink: 0; }
  .card:hover { background: var(--tint-2); }
  .card.broken { border-color: color-mix(in srgb, var(--danger) 40%, transparent); }
  .name { font-weight: 600; font-size: var(--fs-md); color: var(--text-main); line-height: 1.3; word-break: break-word; }
  .meta { display: flex; align-items: center; gap: 0.4rem; font-size: var(--fs-sm); color: var(--text-muted); }
  .meta.col { flex-direction: column; align-items: flex-start; gap: 4px; margin-bottom: 0.45rem; }
  .meta.wrap { flex-wrap: wrap; }
  .row { display: flex; align-items: center; gap: 6px; font-size: var(--fs-sm); }
  .chip { padding: 1px 5px; font-size: var(--fs-xs); color: var(--text-muted); background: var(--tint-2); border: 1px solid var(--border-subtle); border-radius: 4px; }
  .chip.bad { color: var(--danger-text); background: color-mix(in srgb, var(--danger) 20%, transparent); border-color: color-mix(in srgb, var(--danger) 40%, transparent); }
  .reason { width: 100%; font-size: var(--fs-xs); color: var(--danger); }
  .dot { opacity: 0.4; } .muted { color: var(--text-muted); }
  .kind { font-family: monospace; font-size: var(--fs-sm); color: var(--text-dim); word-break: break-all; }
  .actions { display: flex; align-items: center; gap: 0.45rem; margin-top: 0.15rem; }
  .install { flex: 1; display: inline-flex; align-items: center; justify-content: center; gap: 0.35rem; padding: 0.55rem 0.8rem; min-height: 36px; font-size: var(--fs-md); font-weight: 600; color: var(--text-main); background: var(--tint-2); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); transition: all 0.2s ease; }
  .install:hover { background: var(--tint-3); border-color: var(--tint-4); }
  .install.queued { opacity: 0.75; }
  .del { display: inline-flex; align-items: center; justify-content: center; gap: 0.25rem; padding: 0.55rem 0.8rem; min-height: 36px; font-size: var(--fs-md); font-weight: 600; color: var(--text-muted); background: var(--tint-1); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); transition: all 0.2s ease; }
  .del:hover { background: var(--tint-3); color: var(--text-main); }
  .del.full { width: 100%; }
</style>
