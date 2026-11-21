<script lang="ts">
  import type { Snippet } from 'svelte'
  import type { HTMLButtonAttributes } from 'svelte/elements'

  type Variant = 'secondary' | 'primary' | 'danger' | 'success' | 'ghost'
  type Size = 'header' | 'md' | 'sm' | 'xs'

  let { variant = 'secondary', size = 'md', pill = false, children, ...rest }: HTMLButtonAttributes & {
    variant?: Variant
    size?: Size
    /** Fully rounded (the header buttons). */
    pill?: boolean
    children?: Snippet
  } = $props()
</script>

<button class="btn {variant} {size}" class:pill {...rest}>{@render children?.()}</button>

<style>
  .btn { display: inline-flex; align-items: center; justify-content: center; gap: 0.45rem; font-weight: 600; white-space: nowrap;
    border: 1px solid transparent; transition: background 0.15s, border-color 0.15s, color 0.15s; user-select: none; }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .pill { border-radius: var(--radius-full); }

  .header { height: 32px; padding: 0 0.8rem; font-size: var(--fs-md); border-radius: var(--radius-sm); }
  .md { padding: 0.6rem 1.1rem; font-size: var(--fs-md); border-radius: var(--radius-md); }
  .sm { padding: 0.4rem 0.8rem; font-size: var(--fs-md); border-radius: var(--radius-sm); }
  .xs { padding: 0.28rem 0.6rem; font-size: var(--fs-sm); border-radius: 6px; }

  .secondary { background: var(--surface-pill); color: var(--text-main); border-color: var(--border-subtle); }
  .secondary:hover:not(:disabled) { background: var(--bg-card-hover); border-color: var(--tint-4); }
  .primary { background: var(--primary-solid); color: var(--on-primary); }
  .primary:hover:not(:disabled) { background: var(--primary-solid-hover); }
  .success { background: var(--accent); color: var(--surface-1); }
  .danger { background: transparent; color: var(--danger-text); border-color: color-mix(in srgb, var(--danger) 40%, transparent); }
  .ghost { background: transparent; color: var(--text-muted); }
  .ghost:hover:not(:disabled) { color: var(--text-main); background: var(--tint-2); }
</style>
