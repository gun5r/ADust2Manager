<script lang="ts">
  import { BADGE_STYLE, type BadgeKind } from '../lib/categoryIcons'
  import Icon from './Icon.svelte'
  import { badgeUi } from '../lib/badgeStyle.svelte'
  /** One badge of a portrait: a small icon and a number (see BADGE_STYLE). `small` for the narrow 3-column roster. */
  let { kind, n, small = false }: { kind: BadgeKind; n: number | string; small?: boolean } = $props()
  const style = $derived(BADGE_STYLE[kind])
</script>

{#if badgeUi.icons}
  <i class="badge" class:small style:border-color={style.color} title="{n} {style.label}"><Icon name={style.icon} size={small ? 9 : 11} color={style.color} />{n}</i>
{:else}
  <i class="badge" class:small style:border-color={style.color} title="{n} {style.label}">{n}</i>
{/if}

<style>
  .badge { display: inline-flex; align-items: center; gap: 2px; min-width: 17px; padding: 1px 5px; font-size: var(--fs-xs); font-style: normal; font-weight: 700; line-height: 1.3; color: var(--text-main); background: color-mix(in srgb, var(--surface-2) 88%, transparent); border: 1px solid; border-radius: 6px; box-shadow: 0 2px 6px rgba(0, 0, 0, 0.5); white-space: nowrap; }
  .badge.small { padding: 0 3px; font-size: var(--fs-xs); border-radius: 5px; }
</style>
