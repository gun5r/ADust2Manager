<script lang="ts">
  import ToolBar from './ToolBar.svelte'
  import { onMount } from 'svelte'
  import { api } from '../../lib/api'
  import { tabRoot } from '../../lib/filters'
  import type { AppState } from '../../state/app.svelte'
  import type { ToolRun } from '../../lib/toolRun.svelte'

  let { app, tool }: { app: AppState; tool: ToolRun } = $props()

  let scenes = $state<{ scene: string; number: number; character: string | null; costume: string | null }[]>([])
  let pick = $state('')
  // svelte-ignore state_referenced_locally
  let root = $state(app.library.activeTab ? tabRoot(app.library.activeTab) : '')

  onMount(async () => {
    try {
      scenes = (await api.datingScenes()).scenes
      pick = scenes.at(-1)?.scene ?? ''
    } catch (e) {
      tool.message = { kind: 'error', text: String(e) }
    }
  })

  const label = (s: (typeof scenes)[number]) => `Scene ${s.number}${s.character ? ` · ${s.character} - ${s.costume}` : ''}`

  const download = () => tool.run("Taking the scene out of the game's dating bundle (the first run downloads ~450 MB)…", async () => {
    app.log(`Taking ${pick} out of the game's dating bundle...`)
    const r = await api.downloadDatingScene(pick, root)
    await app.rescanRoot(root)
    return `Saved ${r.folders.length} folder${r.folders.length === 1 ? '' : 's'} in that tab. They are in the mod list now.`
  })
</script>

<div class="s-panel" data-ui="dating-scenes-tool"><div class="s-page">
  <p class="s-lead">Writes a dating scene from the game's files as a mod folder in a folder tab, to preview it when no mod exists. First run downloads about 450 MB.</p>
  <section class="s-section">
    <h3 class="s-title">Scene</h3>
    <div class="s-card">
      <label class="s-row"><span class="s-text"><strong>Scene</strong></span>
        <select class="tool-field" bind:value={pick} disabled={tool.busy}>{#each scenes as s (s.scene)}<option value={s.scene}>{label(s)}</option>{/each}</select></label>
      <label class="s-row"><span class="s-text"><strong>Folder tab</strong></span>
        <select class="tool-field" bind:value={root} disabled={tool.busy}>{#each app.library.tabs as t (t.id)}<option value={tabRoot(t)}>{t.name}</option>{/each}</select></label>
    </div>
  </section>
</div>
<ToolBar {app} {tool}><button class="tool-btn primary" disabled={tool.busy || !pick || !root} onclick={download}>Download scene</button></ToolBar>
</div>
