<script lang="ts">
  import Icon from '../../ui/Icon.svelte'
  import { COLORS } from '../../lib/tabs'
  import type { FolderTab } from '../../lib/api'
  import { samePath } from '../../lib/tabs'
  import Modal from '../../ui/Modal.svelte'
  import '../../styles/tools.css'
  import { api } from '../../lib/api'

  let { tab, tabs, onSave, onClose }: {
    /** The tab being configured, or null to add one. */
    tab: FolderTab | null
    tabs: FolderTab[]
    onSave: (draft: Omit<FolderTab, 'id'>) => void
    onClose: () => void
  } = $props()

  // The form is a draft of the tab as it was when the dialog opened (the parent remounts it per edit).
  // svelte-ignore state_referenced_locally
  let name = $state(tab ? tab.name : `${tabs.length + 1}Batch`)
  // svelte-ignore state_referenced_locally
  let path = $state(tab?.path ?? '')
  // svelte-ignore state_referenced_locally
  let color = $state(tab ? (tab.color ?? '') : COLORS[0]) // '' = no colour: the tab keeps the background's own look
  let browsing = $state(false)
  let pickProblem = $state('')
  /** The computer's own folder window (opened by the manager); when it cannot be opened the user pastes the path instead. */
  async function browse() {
    browsing = true
    pickProblem = ''
    try {
      const chosen = (await api.pickFolder(path)).path
      if (chosen) path = chosen
    } catch (e) {
      pickProblem = `${e instanceof Error ? e.message : String(e)}. Copy the folder's path from your file manager and paste it in the field above.`
    } finally {
      browsing = false
    }
  }
  const names = ['Cyan', 'Emerald', 'Purple', 'Amber', 'Rose', 'Blue', 'Teal', 'Red']
  const clash = $derived(path.trim() && tabs.some((t) => t.id !== tab?.id && samePath(t.path, path)))

  /** Clicking outside a new tab's form asks first: a miss click would throw away the name and path typed so far. */
  const onBackdrop = () => (tab || confirm('Discard this new folder tab?')) && onClose()

  function save() {
    if (clash) return
    onSave({ name: name.trim() || `${tabs.length + 1}Batch`, path: path.trim(), color, ...(tab?.is_multi_folder !== undefined ? { is_multi_folder: tab.is_multi_folder } : {}) })
  }
</script>

<Modal label={tab ? 'Configure Folder Tab' : 'Add New Folder Tab'} width="480px" footerJustify="flex-end" footerPadding="0.85rem 1.25rem" bodyGap="1rem" onClose={onClose} {onBackdrop}>
  {#snippet icon()}<span class="icon"><Icon name="folder" size={18} /></span>{/snippet}
  {#snippet title()}{tab ? 'Configure Folder Tab' : 'Add New Folder Tab'}{/snippet}
  <div class="form" data-ui="folder-edit">
    <div class="s-card">
      <div class="s-row stack">
        <div class="s-text"><strong>Tab name</strong></div>
        <!-- svelte-ignore a11y_autofocus -->
        <input id="folder-name" type="text" autofocus placeholder="e.g. Batch #1, Favorites, Summer Mods..." bind:value={name} onkeydown={(e) => e.key === 'Enter' && save()} aria-label="Tab name" />
      </div>
      <div class="s-row stack">
        <div class="s-text"><strong>Folder location</strong></div>
        <div class="pathrow">
          <input id="folder-path" class="mono" type="text" spellcheck="false" placeholder="/media/user/Disk/Mods/#1Batch" bind:value={path} onkeydown={(e) => e.key === 'Enter' && save()} aria-label="Folder location" />
          <button type="button" class="btn browse" title="Choose the folder in a window of your system" disabled={browsing} onclick={browse}><Icon name="folder-open" size={14} /> {browsing ? 'Waiting…' : 'Browse…'}</button>
        </div>
        {#if clash}<span class="warn">Another tab already uses this folder.</span>{/if}
        {#if pickProblem}<span class="warn">{pickProblem}</span>{/if}
      </div>
      <div class="s-row stack">
        <div class="s-text"><strong>Tab accent colour</strong><span>Marks the tab with a coloured underline.</span></div>
        <div class="palette">
          <button type="button" class="swatch none" class:active={!color} title="No color" aria-label="No color" onclick={() => (color = '')}></button>
          {#each COLORS as c, i}
            <button type="button" class="swatch" class:active={color.toLowerCase() === c} style:background={c} style:--glow={c} title={names[i]} aria-label={names[i]} onclick={() => (color = c)}></button>
          {/each}
          <div class="custom" title="Custom Color"><input type="color" bind:value={color} aria-label="Custom colour" /></div>
        </div>
      </div>
    </div>
  </div>
  {#snippet footer()}
    <button class="btn" onclick={onClose}>Cancel</button>
    <button class="btn primary" disabled={!!clash} onclick={save}>Save Folder</button>
  {/snippet}
</Modal>

<style>
  .icon { font-size: var(--fs-2xl); }
  .form { display: contents; }
  input[type='text'] { height: 33px; width: 100%; padding: 0.5rem 0.75rem; font-size: var(--fs-md); line-height: normal; color: var(--text-main); background: color-mix(in srgb, var(--surface-2) 85%, transparent); border: 1px solid var(--border-subtle); border-radius: 6px; outline: none; }
  input[type='text']:focus { border-color: var(--primary); }
  input.mono { height: 35px; font-family: var(--font-mono); font-size: var(--fs-md); }
  .pathrow { display: flex; gap: 0.5rem; }
  .btn.browse { display: inline-flex; align-items: center; gap: 0.35rem; flex-shrink: 0; white-space: nowrap; }
  .warn { margin-top: 0.3rem; font-size: var(--fs-sm); color: var(--warn-text); }
  .palette { display: flex; flex-wrap: wrap; align-items: center; gap: 0.55rem; }
  .swatch { color: var(--text-main); width: 26px; height: 26px; padding: 0; border: 2px solid transparent; border-radius: 50%; transition: all 0.15s ease; }
  .swatch.none { background: color-mix(in srgb, var(--surface-2) 88%, transparent); border: 2px dashed rgba(255, 255, 255, 0.35); }
  .swatch.none.active { border-style: solid; }
  .swatch:hover { transform: scale(1.15); }
  .swatch.active { border-color: #fff; box-shadow: inset 0 0 0 2px rgba(0, 0, 0, 0.5); transform: scale(1.12); }
  .custom input { font-size: var(--fs-md); color: #000; width: 26px; height: 26px; padding: 0; background: none; border: 2px solid var(--tint-4); border-radius: 50%; cursor: pointer; }
  .btn { padding: 0.4rem 0.85rem; font-size: var(--fs-md); font-weight: 600; color: var(--text-main); background: var(--tint-2); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); }
  .btn:hover:not(:disabled) { background: var(--tint-3); }
  .btn.primary { color: var(--on-primary); border: none; background: var(--primary-solid); box-shadow: none; }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
