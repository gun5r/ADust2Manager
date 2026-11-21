<script lang="ts">
  import { tick } from 'svelte'
  import StatusLight from '../../ui/StatusLight.svelte'
  import Icon from '../../ui/Icon.svelte'
  import { api } from '../../lib/api'
  import { duration, percent, stateText, taskSeconds, LIGHT_COLOR } from '../../lib/activity'
  import type { AppState } from '../../state/app.svelte'

  let { app }: { app: AppState } = $props()
  const status = $derived(app.activity.status)
  const tasks = $derived(app.activity.tasks)
  const running = $derived(tasks.filter((t) => t.state === 'running'))
  const recent = $derived(tasks.filter((t) => t.state !== 'running').slice(0, 8))
  const lines = $derived(app.logs.filter((l) => l.seq < 0 || l.seq > app.consoleFrom))
  /** The bar's progress line follows the task that is shown in the text: the newest running one with a known share. */
  const share = $derived(running.findLast((t) => t.progress !== null)?.progress ?? null)
  let stream: HTMLDivElement | undefined = $state()

  const toggle = (panel: 'tasks' | 'console') => (app.barPanel = app.barPanel === panel ? null : panel)

  $effect(() => {
    void lines.length
    if (app.barPanel === 'console') tick().then(() => stream && (stream.scrollTop = stream.scrollHeight))
  })

  async function dismiss() {
    await api.acknowledgeActivity().catch(() => {})
  }
</script>

{#if app.barPanel}
  <div class="panel" data-ui="activity-panel" role="region" aria-label={app.barPanel === 'tasks' ? 'Tasks' : 'Console'}>
    {#if app.barPanel === 'tasks'}
      <div class="tasks">
        {#each running as t (t.id)}
          <div class="task">
            <span class="dot" style:background={LIGHT_COLOR[t.errors ? 'warning' : 'running']}></span>
            <div class="what"><strong>{t.title}</strong><span class="detail">{t.detail || 'Starting…'}</span></div>
            <div class="meter" aria-hidden="true"><i style:width={t.progress === null ? '100%' : `${t.progress * 100}%`} class:unknown={t.progress === null}></i></div>
            <span class="num">{percent(t)}</span>
            <span class="num">{duration(taskSeconds(t, app.clock))}</span>
          </div>
        {:else}
          <p class="none">Nothing is running.</p>
        {/each}
        {#if recent.length}
          <h4>Recently finished</h4>
          {#each recent as t (t.id)}
            <div class="task done">
              <span class="dot" style:background={t.state === 'error' ? LIGHT_COLOR.error : t.state === 'cancelled' ? '#737373' : t.errors ? LIGHT_COLOR.warning : LIGHT_COLOR.running}></span>
              <div class="what"><strong>{t.title}</strong><span class="detail">{t.state === 'error' ? t.error : stateText(t)}</span></div>
              <span class="num wide">{duration(taskSeconds(t, app.clock))}</span>
            </div>
          {/each}
        {/if}
      </div>
    {:else}
      <div class="console-head">
        <span>Everything the program is doing, all tasks together</span>
        <button class="link" onclick={() => (app.consoleFrom = app.logs.at(-1)?.seq ?? 0)}>Clear</button>
      </div>
      <div class="stream" bind:this={stream}>
        {#each lines as line (line.seq)}
          <div class="line {line.level}">{line.message}</div>
        {:else}
          <div class="line info">Nothing logged yet.</div>
        {/each}
      </div>
    {/if}
  </div>
{/if}

<footer class="bar" data-ui="status-bar" class:offline={!app.online}>
  {#if share !== null}<i class="progress" style:width={`${share * 100}%`} style:background={LIGHT_COLOR[status.state]}></i>{/if}
  <StatusLight status={app.online ? status : { state: 'error', label: 'Manager offline', text: 'The page lost the connection to the manager.', running: 0 }} />
  <span class="text" title={status.text}>{app.online ? status.text : 'Reconnecting… If the manager was closed, start it again.'}</span>
  {#if status.state === 'error'}<button class="chip" onclick={dismiss} title="Mark the failure as seen">Dismiss</button>{/if}
  <div class="buttons">
    <button class="btn" class:on={app.barPanel === 'tasks'} aria-pressed={app.barPanel === 'tasks'} title="Show every task in progress" onclick={() => toggle('tasks')}>
      <Icon name="list-checks" size={14} /> Tasks{#if status.running > 0}<span class="count">{status.running}</span>{/if}
    </button>
    <button class="btn" class:on={app.barPanel === 'console'} aria-pressed={app.barPanel === 'console'} title="Show the console: everything the program does, together" onclick={() => toggle('console')}>
      <Icon name="terminal" size={14} /> Console
    </button>
    <button class="btn" title="Open the activity window: all tasks, with their history and details" onclick={() => (app.activityOpen = true)}>
      <Icon name="activity" size={14} /> Activity
    </button>
  </div>
</footer>

<style>
  .bar { position: relative; flex: 0 0 auto; display: flex; align-items: center; gap: 0.9rem; padding: 0 1rem; height: 38px; background: color-mix(in srgb, var(--surface-2) 97%, transparent);
    border-top: 1px solid var(--border-subtle); box-shadow: 0 -6px 18px rgba(0, 0, 0, 0.35); z-index: 45; }
  .progress { position: absolute; left: 0; top: -1px; height: 2px; opacity: 0.85; transition: width 0.3s ease; }
  .text { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: var(--fs-md); color: var(--text-muted); }
  .buttons { display: flex; gap: 0.4rem; flex-shrink: 0; }
  .btn, .chip { display: inline-flex; align-items: center; gap: 0.35rem; padding: 0.28rem 0.7rem; font-size: var(--fs-sm); font-weight: 600; color: var(--text-muted);
    background: var(--tint-1); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); }
  .btn:hover, .chip:hover { color: var(--text-main); border-color: var(--border-focus); }
  .btn.on { color: var(--primary); border-color: var(--border-focus); background: var(--selected-bg); }
  .count { min-width: 1.1rem; padding: 0 0.3rem; text-align: center; border-radius: 9999px; font-size: var(--fs-xs); color: #04130c; background: var(--ok); }
  .panel { position: fixed; z-index: 44; left: 0; right: 0; bottom: 38px; height: min(300px, 45vh); display: flex; flex-direction: column;
    background: color-mix(in srgb, var(--surface-2) 97%, transparent); border-top: 1px solid var(--border-subtle); box-shadow: 0 -10px 25px rgba(0, 0, 0, 0.5); }
  .tasks { flex: 1; overflow-y: auto; padding: 0.5rem 1.25rem 0.8rem; }
  h4 { margin: 0.8rem 0 0.2rem; font-size: var(--fs-xs); letter-spacing: 0.06em; text-transform: uppercase; color: var(--text-dim); }
  .none { color: var(--text-dim); font-size: var(--fs-md); padding: 0.6rem 0; }
  .task { display: flex; align-items: center; gap: 0.75rem; padding: 0.4rem 0; border-bottom: 1px solid var(--border-subtle); font-size: var(--fs-md); }
  .task.done { opacity: 0.8; }
  .dot { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }
  .what { flex: 1; min-width: 0; display: flex; flex-direction: column; }
  .what strong { font-weight: 700; color: var(--text-main); }
  .detail { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text-muted); font-size: var(--fs-sm); }
  .meter { width: 160px; height: 5px; border-radius: 9999px; overflow: hidden; background: var(--tint-2); flex-shrink: 0; }
  .meter i { display: block; height: 100%; background: var(--accent); }
  .meter i.unknown { background: linear-gradient(90deg, transparent, var(--accent), transparent); background-size: 50% 100%; background-repeat: no-repeat; animation: sweep 1.4s linear infinite; }
  @keyframes sweep { from { background-position: -50% 0; } to { background-position: 150% 0; } }
  .num { width: 5.5rem; text-align: right; font-variant-numeric: tabular-nums; color: var(--text-muted); flex-shrink: 0; }
  .num.wide { width: 12rem; }
  .console-head { display: flex; justify-content: space-between; padding: 0.4rem 1.25rem; font-size: var(--fs-sm); color: var(--text-dim); border-bottom: 1px solid var(--border-subtle); }
  .link { font-weight: 600; color: var(--text-muted); } .link:hover { color: var(--primary); }
  .stream { flex: 1; overflow-y: auto; padding: 0.5rem 1.25rem; font-family: var(--font-mono); font-size: var(--fs-sm); line-height: 1.55; }
  .line { color: var(--text-muted); white-space: pre-wrap; }
  .line.success { color: var(--ok-text); } .line.error { color: var(--danger-text); } .line.warning, .line.warn { color: var(--warning); } .line.start { color: var(--primary); }
  @media (max-width: 800px) { .btn { padding: 0.28rem 0.5rem; } .meter { display: none; } }
</style>
