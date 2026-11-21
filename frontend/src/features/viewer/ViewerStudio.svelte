<script lang="ts">
  import { onMount, untrack } from 'svelte'
  import Icon from '../../ui/Icon.svelte'
  import StatusLight from '../../ui/StatusLight.svelte'
  import { LABELS, LABEL_TEXT } from '../../lib/activity'
  import type { AppState } from '../../state/app.svelte'
  import { modKey } from '../../lib/selection'
  import { isInstalled, type IndexMod } from '../../lib/classify'
  import { adjacentCharacter, browserGroups, characterFirst, cycleCategory, linearStep, listOrder, stepWithin } from '../../lib/viewerNav'
  import LayersPanel from './LayersPanel.svelte'
  import AnimationList from './AnimationList.svelte'
  import PlaybackControls from './PlaybackControls.svelte'
  import PlaybackBar from './PlaybackBar.svelte'
  import ModBrowser from './ModBrowser.svelte'
  import PanelTabs from '../../ui/PanelTabs.svelte'
  import PackBrowser from './PackBrowser.svelte'
  import { assetUrl } from '../../lib/spine'
  import { splitPath } from '../../lib/multi'
  import { prefetchMod } from '../../lib/prefetch'
  import TouchControls from './TouchControls.svelte'
  import SceneHud from './SceneHud.svelte'
  import SpotLegend from './SpotLegend.svelte'
  import ShortcutsDialog from './ShortcutsDialog.svelte'
  import { ModHealth } from './modHealth.svelte'

  let { app }: { app: AppState } = $props()
  // `app` is created once for the page, so reading its stores once here is intended.
  // svelte-ignore state_referenced_locally
  const viewer = app.viewer
  // svelte-ignore state_referenced_locally
  const lib = app.library

  const mod = $derived(viewer.mod!)
  const health = new ModHealth()
  $effect(() => { const folder = viewer.mod?.folder_path ?? null; untrack(() => void health.load(folder)) })
  // The stepping keys only walk single mods; inside a pack they walk its variants.
  // Multimods are listed too (marked MULTI); picking one asks to open the multimod selector instead of playing it.
  const groups = $derived(browserGroups(lib.tabMods, lib.roster, lib.installedNames, lib.selected, {
    category: lib.category, status: lib.status, query: viewer.browserQuery,
  }))
  const singles = $derived(groups.flatMap(listOrder).filter((m) => !m.is_multi)) // the list as shown (filters applied), character by character
  const packGroups = $derived(characterFirst(browserGroups(lib.tabMods.filter((m) => m.is_multi), lib.roster, lib.installedNames, lib.selected, {
    category: 'all', status: 'all', query: viewer.browserQuery,
  }), viewer.pack?.character))
  const installedCount = $derived(lib.tabMods.filter((m) => isInstalled(m, lib.installedNames)).length)
  const installed = $derived(isInstalled(mod, lib.installedNames))
  const selected = $derived(lib.selected.has(modKey(mod)))
  const category = $derived(app.categoryLabel(mod))
  const pack = $derived(viewer.pack)
  const preview = $derived(viewer.shownPreview ? splitPath(viewer.shownPreview) : null)
  let queuing = $state(false)
  let playbackVisible = $state(false)
  let playbackTimer: ReturnType<typeof setTimeout> | undefined
  function revealPlayback() {
    playbackVisible = true
    clearTimeout(playbackTimer)
    playbackTimer = setTimeout(() => (playbackVisible = false), 2000)
  }
  function focusPlayback(event: FocusEvent) {
    if (event.relatedTarget && (event.currentTarget as HTMLElement).contains(event.relatedTarget as Node)) return
    playbackVisible = true
    clearTimeout(playbackTimer)
  }
  function blurPlayback(event: FocusEvent) {
    if (event.relatedTarget && (event.currentTarget as HTMLElement).contains(event.relatedTarget as Node)) return
    revealPlayback()
  }

  /** Launch the mod on screen as a desktop mascot (in a pack: the variant being previewed). */
  function launchMascot() {
    app.mascots.launch({
      mod_name: pack ? `${pack.name} [${viewer.variant?.name ?? mod.name}]` : mod.name,
      folder_path: mod.folder_path, asset_stem: mod.asset_stem || mod.id || mod.name, category: mod.category || 'idle',
      character: mod.character || 'Others', files: mod.files, default_animation: viewer.current ?? 'idle',
      is_multi: Boolean(pack), variant_path: pack ? mod.folder_path : '',
    })
  }

  async function queueChosen() {
    queuing = true
    try {
      app.prepare(await viewer.prepareChosen(app.config?.quality || 'HD'))
      viewer.close()
    } catch (e) {
      app.log(`Could not prepare the chosen variants: ${e}`, 'error')
    } finally {
      queuing = false
    }
  }
  const textures = $derived(mod.files.filter((f) => f.toLowerCase().endsWith('.png')).length || mod.texture_count || 1)

  // Once a mod is on screen, warm the next and previous ones so stepping through the list feels instant.
  $effect(() => {
    if (viewer.status !== 'ready' || pack) return
    const path = mod.folder_path
    for (const neighbour of [linearStep(singles, path, 1), linearStep(singles, path, -1)]) if (neighbour) prefetchMod(neighbour)
  })

  function stage(node: HTMLElement) {
    return { destroy: viewer.attach(node) }
  }

  /** Open another pack from the Packs list; chosen variants of the current one would be lost, so ask first. */
  function switchPack(target: IndexMod) {
    if (target.folder_path === mod.folder_path || (pack && target.folder_path === pack.folder_path)) return
    if (viewer.chosen.length && !confirm(`${viewer.chosen.length} variant(s) are selected for install in this pack.\n\nOpening another pack discards that selection. Continue?`)) return
    viewer.show(target)
  }

  /** A click on the dimmed area closes the viewer, after asking when something selected would be lost or is still pending. */
  function onBackdrop(e: MouseEvent) {
    if (e.target !== e.currentTarget) return
    if (pack && viewer.chosen.length && !confirm(`${viewer.chosen.length} variant(s) are selected for install in this pack and have not been prepared.\n\nClose the preview and discard that selection?`)) return
    if (!pack && lib.selected.size && !confirm(`${lib.selected.size} mod(s) are selected for batch install.\n\nThey stay selected after closing. Close the preview?`)) return
    viewer.close()
  }

  /** The portrait belongs to the pack when a pack is open (its variants are only folders inside it). */
  async function setPortrait() {
    const target = viewer.pack ?? mod
    try {
      const blob = await viewer.captureFrame()
      if (!blob) return app.log('Nothing to capture yet: wait for the animation to load.', 'warning')
      await app.portraits.set(target, blob)
      app.log(`Portrait of "${target.name}" updated.`, 'success')
    } catch (e) {
      app.log(`Could not set the portrait: ${e}`, 'error')
    }
  }

  const go = (target: IndexMod | null) => target && viewer.pick(target)

  function onKey(e: KeyboardEvent) {
    const target = e.target as HTMLElement | null
    if (target && ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)) return
    if (document.querySelector('[data-modal]')) return // a dialog (queue, conflicts…) sits on top
    const key = e.key
    if (key === 'Escape') {
      e.preventDefault()
      return viewer.showShortcuts ? (viewer.showShortcuts = false) : viewer.close()
    }
    if (key === '?' || (e.shiftKey && key === '/')) {
      e.preventDefault()
      return (viewer.showShortcuts = !viewer.showShortcuts)
    }
    if (viewer.showShortcuts || e.ctrlKey || e.metaKey || e.altKey) return
    const path = mod.folder_path
    const act = (fn: () => void) => { e.preventDefault(); fn() }
    if (pack) {
      const v = viewer.variant
      if (key === 'ArrowUp' || key === 'ArrowLeft' || key === 'w' || key === 'W') act(() => viewer.stepVariant(-1))
      else if (key === 'ArrowDown' || key === 'ArrowRight' || key === 's' || key === 'S') act(() => viewer.stepVariant(1))
      else if ((key === ' ' || key === 'f' || key === 'F') && v) act(() => (e.shiftKey ? viewer.toggleOptionChosen() : viewer.toggleChosen(v)))
      else if (key === 'a' || key === 'A') act(() => viewer.stepAnimation(-1))
      else if (key === 'd' || key === 'D' || key === 'z' || key === 'Z') act(() => viewer.stepAnimation(1))
      else if (key === 'p' || key === 'P') act(() => viewer.togglePause())
      else if (key === 'l' || key === 'L') act(() => viewer.toggleLoop())
      else if (key === 'r' || key === 'R') act(() => viewer.resetView())
      return
    }
    if (key === 'ArrowUp' && e.shiftKey) act(() => go(adjacentCharacter(groups, viewer.expanded ?? mod.character, -1)))
    else if (key === 'ArrowDown' && e.shiftKey) act(() => go(adjacentCharacter(groups, viewer.expanded ?? mod.character, 1)))
    else if (key === 'ArrowUp' || key === 'w' || key === 'W') act(() => go(stepWithin(groups, viewer.expanded ?? mod.character, path, -1)))
    else if (key === 'ArrowDown' || key === 's' || key === 'S') act(() => go(stepWithin(groups, viewer.expanded ?? mod.character, path, 1)))
    else if (key === 'q' || key === 'Q') act(() => go(adjacentCharacter(groups, viewer.expanded ?? mod.character, -1)))
    else if (key === 'e' || key === 'E') act(() => go(adjacentCharacter(groups, viewer.expanded ?? mod.character, 1)))
    else if (key === 'PageUp') act(() => go(adjacentCharacter(groups, viewer.expanded ?? mod.character, -1)))
    else if (key === 'PageDown') act(() => go(adjacentCharacter(groups, viewer.expanded ?? mod.character, 1)))
    else if (key === 'a' || key === 'A') act(() => viewer.stepAnimation(-1))
    else if (key === 'd' || key === 'D' || key === 'z' || key === 'Z') act(() => viewer.stepAnimation(1))
    else if (key === 'x' || key === 'X') act(() => (lib.category = cycleCategory(lib.category, -1)))
    else if (key === 'c' || key === 'C') act(() => (lib.category = cycleCategory(lib.category, 1)))
    else if (key === ' ' || key === 'f' || key === 'F') act(() => lib.toggle(mod))
    else if (key === 'ArrowLeft') act(() => go(linearStep(singles, path, -1)))
    else if (key === 'ArrowRight') act(() => go(linearStep(singles, path, 1)))
    else if (key === 'p' || key === 'P') act(() => viewer.togglePause())
    else if (key === 'l' || key === 'L') act(() => viewer.toggleLoop())
    else if (key === 'r' || key === 'R') act(() => viewer.resetView())
  }

  onMount(() => () => viewer.close())
</script>

<svelte:window onkeydown={onKey} />

<!-- svelte-ignore a11y_click_events_have_key_events -->
<div class="backdrop" data-ui="viewer-backdrop" role="dialog" tabindex="-1" aria-modal="true" aria-label="Viewer Studio" onclick={onBackdrop}>
  <div class="card" class:seamless={app.seamlessViewer && viewer.background === 'default'} data-ui="viewer">
    <div class="header" data-ui="viewer-header">
      <div class="main">
        <div class="nav">
          <button class="sync chrome-toggle" class:on={lib.syncView} aria-pressed={lib.syncView} title="Show All: list the mods of every folder together" onclick={() => lib.setSyncView(!lib.syncView)}>
            <Icon name="layers" size={13} />
            Show All
          </button>
          <div class="title-row">
            <h2 title={pack?.name ?? mod.name}>{pack?.name ?? mod.name}</h2>
            {#if pack}<span class="badge cat">Multi</span>{:else}<span class="badge cat">{category}</span>{/if}
            <span class="badge sub">{mod.asset_key || mod.asset_stem}</span>
            <span class="badge sub">{textures} PNG{textures > 1 ? 's' : ''}</span>
            {#if mod.has_backup}<span class="badge ok">Merged (.old)</span>{/if}
          </div>
        </div>
      </div>
      <div class="actions">
        {#if viewer.skeletonFiles.length > 1}
          <div class="skeleton"><label for="skeleton">Skeleton:</label>
            <select id="skeleton" value={viewer.skeleton ?? viewer.skeletonFiles[0]} onchange={(e) => viewer.setSkeleton(e.currentTarget.value)}>
              {#each viewer.skeletonFiles as file}<option value={file}>{file}</option>{/each}
            </select>
          </div>
        {/if}
        <button class="icon help" title="Keyboard Shortcuts (?)" aria-label="Keyboard shortcuts" onclick={() => (viewer.showShortcuts = true)}>
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
        </button>
        <button class="icon close" title="Close Preview" aria-label="Close preview" onclick={() => viewer.close()}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
        </button>
      </div>
    </div>

    <div class="body">
      <aside class="left" data-ui="viewer-left">
        <LayersPanel {viewer} />
        <AnimationList {viewer} />
        <PlaybackControls {viewer} onPortrait={setPortrait} />
      </aside>
      <main class="viewport bg-{viewer.background}" style:background-color={viewer.background === 'custom' ? viewer.customBackground : ''} data-ui="viewer-canvas" onpointermove={revealPlayback} onpointerleave={() => { playbackVisible = false; clearTimeout(playbackTimer) }} onfocusin={focusPlayback} onfocusout={blurPlayback}>
        <div class="stage" use:stage></div>
        <PlaybackBar {viewer} dating={!!(viewer.spots.length && viewer.interact)} visible={playbackVisible} />
        {#if viewer.portraitGuide}<div class="guide" aria-hidden="true"></div>{/if}
        {#if viewer.spots.length}<TouchControls {viewer} />{#if viewer.interact}<SceneHud {viewer} /><SpotLegend {viewer} />{/if}{/if}
        {#if pack && preview}
          <button class="corner" class:big={viewer.previewExpanded} title={viewer.previewExpanded ? 'Click to shrink' : 'Click to enlarge'} onclick={() => (viewer.previewExpanded = !viewer.previewExpanded)}>
            <img src={assetUrl(preview[0], preview[1])} alt="Option preview" />
          </button>
        {/if}
        {#if health.damaged.length && !health.hidden}
          <div class="damaged" role="alert" data-ui="damaged-warning">
            <strong><Icon name="triangle-alert" size={13} /> Damaged mod file{health.damaged.length > 1 ? 's' : ''}: parts of the model are missing</strong>
            <p>{health.damaged.map((d) => d.file).join(', ')} {health.damaged.length > 1 ? 'are' : 'is'} cut off, most likely an incomplete download. Download the mod again.</p>
            <button class="act" onclick={() => (health.hidden = true)}>Hide this warning</button>
          </div>
        {/if}
        {#if viewer.spots.length && viewer.datingData !== 'ok' && !viewer.datingWarningHidden && !pack}
          <div class="dating-warning" role="alert" data-ui="dating-warning">
            <strong><Icon name="triangle-alert" size={13} /> {viewer.datingData === 'missing' ? 'Dating data missing' : 'This scene is not in your dating data'}</strong>
            <p>{viewer.datingData === 'missing'
              ? 'Without it the simulator has no touch rules (reactions, guide, phase changes) and no sounds: the scene only plays as an animation.'
              : 'It is probably newer than the data, or a different scene: the simulator has no rules or sounds for it.'}
              Get it in <b>Settings / Tools &gt; Dating &gt; Simulator Data</b> (from your phone or the game's APK){viewer.datingData === 'missing' ? ', or run Initial Setup with the dating simulator option' : ''}.</p>
            <div>
              <button class="act primary" onclick={() => { app.toolsTab = 'dating'; app.toolsOpen = true }}>Open Simulator Data</button>
              <button class="act" onclick={() => (viewer.datingWarningHidden = true)}>Hide this warning</button>
            </div>
          </div>
        {/if}
        {#if viewer.multiPrompt && !pack}
          {@const prompt = viewer.multiPrompt}
          <div class="multi-ask" data-ui="multi-ask">
            <h3>This is a multimod</h3>
            <p><strong>{prompt.name}</strong> holds several variants to choose from, so it cannot be previewed or installed like a single mod.</p>
            <button class="act primary" onclick={() => viewer.showPack(prompt)}>Press here to open the multimod selector</button>
            <small>Your batch selection stays as it is.</small>
          </div>
        {/if}
        {#if viewer.status !== 'ready'}
          <div class="overlay" class:error={viewer.status === 'error'}>{viewer.status === 'loading' ? 'Loading…' : viewer.message}</div>
        {/if}
      </main>
      {#if pack}
        <div class="rightcol">
          <PanelTabs label="Right panel" value={viewer.panel} onChange={(id) => (viewer.panel = id as 'variants' | 'packs')}
                     tabs={[{ id: 'variants', label: 'Variants', icon: 'layout-grid' }, { id: 'packs', label: 'Packs', icon: 'package' }]} />
          {#if viewer.panel === 'packs'}
            <ModBrowser {viewer} packs groups={packGroups} roster={lib.roster} installed={lib.installedNames} selected={lib.selected} selectedCount={0} installedCount={0} uninstalledCount={0}
                        category={lib.category} onCategory={(c) => (lib.category = c)} status={lib.status} onStatus={(v) => (lib.status = v)}
                        onPick={switchPack} onToggleSelect={() => {}} />
          {:else}
            <PackBrowser {viewer} />
          {/if}
        </div>
      {:else}
      <ModBrowser {viewer} {groups} roster={lib.roster} installed={lib.installedNames} selected={lib.selected} selectedCount={lib.selected.size} {installedCount} uninstalledCount={lib.tabMods.length - installedCount}
                  category={lib.category} onCategory={(c) => (lib.category = c)} status={lib.status} onStatus={(v) => (lib.status = v)}
                  onPick={(m) => m.folder_path !== mod.folder_path && viewer.pick(m)} onToggleSelect={(m) => lib.toggle(m)} />
      {/if}
    </div>

    <div class="footer" data-ui="viewer-footer">
      <span class="meter" data-ui="viewer-status">
        <!-- the widest label decides the width: invisible copies of all of them share the cell, so the line sits right after the longest -->
        <span class="sizer" aria-hidden="true">{#each LABELS as light (light)}<StatusLight status={{ state: light, label: LABEL_TEXT[light], text: '', running: 0 }} compact />{/each}</span>
        <span class="live"><StatusLight status={app.activity.status} compact /></span>
      </span>
      {#if pack}
        <div class="group">
          {#if viewer.spots.length}
          <button class="act" class:on={viewer.interact} aria-pressed={viewer.interact} title="Dating scene: click or drag the spots to play the character's reactions, as in the game" onclick={() => viewer.toggleInteract()}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 11V5a2 2 0 1 1 4 0v6"></path><path d="M13 11V9a2 2 0 1 1 4 0v5a6 6 0 0 1-6 6h-1a5 5 0 0 1-4-2l-3-4a2 2 0 0 1 3-2l2 2"></path></svg>
            Simulate
          </button>
          {/if}
          <button class="act" title="Show this mod as a mascot on your desktop" onclick={launchMascot}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect><line x1="8" y1="21" x2="16" y2="21"></line><line x1="12" y1="17" x2="12" y2="21"></line></svg>
          DMascot
        </button>
        <button class="act" title="Add or replace this mod's skeleton: pick another mod's, or the game's original" onclick={() => (app.skeletonFix = mod)}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 10c.7-.7 1.69 0 2.5 0a2.5 2.5 0 1 0 0-5 .5.5 0 0 1-.5-.5 2.5 2.5 0 1 0-5 0c0 .81.7 1.8 0 2.5l-7 7c-.7.7-1.69 0-2.5 0a2.5 2.5 0 0 0 0 5c.28 0 .5.22.5.5a2.5 2.5 0 1 0 5 0c0-.81-.7-1.8 0-2.5Z"></path></svg>
          Skeleton Fix
        </button>
          <span class="hint">{viewer.chosen.length} selected — picking a variant replaces any other chosen for the same asset</span>
        </div>
        <div class="group">
          <button class="act" class:on={viewer.variant && viewer.chosen.some((c) => c.full_path === viewer.variant?.full_path)} disabled={!viewer.variant} title="Choose the variant on screen for install (double-click it in the list, or Space / F)"
                  onclick={() => viewer.variant && viewer.toggleChosen(viewer.variant)}>
            {viewer.variant && viewer.chosen.some((c) => c.full_path === viewer.variant?.full_path) ? 'Selected' : 'Select'}
          </button>
          <button class="act" disabled={!viewer.chosen.length} onclick={() => (viewer.chosen = [])}>Clear</button>
          <button class="act" class:primary={viewer.chosen.length > 0} class:dim={!viewer.chosen.length} disabled={!viewer.chosen.length || queuing} onclick={queueChosen}>
            {queuing ? 'Preparing…' : `Prepare Selected Variants${viewer.chosen.length ? ` (${viewer.chosen.length})` : ''}`}
          </button>
        </div>
      {:else}
      <div class="group">
        <button class="act" title={mod.has_backup ? 'Restore the original textures from the .old backup' : 'Merge Spine textures down into fewer sheets to prevent in-game crashes'} onclick={() => app.toggleMerge(mod)}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="8" height="8" rx="1"></rect><rect x="14" y="2" width="8" height="8" rx="1"></rect><rect x="8" y="14" width="8" height="8" rx="1"></rect></svg>
          {mod.has_backup ? 'Unmerge Spine' : 'Merge Spine'}
        </button>
        <button class="act" title="Add or replace this mod's skeleton: pick another mod's, or the game's original" onclick={() => (app.skeletonFix = mod)}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 10c.7-.7 1.69 0 2.5 0a2.5 2.5 0 1 0 0-5 .5.5 0 0 1-.5-.5 2.5 2.5 0 1 0-5 0c0 .81.7 1.8 0 2.5l-7 7c-.7.7-1.69 0-2.5 0a2.5 2.5 0 0 0 0 5c.28 0 .5.22.5.5a2.5 2.5 0 1 0 5 0c0-.81-.7-1.8 0-2.5Z"></path></svg>
          Skeleton Fix
        </button>
        <button class="act" title="Show this mod as a mascot on your desktop" onclick={launchMascot}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect><line x1="8" y1="21" x2="16" y2="21"></line><line x1="12" y1="17" x2="12" y2="21"></line></svg>
          DMascot
        </button>
        {#if viewer.spots.length}
          <button class="act" class:on={viewer.interact} aria-pressed={viewer.interact} title="Dating scene: click or drag the spots to play the character's reactions, as in the game" onclick={() => viewer.toggleInteract()}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 11V5a2 2 0 1 1 4 0v6"></path><path d="M13 11V9a2 2 0 1 1 4 0v5a6 6 0 0 1-6 6h-1a5 5 0 0 1-4-2l-3-4a2 2 0 0 1 3-2l2 2"></path></svg>
            Simulate
          </button>
        {/if}
      </div>
      <div class="group">
        <button class="act" class:on={installed} title={installed ? 'Installed (click to mark as not installed)' : 'Mark as installed'} onclick={() => app.toggleInstalled(mod)}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">{#if installed}<polyline points="20 6 9 17 4 12"></polyline>{:else}<circle cx="12" cy="12" r="9"></circle>{/if}</svg>
          {installed ? 'Installed' : 'Mark Installed'}
        </button>
        <button class="act" class:sel={selected} aria-pressed={selected} title="Add or remove this mod from the selection (F / Space)" onclick={() => lib.toggle(mod)}>
          <span class="batch-dot" class:picked={selected}></span>
          {selected ? 'Selected' : 'Select'}
        </button>
        <button class="act primary" title={selected && lib.selected.size > 1 ? 'Prepare every selected mod for installation' : 'Prepare the previewed mod for installation'} onclick={() => (selected && lib.selected.size > 1 ? app.prepareSelected() : app.prepare([mod]))}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"></path><path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"></path><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"></path><path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"></path></svg>
          {selected && lib.selected.size > 1 ? `Prepare ${lib.selected.size} Selected` : 'Prepare for Install'}
        </button>
      </div>
      {/if}
    </div>
  </div>
</div>

{#if viewer.showShortcuts}<ShortcutsDialog onClose={() => (viewer.showShortcuts = false)} />{/if}

<style>
  .backdrop { position: fixed; inset: 0; z-index: 60; display: flex; align-items: center; justify-content: center; background: var(--scrim); }
  .card { width: min(95vw, 1560px); height: calc(100vh - 16px); display: flex; flex-direction: column; background: var(--viewer-bg); border: 1px solid var(--border-subtle); border-radius: var(--radius-lg);
    box-shadow: 0 25px 60px -12px rgba(0, 0, 0, 0.85); overflow: hidden; }
  /* Seamless: the panels take the canvas' colour (a fixed mid-tone of its gradient) and lose the lines between their sections. The
     two variables are what the panels (here and in their components) read: --panel-line for their dividers, --panel-fill for the
     switches, filter block and headings. Their selected states keep a tint. */
  .card.seamless { --flat: color-mix(in srgb, var(--viewport-1) 45%, var(--viewport-2)); --panel-line: transparent; --panel-fill: var(--flat); background: var(--flat); }
  .card.seamless .viewport.bg-default { background: var(--flat); }
  .header { display: flex; align-items: center; justify-content: space-between; padding: 0.55rem 1.1rem; background: transparent; border-bottom: 1px solid var(--panel-line, var(--border-subtle)); flex: 0 0 auto; }
  .main { flex: 1; min-width: 0; display: flex; align-items: center; gap: 1rem; }
  .nav { display: flex; align-items: center; gap: 0.65rem; min-width: 0; }
  .sync { display: flex; align-items: center; gap: 0.38rem; padding: 0.3rem 0.6rem; font-size: var(--fs-sm); font-weight: 600; color: var(--text-muted); background: transparent; border: 0; border-radius: 8px; white-space: nowrap; }
  .sync:hover { background: var(--tint-2); color: var(--text-main); }
  .title-row { display: flex; align-items: center; gap: 0.5rem; min-width: 0; }
  h2 { font-size: var(--fs-xl); font-weight: 700; color: var(--text-main); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .badge { flex-shrink: 0; padding: 0.15rem 0.5rem; font-size: var(--fs-sm); font-weight: 600; border-radius: 4px; border: 1px solid; white-space: nowrap; }
  .cat { color: var(--text-main); background: var(--tint-2); border-color: transparent; }
  .sub { color: var(--text-dim); background: transparent; border-color: transparent; font-family: var(--font-mono); }
  .ok { color: var(--ok-text); background: color-mix(in srgb, var(--ok) 15%, transparent); border-color: color-mix(in srgb, var(--ok) 30%, transparent); }
  .actions { display: flex; align-items: center; gap: 0.5rem; flex-shrink: 0; }
  .skeleton { display: flex; align-items: center; gap: 0.4rem; font-size: var(--fs-sm); color: var(--text-muted); }
  .skeleton select { padding: 2px 6px; font-size: var(--fs-sm); color: var(--text-main); background: color-mix(in srgb, var(--surface-2) 90%, transparent); border: 1px solid var(--border-subtle); border-radius: 6px; }
  .icon { display: flex; align-items: center; justify-content: center; border-radius: 50%; color: var(--text-muted); transition: all 0.15s ease; }
  .help { width: 30px; height: 30px; border: 1px solid transparent; }
  .help:hover { color: var(--text-main); background: var(--tint-2); }
  .close { width: 32px; height: 32px; background: transparent; border: 0; }
  .close:hover { color: var(--danger-text); border-color: color-mix(in srgb, var(--danger) 50%, transparent); background: color-mix(in srgb, var(--danger) 15%, transparent); }
  .body { flex: 1; min-height: 0; display: flex; }
  .left { width: 250px; flex: 0 0 auto; display: flex; flex-direction: column; min-height: 0; overflow: hidden; background: transparent; border-right: 1px solid var(--panel-line, var(--border-subtle)); }
  .dating-warning { position: absolute; top: 12px; left: 50%; transform: translateX(-50%); z-index: 5; width: min(34rem, calc(100% - 24px)); display: flex; flex-direction: column; gap: 0.5rem; padding: 0.8rem 1rem; color: var(--warn-text); background: rgba(120, 53, 15, 0.96); border: 2px solid var(--warn); border-radius: 10px; box-shadow: 0 0 22px color-mix(in srgb, var(--warn) 55%, transparent); }
  .damaged { position: absolute; left: 12px; bottom: 12px; z-index: 5; max-width: min(28rem, calc(100% - 24px)); display: flex; flex-direction: column; gap: 0.35rem; padding: 0.65rem 0.85rem; color: var(--warn-text); background: color-mix(in srgb, var(--warn) 16%, var(--surface-1)); border-radius: var(--radius-md); }
  .damaged p { margin: 0; font-size: var(--fs-sm); line-height: 1.35; color: var(--text-main); }
  .damaged .act { align-self: flex-start; padding: 0.2rem 0.5rem; }
  .dating-warning strong { font-size: var(--fs-xl); color: var(--warn-text); }
  .dating-warning p { margin: 0; font-size: var(--fs-md); line-height: 1.35; }
  .dating-warning div { display: flex; gap: 0.5rem; flex-wrap: wrap; }
  .multi-ask { position: absolute; inset: 0; z-index: 3; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 0.9rem; padding: 2rem; text-align: center; background: var(--surface-2); }
  .multi-ask h3 { font-size: var(--fs-2xl); color: var(--text-main); }
  .multi-ask p { max-width: 34rem; color: var(--text-muted); }
  .multi-ask small { color: var(--text-dim); }
  .multi-ask .primary { padding: 0.8rem 1.6rem; font-size: var(--fs-lg); }
  .guide { position: absolute; top: 0; bottom: 0; left: 50%; aspect-ratio: 4 / 5; max-width: 100%; transform: translateX(-50%); border: 2px dashed color-mix(in srgb, var(--cat-dating) 80%, transparent); background: color-mix(in srgb, var(--cat-dating) 5%, transparent); pointer-events: none; z-index: 2; }
  .viewport { --dating-playback-bottom: 10.75rem; /* clears the six-row legend and bottom-right dating tools */ position: relative; flex: 1; min-width: 0; display: flex; align-items: center; justify-content: center; overflow: hidden;
    background-image: radial-gradient(circle, var(--viewport-1) 0%, var(--viewport-2) 100%); }
  .viewport.bg-black { background: #000; } .viewport.bg-white { background: #fff; } .viewport.bg-skyblue { background: #38bdf8; }
  .viewport.bg-custom { background-image: none; }
  .corner { position: absolute; right: 12px; bottom: 12px; z-index: 2; display: flex; padding: 0; width: 180px; height: 180px; border-radius: 8px; border: 1px solid var(--border-subtle); background: color-mix(in srgb, var(--surface-2) 85%, transparent); cursor: zoom-in; overflow: hidden; }
  .corner.big { inset: 12px; width: auto; height: auto; cursor: zoom-out; background: color-mix(in srgb, var(--surface-2) 92%, transparent); }
  .corner img { width: 100%; height: 100%; object-fit: contain; }
  .rightcol { width: 265px; flex: 0 0 auto; display: flex; flex-direction: column; min-height: 0; border-left: 1px solid var(--panel-line, var(--border-subtle)); background: transparent; }
  .rightcol > :global(aside) { flex: 1 1 0; width: auto; min-height: 0; border-left: 0; }
  @media (max-width: 1100px) { .rightcol { width: 220px; } }
  @media (max-width: 760px) { .rightcol { display: none; } }
  .hint { font-size: var(--fs-sm); color: var(--text-muted); }
  .stage { position: absolute; inset: 0; cursor: grab; }
  .stage:active { cursor: grabbing; }
  .stage :global(.spine-player) { width: 100%; height: 100%; }
  .stage :global(canvas) { width: 100%; height: 100%; display: block; }
  .overlay { position: absolute; inset: 0; display: grid; place-items: center; padding: 24px; text-align: center; color: var(--text-muted); pointer-events: none; }
  .overlay.error { color: var(--warning); }
  /* the status sits at the left end of the button row, set off by a thin line; wide enough for its longest text */
  .meter { flex: 0 0 auto; display: grid; align-items: center; align-self: stretch; padding-right: 0.7rem; margin-right: 0.2rem; border-right: 1px solid var(--border-subtle); }
  .sizer, .live { grid-area: 1 / 1; }
  .sizer { display: grid; visibility: hidden; height: 0; overflow: hidden; }
  .live { align-self: center; }
  .footer > .group:last-child { margin-left: auto; }
  .footer { position: relative; display: flex; align-items: center; justify-content: flex-start; gap: 0.5rem; padding: 0.5rem 1.1rem; background: transparent; border-top: 1px solid var(--panel-line, var(--border-subtle)); flex: 0 0 auto; }
  .group { display: flex; align-items: center; gap: 0.5rem; }
  /* quiet by default; the one primary action of the viewer is filled */
  .act { display: flex; align-items: center; justify-content: center; gap: 0.45rem; padding: 0.4rem 0.75rem; font-size: var(--fs-md); font-weight: 600; color: var(--text-muted); background: transparent;
    border: 1px solid transparent; border-radius: var(--radius-sm); white-space: nowrap; transition: background 0.12s, color 0.12s; }
  .act:hover:not(:disabled) { background: var(--tint-2); color: var(--text-main); }
  .act.on { color: var(--ok-text); }
  .act.sel { color: var(--primary); background: var(--selected-bg); }
  .act.primary { color: var(--on-primary); background: var(--primary-solid); }
  .act.primary:hover:not(:disabled) { background: var(--primary-solid-hover); color: var(--on-primary); }
  .act.dim, .act:disabled { opacity: 0.45; cursor: not-allowed; }
  .batch-dot { width: 8px; height: 8px; border: 1.5px solid currentColor; border-radius: 50%; }
  .batch-dot.picked { background: currentColor; }
  .group:last-child .act:nth-child(2) { gap: 0.4rem; }
  @media (max-width: 1100px) { .left { width: 210px; } .footer { flex-wrap: wrap; } .footer > .group:last-child { margin-left: 0; } }
  @media (max-width: 760px) { .left { width: 170px; } .nav .sync { display: none; } h2 { font-size: var(--fs-md); } }
</style>
