<script lang="ts">
  import Icon from './ui/Icon.svelte'
  import { onMount } from 'svelte'
  import { AppState } from './state/app.svelte'
  import { estimateGroupHeight, LAYOUT, type CharacterGroup } from './lib/grouping'
  import type { IndexMod } from './lib/classify'
  import Header from './features/shell/Header.svelte'
  import StatusBar from './features/shell/StatusBar.svelte'
  import ActivityModal from './features/dialogs/ActivityModal.svelte'
  import TabBar from './features/library/TabBar.svelte'
  import Roster from './features/library/Roster.svelte'
  import CharacterGroupView from './features/library/CharacterGroup.svelte'
  import RightPanel from './features/library/RightPanel.svelte'
  import VirtualList from './ui/VirtualList.svelte'
  import FolderEditModal from './features/dialogs/FolderEditModal.svelte'
  import FolderDeleteModal from './features/dialogs/FolderDeleteModal.svelte'
  import SettingsModal from './features/dialogs/SettingsModal.svelte'
  import MascotModal from './features/dialogs/MascotModal.svelte'
  import SkeletonFixModal from './features/dialogs/SkeletonFixModal.svelte'
  import CostumeMode from './features/library/CostumeMode.svelte'
  import ToolsModal from './features/dialogs/ToolsModal.svelte'
  import DuplicateInspector from './features/dialogs/DuplicateInspector.svelte'
  import QueueModal from './features/queue/QueueModal.svelte'
  import ConflictResolver from './features/queue/ConflictResolver.svelte'
  import SharedBundleModal from './features/queue/SharedBundleModal.svelte'
  import SaveTemplateModal from './features/queue/SaveTemplateModal.svelte'
  import { fromQueue, fromSelection } from './lib/conflictView'
  import { modKey, selectionLabels } from './lib/selection'
  import { rosterEntries } from './lib/filters'
  import ViewerStudio from './features/viewer/ViewerStudio.svelte'

  const app = new AppState()
  const lib = app.library
  let list: VirtualList<CharacterGroup> | undefined = $state()
  let costumes: CostumeMode | undefined = $state()
  /** The character clicked in the roster: its card, its costumes and its mod section are framed (clicking it again clears it). */
  let litCharacter = $state<string | null>(null)
  const rosterBadges = $derived(rosterEntries(lib.displayGroups, lib.installedNames, lib.rosterQuery, app.queuedFolders))

  onMount(() => {
    let stop = () => {}
    void app.init().then((fn) => (stop = fn))
    void app.portraits.refresh()
    return () => stop()
  })


  function selectCharacter(name: string) {
    drawer = null
    litCharacter = litCharacter === name ? null : name // the clicked character's costumes and mods are framed in whichever view is open
    void costumes?.jump(name)
    if (app.isolatedList) {
      lib.isolate(name)
      list?.scrollToTop()
    } else list?.scrollToKey(name)
  }

  /** At narrow widths, side panels become slide-in drawers (classic's floating buttons). */
  let drawer = $state<'left' | 'right' | null>(null)
  let savingTemplate = $state<'selected' | 'installed' | null>(null)
  const selectedMods = $derived(lib.mods.filter((m) => lib.selected.has(modKey(m))))
  const labels = $derived(selectionLabels(selectedMods, lib.roster))
  const selectedNames = $derived(selectedMods.map((m) => m.name))
  const installedNames = $derived(lib.tabMods.filter((m) => lib.installedNames.has(m.name)).map((m) => m.name))
  function saveTemplate() {
    if (!selectedNames.length) return app.log('Select some mods before saving a template.', 'warning')
    savingTemplate = 'selected'
  }
  function saveInstalledTemplate() {
    if (!installedNames.length) return app.log('No mod of this folder is marked as installed.', 'warning')
    savingTemplate = 'installed'
  }

  /** "Add all shared installed mods": rebuild every installed companion together with the new mods. */
  function addSharedCompanions() {
    const prompt = app.flow.sharedPrompt
    if (!prompt) return
    const own = new Set([...prompt.mods.map((m) => m.folder_path), ...(prompt.cached ?? []).flatMap((c) => (c.mod_folders?.length ? c.mod_folders : [c.mod_folder]))])
    const extra = new Map(prompt.groups.flatMap((g) => g.installed_mods).filter((m) => !own.has(m.folder_path)).map((m) => [m.folder_path, m]))
    app.flow.enqueue(prompt.mods, [...extra.values()], prompt.replaces)
  }

  const preview = (mod: IndexMod | undefined) => mod && app.viewer.show(mod)
</script>

<svelte:window onkeydown={(e) => e.key === 'Escape' && drawer && !document.querySelector('[data-modal]') && (drawer = null)} />

<div class="shell">
  <Header adb={app.adb} cache={app.cache} queueCount={app.queue.waiting + app.queue.ready + app.queue.failed} queueText={app.queue.failed ? `${app.queue.ready} ready / ${app.queue.failed} fail` : undefined} queueFailed={app.queue.failed > 0}
          onQueue={() => app.flow.show()} onSettings={() => (app.settingsOpen = true)} mascotCount={app.mascots.list.length} onMascots={() => app.mascots.show()} onTools={() => (app.toolsOpen = true)} onRefreshAdb={() => app.refreshDevices()} />
  <main>
    <TabBar tabs={lib.tabs} activeId={lib.activeTab?.id ?? ''} syncView={lib.syncView} scanning={app.scanning}
            onSelect={(id) => app.switchTab(id)} onSync={() => lib.setSyncView(!lib.syncView)} onScan={() => app.scan()}
            onAdd={() => (app.tabEditor = { tab: null })} onEdit={(tab) => (app.tabEditor = { tab })} onRemove={(tab) => app.askRemoveTab(tab)} onOpen={(tab) => app.openTabFolder(tab)} />
    {#if app.error}
      <div class="alert" role="alert">
        <span><Icon name="triangle-alert" size={14} color="var(--warn-text)" /> {app.error}</span>
        <span class="alert-actions">
          <button onclick={() => { app.error = ''; void app.library.load().catch((e) => (app.error = String(e))) }}>Retry</button>
          <button onclick={() => (app.error = '')} aria-label="Dismiss"><Icon name="x" size={14} /></button>
        </span>
      </div>
    {/if}
    <div class="fabs">
      <button class="fab" title="Open Characters" onclick={() => (drawer = 'left')}><Icon name="users" size={16} /> Characters</button>
      <button class="fab" title="Open Filters &amp; Views" onclick={() => (drawer = 'right')}><Icon name="sparkles" size={16} /> Filters &amp; Views</button>
    </div>
    {#if drawer}<button class="scrim" aria-label="Close panel" onclick={() => (drawer = null)}></button>{/if}
    <div class="grid">
      <div class="slot left" class:open={drawer === 'left'}>
      <div class="drawer-head"><span><Icon name="users" size={16} /> Characters</span><button class="x" aria-label="Close" onclick={() => (drawer = null)}><Icon name="x" size={14} /></button></div>
      <Roster entries={rosterBadges} roster={lib.roster} columns={lib.rosterColumns} query={lib.rosterQuery} active={lib.isolated} lit={litCharacter}
              onQuery={(v) => (lib.rosterQuery = v)} onColumns={() => (lib.rosterColumns = lib.rosterColumns === 2 ? 3 : 2)}
              onSelect={selectCharacter} />
      </div>
      <section class="center">
        {#if !lib.listMode && lib.shownDisplayGroups.length}
          <CostumeMode bind:this={costumes} groups={lib.shownDisplayGroups} installed={lib.installedNames} queued={app.queuedFolders} wrap={app.costumeWrap} lit={litCharacter} portraits={app.portraits} size={lib.costumeSize} onSize={(px) => lib.setCostumeSize(px)} modSize={lib.modSize} onModSize={(px) => lib.setModSize(px)} clustered={lib.costumeClustered} onCluster={() => lib.setCostumeClustered(!lib.costumeClustered)}
            showOptions={app.costumeOptions} onHideOptions={() => app.saveSettings({ costume_options: false })} overlay={lib.costumeOverlay} onOverlay={() => lib.setCostumeOverlay(!lib.costumeOverlay)} resetKey={[lib.activeTab?.id, lib.status, lib.category, lib.isolated].join('|')}
            selected={lib.selected} onToggle={(m) => lib.toggle(m)} onMark={(m) => app.toggleInstalled(m)} onPreview={preview} onPrepare={(m) => app.prepare([m])} />
        {:else if lib.shownGroups.length}
          <VirtualList bind:this={list} items={lib.shownGroups} key={(g) => g.name} estimate={estimateGroupHeight} gap={LAYOUT.groupGap} endPadding={56}>
            {#snippet children(group)}
              <CharacterGroupView {group} lit={litCharacter === group.name} roster={lib.roster} selected={lib.selected} installed={lib.installedNames}
                onToggle={(m) => lib.toggle(m)} onSelectGroup={(mods, on) => lib.setMany(mods, on)} onMark={(m) => app.toggleInstalled(m)}
                onMerge={(m) => app.toggleMerge(m)} onPreview={preview} onPrepare={(m) => app.prepare([m])} onChoose={preview} />
            {/snippet}
          </VirtualList>
        {:else}
          <div class="empty" role="status">
            {#if lib.loading}
              <span class="spin big" aria-hidden="true"></span>
              <h3>Loading mods…</h3>
            {:else if lib.tabs.length === 0}
              <Icon name="folder-open" size={30} />
              <h3>No mod folders</h3>
              <p>The manager works on the folders you give it. Add the folder where your mods are.</p>
              <button class="reset primary" onclick={() => (app.tabEditor = { tab: null })}>Add a folder</button>
            {:else if lib.mods.length === 0}
              <Icon name="package" size={30} />
              <h3>No mods loaded yet</h3>
              <p>Add a folder tab and press the scan button, or adjust the filters.</p>
            {:else}
              <Icon name="search" size={30} />
              <h3>No mods match the current filters</h3>
              <p>{lib.mods.length} mods are hidden by the filters or the character isolation.</p>
              <button class="reset" onclick={() => lib.resetFilters()}>Reset Filters</button>
            {/if}
          </div>
        {/if}
      </section>
      <div class="slot right" class:open={drawer === 'right'}>
      <div class="drawer-head"><span><Icon name="sparkles" size={16} /> Filters &amp; Actions</span><button class="x" aria-label="Close" onclick={() => (drawer = null)}><Icon name="x" size={14} /></button></div>
      <RightPanel templates={app.templates} template={app.template} status={lib.status} category={lib.category} counts={lib.counts} detected={lib.counts.total} selected={lib.selected.size} {selectedMods} selectedLabel={(m) => labels.get(modKey(m)) ?? m.name} onRemove={(m) => lib.toggle(m)}
        onTemplate={(n) => (app.template = n)} onLoad={() => app.loadTemplate()} onSave={saveTemplate} onSaveInstalled={saveInstalledTemplate} installedCount={installedNames.length} listMode={lib.listMode} onListMode={() => lib.setListMode(!lib.listMode)} showLegend={app.showLegend} onHideLegend={() => app.saveSettings({ show_legend: false })} onDelete={() => app.deleteTemplate()}
        onStatus={(v) => (lib.status = v)} onCategory={(v) => (lib.category = v)} onReset={() => lib.resetFilters()}
        onSelectAll={() => lib.setMany(lib.visible, true)} onDeselectAll={() => (lib.selected = new Set())} onPrepare={() => app.prepareSelected()} />
      </div>
    </div>
  </main>
  <StatusBar {app} />
  {#if app.activityOpen}<ActivityModal {app} onClose={() => (app.activityOpen = false)} />{/if}

  {#if app.tabEditor && app.library.tabs}
    {#key app.tabEditor.tab?.id ?? 'new'}
      <FolderEditModal tab={app.tabEditor.tab} tabs={lib.tabs} onSave={(d) => app.saveTabEdit(d)} onClose={() => (app.tabEditor = null)} />
    {/key}
  {/if}
  {#if app.tabDeleting}<FolderDeleteModal tab={app.tabDeleting} onConfirm={() => app.removeTab(app.tabDeleting!)} onClose={() => (app.tabDeleting = null)} />{/if}
  {#if app.viewer.mod}
    <ViewerStudio {app} />
  {/if}
  {#if app.flow.checks > 0}<div class="toast" role="status"><span class="spin"></span> Checking for conflicts and shared game bundles…</div>{/if}
  {#if app.flow.open}<QueueModal {app} />{/if}
  {#if app.inspector}{#key app.inspector}<DuplicateInspector {app} onClose={() => (app.inspector = null)} />{/key}{/if}
  {#if app.mascots.open}<MascotModal mascots={app.mascots} />{/if}
  {#if app.skeletonFix}
    {@const fixing = app.skeletonFix}
    <SkeletonFixModal mod={fixing} onFix={(donor) => app.fixSkeleton(fixing, donor)} onClose={() => (app.skeletonFix = null)} />
  {/if}
  {#if app.toolsOpen}<ToolsModal {app} onClose={() => (app.toolsOpen = false)} />{/if}
  {#if app.settingsOpen}<SettingsModal {app} onClose={() => (app.settingsOpen = false)} />{/if}
  {#if app.flow.conflictPrompt}
    <ConflictResolver portraitOf={(f) => app.portraits.urlOfFolder(f)} groups={fromSelection(app.flow.conflictPrompt.conflicts)} onConfirm={(c) => app.flow.resolveSelectionConflicts(c)} onCancel={() => (app.flow.conflictPrompt = null)} />
  {/if}
  {#if app.flow.queueConflicts}
    <ConflictResolver portraitOf={(f) => app.portraits.urlOfFolder(f)} groups={fromQueue(app.flow.queueConflicts)} onConfirm={(c) => app.flow.resolveQueueConflicts(c)} onCancel={() => (app.flow.queueConflicts = null)} />
  {/if}
  {#if app.flow.sharedPrompt}
    <SharedBundleModal portraitOf={(f) => app.portraits.urlOfFolder(f)} groups={app.flow.sharedPrompt.groups} onAddAll={addSharedCompanions} onCancel={() => (app.flow.sharedPrompt = null)}
                       onAlone={() => app.flow.enqueue(app.flow.sharedPrompt!.mods, [], app.flow.sharedPrompt!.replaces)} />
  {/if}
  {#if savingTemplate}
    <SaveTemplateModal names={savingTemplate === 'installed' ? installedNames : selectedNames} initial={savingTemplate === 'installed' ? 'Installed mods' : ''}
                       onCancel={() => (savingTemplate = null)} onSave={(n) => { const names = savingTemplate === 'installed' ? installedNames : undefined; savingTemplate = null; void app.saveTemplate(n, names) }} />
  {/if}
</div>

<style>
  .shell { display: flex; flex-direction: column; height: 100%; }
  main { flex: 1; min-height: 0; display: flex; flex-direction: column; padding: 0.4rem 20px 4px; overflow: hidden; }
  .grid { flex: 1; min-height: 0; display: grid; grid-template-columns: 335px minmax(0, 1fr) 290px; gap: 16px; align-items: stretch; overflow: hidden; }
  /* classic's adaptive column widths */
  @media (max-width: 1749px) { .grid { grid-template-columns: 310px minmax(0, 1fr) 280px; gap: 0.85rem; } }
  @media (max-width: 1349px) { .grid { grid-template-columns: 240px minmax(0, 1fr) 260px; gap: 0.75rem; } }
  @media (max-width: 1049px) { .grid { grid-template-columns: 190px minmax(0, 1fr) 240px; gap: 0.6rem; } }
  .slot { display: contents; }
  .drawer-head, .fabs, .scrim { display: none; }
  @media (min-width: 851px) and (max-width: 1100px) {
    .grid { grid-template-columns: minmax(0, 1fr) 240px; gap: 0.6rem; }
    .fabs { display: flex; align-items: center; justify-content: flex-start; gap: 0.5rem; flex-shrink: 0; margin-bottom: 0.45rem; padding: 0.35rem 0.75rem; background: color-mix(in srgb, var(--surface-2) 95%, transparent); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); }
    .fab + .fab { display: none; }
    .fab { display: inline-flex; align-items: center; gap: 0.45rem; padding: 0.4rem 0.85rem; font-size: var(--fs-sm); font-weight: 600; color: var(--text-main); background: var(--tint-2); border: 1px solid var(--tint-4); border-radius: var(--radius-sm); }
    .fab:hover, .fab:focus-visible { background: var(--selected-bg); border-color: var(--primary); }
    .scrim { display: block; position: fixed; inset: 0; z-index: 99; background: var(--scrim-soft); }
    .slot.left { display: none; position: fixed; top: 0; bottom: 0; left: 0; z-index: 100; width: 310px; max-width: 85vw; flex-direction: column; padding: 0.85rem; background: var(--surface-2); box-shadow: var(--shadow-card); border-radius: 0 12px 12px 0; }
    .slot.left.open { display: flex; }
    .slot.left > :global(.panel) { flex: 1; min-height: 0; }
    .slot.right { display: block; grid-column: 2; grid-row: 1; min-width: 0; min-height: 0; }
    .slot.right > .drawer-head { display: none; }
    .drawer-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem; padding-bottom: 0.45rem; font-size: var(--fs-md); font-weight: 700; color: var(--text-main); border-bottom: 1px solid var(--border-subtle); }
    .x { padding: 4px 6px; line-height: 0; color: var(--text-muted); border-radius: 4px; }
    .x:hover { color: var(--text-main); background: var(--tint-3); }
  }
  @media (max-width: 850px) {
    .grid { grid-template-columns: minmax(0, 1fr); }
    .fabs { display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; flex-shrink: 0; margin-bottom: 0.45rem; padding: 0.35rem 0.75rem; background: color-mix(in srgb, var(--surface-2) 95%, transparent); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); }
    .fab { display: inline-flex; align-items: center; gap: 0.45rem; padding: 0.4rem 0.85rem; font-size: var(--fs-sm); font-weight: 600; color: var(--text-main); background: var(--tint-2); border: 1px solid var(--tint-4); border-radius: var(--radius-sm); }
    .fab + .fab { display: inline-flex; }
    .fab:hover, .fab:focus-visible { background: var(--selected-bg); border-color: var(--primary); }
    .scrim { display: block; position: fixed; inset: 0; z-index: 99; background: var(--scrim-soft); }
    .slot { display: none; position: fixed; top: 0; bottom: 0; z-index: 100; width: 310px; max-width: 85vw; flex-direction: column; padding: 0.85rem; background: var(--surface-2); }
    .slot.left { left: 0; box-shadow: 6px 0 28px rgba(0, 0, 0, 0.85); border-radius: 0 12px 12px 0; }
    .slot.right { right: 0; box-shadow: -6px 0 28px rgba(0, 0, 0, 0.85); border-radius: 12px 0 0 12px; }
    .slot.open { display: flex; }
    .slot > :global(.panel) { flex: 1; min-height: 0; }
    .drawer-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem; padding-bottom: 0.45rem; font-size: var(--fs-md); font-weight: 700; color: var(--text-main); border-bottom: 1px solid var(--border-subtle); }
    .x { padding: 4px 6px; line-height: 0; color: var(--text-muted); border-radius: 4px; }
    .x:hover { color: var(--text-main); background: var(--tint-3); }
  }
  .center { container: centerpanel / inline-size; min-height: 0; min-width: 0; padding-right: 0.55rem; overflow: hidden; }
  .empty { display: flex; flex-direction: column; align-items: center; gap: 0.5rem; text-align: center; padding: 6rem 1rem; color: var(--text-dim); }
  .toast { position: fixed; left: 50%; bottom: 76px; transform: translateX(-50%); z-index: 90; display: flex; align-items: center; gap: 0.6rem; padding: 0.55rem 1.1rem; font-size: var(--fs-md); font-weight: 600; color: var(--text-main);
    background: color-mix(in srgb, var(--surface-2) 96%, transparent); border: 1px solid var(--border-focus); border-radius: var(--radius-full); box-shadow: 0 8px 24px rgba(0, 0, 0, 0.55); }
  .spin { width: 12px; height: 12px; border: 2px solid var(--primary); border-right-color: transparent; border-radius: 50%; animation: turn 0.75s linear infinite; }
  @keyframes turn { to { transform: rotate(360deg); } }
  .alert { display: flex; align-items: center; justify-content: space-between; gap: 0.75rem; flex-shrink: 0; margin-bottom: 0.5rem; padding: 0.55rem 0.9rem; font-size: var(--fs-md); color: var(--danger-text); background: color-mix(in srgb, var(--danger) 12%, transparent); border: 1px solid color-mix(in srgb, var(--danger) 40%, transparent); border-radius: var(--radius-sm); }
  .alert-actions { display: flex; gap: 0.4rem; flex-shrink: 0; }
  .alert button { padding: 0.2rem 0.6rem; font-size: var(--fs-sm); font-weight: 600; color: var(--text-main); background: var(--tint-2); border: 1px solid var(--tint-4); border-radius: 6px; }
  .alert button:hover { background: var(--tint-4); }
  .empty .reset { margin-top: 0.9rem; padding: 0.45rem 0.9rem; font-size: var(--fs-md); font-weight: 600; color: var(--text-muted); background: color-mix(in srgb, var(--surface-3) 70%, transparent); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); }
  .empty .reset:hover { color: var(--text-main); border-color: var(--primary); }
  .empty h3 { color: var(--text-main); font-size: var(--fs-lg); font-weight: 600; }
  .empty p { max-width: 34rem; font-size: var(--fs-md); }
  .empty .reset.primary { color: var(--on-primary); background: var(--primary-solid); border-color: transparent; }
  .empty .reset.primary:hover { background: var(--primary-solid-hover); }
  .spin.big { width: 22px; height: 22px; border-width: 2px; }
</style>
