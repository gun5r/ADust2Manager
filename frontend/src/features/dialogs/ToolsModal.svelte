<script lang="ts">
  import { api, type DatingInfo } from '../../lib/api'
  import { friendly, ToolRun } from '../../lib/toolRun.svelte'
  import { formatBytes } from '../../lib/duplicates'
  import { portraitEligible } from '../../lib/portraits'
  import type { AppState } from '../../state/app.svelte'
  import Modal from '../../ui/Modal.svelte'
  import Icon from '../../ui/Icon.svelte'
  import '../../styles/tools.css'
  import StatusDot from '../../ui/StatusDot.svelte'
  import SkeletonTool from './SkeletonTool.svelte'
  import SettingsTool from './SettingsTool.svelte'
  import BackupsTool from './BackupsTool.svelte'
  import Spine42Tool from './Spine42Tool.svelte'
  import ToolBar from './ToolBar.svelte'
  import ToolStatus from './ToolStatus.svelte'
  import DatingScenesTool from './DatingScenesTool.svelte'

  let { app, onClose }: { app: AppState; onClose: () => void } = $props()

  // More tools go here: an id, a name and the panel of the right-hand side is chosen by id below.
  const tools = [
    { group: '', id: 'settings', name: 'General', icon: 'settings', blurb: 'Preferences' },
    { group: 'Setup', id: 'setup', icon: 'rocket', name: 'Initial Setup', blurb: 'Characters and portraits, optionally the dating simulator' },
    { group: 'Setup', id: 'characters', icon: 'users', name: 'Update Characters', blurb: 'Characters, costumes and portraits' },
    { group: 'Setup', id: 'portraits', icon: 'images', name: 'Generate Portraits', blurb: 'Thumbnails for Costume mode' },
    { group: 'Dating', id: 'dating', icon: 'heart', name: 'Simulator Data', blurb: 'Touch rules and sound names of the dating scenes' },
    { group: 'Dating', id: 'scenes', icon: 'clapperboard', name: 'Download Scenes', blurb: "A dating scene from the game as a mod folder" },
    { group: 'Maintenance', id: 'spine42', icon: 'refresh-cw', name: 'Spine 4.2 Update', blurb: 'Convert your mods to the Spine version the game uses now' },
    { group: 'Maintenance', id: 'skeleton', icon: 'bone', name: 'Mass Skeleton Fix', blurb: 'Add the missing skeletons' },
    { group: 'Maintenance', id: 'backups', icon: 'hard-drive', name: 'Phone Backups', blurb: 'Restore or delete the original game files the manager saved on the phone' },
    { group: 'Maintenance', id: 'troubleshooting', icon: 'wrench', name: 'Troubleshooting', blurb: 'Phone connection (adb) and fixes for previews that look wrong' },
  ]
  // the tab to open on is read once, when the window opens
  // svelte-ignore state_referenced_locally
  let selected = $state(app.toolsTab)
  const current = $derived(tools.find((t) => t.id === selected))
  // svelte-ignore state_referenced_locally
  app.toolsTab = 'settings'

  let info = $state<DatingInfo | null>(null)
  let chars = $state<{ count: number; costumes: number; updated_at: number | null; portraits: number } | null>(null)
  let thumbs = $state<{ count: number; bytes: number; updated_at: number | null } | null>(null)
  const pj = $derived(app.portraits)
  const eligible = $derived(app.library.mods.filter(portraitEligible).length)
  /** The tool in progress: what it is doing, and how it ended (see ToolRun). */
  const tool = new ToolRun(() => app.logs)
  const busy = $derived(tool.busy)

  const refresh = async () => { try { info = await api.datingDataInfo() } catch { /* keeps the last numbers */ } }
  const refreshChars = async () => { try { chars = await api.charactersInfo() } catch { /* keeps the last numbers */ } }
  const refreshThumbs = async () => { try { thumbs = await api.portraitsInfo() } catch { /* keeps the last numbers */ } }
  $effect(() => { void refresh(); void refreshChars(); void refreshThumbs(); void app.portraits.refresh() })
  let adbFound = $state<boolean | null>(null)
  let adbPath = $state('')
  const refreshAdb = async () => { try { const r = await api.adbInfo(); adbFound = r.found; adbPath = r.found ? r.path : '' } catch { /* keeps the last state */ } }
  const installAdb = () => tool.run('Downloading adb…', async () => {
    await api.installAdb()
    await refreshAdb()
    void app.refreshDevices?.()
    return 'adb is ready. Connect your phone with USB debugging on.'
  })
  $effect(() => { void refreshAdb() })
  const when = (t: number | null | undefined) => (t ? new Date(t * 1000).toLocaleString() : 'Never')

  const datingSummary = (r: { scenes: number; spots: number; matched: number; unmatched: number[] }) =>
    `Done: ${r.scenes} scenes, ${r.spots} spots, ${r.matched} matched to their sound banks.` + (r.unmatched.length ? ` No sound match for scene(s) ${r.unmatched.join(', ')}.` : '')

  let apkPath = $state('')
  const updateFromApk = () => tool.run('Updating the dating data from the APK file…', async () => datingSummary(await api.updateDatingDataFromApk(apkPath))).then(refresh)
  const update = () => tool.run('Updating the dating data from the phone…', async () => datingSummary(await api.updateDatingData())).then(refresh)

  const updateCharacters = () => tool.run('Downloading the character list and costume portraits…', async () => {
    const r = await app.updateCharacters()
    return r.portrait_error
      ? { kind: 'error', text: `Characters updated (${r.total} in total), but the costume portraits failed: ${r.portrait_error}` }
      : `Done: ${r.added} added, ${r.updated} updated, ${r.total} characters and ${r.portraits ?? chars?.portraits ?? 0} costume portraits.`
  }).then(refreshChars)

  /** Also draw the variants of multimods (they are not in the mod list, but the conflict windows show their portraits). */
  let withVariants = $state(false)
  async function generate(all: boolean) {
    tool.message = null
    await app.portraits.generate(app.library.mods, all, withVariants)
    await refreshThumbs()
    const p = app.portraits
    tool.message = { kind: p.failed ? 'error' : 'ok', text: `${p.done} of ${p.total} processed${p.failed ? `, ${p.failed} could not be drawn (see the Console)` : ''}.` }
  }

  async function removePortraits() {
    if (!confirm('Delete all generated mod portraits? You can generate them again at any time.')) return
    await tool.run('Deleting the mod portraits…', async () => {
      thumbs = await api.deletePortraits()
      await app.portraits.refresh()
      return 'Mod portraits deleted.'
    })
  }

  async function removeCharacters() {
    if (!confirm('Delete all character data?\n\nNames, costume names, dating links and costume portraits are removed, and your mods are listed under Others until you press Update Characters, which rebuilds everything from the website and the game.')) return
    await tool.run('Deleting the character data…', async () => {
      await app.deleteCharacters()
      return 'Character data deleted. Press Update Characters to rebuild it.'
    }).then(refreshChars)
  }

  const downloadSounds = () => tool.run('Downloading the sounds of every dating scene…', async () => {
    const r = await api.downloadDatingSounds()
    return { kind: r.failed.length ? 'error' : 'ok', text: `Sounds ready for all ${r.with_sounds} scenes${r.downloaded.length ? ` (${r.downloaded.length} just downloaded)` : ''}.` + (r.failed.length ? ` Failed: scene(s) ${r.failed.join(', ')}.` : '') }
  }).then(refresh)

  async function remove() {
    if (!confirm('Delete the dating data?\n\nThe touch simulator and its sounds stop working until you update it again from a connected phone.')) return
    await tool.run('Deleting the dating data…', async () => { info = await api.deleteDatingData(); return 'Dating data deleted.' })
  }

  /** One go: characters (website + game servers), the dating tables (phone or APK), then the sounds. Each step reports, a failure stops the run. */
  type Step = { name: string; state: 'wait' | 'run' | 'ok' | 'skip' | 'error'; note: string }
  let steps = $state<Step[]>([])
  /** The dating simulator is optional: its data takes a long time (about 5 to 15 minutes) and only the touch simulation needs it. */
  let withDating = $state(false)
  const setupAll = () => tool.run('Setting up…', async () => {
    const wanted = withDating ? 4 : 2
    steps = ['Phone connection (adb)', 'Characters and costume portraits', 'Dating simulator data', 'Dating sounds'].slice(0, wanted).map((name) => ({ name, state: 'wait', note: '' }))
    /** Runs step `i`; its text result is a note that the step was skipped or partly done, no result means it went fine. */
    const step = async (i: number, job: () => Promise<string | void>): Promise<boolean> => {
      steps[i].state = 'run'
      tool.step(`Step ${i + 1} of ${steps.length}: ${steps[i].name}…`)
      try {
        const note = await job()
        steps[i].state = note ? 'skip' : 'ok'
        if (note) steps[i].note = note
        return true
      } catch (e) {
        steps[i].state = 'error'
        steps[i].note = friendly(e)
        return false
      }
    }
    // adb first: the dating tables can be read from the phone only with it. Without internet this is a note, not a failure (the APK path still works).
    await step(0, async () => {
      if ((await api.adbInfo()).found) return
      try { await api.installAdb() } catch (e) { return `Could not download adb (${friendly(e)}); the APK file path below still works.` }
      await app.refreshDevices()
      steps[0].note = 'Downloaded Google\'s platform-tools'
    })
    const characters = await step(1, async () => { const r = await app.updateCharacters(); steps[1].note = `${r.total} characters, ${r.portraits ?? 0} costume portraits`; if (r.portrait_error) return `Names done, portraits failed: ${r.portrait_error}` })
    const done = characters && (!withDating || (await step(2, async () => {
        if (apkPath.trim()) { const r = await api.updateDatingDataFromApk(apkPath); steps[2].note = `${r.scenes} scenes, ${r.spots} spots from the APK`; return }
        if (app.adb.state === 'connected') { const r = await api.updateDatingData(); steps[2].note = `${r.scenes} scenes, ${r.spots} spots from the phone`; return }
        if (info?.files) return 'Kept the data you already have (no phone and no APK file given)'
        throw new Error("Connect the phone with USB debugging, or type the path of the game's APK below, then run this again.")
      }))
      && (await step(3, async () => { const r = await api.downloadDatingSounds(); steps[3].note = `${r.with_sounds} scenes${r.downloaded.length ? `, ${r.downloaded.length} just downloaded` : ''}`; if (r.failed.length) return `Failed: scene(s) ${r.failed.join(', ')}` })))
    const failed = steps.find((s) => s.state === 'error')
    return failed ? { kind: 'error', text: `${failed.name}: ${failed.note}` } : done ? 'Everything is set up.' : undefined
  }).then(() => Promise.all([refresh(), refreshChars()]))
</script>

<Modal label="Settings / Tools" width="1060px" height="700px" {onClose}>
  {#snippet title()}Settings <span class="slash">/</span> <span class="crumb">{current?.name ?? ''}</span>{/snippet}
  <div class="layout">
    <nav class="list" aria-label="Settings and tools">
      {#each tools as t, i (t.id)}
        {#if t.group && t.group !== tools[i - 1]?.group}<span class="group">{t.group}</span>{/if}
        <button class="item" class:active={selected === t.id} title={t.blurb} onclick={() => { selected = t.id; tool.message = null }}>
          <Icon name={t.icon} size={16} /><strong>{t.name}</strong>
        </button>
      {/each}
    </nav>

    <section class="panel">
      {#snippet adbBar()}
      <button class="adb" class:off={app.adb.state !== 'connected'} title="Check for connected phones again" onclick={() => app.refreshDevices()}>
        <StatusDot state={app.adb.state} /><span class="name">{app.adb.label}</span>
        <span class="retry"><Icon name="refresh-cw" size={13} /> {app.adb.state === 'connected' ? 'Refresh' : 'Retry'}</span>
      </button>
      {/snippet}

      {#if selected === 'settings'}
        <SettingsTool {app} />
        <ToolStatus {app} {tool} />
      {:else if selected === 'setup'}
        <div class="s-panel"><div class="s-page">
          <p class="s-lead">Run once on a new computer; later runs only fill in what is missing.</p>
          <section class="s-section">
            <h3 class="s-title">Options</h3>
            <div class="s-card">
              <label class="s-row">
                <span class="s-text"><strong>Also set up the dating simulator</strong><span>Reads the dating data and downloads the sounds (about 450 MB, <b class="warn">5 to 15 minutes.</b>)</span></span>
                <input class="s-switch" type="checkbox" role="switch" bind:checked={withDating} disabled={busy} />
              </label>
              {#if withDating}
                <div class="s-row note"><span class="s-text"><span>The dating data cannot be downloaded from the BD2 CDN: choose one method to get it, either the game's APK file or your phone.</span></span></div>
                <div class="s-row stack">
                  <div class="s-text"><strong>Game APK</strong></div>
                  <div class="s-ctl"><input class="tool-field grow" type="text" spellcheck="false" placeholder="/path/to/browndust2.apk" bind:value={apkPath} aria-label="Path of the game's APK file" /></div>
                </div>
                <div class="or" role="separator"><span>Or</span></div>
                <div class="s-row stack">{@render adbBar()}</div>
              {/if}
            </div>
          </section>
          {#if steps.length}
            <section class="s-section">
              <h3 class="s-title">Progress</h3>
              <div class="s-card">
                {#each steps as step}
                  <div class="s-row s-step {step.state}">
                    <span class="mark">{#if step.state === 'ok'}<Icon name="check" size={13} />{:else if step.state === 'error'}<Icon name="x" size={13} />{:else if step.state === 'run'}<Icon name="loader" size={13} />{:else if step.state === 'skip'}–{:else}○{/if}</span>
                    <span class="s-text" style="flex:1"><strong>{step.name}</strong>{#if step.note}<span>{step.note}</span>{/if}</span>
                  </div>
                {/each}
              </div>
            </section>
          {/if}
        </div>
        <ToolBar {app} {tool}><button class="tool-btn primary" disabled={busy} onclick={setupAll}>Start setup</button></ToolBar>
        </div>
      {:else if selected === 'dating'}
        <div class="s-panel"><div class="s-page">
          <p class="s-lead">Touch rules, spot sizes and sounds of the dating scenes, read from your phone or the game's APK. Update after a game update adds scenes. First update downloads about 450 MB.</p>
          <section class="s-section">
            <h3 class="s-title">Current data</h3>
            <div class="s-card">
              <div class="s-row"><span class="s-text"><strong>Last updated</strong></span><span class="s-value">{when(info?.updated_at)}</span></div>
              <div class="s-row"><span class="s-text"><strong>Files</strong></span><span class="s-value">{info ? (info.files ? `${formatBytes(info.bytes)} in ${info.files} files` : 'None') : '…'}</span></div>
              <div class="s-row"><span class="s-text"><strong>Scenes</strong></span><span class="s-value">{info ? `${info.scenes} known, ${info.with_sounds} with sounds` : '…'}</span></div>
              {#if info?.new_scenes.length}<div class="s-row"><span class="s-text"><strong>New scenes</strong><span class="warn">Scene {info.new_scenes.join(', ')} of your library: update from the phone to add them</span></span></div>{/if}
            </div>
          </section>
          <section class="s-section">
            <h3 class="s-title">Update</h3>
            <div class="s-card">
              <div class="s-row stack"><div class="s-text"><strong>Game APK file</strong></div>
                <div class="s-ctl"><input class="tool-field grow" type="text" spellcheck="false" placeholder="/path/to/browndust2.apk" bind:value={apkPath} onkeydown={(e) => e.key === 'Enter' && apkPath.trim() && updateFromApk()} aria-label="Path of the game's APK file" /></div></div>
              <div class="s-row stack">{@render adbBar()}</div>
            </div>
          </section>
        </div>
        <ToolBar {app} {tool}>
          <button class="tool-btn danger" disabled={busy || !info?.files} onclick={remove}>Delete data</button>
          <button class="tool-btn" disabled={busy || !info?.with_sounds} onclick={downloadSounds}>Download all sounds</button>
          <button class="tool-btn" disabled={busy || !apkPath.trim()} onclick={updateFromApk}>Update from APK</button>
          <button class="tool-btn primary" disabled={busy} onclick={update}>{busy ? 'Updating…' : 'Update from phone'}</button>
        </ToolBar>
        </div>
      {:else if selected === 'portraits'}
        <div class="s-panel"><div class="s-page">
          <p class="s-lead">Draws a thumbnail of each idle, skill and dating mod for Costume mode. Keep the manager open until it finishes.</p>
          <section class="s-section">
            <h3 class="s-title">Current data</h3>
            <div class="s-card">
              <div class="s-row"><span class="s-text"><strong>Last generated</strong></span><span class="s-value">{when(thumbs?.updated_at)}</span></div>
              <div class="s-row"><span class="s-text"><strong>Portraits</strong></span><span class="s-value">{thumbs ? `${thumbs.count} portraits, ${formatBytes(thumbs.bytes)} (${eligible} mods can have one)` : '…'}</span></div>
              {#if pj.running}<div class="s-row stack"><div class="s-text"><strong>Progress: {pj.done} / {pj.total}{pj.failed ? ` (${pj.failed} failed)` : ''}</strong></div><progress class="s-progress" max={pj.total} value={pj.done}></progress></div>{/if}
            </div>
          </section>
          <section class="s-section">
            <h3 class="s-title">Options</h3>
            <div class="s-card">
              <label class="s-row"><span class="s-text"><strong>Also the variants of multimods</strong><span>Adds portraits to the conflict window. Takes longer.</span></span>
                <input class="s-switch" type="checkbox" role="switch" bind:checked={withVariants} disabled={pj.running} /></label>
            </div>
          </section>
        </div>
        <ToolBar {app} {tool}>
          {#if pj.running}
            <button class="tool-btn danger" onclick={() => pj.cancel()}>Stop</button>
          {:else}
            <button class="tool-btn danger" disabled={!thumbs?.count} onclick={removePortraits}>Delete portraits</button>
            <button class="tool-btn" onclick={() => generate(true)}>Regenerate all</button>
            <button class="tool-btn primary" onclick={() => generate(false)}>Generate missing</button>
          {/if}
        </ToolBar>
        </div>
      {:else if selected === 'characters'}
        <div class="s-panel"><div class="s-page">
          <p class="s-lead">Gets characters, costumes and dating-scene links from the community site, and costume portraits from the game servers. Needs internet, not a phone.</p>
          <section class="s-section">
            <h3 class="s-title">Current data</h3>
            <div class="s-card">
              <div class="s-row"><span class="s-text"><strong>Last updated</strong></span><span class="s-value">{when(chars?.updated_at)}</span></div>
              <div class="s-row"><span class="s-text"><strong>Characters</strong></span><span class="s-value">{chars ? `${chars.count} characters, ${chars.costumes} costumes, ${chars.portraits} costume portraits` : '…'}</span></div>
            </div>
          </section>
        </div>
        <ToolBar {app} {tool}>
          <button class="tool-btn danger" disabled={busy || !chars?.count} onclick={removeCharacters}>Delete data</button>
          <button class="tool-btn primary" disabled={busy} onclick={updateCharacters}>{busy ? 'Updating…' : 'Update characters'}</button>
        </ToolBar>
        </div>
      {:else if selected === 'scenes'}
        <DatingScenesTool {app} {tool} />
      {:else if selected === 'troubleshooting'}
        <div class="s-page">
          <section class="s-section">
            <h3 class="s-title">Phone connection</h3>
            <div class="s-card">
              <div class="s-row"><span class="s-text"><strong>adb</strong></span><span class="s-value" class:warn={adbFound === false}>{adbFound === null ? '…' : adbFound ? 'Available' : 'Not found'}</span></div>
              {#if adbPath}<div class="s-row"><span class="s-text"><strong>Location</strong></span><span class="s-value path">{adbPath}</span></div>{/if}
              <div class="s-row"><div class="s-text"><strong>{adbFound ? 'Download adb again' : 'Download adb'}</strong><span>adb is how the manager talks to your phone. If it is missing, this downloads Google's platform-tools into the manager's own folder.</span></div><button class="tool-btn primary" disabled={busy} onclick={installAdb}>{adbFound ? 'Download again' : 'Download adb'}</button></div>
            </div>
          </section>
          <section class="s-section">
            <h3 class="s-title">Previews</h3>
            <div class="s-card">
              <label class="s-row"><span class="s-text"><strong>Premultiplied alpha (PMA) textures</strong><span>Turn on when the previews show washed-out or dark edges: the textures are premultiplied already.</span></span>
                <input class="s-switch" type="checkbox" role="switch" checked={app.config?.settings?.pma_textures === true} onchange={(e) => app.saveSettings({ pma_textures: e.currentTarget.checked })} /></label>
            </div>
          </section>
        </div>
        <ToolStatus {app} {tool} />
      {:else if selected === 'skeleton'}
        <SkeletonTool {app} {tool} />
      {:else if selected === 'spine42'}
        <Spine42Tool {app} {tool} />
      {:else if selected === 'backups'}
        <BackupsTool {app} {tool} />
      {/if}

    </section>
  </div>
</Modal>

<style>
  .or { display: flex; align-items: center; gap: 0.8rem; padding: 0 1.15rem; color: var(--text-dim); font-size: var(--fs-sm); font-weight: 600; }
  .or::before, .or::after { content: ''; flex: 1; height: 1px; background: var(--border-subtle); }
  .slash { margin: 0 0.35rem; color: var(--text-dim); font-weight: 400; }
  .crumb { font-weight: 700; }
  .layout { display: grid; grid-template-columns: 240px 1fr; gap: 1.1rem; height: 100%; min-height: 0; }
  .list { position: relative; display: flex; flex-direction: column; gap: 3px; overflow-y: auto; padding: 0.2rem 0.9rem 0.2rem 0; }
  /* a short bar, not a panel edge, separates the sections from the page on the right */
  .layout { position: relative; }
  .layout::before { content: ''; position: absolute; left: 240px; top: 8%; bottom: 8%; width: 1px; margin-left: calc(0.55rem - 1px); background: var(--border-subtle); pointer-events: none; }
  .group { margin: 1.1rem 0 0.3rem 0.9rem; font-size: var(--fs-sm); font-weight: 600; color: var(--text-dim); }
  .item { display: flex; align-items: center; gap: 0.7rem; text-align: left; padding: 0.8rem 0.9rem; border-radius: var(--radius-md); border: 0; background: transparent; color: var(--text-muted); cursor: pointer; }
  .item:hover { background: var(--tint-2); }
  .item strong { color: inherit; font-size: var(--fs-lg); font-weight: 600; }
  .item:hover { color: var(--text-main); }
  .item.active { background: var(--tint-3); color: var(--text-main); }
  .panel { display: flex; flex-direction: column; gap: 0.8rem; min-width: 0; min-height: 0; }
  .adb { display: flex; align-items: center; gap: 0.6rem; width: 100%; padding: 0.65rem 0.9rem; border: 1px solid var(--border-subtle); border-radius: var(--radius-md); background: var(--tint-1); color: var(--text-main); font-size: var(--fs-md); font-weight: 600; cursor: pointer; text-align: left; }
  .adb:hover { background: var(--tint-2); }
  .name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .retry { color: var(--text-muted); font-size: var(--fs-md); white-space: nowrap; }
  .adb:hover .retry { color: var(--text-main); }
  .s-value.path { word-break: break-all; font-weight: 500; max-width: 28rem; }
  b.warn { color: var(--warn-text); }
</style>
