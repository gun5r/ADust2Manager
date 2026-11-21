<script lang="ts">
  import type { Snippet } from 'svelte'

  let { label, onClose, onBackdrop = onClose, width = '650px', height, footerJustify = 'space-between', footerPadding, bodyGap, bodyStyle, radius, plainTitle = false, titleColor, title, icon, badges, actions, footer, children }: {
    label: string
    onClose: () => void
    /** A click on the dark area around the dialog (defaults to closing it; a form can ask first so a miss click does not lose its input). */
    onBackdrop?: () => void
    width?: string
    height?: string
    /** classic's .modal-footer is space-between; some dialogs override it to flex-end. */
    footerJustify?: 'space-between' | 'flex-end'
    bodyGap?: string
    footerPadding?: string
    /** Extra inline style for the body (classic puts font and spacing on it). */
    bodyStyle?: string
    radius?: string
    /** Unstyled h2 (24px), as in classic dialogs whose header uses .modal-header-left. */
    plainTitle?: boolean
    titleColor?: string
    title: Snippet
    /** Icon left of the title (a sibling of the h2, as in classic). */
    icon?: Snippet
    /** Extra header content next to the title (status pills). */
    badges?: Snippet
    /** Header buttons left of the close button. */
    actions?: Snippet
    footer?: Snippet
    children: Snippet
  } = $props()

  /** Move focus into the dialog, keep Tab inside it, and give focus back to whatever opened it. */
  function trap(card: HTMLElement) {
    const opener = document.activeElement as HTMLElement | null
    const focusables = () => [...card.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])')]
    ;(card.querySelector<HTMLElement>('[autofocus]') ?? card).focus({ preventScroll: true })
    const onTab = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return
      const items = focusables()
      if (!items.length) return e.preventDefault()
      const first = items[0], last = items[items.length - 1]
      if (e.shiftKey && (document.activeElement === first || document.activeElement === card)) (e.preventDefault(), last.focus())
      else if (!e.shiftKey && document.activeElement === last) (e.preventDefault(), first.focus())
    }
    card.addEventListener('keydown', onTab)
    return { destroy() { card.removeEventListener('keydown', onTab); opener?.isConnected && opener.focus({ preventScroll: true }) } }
  }

  function onKey(e: KeyboardEvent) {
    if (e.key !== 'Escape' || e.defaultPrevented || (e.target as HTMLElement | null)?.matches?.('textarea, select')) return
    e.preventDefault()
    onClose()
  }
</script>

<svelte:window onkeydown={onKey} />

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="backdrop" tabindex="-1" data-modal={label} role="dialog" aria-modal="true" aria-label={label} onclick={(e) => e.target === e.currentTarget && onBackdrop()}>
  <div class="card" tabindex="-1" use:trap style:width style:height style:border-radius={radius} style:max-height={height ? '92vh' : undefined}>
    <div class="header">
      <div class="title-row">
        {@render icon?.()}
        <h2 class:plain={plainTitle} style:color={titleColor}>{@render title()}</h2>
        {@render badges?.()}
      </div>
      <div class="header-actions">
        {@render actions?.()}
        <button class="close" title="Close" aria-label="Close" onclick={onClose}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
        </button>
      </div>
    </div>
    <div class="body scroll-cue" style:gap={bodyGap} style={bodyStyle}>{@render children()}</div>
    {#if footer}<div class="footer" style:justify-content={footerJustify} style:padding={footerPadding}>{@render footer()}</div>{/if}
  </div>
</div>

<style>
  .backdrop { position: fixed; inset: 0; z-index: 100; display: flex; align-items: center; justify-content: center; background: var(--scrim); }
  .card:focus { outline: none; }
  .card { display: flex; flex-direction: column; max-width: 97vw; max-height: 85vh; overflow: hidden; background: var(--surface-dialog); border: 1px solid var(--border-subtle); border-radius: var(--radius-lg);
    box-shadow: var(--shadow-lg); }
  .header { display: flex; align-items: center; justify-content: space-between; padding: 0.65rem 1.25rem; background: transparent; border-bottom: 1px solid var(--border-subtle); flex-shrink: 0; }
  .title-row { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
  h2 { display: flex; align-items: center; gap: 0.5rem; font-size: var(--fs-xl); font-weight: 700; color: var(--text-main); }
  h2.plain { display: block; font-size: var(--fs-2xl); font-weight: 700; color: var(--text-main); }
  .header-actions { display: flex; align-items: center; gap: 0.5rem; }
  .close { width: 32px; height: 32px; display: inline-flex; align-items: center; justify-content: center; color: var(--text-muted); background: transparent; border: 0; border-radius: 50%; transition: background 0.12s, color 0.12s; }
  .close:hover { color: var(--text-main); background: var(--tint-3); }
  .body { flex: 1; min-height: 0; overflow-y: auto; display: flex; flex-direction: column; padding: 1.35rem 1.65rem; } /* classic: .modal-card:not(.modal-card-studio) .modal-body */
  .footer { display: flex; justify-content: space-between; align-items: center; gap: 0.5rem; padding: 0.55rem 1.25rem; background: transparent; border-top: 1px solid var(--border-subtle); flex-shrink: 0; }
</style>
