<script lang="ts">
  import ToolBar from './ToolBar.svelte'
  import { onMount } from 'svelte'
  import { api, type PhoneBackup } from '../../lib/api'
  import type { AppState } from '../../state/app.svelte'
  import { friendly, type ToolRun } from '../../lib/toolRun.svelte'
  import { formatBytes } from '../../lib/duplicates'

  let { app, tool }: { app: AppState; tool: ToolRun } = $props()

  let rows = $state<PhoneBackup[] | null>(null)
  const device = $derived(app.adb.state === 'connected' ? app.devices[0]?.id : undefined)

  async function load() {
    tool.message = null
    if (!device) { rows = []; return }
    try {
      rows = (await api.phoneBackups(device)).backups
    } catch (e) {
      rows = []
      tool.message = { kind: 'error', text: friendly(e) }
    }
  }
  onMount(load)

  /** Run `act` on each backup, one after another; the list is read again at the end. */
  const each = (title: string, list: PhoneBackup[], act: (id: string, b: PhoneBackup) => Promise<unknown>, done: string) => tool.run(title, async () => {
    let ok = 0
    for (const [i, b] of list.entries()) {
      tool.step(`${title.replace('…', '')} ${i + 1} of ${list.length}…`)
      try { await act(device!, b); ok++ } catch { /* counted below */ }
    }
    await load()
    return { kind: ok === list.length ? 'ok' : 'error', text: `${ok} of ${list.length} ${done}.` }
  })

  const restore = (list: PhoneBackup[]) => {
    if (!confirm(`Restore ${list.length === 1 ? 'this original file' : `all ${list.length} original files`} on the phone?\n\nThe mod that replaced it goes away and the game's original comes back; the backup is used up. Mods you installed there stay marked as installed in the manager.`)) return
    void each('Restoring…', list, api.restoreBackup, 'restored')
  }
  const remove = (list: PhoneBackup[]) => {
    if (!confirm(`Delete ${list.length === 1 ? 'this backup' : `all ${list.length} backups`}?\n\nThe installed mods stay as they are. You can always get the game's original files back with the repair or re-download button in the game.`)) return
    void each('Deleting…', list, api.deleteBackup, 'deleted')
  }
  const when = (seconds: number) => new Date(seconds * 1000).toLocaleString()
</script>

<div class="s-panel" data-ui="backups-tool"><div class="s-page">
  <p class="s-lead">Before a mod overwrites a game file, the original is kept on the phone. Restore puts it back (the mod goes away); Delete keeps the mod and removes the backup.</p>
  <section class="s-section">
    <h3 class="s-title">Backups on the phone</h3>
    <div class="s-card">
      <div class="s-row"><span class="s-text"><strong>
        {#if !device}Connect the phone (USB debugging) to see its backups.{:else if rows === null}Reading the phone…{:else if !rows.length}No backups on the phone.{:else}<strong>{rows.length}</strong> backup{rows.length === 1 ? '' : 's'}, {formatBytes(rows.reduce((n, b) => n + b.size, 0))}.{/if}
      </strong></span></div>
      {#if rows?.length}
        <ul class="s-list">
          {#each rows as b (b.bundle_name + b.bundle_hash)}
            <li>
              <span class="name" title="{b.bundle_name} / {b.bundle_hash}">{b.bundle_name}</span>
              <span class="meta" title={when(b.modified)}>{b.bundle_hash.slice(0, 8)} · {formatBytes(b.size)} · {when(b.modified)}</span>
              <button class="tool-btn sm" disabled={tool.busy} onclick={() => restore([b])}>Restore</button>
              <button class="tool-btn sm danger" disabled={tool.busy} onclick={() => remove([b])}>Delete</button>
            </li>
          {/each}
        </ul>
      {/if}
    </div>
  </section>
</div>
<ToolBar {app} {tool}>
  <button class="tool-btn danger" disabled={tool.busy || !rows?.length} onclick={() => remove(rows!)}>Delete all…</button>
  <button class="tool-btn" disabled={tool.busy} onclick={load}>Refresh</button>
  <button class="tool-btn primary" disabled={tool.busy || !rows?.length} onclick={() => restore(rows!)}>Restore all…</button>
</ToolBar>
</div>

<style>
  .name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--text-main); }
  .meta { white-space: nowrap; font-size: var(--fs-sm); color: var(--text-muted); }
</style>
