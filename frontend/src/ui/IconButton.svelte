<script lang="ts">
  import type { Snippet } from 'svelte'
  import type { HTMLButtonAttributes } from 'svelte/elements'

  let { children, ...rest }: HTMLButtonAttributes & { children?: Snippet } = $props()
</script>

<button class="icon" {...rest}>{@render children?.()}</button>

<style>
  .icon { display: flex; align-items: center; justify-content: center; padding: 0.35rem; border-radius: 50%;
    color: var(--text-muted); transition: all 0.15s ease; }
  .icon:hover { color: var(--text-main); background: var(--tint-2); }
</style>
