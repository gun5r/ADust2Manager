<script lang="ts">
  import type { StatusFilter } from '../../lib/filters'

  /** Installed / Not installed / Selected as underlined tabs (shared by the main list and the preview); clicking the active one clears the filter. */
  let { status, onStatus, installed, uninstalled, selected }: { status: StatusFilter; onStatus: (value: StatusFilter) => void; installed?: number; uninstalled?: number; selected?: number } = $props()
  const flip = (value: StatusFilter) => onStatus(status === value ? 'all' : value)
  const tabs = $derived<{ key: StatusFilter; label: string; n?: number }[]>([
    { key: 'installed', label: 'Installed', n: installed }, { key: 'uninstalled', label: 'Not installed', n: uninstalled }, { key: 'selected', label: 'Selected', n: selected },
  ])
</script>

<div class="tabs" role="group" aria-label="Install status">
  {#each tabs as t (t.key)}
    <button class:active={status === t.key} aria-pressed={status === t.key} onclick={() => flip(t.key)}><span>{t.label}</span>{#if t.n !== undefined}<em>{t.n}</em>{/if}</button>
  {/each}
</div>

<style>
  .tabs { display: grid; grid-template-columns: repeat(3, 1fr); border-bottom: 1px solid var(--border-subtle); }
  .tabs button { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 0.1rem; min-width: 0; white-space: nowrap; padding: 0.35rem 0.1rem 0.5rem; font-size: var(--fs-sm); font-weight: 600; color: var(--text-muted); border-bottom: 2px solid transparent; margin-bottom: -1px; }
  .tabs button em { font-style: normal; font-weight: 500; color: var(--text-dim); }
  .tabs button:hover { color: var(--text-main); }
  .tabs button.active { color: var(--text-main); border-bottom-color: var(--primary); }
  @media (max-width: 1349px) { .tabs button { font-size: var(--fs-xs); } }
</style>
