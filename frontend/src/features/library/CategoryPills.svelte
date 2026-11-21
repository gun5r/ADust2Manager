<script lang="ts">
  import { CATEGORIES, type CategoryFilter } from '../../lib/classify'
  import { CATEGORY_ICON } from '../../lib/categoryIcons'
  import Icon from '../../ui/Icon.svelte'

  /** The category filter pills (clicking the active one clears it), shared by the main window's right panel and the viewer's side panel. */
  let { category, onCategory }: { category: CategoryFilter; onCategory: (key: CategoryFilter) => void } = $props()

</script>

<div class="pills">
  {#each CATEGORIES as pill (pill.key)}
    <button class="pill" class:active={category === pill.key} class:multi={pill.key === 'multi'} onclick={() => onCategory(category === pill.key ? 'all' : pill.key)}>
      {#if CATEGORY_ICON[pill.key]}<Icon name={CATEGORY_ICON[pill.key].icon} size={13} color={CATEGORY_ICON[pill.key].color} />{/if}{pill.label}
    </button>
  {/each}
</div>

<style>
  /* one united block, three equal cells per row; only a short bar separates cells */
  .pills { display: grid; grid-template-columns: repeat(3, 1fr); overflow: hidden; background: var(--panel-fill, var(--surface-1)); border-radius: var(--radius-md); }
  .pill { min-width: 0; position: relative; justify-content: center; display: inline-flex; align-items: center; gap: 0.3rem; white-space: nowrap; padding: 0.4rem 0.4rem; font-size: var(--fs-sm); font-weight: 600; color: var(--text-muted);
    background: transparent; border: 0; border-radius: 0; transition: background 0.12s, color 0.12s; }
  .pill:not(:nth-child(3n + 1))::before { content: ''; position: absolute; left: 0; top: 25%; bottom: 25%; width: 1px; background: var(--border-subtle); }
  .pill:hover { color: var(--text-main); background: var(--tint-3); }
  .pill.active { color: var(--text-main); background: var(--selected-bg); }
  .pill.multi.active { background: color-mix(in srgb, var(--cat-multi) 25%, transparent); }
</style>
