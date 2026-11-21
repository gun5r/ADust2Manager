<script lang="ts">
  import type { FolderTab } from '../../lib/api'
  import Modal from '../../ui/Modal.svelte'

  let { tab, onConfirm, onClose }: { tab: FolderTab; onConfirm: () => void; onClose: () => void } = $props()
</script>

<Modal label="Remove Folder Tab?" width="440px" footerJustify="flex-end" footerPadding="0.85rem 1.25rem" titleColor="var(--danger)" bodyStyle="font-size: var(--fs-md); line-height: 1.5; color: var(--text-main)" onClose={onClose}>
  {#snippet icon()}
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--danger)" stroke-width="2.5"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
  {/snippet}
  {#snippet title()}Remove Folder Tab?{/snippet}
  <div class="text">
    <p>Are you sure you want to remove <strong>"{tab.name}"</strong> from managed folders?</p>
    <p class="note">This only removes the tab from ADust2Manager. It does <strong>not</strong> delete any files or folders from your disk.</p>
  </div>
  {#snippet footer()}
    <button class="btn" onclick={onClose}>Cancel</button>
    <button class="btn danger" onclick={onConfirm}>Remove Tab</button>
  {/snippet}
</Modal>

<style>
  .text strong { color: var(--primary); }
  .note { margin-top: 0.5rem; font-size: var(--fs-sm); color: var(--text-muted); }
  .note strong { color: inherit; }
  .btn { padding: 0.4rem 0.85rem; font-size: var(--fs-md); font-weight: 600; color: var(--text-main); background: var(--tint-2); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); }
  .btn:hover { background: var(--tint-3); }
  .btn.danger { color: var(--text-main); background: var(--danger); border: 0; }
</style>
