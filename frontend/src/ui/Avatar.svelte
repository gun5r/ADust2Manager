<script lang="ts">
  /** `urls` are tried in order: a portrait that does not exist is skipped, the initial shows when none loads. A card (character list) shows a missing-portrait icon, or the name for Others and NPCs. */
  let { name, urls = [], variant = 'header' }: { name: string; urls?: string[]; variant?: 'header' | 'card' } = $props()
  let at = $state(0)
  $effect(() => {
    void urls.join('|')
    at = 0
  })
  const url = $derived(urls[at] ?? '')
  const initial = $derived(name && name !== 'Others' ? name.charAt(0).toUpperCase() : '?')
  import Icon from './Icon.svelte'
  import { neverHasPortrait } from '../lib/grouping'
</script>

<div class="avatar {variant}" title={name}>
  {#if url}
    <img src={url} alt={name} loading="lazy" onerror={() => at++} />
  {:else if variant === 'card' && neverHasPortrait(name)}<span class="word">{name}</span>{:else if variant === 'card'}<Icon name="image" size={30} />{:else}{initial}{/if}
</div>

<style>
  .avatar { display: flex; align-items: center; justify-content: center; overflow: hidden; flex-shrink: 0; color: var(--primary); font-weight: 800; }
  .header { width: 34px; height: 34px; border-radius: 50%; background: color-mix(in srgb, var(--surface-3) 80%, transparent); border: 2px solid rgba(var(--primary-rgb), 0.4);
    font-size: var(--fs-md); box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3); }
  .card { width: 100%; height: 100%; border-radius: 7px; font-size: var(--fs-2xl); container-type: inline-size; }
  /* a card nobody can have a portrait for (Others, NPCs) says who it is, in the same words as in the mod list */
  /* three sizes by the width of the card, so the word never wraps */
  .word { padding: 0 4px; font-size: var(--fs-sm); font-weight: 800; line-height: 1.1; text-align: center; white-space: nowrap; color: var(--primary); }
  @container (min-width: 76px) { .word { font-size: var(--fs-xl); } }
  @container (min-width: 104px) { .word { font-size: var(--fs-2xl); } }
  img { width: 100%; height: 100%; object-fit: cover; object-position: top center; }
</style>
