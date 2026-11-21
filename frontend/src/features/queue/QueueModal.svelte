<script lang="ts">
  import Icon from '../../ui/Icon.svelte'
  import type { AppState } from '../../state/app.svelte'
  import type { QueueJob } from '../../lib/api'
  import { detectConflicts, groupByBundle } from '../../lib/queue'
  import Modal from '../../ui/Modal.svelte'
  import CachePanel from './CachePanel.svelte'
  import StatusDot from '../../ui/StatusDot.svelte'
  import AssemblyPlan from './AssemblyPlan.svelte'

  let { app }: { app: AppState } = $props()
  // svelte-ignore state_referenced_locally
  const flow = app.flow
  // svelte-ignore state_referenced_locally
  const runner = app.runner

  // The runner mutates jobs in place and bumps `queueVersion`; copy so rows re-render.
  const jobs = $derived<QueueJob[]>(app.queueVersion >= 0 ? runner.jobs.map((j) => ({ ...j })) : [])
  const by = (...s: QueueJob['status'][]) => jobs.filter((j) => s.includes(j.status))
  const active = $derived(by('queued', 'preparing', 'transferring'))
  const ready = $derived(by('prepared'))
  const failed = $derived(by('failed_prepare', 'failed_transfer'))
  const done = $derived(by('completed'))
  const preparing = $derived(by('queued', 'preparing').length)
  const queuedOnly = $derived(by('queued').length)
  const conflicts = $derived(detectConflicts(ready))
  /** How each ready job will travel: with others in one assembled bundle, alone, or in a clash (same grouping as the plan on the right). */
  const route = $derived(new Map(groupByBundle(ready).flatMap((g) => g.jobs.map((j) => [j.id, g.hasConflict ? 'conflict' : g.needsAssembly ? 'bundled' : 'standalone'] as const))))
  const conflicting = $derived(new Set(conflicts.flatMap((c) => c.jobs.map((j) => j.id))))
  /** Jobs whose mod has its Spine textures merged: if one misbehaves in game, that may be why. */
  const mergedMods = $derived(new Set(app.library.mods.filter((m) => m.has_backup).map((m) => m.folder_path)))
  const isMerged = (job: QueueJob) => (job.mod_folders ?? [job.mod_folder]).some((f) => mergedMods.has(f))
  const turbo = $derived(Boolean(app.config?.settings?.turbo_mode))
  const hasPhone = $derived(app.devices.some((d) => d.status === 'device'))
  const transferring = $derived(app.queueVersion >= 0 && runner.transferring)

  const statusText = $derived(
    transferring ? 'Pushing repacked files to Android device via ADB in safe batches of 5... Please do not disconnect your phone.'
      : ready.length && preparing ? `${ready.length} mod(s) are ready, ${preparing} still preparing. Wait for them if they belong in the same bundle (e.g. dating mods).`
      : '',
  )
</script>

<Modal label="Queue" width="1360px" height="86vh" onClose={() => (flow.open = false)}>
  {#snippet title()}Queue{/snippet}
  {#snippet icon()}
    <Icon name="list-checks" size={22} />
  {/snippet}
  {#snippet badges()}
    <div class="pills">
      {#if failed.length}<span class="pill danger">{failed.length} Failed</span>{/if}
    </div>
  {/snippet}
  {#snippet actions()}
    <span class="turbo-wrap">
      <button class="btn turbo" class:on={turbo} aria-pressed={turbo} aria-describedby="turbo-tip" onclick={() => app.saveSettings({ turbo_mode: !turbo })}><Icon name="zap" size={14} color="var(--warn-text)" /> Turbo Mode: {turbo ? 'On' : 'Off'}</button>
      <span class="tip" id="turbo-tip" role="tooltip"><strong>Turbo Mode</strong> repacks several mods at the same time, for when you just want speed. It can use most of your CPU and memory. Off (default): up to 3 mods download at once, but only one is repacked at a time.</span>
    </span>
  {/snippet}

  <div class="split" data-ui="queue-split">
    <CachePanel {app} />

    <section class="main">
      <!-- the phone: always shown at the top of this column -->
      <div class="phone" class:off={app.adb.state !== 'connected'}>
        <StatusDot state={app.adb.state} /><span class="pname">{app.adb.label}</span>
        <button class="btn small" title="Check for connected phones again" onclick={() => app.refreshDevices()}>{app.adb.state === 'connected' ? 'Refresh' : 'Check ADB'}</button>
      </div>
      {#if statusText || flow.transferMessage}
        <div class="banner"><div class="info">{#if statusText}<p>{statusText}</p>{/if}{#if flow.transferMessage}<p class="warn">{flow.transferMessage}</p>{/if}</div></div>
      {/if}

      {#if !hasPhone && ready.length}
        <div class="phone-warning">
          <div class="row"><span class="big"><Icon name="triangle-alert" size={20} color="var(--warn-text)" /></span><span><strong>Phone not connected:</strong> Please ensure your phone is connected with USB Debugging enabled, and BrownDust II is installed.</span></div>
        </div>
      {/if}

      {#if !jobs.length}
        <div class="empty-state" data-ui="queue-empty">
          <Icon name="list-checks" size={36} color="var(--text-muted)" />
          <div class="et">Nothing in the queue</div>
          <div class="es">Pick mods and press Prepare for Install.</div>
          <button class="btn" onclick={() => (flow.open = false)}>Choose mods</button>
        </div>
      {/if}

      {#if active.length}
        <div class="section" data-ui="queue-active">
          <div class="section-head">
            <span><Icon name="loader" size={14} color="var(--primary)" /> In Progress &amp; Queued ({active.length})</span>
            <div class="right">
              {#if queuedOnly}<button class="btn small" title="Remove all waiting/unprocessed mods from queue" onclick={() => runner.clear('waiting')}>Clear Waiting</button>{/if}
            </div>
          </div>
          <div class="items">
            {#each active as job (job.id)}
              <div class="item">
                <div class="left">
                  <span class="name">{job.mod_name}{#if isMerged(job)}<span class="mini merged" title="Its Spine textures are merged: if this mod causes a problem in game, that may be the reason">Merged</span>{/if}</span>
                  <span class="desc">{job.character} •
                    {#if job.status === 'preparing'}<span class="mini accent">Converting...</span>{:else if job.status === 'transferring'}<span class="mini primary">Transferring...</span>{:else}<span class="mini subtle">Queued</span>{/if}
                  </span>
                </div>
                <div class="progress"><div class="bar"><div class="fill" style:width="{job.progress}%"></div></div><span class="ptext">{job.progress_text}</span></div>
                <div class="item-actions"><button class="remove" title="Remove from queue / cancel" onclick={() => runner.remove(job.id)}><Icon name="x" size={12} /> Remove</button></div>
              </div>
            {/each}
          </div>
        </div>
      {/if}

      {#if ready.length}
        <div class="section" data-ui="queue-ready">
          <div class="section-head success">
            <span><Icon name="package" size={14} color="var(--zone-ready)" /> Ready to Bundle &amp; Transfer ({ready.length})</span>
            <button class="btn small" title="Remove all prepared mods from queue" onclick={() => runner.clear('ready')}>Clear Ready</button>
          </div>
          <div class="items">
            {#if conflicts.length}
              <div class="conflict-box">
                <div class="row"><span class="big"><Icon name="triangle-alert" size={20} color="var(--warn-text)" /></span><div><div class="c-title">{conflicts.length} Conflict Group(s) Detected in Queue</div><div class="c-sub">Multiple ready mods modify the same animation or conflict with installed mods.</div></div></div>
                <button class="resolve" onclick={() => (flow.queueConflicts = conflicts)}>Resolve Conflicts</button>
              </div>
            {/if}
            {#each ready as job (job.id)}
              {@const bad = conflicting.has(job.id)}
              <div class="item {route.get(job.id) ?? ''}" class:bad>
                <div class="left">
                  <span class="name">{job.mod_name}{#if isMerged(job)}<span class="mini merged" title="Its Spine textures are merged: if this mod causes a problem in game, that may be the reason">Merged</span>{/if}</span>
                  <span class="desc ok"><Icon name="check" size={12} /> Prepared ({job.prepared_data ? job.prepared_data.bundle_name : 'Ready'}){#if route.get(job.id) === 'bundled'}<span class="mini route bundled">Bundled</span>{:else if route.get(job.id) === 'standalone'}<span class="mini route standalone">Standalone</span>{/if}{#if bad}<span class="mini warn"><Icon name="triangle-alert" size={12} color="var(--warn-text)" /> Conflict</span>{/if}</span>
                </div>
                <div class="item-actions">
                  {#if bad}<button class="resolve small" title="Resolve this conflict" onclick={() => (flow.queueConflicts = conflicts)}>Resolve</button>{/if}
                  <button class="remove" title="Remove from transfer queue" onclick={() => runner.remove(job.id)}><Icon name="x" size={12} /> Remove</button>
                </div>
              </div>
            {/each}
          </div>
        </div>
      {/if}

      {#if failed.length}
        <div class="section failed" data-ui="queue-failed">
          <div class="section-head danger">
            <span><Icon name="circle-x" size={14} color="var(--danger-text)" /> Failed Mods ({failed.length})</span>
            <div class="right">
              <button class="outline-danger" onclick={() => failed.forEach((j) => runner.retry(j.id))}><Icon name="refresh-cw" size={14} /> Retry All Failed</button>
              <button class="remove-all" title="Remove all failed jobs from queue" onclick={() => runner.clear('failed')}><Icon name="trash-2" size={14} /> Remove All Failed</button>
            </div>
          </div>
          <div class="items">
            {#each failed as job (job.id)}
              <div class="item">
                <div class="left"><span class="name">{job.mod_name}{#if isMerged(job)}<span class="mini merged" title="Its Spine textures are merged: if this mod causes a problem in game, that may be the reason">Merged</span>{/if}</span><span class="desc bad-text"><Icon name="triangle-alert" size={14} color="var(--warn-text)" /> {job.error || 'Failed'}</span></div>
                <div class="item-actions">
                  <button class="outline-danger" title="Retry this mod" onclick={() => runner.retry(job.id)}><Icon name="refresh-cw" size={14} /> Retry</button>
                  <button class="remove" title="Dismiss / Remove from queue" onclick={() => runner.remove(job.id)} aria-label="Dismiss"><Icon name="x" size={12} /></button>
                </div>
              </div>
            {/each}
          </div>
        </div>
      {/if}

      {#if done.length}
        <div class="section" data-ui="queue-done">
          <div class="section-head muted"><span><Icon name="check" size={14} /> Completed Transfers ({done.length})</span><button class="btn small" title="Clear completed tasks from list" onclick={() => runner.clear('done')}>Clear Finished</button></div>
          <div class="items">
            {#each done as job (job.id)}
              <div class="item"><div class="left"><span class="name">{job.mod_name}</span><span class="desc done-text"><Icon name="check" size={12} /> Installed &amp; Active on Phone</span></div></div>
            {/each}
          </div>
        </div>
      {/if}
    </section>

    <AssemblyPlan {jobs} {transferring} onTransfer={() => flow.transfer()} />
  </div>
</Modal>

<style>
  .empty-state { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 0.5rem; text-align: center; color: var(--text-muted); }
  .empty-state .btn { margin-top: 0.5rem; }
  .empty-state .et { font-size: var(--fs-lg); font-weight: 600; color: var(--text-main); }
  .empty-state .es { font-size: var(--fs-md); }

  .pills { display: flex; align-items: center; gap: 0.5rem; margin-left: 0.75rem; }
  .pill { padding: 0.15rem 0.5rem; font-size: var(--fs-sm); font-weight: 600; border-radius: 4px; border: 1px solid; }
  .pill.danger { color: var(--danger-text); background: color-mix(in srgb, var(--danger) 18%, transparent); border-color: color-mix(in srgb, var(--danger) 40%, transparent); }
  .btn { white-space: nowrap; display: inline-flex; align-items: center; gap: 0.5rem; line-height: normal; padding: 0.55rem 1rem; font-size: var(--fs-md); min-height: 38px; font-weight: 600; color: var(--text-main); background: var(--tint-2); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); }
  .btn:hover { background: var(--tint-3); border-color: var(--tint-4); }
  .turbo-wrap { position: relative; display: inline-flex; }
  .btn.turbo.on { color: var(--warn-text); background: color-mix(in srgb, var(--warn) 15%, transparent); border-color: color-mix(in srgb, var(--warn) 50%, transparent); }
  .tip { display: none; position: absolute; top: calc(100% + 8px); right: 0; z-index: 5; width: 300px; padding: 0.65rem 0.8rem; font-size: var(--fs-sm); line-height: 1.45; color: var(--text-muted); background: var(--surface-2); border: 1px solid var(--border-focus); border-radius: var(--radius-sm); box-shadow: 0 10px 28px rgba(0, 0, 0, 0.6); }
  .tip strong { color: var(--text-main); }
  .turbo-wrap:hover .tip, .turbo-wrap:has(:focus-visible) .tip { display: block; } /* not :focus-within: a click leaves focus on the button and the tip would stay */
  .btn.small { padding: 0.5rem 1rem; font-size: var(--fs-md); min-height: 36px; }
  .split { flex: 1; min-height: 0; display: grid; grid-template-columns: 290px 1fr 310px; gap: 1rem; height: 100%; overflow: hidden; }
  /* the middle column is the green zone: what will be transferred */
  .main { --zone: var(--zone-ready); display: flex; flex-direction: column; min-height: 0; height: 100%; overflow-y: auto; gap: 1.15rem; padding: 0.85rem; background: var(--surface-panel); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); }
  .phone { display: flex; align-items: center; gap: 0.6rem; flex-shrink: 0; padding: 0.6rem 0.9rem; font-size: var(--fs-md); font-weight: 600; color: var(--text-main); background: var(--tint-1); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); }
  .pname { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .banner { display: flex; align-items: center; justify-content: space-between; gap: 1rem; padding: 1rem 1.25rem; background: color-mix(in srgb, var(--zone) 10%, transparent); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); flex-shrink: 0; }
  .info p { font-size: var(--fs-md); line-height: 1.4; color: var(--text-muted); }
  .info .warn { margin-top: 0.3rem; color: var(--warn-text); }
  .phone-warning { display: flex; align-items: center; justify-content: space-between; gap: 0.75rem; padding: 0.75rem 1rem; font-size: var(--fs-md); color: var(--warn-text); background: transparent; border: 1px solid color-mix(in srgb, var(--warn) 35%, transparent); border-radius: var(--radius-md); flex-shrink: 0; }
  .row { display: flex; align-items: center; gap: 0.5rem; } .big { font-size: var(--fs-xl); }
  .section { padding: 0.85rem 1rem; background: var(--tint-1); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); flex-shrink: 0; }
  .section.failed { background: transparent; border-color: color-mix(in srgb, var(--danger) 30%, transparent); }
  .section-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.75rem; padding-bottom: 0.4rem; font-size: var(--fs-md); font-weight: 700; border-bottom: 1px solid var(--border-subtle); }
.section-head.danger { color: var(--danger); } .section-head.muted { color: var(--text-muted); }
  .right { display: flex; align-items: center; gap: 0.5rem; margin-left: auto; }
  .items { display: flex; flex-direction: column; gap: 0.5rem; max-height: 280px; overflow-y: auto; }
  .item { display: flex; align-items: center; justify-content: space-between; gap: 0.75rem; padding: 0.55rem 0.85rem; font-size: var(--fs-md); background: var(--tint-1); border: 0; border-radius: var(--radius-sm); flex-shrink: 0; }
  .item { border-left: 3px solid transparent; }
  .item.bundled { border-left-color: var(--zone-bundled); }
  .item.standalone { border-left-color: var(--zone-standalone); }
  .item.bad { border-left-color: var(--warn); }
  .mini.route { margin-left: 0.4rem; }
  .mini.route.bundled { color: var(--zone-bundled); background: color-mix(in srgb, var(--zone-bundled) 15%, transparent); border-color: color-mix(in srgb, var(--zone-bundled) 40%, transparent); }
  .mini.route.standalone { color: var(--zone-standalone); background: color-mix(in srgb, var(--zone-standalone) 15%, transparent); border-color: color-mix(in srgb, var(--zone-standalone) 40%, transparent); }
  .left { display: flex; flex-direction: column; gap: 0.2rem; flex: 1; min-width: 0; }
  .name { font-weight: 600; color: var(--text-main); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .desc { display: flex; align-items: center; gap: 0.4rem; font-size: var(--fs-sm); color: var(--text-dim); }
.desc.done-text { color: var(--ok); } .desc.bad-text { color: var(--danger); }
  .mini { padding: 1px 6px; font-size: var(--fs-xs); font-weight: 600; border-radius: 4px; border: 1px solid; }
  .mini.accent { color: var(--ok-text); background: color-mix(in srgb, var(--ok) 15%, transparent); border-color: color-mix(in srgb, var(--ok) 30%, transparent); }
  .mini.primary { color: var(--text-main); background: var(--tint-2); border-color: transparent; }
  .mini.subtle { color: var(--text-dim); background: transparent; border-color: transparent; font-family: var(--font-mono); }
  .mini.merged { margin-left: 0.5rem; vertical-align: 1px; color: var(--cat-merged); background: color-mix(in srgb, var(--cat-merged) 15%, transparent); border-color: transparent; }
  .mini.warn { margin-left: 6px; color: var(--warn-text); background: color-mix(in srgb, var(--warn) 25%, transparent); border-color: color-mix(in srgb, var(--warn) 40%, transparent); }
  .progress { width: 140px; flex-shrink: 0; display: flex; flex-direction: column; gap: 0.25rem; }
  .bar { width: 100%; height: 6px; overflow: hidden; background: var(--tint-2); border-radius: 999px; }
  .fill { height: 100%; background: linear-gradient(90deg, var(--primary), var(--primary)); border-radius: 999px; transition: width 0.3s ease; }
  .ptext { font-size: var(--fs-xs); color: var(--text-dim); text-align: right; }
  .item-actions { display: flex; align-items: center; gap: 0.5rem; flex-shrink: 0; }
  .remove { padding: 0.55rem 0.95rem; min-height: 36px; font-size: var(--fs-md); font-weight: 600; line-height: 1; color: var(--text-dim); background: var(--tint-2); border: 1px solid var(--tint-4); border-radius: var(--radius-sm); transition: all 0.15s ease; }
  .remove:hover { color: var(--danger-text); background: color-mix(in srgb, var(--danger) 20%, transparent); border-color: color-mix(in srgb, var(--danger) 50%, transparent); }
  .outline-danger { padding: 0.55rem 0.95rem; min-height: 36px; font-size: var(--fs-md); font-weight: 600; color: var(--danger-text); background: transparent; border: 1px solid color-mix(in srgb, var(--danger) 50%, transparent); border-radius: var(--radius-sm); }
  .outline-danger:hover { color: var(--text-main); background: color-mix(in srgb, var(--danger) 15%, transparent); border-color: var(--danger); }
  .remove-all { padding: 0.55rem 0.95rem; min-height: 36px; font-size: var(--fs-md); font-weight: 600; color: var(--text-muted); background: transparent; border: 1px solid var(--tint-4); border-radius: var(--radius-sm); }
  .remove-all:hover { color: var(--danger-text); background: color-mix(in srgb, var(--danger) 15%, transparent); border-color: color-mix(in srgb, var(--danger) 40%, transparent); }
  .conflict-box { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px; padding: 10px 14px; background: transparent; border: 1px solid color-mix(in srgb, var(--warn) 40%, transparent); border-radius: 8px; flex-shrink: 0; }
  .c-title { font-size: var(--fs-md); font-weight: 700; color: var(--warn-text); } .c-sub { font-size: var(--fs-sm); color: var(--text-muted); }
  .resolve { padding: 0.6rem 1.1rem; min-height: 38px; font-size: var(--fs-md); font-weight: 700; color: #000; background: var(--warn); border: none; border-radius: 6px; }
  .resolve.small { padding: 0.5rem 0.95rem; min-height: 36px; font-size: var(--fs-md); font-weight: 600; color: var(--warn-text); background: color-mix(in srgb, var(--warn) 10%, transparent); border: 1px solid color-mix(in srgb, var(--warn) 40%, transparent); }
  @media (max-width: 1100px) { .split { grid-template-columns: 260px 1fr; } .split > :global(.sidebar:last-child) { display: none; } }
</style>
