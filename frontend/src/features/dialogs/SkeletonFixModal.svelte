<script lang="ts">
  import Icon from '../../ui/Icon.svelte'
  import { onMount } from 'svelte'
  import { api, type SkeletonDonor } from '../../lib/api'
  import { lacksSkeleton } from '../../lib/skeleton'
  import type { IndexMod } from '../../lib/classify'
  import Modal from '../../ui/Modal.svelte'

  let { mod, onFix, onClose }: {
    mod: IndexMod
    /** Resolves when the skeleton is in place; `donor` is a mod folder, or undefined for the game's original. */
    onFix: (donor?: string) => Promise<void>
    onClose: () => void
  } = $props()

  const bare = $derived(lacksSkeleton(mod))
  let donors = $state<SkeletonDonor[] | null>(null)
  let busy = $state(false)
  let error = $state('')

  onMount(() => {
    api.skeletonDonors(mod.folder_path).then((r) => (donors = r.donors)).catch((e) => { donors = []; error = String(e) })
  })

  async function fix(donor?: string) {
    busy = true
    error = ''
    try {
      await onFix(donor)
      onClose()
    } catch (e) {
      error = String(e).replace(/^Error:\s*/, '')
      busy = false
    }
  }
</script>

<Modal label="Missing skeleton" width="560px" footerJustify="flex-end" footerPadding="0.85rem 1.25rem" bodyGap="1rem" onClose={onClose}>
  {#snippet icon()}<span><Icon name="bone" size={18} /></span>{/snippet}
  {#snippet title()}{bare ? 'This mod has no skeleton file' : 'Replace the skeleton'}{/snippet}
  <div class="body" data-ui="skeleton-fix">
    <p><strong>{mod.name}</strong> {#if bare}has its textures and atlas but no <code>.skel</code>, so it cannot be previewed or prepared. Add one:{:else}already has a skeleton. Use another if it is broken or does not fit this mod (the old one is kept as <code>.bak</code>):{/if}</p>
    <button class="game" disabled={busy} onclick={() => fix()}>
      <strong>Download the game's original skeleton</strong>
      <small>Same animations as the game; fine for mods that only repaint the textures.</small>
    </button>
    <h4>Or copy it from a mod of the same costume and animation</h4>
    {#if donors === null}
      <p class="muted">Looking for similar mods…</p>
    {:else if !donors.length}
      <p class="muted">No other mod in your library replaces the same asset with a skeleton.</p>
    {:else}
      <ul>
        {#each donors as d (d.folder_path)}
          <li><span class="name" title={d.folder_path}>{d.name}</span><button disabled={busy} onclick={() => fix(d.folder_path)}>Use this skeleton</button></li>
        {/each}
      </ul>
    {/if}
    {#if busy}<p class="muted">Working…</p>{/if}
    {#if error}<p class="err" role="alert">{error}</p>{/if}
  </div>
  {#snippet footer()}<button class="btn" onclick={onClose}>Cancel</button>{/snippet}
</Modal>

<style>
  .body { display: flex; flex-direction: column; gap: 0.7rem; font-size: var(--fs-md); color: var(--text-main); }
  p { margin: 0; }
  code { color: var(--primary); }
  .muted { color: var(--text-dim); }
  .err { color: var(--danger-text); }
  h4 { margin: 0.3rem 0 0; font-size: var(--fs-md); color: var(--text-muted); }
  .game { display: flex; flex-direction: column; gap: 0.2rem; padding: 0.75rem 1rem; border-radius: var(--radius-sm); border: 1px solid var(--border-focus); background: var(--selected-bg); color: var(--text-main); text-align: left; cursor: pointer; }
  .game small { color: var(--text-muted); }
  .game:hover:not(:disabled) { background: var(--selected-bg); }
  ul { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 0.35rem; max-height: 14rem; overflow-y: auto; }
  li { display: flex; align-items: center; gap: 0.6rem; padding: 0.4rem 0.6rem; border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); background: var(--surface-row); }
  .name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  li button { padding: 0.3rem 0.7rem; font-size: var(--fs-sm); font-weight: 600; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle); background: var(--tint-2); color: var(--text-main); cursor: pointer; white-space: nowrap; }
  li button:hover:not(:disabled) { border-color: var(--primary); }
  button:disabled { opacity: 0.5; cursor: progress; }
</style>
