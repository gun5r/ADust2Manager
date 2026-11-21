<script lang="ts">
  import type { AppState } from '../../state/app.svelte'
  import type { ToolRun } from '../../lib/toolRun.svelte'

  /** What the window is doing: the running tool and how far it is, the portraits being drawn, or the manager's background work; else how the last run ended. */
  let { app, tool }: { app: AppState; tool: ToolRun } = $props()
  const pj = $derived(app.portraits)
  const running = $derived(tool.busy || pj.running || app.activity.status.running > 0)
</script>

<!-- fixed height: the status, however long, scrolls inside instead of resizing the window -->
{#if running || tool.message}
  <div class="status {running ? 'busy' : tool.message?.kind ?? ''}" role="status" aria-live="polite" data-ui="tool-status">
    {#if tool.busy}
      <span class="spin" aria-hidden="true"></span>
      <span class="text"><span class="head"><strong>{tool.working}</strong><span class="time">{tool.elapsed}</span></span>{#if tool.latest}<span class="live">{tool.latest}</span>{/if}</span>
    {:else if pj.running}
      <span class="spin" aria-hidden="true"></span>
      <span class="text"><strong>Drawing portraits: {pj.done} of {pj.total}{pj.failed ? ` (${pj.failed} failed)` : ''}</strong></span>
    {:else if app.activity.status.running > 0}
      <span class="spin" aria-hidden="true"></span>
      <span class="text"><strong>Working in the background</strong><span class="live">{app.activity.status.text}</span></span>
    {:else if tool.message}
      <span class="text">{tool.message.text}</span>
    {/if}
  </div>
{/if}

<style>
  .status { flex: none; display: flex; align-items: center; gap: 0.7rem; height: 4rem; overflow-y: auto; padding: 0.5rem 0.9rem; border-radius: var(--radius-md); font-size: var(--fs-md); color: var(--text-muted); border: 1px solid var(--border-subtle); background: var(--surface-panel); }
  .status .text { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 0.1rem; }
  .status .head { display: flex; align-items: baseline; gap: 0.2rem; }
  .status .time { color: var(--text-dim); font-weight: 500; margin-left: 0.4rem; }
  .status .live { color: var(--text-muted); font-family: var(--font-mono, monospace); font-size: var(--fs-sm); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .status.busy { color: var(--text-main); }
  .status.ok { color: var(--ok); }
  .status.error { color: var(--danger); border-color: color-mix(in srgb, var(--danger) 40%, transparent); }
  .spin { flex: none; width: 16px; height: 16px; border-radius: 50%; border: 2px solid rgba(var(--primary-rgb), 0.25); border-top-color: var(--primary); animation: spin 0.8s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
