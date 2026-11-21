<script lang="ts">
  import Icon from '../../ui/Icon.svelte'
  let { onClose }: { onClose: () => void } = $props()
  let tab = $state<'normal' | 'multi'>('normal')

  type Row = [label: string, keys: string[][]]
  const normal: [string, Row[]][] = [
    ['👤 Character Navigation', [['Previous / Next Character (starts at the top of its list)', [['Q', 'E'], ['PgUp', 'PgDn'], ['Shift+↑', 'Shift+↓']]], ['Previous / Next Category Filter', [['X', 'C']]]]],
    ['🎬 Mod & Animation Navigation', [['Previous / Next Mod of the Character (wraps around)', [['W', 'S'], ['↑', '↓']]], ['Step Animation Track', [['A', 'D'], ['Z']]], ['Previous / Next Mod in the whole list', [['←', '→']]]]],
    ['📦 Batch Selection', [['Toggle Select Mod for Batch', [['F'], ['Space']]]]],
    ['⚙️ Playback & View Controls', [['Play / Pause Animation', [['P']]], ['Toggle Motion Loop', [['L']]], ['Reset Camera View (Pan & Zoom)', [['R']]], ['Toggle Shortcuts Guide', [['?']]], ['Close Preview / Modal', [['Esc']]]]],
  ]
  const multi: [string, Row[]][] = [
    ['🎬 Variant (Mod) Navigation', [['Previous / Next Variant (Mod)', [['W', 'S'], ['↑', '↓'], ['←', '→']]], ['Step Animation Track (if multi-clip)', [['A', 'D']]]]],
    ['📦 Variant Selection', [['Toggle Select Active Variant', [['F'], ['Space']]], ['Toggle Select ALL Variants in Option', [['Shift+F'], ['Shift+Space']]]]],
    ['⚙️ Playback & View Controls', [['Play / Pause Animation', [['P']]], ['Toggle Motion Loop', [['L']]], ['Reset Camera View (Auto-Framing)', [['R']]], ['Toggle Shortcuts Guide', [['?']]], ['Close Preview / Modal', [['Esc']]]]],
  ]
  /** The section titles start with a pictograph; it is shown as an icon instead. */
  const ICON: Record<string, [string, string]> = { '👤': ['user', 'var(--primary)'], '🎬': ['clapperboard', 'var(--warn-text)'], '📦': ['package', 'var(--cat-illust)'], '⚙️': ['settings', 'var(--text-muted)'], '📂': ['folder-open', 'var(--warn-text)'] }
  const head = (title: string) => { const [mark, ...rest] = title.split(' '); return { icon: ICON[mark], text: rest.join(' ') } }
  const sections = $derived(tab === 'normal' ? normal : multi)
</script>

<div class="backdrop" role="dialog" aria-modal="true" aria-label="Keyboard shortcuts" tabindex="-1" onclick={(e) => e.target === e.currentTarget && onClose()} onkeydown={(e) => e.key === 'Escape' && onClose()}>
  <div class="card">
    <div class="head">
      <h2>Player Keyboard Shortcuts</h2>
      <button class="x" onclick={onClose} aria-label="Close"><Icon name="x" size={14} /></button>
    </div>
    <div class="tabs">
      <button class:active={tab === 'normal'} onclick={() => (tab = 'normal')}>Normal Mode</button>
      <button class:active={tab === 'multi'} onclick={() => (tab = 'multi')}>Multi Mode</button>
    </div>
    <div class="body">
      {#each sections as [title, rows]}
        {@const h = head(title)}
        <h3>{#if h.icon}<Icon name={h.icon[0]} size={15} color={h.icon[1]} />{/if} {h.text}</h3>
        {#each rows as [label, groups]}
          <div class="row"><span>{label}</span>
            <span class="keys">{#each groups as keys, i}{#if i}<span class="or">or</span>{/if}{#each keys as key}<kbd>{key}</kbd>{/each}{/each}</span>
          </div>
        {/each}
      {/each}
      <p class="safety"><Icon name="shield" size={14} color="var(--ok-text)" /> <strong>Install Safety:</strong> Installing single mods or batch mods cannot be triggered by keyboard shortcuts. It strictly requires an intentional mouse click.</p>
    </div>
    <div class="foot"><button class="got" onclick={onClose}>Got it</button></div>
  </div>
</div>

<style>
  .backdrop { position: fixed; inset: 0; z-index: 70; display: grid; place-items: center; background: var(--scrim-soft); backdrop-filter: blur(4px); }
  .card { width: min(560px, 92vw); max-height: 88vh; display: flex; flex-direction: column; background: var(--surface-1); border: 1px solid var(--border-subtle); border-radius: var(--radius-lg); box-shadow: var(--shadow-lg); overflow: hidden; }
  .head { display: flex; align-items: center; justify-content: space-between; padding: 0.8rem 1.25rem; background: color-mix(in srgb, var(--surface-2) 95%, transparent); border-bottom: 1px solid var(--border-subtle); }
  h2 { font-size: var(--fs-xl); font-weight: 700; }
  .x { width: 32px; height: 32px; border-radius: 50%; color: var(--text-muted); background: var(--tint-2); border: 1px solid var(--border-subtle); }
  .tabs { display: flex; gap: 0.5rem; padding: 0.6rem 1.25rem 0; }
  .tabs button { padding: 0.4rem 0.9rem; font-size: var(--fs-md); font-weight: 600; color: var(--text-muted); border-radius: 8px 8px 0 0; border-bottom: 2px solid transparent; }
  .tabs button.active { color: var(--primary); border-bottom-color: var(--primary); }
  .body { overflow-y: auto; padding: 0.5rem 1.25rem 1rem; }
  h3 { margin: 1rem 0 0.4rem; font-size: var(--fs-md); color: var(--text-muted); }
  .row { display: flex; align-items: center; justify-content: space-between; gap: 1rem; padding: 0.35rem 0; font-size: var(--fs-md); border-bottom: 1px solid var(--border-subtle); }
  .keys { display: flex; align-items: center; gap: 0.3rem; flex-shrink: 0; }
  kbd { min-width: 24px; padding: 2px 7px; text-align: center; font-family: var(--font-mono); font-size: var(--fs-sm); font-weight: 700; color: var(--text-main); background: var(--tint-2); border: 1px solid var(--tint-4); border-bottom-width: 2px; border-radius: 5px; }
  .or { font-size: var(--fs-xs); color: var(--text-dim); margin: 0 0.15rem; }
  .safety { margin-top: 1rem; padding: 0.65rem 0.85rem; font-size: var(--fs-sm); color: var(--text-muted); background: color-mix(in srgb, var(--ok) 8%, transparent); border: 1px solid color-mix(in srgb, var(--ok) 25%, transparent); border-radius: 8px; }
  .foot { padding: 0.75rem 1.25rem; border-top: 1px solid var(--border-subtle); display: flex; justify-content: flex-end; }
  .got { padding: 0.45rem 1.1rem; font-weight: 700; color: var(--on-primary); background: var(--primary-solid); border-radius: var(--radius-sm); }
</style>
