<script lang="ts">
  import Icon from '../../ui/Icon.svelte'
  import type { QueueJob } from '../../lib/api'
  import { detectConflicts, groupByBundle, namesOf } from '../../lib/queue'

  let { jobs, transferring, onTransfer }: { jobs: QueueJob[]; transferring: boolean; onTransfer: () => void } = $props()
  const ready = $derived(jobs.filter((j) => j.status === 'prepared'))
  const preparing = $derived(jobs.filter((j) => j.status === 'queued' || j.status === 'preparing'))
  const groups = $derived(groupByBundle(ready).map((g) => ({
    ...g, bundleName: g.jobs[0].prepared_data?.bundle_name ?? '', conflictKey: detectConflicts(g.jobs)[0]?.assetKey ?? 'Duplicate Mod Type',
  })))
  const short = (hash: string | null) => (hash ? (hash.length > 16 ? `${hash.slice(0, 10)}...` : hash) : 'no-bundle')
</script>

<aside class="sidebar" data-ui="queue-plan">
  <div class="head">
    <div class="title">
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
      <span>Transfer Actions Plan</span>
    </div>
    <span class="badge">{ready.length || preparing.length ? `${groups.length} Transfer ${groups.length === 1 ? 'Bundle' : 'Bundles'}` : '0 Bundles'}</span>
  </div>
  <div class="send">
    <button class="transfer" disabled={!ready.length || transferring} onclick={onTransfer}>
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="5" y="2" width="14" height="20" rx="2" ry="2"></rect><line x1="12" y1="18" x2="12.01" y2="18"></line></svg>
      <span>{transferring ? 'Transferring to phone (Batches of 5)...' : `Transfer files to phone (${ready.length} Ready)`}</span>
    </button>
  </div>
  <div class="body">
    {#if !ready.length && !preparing.length}
      <div class="empty">Prepared mods show their transfer plan here.</div>
    {/if}
    {#each groups as g (g.hash ?? g.jobs[0].id)}
      <div class="plan" class:conflict={g.hasConflict} class:bundled={!g.hasConflict && g.needsAssembly} class:standalone={!g.hasConflict && !g.needsAssembly}>
        <div class="plan-head">
          {#if g.hasConflict}<span class="tag bad"><Icon name="triangle-alert" size={14} color="var(--warn-text)" /> Conflict ({g.conflictKey})</span>
          {:else if g.needsAssembly}<span class="tag bundled"><Icon name="package" size={13} color="#fb923c" /> Bundled ({g.jobs.length} Mods)</span>
          {:else}<span class="tag standalone"><Icon name="zap" size={13} color="var(--zone-standalone)" /> Standalone</span>{/if}
          <span class="hash" title="{g.bundleName} ({g.hash})">{short(g.hash)}</span>
        </div>
        <div class="mods">
          {#each g.jobs.flatMap(namesOf) as name}
            <div class="mod"><b class:bad={g.hasConflict} class:violet={!g.hasConflict && g.needsAssembly}>•</b><span>{name}</span></div>
          {/each}
        </div>
        {#if g.hasConflict}<div class="note bad"><Icon name="triangle-alert" size={14} color="var(--warn-text)" /> Conflicting mod types in same bundle! Resolve conflicts before transferring.</div>
        {:else if g.needsAssembly}<div class="note">Auto-assembled into 1 unified package on transfer to prevent texture overwrites.</div>
        {:else}<div class="note slate">Transferred as an individual bundle file to phone.</div>{/if}
      </div>
    {/each}
    {#if preparing.length}
      <div class="plan pending">
        <div class="plan-head"><span class="tag wait">⏳ Preparing ({preparing.length})</span></div>
        <div class="pending-names">{preparing.map((j) => j.mod_name).join(', ')}</div>
        <div class="pending-note">Will be added to transfer plan once preparation completes.</div>
      </div>
    {/if}
  </div>
</aside>

<style>
  .sidebar { display: flex; flex-direction: column; min-height: 0; height: 100%; background: var(--surface-panel); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); overflow: hidden; }
  .head { display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; padding: 0.75rem 0.9rem; background: transparent; border-bottom: 1px solid var(--border-subtle); flex-shrink: 0; }
  .title { white-space: nowrap; display: flex; align-items: center; gap: 0.45rem; font-weight: 700; font-size: var(--fs-md); color: var(--text-main); }
  .badge { white-space: nowrap; line-height: 1.1; padding: 0.075rem 0.5rem; font-size: var(--fs-sm); }  /* classic: plain text, .badge-subtle only styles inside the title row */
  .body { flex: 1; min-height: 0; overflow-y: auto; padding: 0.65rem; display: flex; flex-direction: column; gap: 0.6rem; }
  .empty { padding: 1.5rem 0.5rem; text-align: center; font-size: var(--fs-md); color: var(--text-dim); }
  .plan { display: flex; flex-direction: column; gap: 0.4rem; padding: 0.65rem 0.75rem; background: var(--tint-1); border: 1px solid transparent; border-radius: var(--radius-sm); flex-shrink: 0; }
  .plan { border-left: 3px solid color-mix(in srgb, var(--c, var(--tint-4)) 85%, transparent); }
  .plan.bundled { --c: var(--zone-bundled); background: color-mix(in srgb, var(--c) 8%, transparent); }
  .plan.standalone { --c: var(--zone-standalone); background: color-mix(in srgb, var(--c) 8%, transparent); }
  .plan.conflict { border-color: color-mix(in srgb, var(--danger) 50%, transparent); background: color-mix(in srgb, var(--danger) 6%, transparent); }
  .plan.pending { border-style: dashed; opacity: 0.75; }
  .plan-head { display: flex; align-items: center; justify-content: space-between; gap: 0.4rem; }
  .tag { padding: 2px 6px; font-size: var(--fs-xs); font-weight: 700; text-transform: uppercase; border-radius: 4px; }
  .tag.bundled { color: var(--zone-bundled); background: color-mix(in srgb, var(--zone-bundled) 18%, transparent); border: 1px solid color-mix(in srgb, var(--zone-bundled) 40%, transparent); }
  .tag.standalone { color: var(--zone-standalone); background: color-mix(in srgb, var(--zone-standalone) 18%, transparent); border: 1px solid color-mix(in srgb, var(--zone-standalone) 40%, transparent); }
  .tag.bad { color: var(--danger-text); background: color-mix(in srgb, var(--danger) 20%, transparent); border: 1px solid color-mix(in srgb, var(--danger) 40%, transparent); }
  .tag.wait { color: var(--warn-text); background: color-mix(in srgb, var(--warn) 20%, transparent); border: 1px solid color-mix(in srgb, var(--warn) 35%, transparent); }
  .hash { font-family: monospace; font-size: var(--fs-xs); color: var(--text-muted); }
  .mods { display: flex; flex-direction: column; gap: 0.25rem; margin-top: 0.2rem; }
  .mod { display: flex; align-items: center; gap: 0.35rem; padding: 3px 6px; font-size: var(--fs-sm); color: var(--text-main); background: rgba(0, 0, 0, 0.25); border-radius: 3px; }
  .mod span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .mod b { color: var(--zone-standalone); } .mod b.bad { color: var(--danger-text); } .mod b.violet { color: var(--zone-bundled); }
  .note { margin-top: 0.2rem; font-size: var(--fs-xs); font-style: italic; color: var(--text-muted); }
  .note.bad { color: var(--danger-text); } .note.slate { color: var(--text-muted); }
  .pending-names { margin-top: 0.3rem; font-size: var(--fs-sm); color: var(--text-muted); }
  .pending-note { margin-top: 0.25rem; font-size: var(--fs-xs); font-style: italic; color: var(--text-dim); }
  .send { padding: 0.65rem 0.65rem 0; flex-shrink: 0; }
  .transfer { display: flex; align-items: center; justify-content: center; gap: 0.5rem; width: 100%; padding: 0.7rem 1rem; font-size: var(--fs-md); line-height: normal; font-weight: 700; color: var(--on-primary); white-space: nowrap; background: var(--primary-solid); border: none; border-radius: var(--radius-md); transition: background 0.15s; }
  .transfer:hover:not(:disabled) { background: var(--primary-solid-hover); }
  .transfer:disabled { color: var(--text-dim); background: var(--tint-2); border: 1px solid var(--border-subtle); cursor: not-allowed; }
</style>
