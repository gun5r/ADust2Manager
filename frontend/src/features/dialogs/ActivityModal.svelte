<script lang="ts">
  import Modal from '../../ui/Modal.svelte'
  import StatusLight from '../../ui/StatusLight.svelte'
  import { api } from '../../lib/api'
  import { duration, percent, stateText, taskSeconds, LIGHT_COLOR, type ActivityTask } from '../../lib/activity'
  import type { AppState } from '../../state/app.svelte'

  let { app, onClose }: { app: AppState; onClose: () => void } = $props()
  let picked = $state<number | null>(null)
  let filter = $state<'all' | 'running' | 'problems'>('all')

  const tasks = $derived(app.activity.tasks.filter((t) => filter === 'all' || (filter === 'running' ? t.state === 'running' : t.state === 'error' || t.errors > 0)))
  const chosen = $derived(app.activity.tasks.find((t) => t.id === picked) ?? null)
  const lines = $derived(chosen ? app.logs.filter((l) => l.task === chosen.id) : [])
  const color = (t: ActivityTask) => LIGHT_COLOR[t.state === 'error' ? 'error' : t.state === 'running' ? (t.errors ? 'warning' : 'running') : t.errors ? 'warning' : 'idle']
  const clock = (seconds: number) => new Date(seconds * 1000).toLocaleTimeString()
</script>

<Modal label="Activity" {onClose} width="min(1000px, 94vw)" height="80vh">
  {#snippet title()}Activity{/snippet}
  {#snippet badges()}<StatusLight status={app.activity.status} />{/snippet}
  <div class="wrap">
    <div class="filters" role="group" aria-label="Show">
      {#each [['all', 'All'], ['running', 'Running'], ['problems', 'With errors']] as [id, name] (id)}
        <button class:on={filter === id} onclick={() => (filter = id as typeof filter)}>{name}</button>
      {/each}
      <span class="hint">Tasks finished before the manager was last closed are not kept.</span>
    </div>
    <div class="split">
      <div class="list">
        {#each tasks as t (t.id)}
          <button class="row" class:picked={picked === t.id} onclick={() => (picked = picked === t.id ? null : t.id)}>
            <span class="dot" style:background={color(t)}></span>
            <span class="what"><strong>{t.title}</strong><span class="detail">{t.state === 'error' ? t.error : t.detail || stateText(t)}</span></span>
            <span class="meta">{stateText(t)}{percent(t) ? ` · ${percent(t)}` : ''}<br />{clock(t.started)} · {duration(taskSeconds(t, app.clock))}</span>
          </button>
        {:else}
          <p class="none">{filter === 'all' ? 'Nothing has run yet.' : 'No task matches.'}</p>
        {/each}
      </div>
      <div class="detailbox">
        {#if chosen}
          <h3>{chosen.title}</h3>
          <p class="sub">{stateText(chosen)} · started {clock(chosen.started)} · {duration(taskSeconds(chosen, app.clock))} · {chosen.errors} error line(s)</p>
          <div class="stream">
            {#each lines as line (line.seq)}<div class="line {line.level}">{line.message}</div>{:else}<div class="line info">No lines kept for this task.</div>{/each}
          </div>
        {:else}
          <p class="none">Pick a task to read what it logged.</p>
        {/if}
      </div>
    </div>
  </div>
  {#snippet footer()}
    {#if app.activity.status.state === 'error'}<button class="btn" onclick={() => api.acknowledgeActivity()}>Dismiss the failure</button>{:else}<span></span>{/if}
    <button class="btn" onclick={onClose}>Close</button>
  {/snippet}
</Modal>

<style>
  .wrap { display: flex; flex-direction: column; gap: 0.7rem; height: 100%; min-height: 0; }
  .filters { display: flex; align-items: center; gap: 0.4rem; }
  .filters button, .btn { padding: 0.3rem 0.8rem; font-size: var(--fs-sm); font-weight: 600; color: var(--text-muted); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); background: var(--tint-1); }
  .filters button.on { color: var(--primary); border-color: var(--border-focus); }
  .hint { margin-left: auto; font-size: var(--fs-xs); color: var(--text-dim); }
  .split { flex: 1; min-height: 0; display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 0.8rem; }
  .list, .detailbox { min-height: 0; overflow-y: auto; background: var(--surface-panel); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); padding: 0.4rem; }
  .row { display: flex; align-items: center; gap: 0.7rem; width: 100%; text-align: left; padding: 0.5rem 0.6rem; border-radius: var(--radius-sm); }
  .row:hover, .row.picked { background: var(--selected-bg); }
  .dot { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }
  .what { flex: 1; min-width: 0; display: flex; flex-direction: column; font-size: var(--fs-md); }
  .detail { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: var(--fs-sm); color: var(--text-muted); }
  .meta { font-size: var(--fs-xs); color: var(--text-dim); text-align: right; flex-shrink: 0; }
  .none { padding: 1rem; font-size: var(--fs-md); color: var(--text-dim); }
  h3 { font-size: var(--fs-md); padding: 0.4rem 0.5rem 0; }
  .sub { padding: 0 0.5rem 0.4rem; font-size: var(--fs-sm); color: var(--text-dim); }
  .stream { padding: 0.3rem 0.5rem; font-family: var(--font-mono); font-size: var(--fs-sm); line-height: 1.5; }
  .line { color: var(--text-muted); white-space: pre-wrap; }
  .line.success { color: var(--ok-text); } .line.error { color: var(--danger-text); } .line.warning { color: var(--warning); } .line.start { color: var(--primary); }
  @media (max-width: 800px) { .split { grid-template-columns: 1fr; } }
</style>
