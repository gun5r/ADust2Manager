<script lang="ts">
  import type { IndexMod } from '../../lib/classify'
  import { cancelPrefetchIntent, prefetchOnIntent } from '../../lib/prefetch'

  /** The Mark / Merge / Preview / Prepare (or Choose) buttons of one mod: the same in the list rows and in costume mode. */
  let { mod, installed, onMark, onMerge, onPreview, onPrepare, onChoose }: {
    mod: IndexMod
    installed: boolean
    onMark: () => void
    onMerge: () => void
    onPreview: () => void
    onPrepare: () => void
    onChoose: () => void
  } = $props()
</script>

{#if mod.is_multi}
  <button class="action choose" title="Open Multi-Mod Studio to Choose Variants" onclick={onChoose}>
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
    <span class="text">Choose</span>
  </button>
{:else}
  <button class="action mark" class:on={installed} title={installed ? 'Installed (Click to mark not installed)' : 'Not installed (Click to mark as installed)'} onclick={onMark}>
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width={installed ? 3 : 2}>
      {#if installed}<polyline points="20 6 9 17 4 12"></polyline>{:else}<circle cx="12" cy="12" r="9"></circle>{/if}
    </svg>
    <span class="text">{installed ? 'Installed' : 'Mark'}</span>
  </button>
  <button class="action merge" class:merged={mod.has_backup}
          title={mod.has_backup ? 'Unmerge Spine textures (Click to restore original .old/ backup)' : 'Merge Spine textures down into fewer sheets to prevent in-game crashes'} onclick={onMerge}>
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      {#if mod.has_backup}
        <path d="M3 12a9 9 0 0 1 15-6.7L21 8"></path><path d="M21 3v5h-5"></path><path d="M21 12a9 9 0 0 1-15 6.7L3 16"></path><path d="M3 21v-5h5"></path>
      {:else}
        <rect x="2" y="2" width="8" height="8" rx="1"></rect><rect x="14" y="2" width="8" height="8" rx="1"></rect><rect x="8" y="14" width="8" height="8" rx="1"></rect>
      {/if}
    </svg>
    <span class="text">{mod.has_backup ? 'Unmerge' : 'Merge'}</span>
  </button>
  <button class="action preview" title="Live Spine 2D Preview" onclick={onPreview} onpointerenter={() => prefetchOnIntent(mod)} onpointerleave={cancelPrefetchIntent}>
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
    <span class="text">Preview</span>
  </button>
  <button class="action prepare" title="Repack &amp; Prepare for Install" onclick={onPrepare}>
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"></path>
      <path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"></path>
      <path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"></path><path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"></path>
    </svg>
    <span class="text">Prepare</span>
  </button>
{/if}

<style>
  .action { display: inline-flex; align-items: center; gap: 0.35rem; padding: 0.38rem 0.75rem; border-radius: var(--radius-sm); font-size: var(--fs-sm); font-weight: 600;
    border: 1px solid transparent; transition: all 0.15s ease; white-space: nowrap; color: var(--text-main); }
  .mark { background: var(--tint-1); border-color: var(--border-subtle); color: var(--text-muted); border-radius: var(--radius-sm); padding: 0.38rem 0.75rem; }
  .mark:hover { background: var(--tint-2); border-color: var(--tint-4); color: var(--text-main); }
  .mark.on { background: color-mix(in srgb, var(--ok) 12%, transparent); border-color: color-mix(in srgb, var(--ok) 40%, transparent); color: var(--ok-text); }
  .mark.on:hover { background: color-mix(in srgb, var(--ok) 25%, transparent); border-color: var(--ok); }
  .merge.merged { background: color-mix(in srgb, var(--cat-multi) 15%, transparent); border-color: color-mix(in srgb, var(--cat-multi) 40%, transparent); color: var(--cat-multi); }
  .merge.merged:hover { background: color-mix(in srgb, var(--danger) 20%, transparent); border-color: color-mix(in srgb, var(--danger) 50%, transparent); color: var(--danger-text); }
  .merge:not(.merged):hover { background: var(--tint-2); }
  .preview { background: var(--tint-2); border-color: var(--border-subtle); }
  .preview:hover { background: var(--tint-3); border-color: rgba(255, 255, 255, 0.3); }
  .prepare { background: var(--primary-solid); color: var(--on-primary); border: 0; }
  .prepare:hover { background: var(--primary-solid-hover); }
  .choose { background: var(--tint-2); border-color: var(--tint-4); color: var(--text-main); }
  .choose:hover { background: var(--tint-3); border-color: rgba(255, 255, 255, 0.35); }
</style>
