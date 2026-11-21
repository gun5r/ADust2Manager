<script lang="ts">
  import Icon from './Icon.svelte'
  /** (Clicking the tab that is already on switches to the other one.)
   *  A segmented switch at the top of a side panel (viewer: Costumes | Characters, Variants | Packs): same look as Costumes | List on the mod list. */
  let { tabs, value, onChange, label }: {
    tabs: { id: string; label: string; icon?: string; count?: number }[]
    value: string
    onChange: (id: string) => void
    label: string
  } = $props()
</script>

<div class="seg" role="tablist" aria-label={label}>
  {#each tabs as t (t.id)}
    <button role="tab" aria-selected={value === t.id} class:on={value === t.id} onclick={() => onChange(value === t.id ? (tabs.find((x) => x.id !== t.id)?.id ?? t.id) : t.id)}>
      {#if t.icon}<Icon name={t.icon} size={14} />{/if}{t.label}{#if t.count !== undefined}<span class="n">{t.count}</span>{/if}
    </button>
  {/each}
</div>

<style>
  .seg { display: grid; grid-auto-flow: column; grid-auto-columns: 1fr; padding: 3px; gap: 3px; margin: 0.5rem 0.55rem 0.15rem; flex-shrink: 0; background: var(--panel-fill, var(--surface-1)); border: 1px solid var(--panel-line, var(--border-subtle)); border-radius: var(--radius-md); }
  button { display: inline-flex; align-items: center; justify-content: center; gap: 0.4rem; padding: 0.4rem 0; font-size: var(--fs-md); font-weight: 600; color: var(--text-muted); border-radius: var(--radius-sm); white-space: nowrap; }
  button:hover { color: var(--text-main); }
  button.on { color: var(--text-main); background: var(--tint-3); }
  .n { margin-left: 0.1rem; font-family: var(--font-mono); font-size: var(--fs-sm); opacity: 0.7; }
</style>
