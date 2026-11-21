<script lang="ts">
  import Icon from '../../ui/Icon.svelte'
  import { onMount } from 'svelte'
  import Modal from '../../ui/Modal.svelte'
  import '../../styles/tools.css'
  import type { MascotState } from '../../state/mascots.svelte'

  let { mascots }: { mascots: MascotState } = $props()
  const current = $derived(mascots.selected)
  const engine = $derived(
    !mascots.diagnostics ? 'Checking the mascot engine…'
      : mascots.diagnostics.has_pyside6 ? 'Native PySide6 ready'
      : mascots.diagnostics.has_pyqt6 ? 'Native PyQt6 ready'
      : 'Running in an isolated app window',
  )

  // A mascot window can be closed from the desktop itself, so keep the list fresh while this window is open.
  onMount(() => {
    const timer = setInterval(() => void mascots.refresh(), 3000)
    return () => clearInterval(timer)
  })
</script>

<Modal label="Desktop Mascots" width="920px" onClose={() => (mascots.open = false)}>
  {#snippet title()}Desktop Mascots (DMascot){/snippet}
  {#snippet badges()}<span class="count">{mascots.list.length} Active</span>{/snippet}

  <div class="cols">
    <section class="list">
      <div class="head">
        <strong>Active Mascots</strong>
        <button class="link danger" disabled={!mascots.list.length} onclick={() => mascots.closeAll()}>Close All</button>
      </div>
      {#each mascots.list as m (m.id)}
        <div class="card" class:active={m.id === current?.id} role="button" tabindex="0" onclick={() => (mascots.selectedId = m.id)} onkeydown={(e) => e.key === 'Enter' && (mascots.selectedId = m.id)}>
          <span class="meta"><span class="name" title={m.mod_name}>{m.mod_name}</span><span class="char">{m.character} • {m.layer === 'below' ? 'Desktop' : 'Above'}</span></span>
          <button class="link danger" title="Close this mascot" aria-label="Close this mascot" onclick={(e) => { e.stopPropagation(); void mascots.close(m.id) }}><Icon name="x" size={13} /></button>
        </div>
      {:else}
        <p class="none">No active mascots.<br />Open any mod in Viewer Mode and click <strong>DMascot</strong> at the bottom to launch one!</p>
      {/each}
    </section>

    <section class="detail">
      {#if current}
        <div class="s-page">
          <section class="s-section">
            <div class="who"><div class="s-text"><h3 class="s-title" style="padding:0">{current.mod_name}</h3><span>{current.character}</span></div>
              <button class="tool-btn danger" onclick={() => mascots.close(current.id)}>Close mascot</button></div>
            <div class="s-card">
              <label class="s-row"><span class="s-text"><strong>Draggable</strong><span>Allow dragging anywhere on screen with the mouse.</span></span>
                <input class="s-switch" type="checkbox" role="switch" checked={current.draggable && !current.locked} onchange={(e) => mascots.update(current.id, { draggable: e.currentTarget.checked, locked: !e.currentTarget.checked })} /></label>
              <label class="s-row"><span class="s-text"><strong>Lock position</strong><span>Prevent accidental movement.</span></span>
                <input class="s-switch" type="checkbox" role="switch" checked={current.locked} onchange={(e) => mascots.update(current.id, { locked: e.currentTarget.checked, draggable: !e.currentTarget.checked })} /></label>
              <label class="s-row"><span class="s-text"><strong>Click-through</strong><span>Mouse clicks pass straight to the windows and games below.</span></span>
                <input class="s-switch" type="checkbox" role="switch" checked={current.click_through} onchange={(e) => mascots.update(current.id, { click_through: e.currentTarget.checked })} /></label>
            </div>
          </section>
          <section class="s-section">
            <h3 class="s-title">Desktop layering</h3>
            <div class="s-card"><div class="s-row">
              <div class="s-text"><strong>Layer</strong><span>Where the mascot sits among your windows.</span></div>
              <div class="s-choices" role="radiogroup" aria-label="Desktop layering">
                <button class="s-choice" class:on={current.layer !== 'below'} role="radio" aria-checked={current.layer !== 'below'} onclick={() => mascots.update(current.id, { layer: 'above' })}><Icon name="shield" size={14} /> Above everything</button>
                <button class="s-choice" class:on={current.layer === 'below'} role="radio" aria-checked={current.layer === 'below'} onclick={() => mascots.update(current.id, { layer: 'below' })}><Icon name="image" size={14} /> Behind (desktop)</button>
              </div></div></div>
          </section>
          <section class="s-section">
            <h3 class="s-title">Appearance</h3>
            <div class="s-card">
              <label class="s-row"><span class="s-text"><strong>Scale</strong></span>
                <span class="s-ctl"><input class="range" type="range" min="0.4" max="2" step="0.05" value={current.scale || 1} oninput={(e) => mascots.update(current.id, { scale: Number(e.currentTarget.value) })} /><span class="s-value pct">{Math.round((current.scale || 1) * 100)}%</span></span></label>
              <label class="s-row"><span class="s-text"><strong>Opacity</strong></span>
                <span class="s-ctl"><input class="range" type="range" min="0.2" max="1" step="0.05" value={current.opacity || 1} oninput={(e) => mascots.update(current.id, { opacity: Number(e.currentTarget.value) })} /><span class="s-value pct">{Math.round((current.opacity || 1) * 100)}%</span></span></label>
            </div>
          </section>
        </div>
      {:else}
        <div class="placeholder"><span><Icon name="sparkles" size={28} /></span><p>Launch a mascot from Viewer Mode to manage it here.</p></div>
      {/if}
    </section>
  </div>

  {#snippet footer()}
    <div class="engine"><span>{engine}</span><button class="btn small" title="Configure the BD2_Mascot rule in ~/.config/kwinrulesrc" onclick={() => mascots.configureKwin()}>Configure KWin Rule</button></div>
    <button class="btn" onclick={() => (mascots.open = false)}>Close</button>
  {/snippet}
</Modal>

<style>
  .count { padding: 0.1rem 0.5rem; font-size: var(--fs-sm); font-weight: 600; color: var(--text-muted); background: var(--tint-2); border: 0; border-radius: 4px; }
  .cols { display: flex; gap: 1.2rem; min-height: 380px; }
  .list { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 0.5rem; padding: 0.75rem; background: var(--surface-panel); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); max-height: 420px; overflow-y: auto; }
  .head { display: flex; align-items: center; justify-content: space-between; font-size: var(--fs-sm); color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; }
  .link { font-size: var(--fs-sm); color: var(--text-muted); } .link.danger { color: var(--danger-text); } .link:disabled { opacity: 0.4; }
  .card { display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; padding: 0.55rem 0.7rem; cursor: pointer; background: var(--tint-1); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); }
  .card:hover { background: var(--tint-2); }
  .card.active { background: var(--selected-bg); border-color: var(--primary); }
  .meta { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
  .name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: var(--fs-md); font-weight: 600; color: var(--text-main); }
  .char { font-size: var(--fs-sm); color: var(--text-muted); }
  .none { padding: 2rem 1rem; text-align: center; font-size: var(--fs-md); color: var(--text-dim); line-height: 1.6; }
  .detail { flex: 1.5; min-width: 0; }
  .who { display: flex; align-items: center; justify-content: space-between; gap: 1rem; padding: 0 0.25rem; }
  .who .s-text > span { font-size: var(--fs-sm); color: var(--text-muted); }
  .range { width: 9rem; }
  .pct { min-width: 3rem; }
  .placeholder { height: 320px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 0.5rem; text-align: center; color: var(--text-dim); font-size: var(--fs-md); }
  .placeholder span { font-size: 2.2rem; }
  .engine { display: flex; align-items: center; gap: 0.6rem; font-size: var(--fs-sm); color: var(--text-dim); }
  .btn { padding: 0.4rem 0.85rem; font-size: var(--fs-md); font-weight: 600; color: var(--text-main); background: var(--tint-2); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); }
  .btn.small { padding: 2px 8px; font-size: var(--fs-sm); }
  @media (max-width: 760px) { .cols { flex-direction: column; } .list { border-right: 0; padding-right: 0; max-height: 180px; } }
</style>
