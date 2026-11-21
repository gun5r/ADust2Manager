<script lang="ts">
  import Icon from '../../ui/Icon.svelte'
  import Modal from '../../ui/Modal.svelte'

  let { names, initial = '', onSave, onCancel }: { names: string[]; initial?: string; onSave: (name: string) => void; onCancel: () => void } = $props()
  // svelte-ignore state_referenced_locally
  let name = $state(initial)
  const submit = () => name.trim() && onSave(name.trim())
</script>

<Modal label="Save Fast-Install Template" width="480px" onClose={onCancel}>
  {#snippet title()}<Icon name="zap" size={16} color="var(--warn-text)" /> Save Fast-Install Template{/snippet}
  <div class="body">
    <p class="sub">Save these mods as a named template for this folder. Whenever the game updates, you can reinstall your entire setup with a single click.</p>
    <div class="group">
      <label for="template-name"><strong>Template Name:</strong></label>
      <!-- svelte-ignore a11y_autofocus -->
      <input id="template-name" type="text" autofocus placeholder="e.g. My Active Mods, Core Set, Summer Batch" bind:value={name}
             onkeydown={(e) => e.key === 'Enter' && submit()} />
    </div>
    <div class="preview">{#each names as n}<span class="chip">{n}</span>{/each}</div>
  </div>
  {#snippet footer()}
    <button class="btn" onclick={onCancel}>Cancel</button>
    <button class="btn accent" disabled={!name.trim()} onclick={submit}>Save Template</button>
  {/snippet}
</Modal>

<style>
  .sub { font-size: var(--fs-md); line-height: 1.5; color: var(--text-muted); }
  .group { margin-top: 1rem; display: flex; flex-direction: column; gap: 0.35rem; }
  label { font-size: var(--fs-md); color: var(--text-main); }
  input { width: 100%; padding: 0.5rem 0.75rem; font-size: var(--fs-md); color: var(--text-main); background: color-mix(in srgb, var(--surface-2) 85%, transparent); border: 1px solid var(--border-subtle); border-radius: 6px; outline: none; }
  input:focus { border-color: var(--primary); }
  .preview { display: flex; flex-wrap: wrap; gap: 0.35rem; max-height: 120px; margin-top: 0.75rem; padding: 0.5rem; overflow-y: auto; background: color-mix(in srgb, var(--surface-2) 50%, transparent); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); }
  .chip { padding: 1px 6px; font-size: var(--fs-xs); color: var(--primary); background: var(--selected-bg); border: 1px solid rgba(var(--primary-rgb), 0.25); border-radius: 3px; }
  .btn { padding: 0.6rem 1.1rem; font-size: var(--fs-md); font-weight: 600; color: var(--text-main); background: var(--tint-2); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); }
  .btn:hover:not(:disabled) { background: var(--tint-3); }
  .btn.accent { color: var(--on-primary); border: none; background: var(--primary-solid); }
  .btn:disabled { opacity: 0.4; cursor: not-allowed; }
</style>
