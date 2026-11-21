<script lang="ts">
  import ToolBar from './ToolBar.svelte'
  import { onMount } from 'svelte'
  import { api, type Spine42Scan } from '../../lib/api'
  import type { AppState } from '../../state/app.svelte'
  import type { ToolRun } from '../../lib/toolRun.svelte'
  import { friendly } from '../../lib/toolRun.svelte'

  let { app, tool }: { app: AppState; tool: ToolRun } = $props()
  let scan = $state<Spine42Scan | null>(null)

  const fetchScan = async () => { scan = await api.spine42Scan() }
  /** The check reads every skeleton of the library, which takes a while on a big one: the status panel shows it running and how far it is. */
  const load = () => tool.run('Checking the mod skeletons…', fetchScan)
  onMount(load)

  const update = () => {
    if (!confirm(`Update ${scan?.v41 ?? 0} skeletons to Spine 4.2?\n\nEvery changed file is copied to a ".spine41" folder next to it first, so the original stays. Mods already on the phone are not touched: prepare and install them again.`)) return
    void tool.run('Updating the mod skeletons to Spine 4.2…', async () => {
      const r = await api.spine42Update()
      scan = r.counts
      return { kind: r.failed.length ? 'error' : 'ok', text: `${r.updated} of ${r.checked} skeletons updated to Spine 4.2.${r.failed.length ? ` ${r.failed.length} damaged file(s) were left as they are (see the Console).` : ''}` }
    })
  }
</script>

<div class="s-panel" data-ui="spine42-tool"><div class="s-page">
  <p class="s-lead">The game now uses Spine 4.2, and a mod made for 4.1 does not load in game. This converts the skeletons of your mods. Mods you prepare for install are converted automatically either way; this makes the files themselves 4.2.</p>
  <section class="s-section">
    <h3 class="s-title">Your mod skeletons</h3>
    <div class="s-card">
      <div class="s-row"><span class="s-text"><strong>Spine 4.1 (need updating)</strong></span><span class="s-value">{scan ? `${scan.v41} in ${scan.folders} mod folders` : 'Checking…'}</span></div>
      <div class="s-row"><span class="s-text"><strong>Spine 4.2 (up to date)</strong></span><span class="s-value">{scan ? scan.v42 : 'Checking…'}</span></div>
      {#if scan && scan.other}<div class="s-row"><span class="s-text"><strong>Not recognised</strong><span>Damaged or from another Spine version: left alone.</span></span><span class="s-value">{scan.other}</span></div>{/if}
    </div>
  </section>
</div>
<ToolBar {app} {tool}>
  <button class="tool-btn" disabled={tool.busy} onclick={load}>Check again</button>
  <button class="tool-btn primary" disabled={tool.busy || !scan?.v41} onclick={update}>Update all to Spine 4.2</button>
</ToolBar>
</div>
