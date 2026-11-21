<script lang="ts">
  import ToolBar from './ToolBar.svelte'
  import Icon from '../../ui/Icon.svelte'
  import { onMount } from 'svelte'
  import { api, type SkeletonCase } from '../../lib/api'
  import type { AppState } from '../../state/app.svelte'
  import { friendly, type ToolRun } from '../../lib/toolRun.svelte'

  let { app, tool }: { app: AppState; tool: ToolRun } = $props()

  /** `choice`: '' nothing picked yet, 'game' the original from the game servers, otherwise a donor folder. */
  type Row = SkeletonCase & { choice: string; state: 'idle' | 'working' | 'done' | 'error'; error: string }
  let rows = $state<Row[] | null>(null)
  let stop = false

  async function scan() {
    tool.message = null
    try {
      rows = (await api.skeletonScan()).mods.map((m) => ({ ...m, choice: '', state: 'idle', error: '' }))
    } catch (e) {
      rows = []
      tool.message = { kind: 'error', text: friendly(e) }
    }
  }
  onMount(scan)

  const open = $derived((rows ?? []).filter((r) => r.state !== 'done'))
  const fixed = $derived((rows ?? []).filter((r) => r.state === 'done').length)

  async function fixRow(row: Row, choice: string): Promise<boolean> {
    row.state = 'working'
    row.error = ''
    try {
      await api.fixSkeleton(row.folder_path, choice === 'game' ? undefined : choice)
      row.state = 'done'
      return true
    } catch (e) {
      row.state = 'error'
      row.error = friendly(e)
      return false
    }
  }

  /** One at a time: the original bundles come from the game servers, and bursts of downloads can get this IP rate limited. */
  function run(pick: (r: Row) => string) {
    stop = false
    const todo = open.filter((r) => pick(r))
    return tool.run('Fixing skeletons…', async () => {
      let ok = 0
      for (const [i, row] of todo.entries()) {
        if (stop) break
        row.choice = pick(row)
        tool.step(`Fixing skeleton ${i + 1} of ${todo.length}: ${row.name}…`)
        if (await fixRow(row, row.choice)) ok++
      }
      tool.step('Adding the fixed mods to the list…')
      await app.rescanFolders(todo.filter((r) => r.state === 'done').map((r) => r.folder_path))
      return { kind: ok === todo.length ? 'ok' : 'error', text: `${ok} of ${todo.length} skeletons added${stop ? ' (stopped)' : ''}. ${todo.length - ok ? 'See the failed rows.' : ''}` }
    })
  }

  const autoFix = () => run((r) => r.donors[0]?.folder_path ?? 'game')
  const fixChosen = () => run((r) => r.choice)
  function downloadAll() {
    const n = open.length
    if (!confirm(`Download the game's original skeleton for all ${n} mods, even those that have a donor?\n\nEvery different game file is downloaded from the official servers, one after another. Fetching many files in a short time can get your IP rate limited by them.\n\nContinue?`)) return
    void run(() => 'game')
  }
  const single = (row: Row) => tool.run(`Fixing the skeleton of ${row.name}…`, async () => {
    await fixRow(row, row.choice)
    if (row.state === 'done') await app.rescanFolders([row.folder_path])
  })
</script>

<div class="s-panel" data-ui="skeleton-tool"><div class="s-page">
  <p class="s-lead">Finds mods that have textures but no skeleton and adds one: copied from another mod of the same costume, or the game's original.</p>
  <section class="s-section">
    <h3 class="s-title">Mods without a skeleton</h3>
    <div class="s-card">
      <div class="s-row"><span class="s-text"><strong>
        {#if rows === null}Scanning…{:else if !rows.length}No mod without a skeleton.{:else}{open.length} without a skeleton{fixed ? `, ${fixed} fixed` : ''}{/if}
      </strong></span></div>
      {#if rows?.length}
        <ul class="s-list">
          {#each rows as row (row.folder_path)}
            <li class={row.state}>
              <span class="name" title={row.folder_path}>{row.name}</span>
              {#if row.state === 'done'}
                <span class="ok"><Icon name="check" size={12} /> fixed</span>
              {:else}
                <select class="tool-field sm" bind:value={row.choice} disabled={tool.busy || row.state === 'working'} aria-label="Skeleton for {row.name}">
                  <option value="">Choose…</option>
                  {#each row.donors as d (d.folder_path)}<option value={d.folder_path}>Copy from {d.name}</option>{/each}
                  <option value="game">Download the game's original</option>
                </select>
                <button class="tool-btn sm" disabled={tool.busy || !row.choice || row.state === 'working'} onclick={() => single(row)}>{row.state === 'working' ? '…' : 'Fix'}</button>
              {/if}
              {#if row.error}<span class="err" title={row.error}>{row.error}</span>{/if}
            </li>
          {/each}
        </ul>
      {/if}
    </div>
  </section>
</div>
<ToolBar {app} {tool}>
  <button class="tool-btn" disabled={tool.busy} onclick={scan}>Rescan</button>
  <button class="tool-btn" disabled={tool.busy || !open.length} onclick={downloadAll}>Download all…</button>
  <button class="tool-btn" disabled={tool.busy || !open.some((r) => r.choice)} onclick={fixChosen}>Fix chosen</button>
  {#if tool.busy}<button class="tool-btn danger" onclick={() => (stop = true)}>Stop</button>{:else}<button class="tool-btn primary" disabled={!open.length} onclick={autoFix}>Auto-fix all</button>{/if}
</ToolBar>
</div>

<style>
  .name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text-main); }
  select { flex: none; width: 15rem; }
  .ok { color: var(--ok-text); font-weight: 600; }
  .err { max-width: 12rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--danger-text); }
  li.error { box-shadow: inset 3px 0 0 var(--danger); }
</style>
