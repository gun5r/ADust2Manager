<script lang="ts">
  import Icon from '../../ui/Icon.svelte'
  import type { ViewerState } from './viewer.svelte'
  let { viewer }: { viewer: ViewerState } = $props()
</script>

<div class="sub">
  <div class="header"><span>Animations</span></div>
  <div class="list" data-ui="animations">
    {#if viewer.sequence.length}
      <button class="pill" class:active={viewer.sequencePlaying} title="Play complete sequence: {viewer.sequence.join(' → ')}" onclick={() => viewer.playSequence()}>
        <span class="icon"><Icon name="clapperboard" size={13} /></span><span class="label">Full Cutscene ({viewer.sequence.join(' → ')})</span>
      </button>
    {/if}
    {#each viewer.clips as clip (clip.name)}
      <button class="pill" class:active={viewer.current === clip.name} title="Animation: {clip.name} (Duration: {clip.duration.toFixed(2)}s)" onclick={() => viewer.play(clip.name)}>
        <span class="icon">▶</span><span class="label">{clip.name}</span><span class="dur">{clip.duration ? `${clip.duration.toFixed(1)}s` : ''}</span>
      </button>
    {:else}
      <span class="empty">{viewer.status === 'loading' ? 'Loading animations...' : 'No animation clips detected in this skeleton.'}</span>
    {/each}
  </div>
</div>

<style>
  .sub { display: flex; flex-direction: column; flex: 1; min-height: 0; }
  .header { padding: 0.5rem 0.75rem; font-size: var(--fs-sm); font-weight: 700; letter-spacing: 0.08em; color: var(--text-dim); text-transform: uppercase; flex-shrink: 0; }
  .list { flex: 1; min-height: 0; overflow-y: auto; display: flex; flex-direction: column; gap: 3px; padding: 4px 4.8px; }
  .pill { width: 100%; display: flex; align-items: center; gap: 0.45rem; min-height: 33px; flex-shrink: 0; padding: 0.38rem 0.65rem; font-size: var(--fs-md); font-weight: 550; color: var(--text-main); text-align: left;
    background: transparent; border: 1px solid transparent; border-radius: var(--radius-sm); transition: background 0.12s; user-select: none; }
  .pill:hover { background: var(--tint-2); color: var(--text-main); }
  .pill.active { background: var(--selected-bg); border-color: rgba(var(--primary-rgb), 0.6); color: var(--text-main); font-weight: 700; }
  .icon { font-size: var(--fs-xs); color: var(--text-muted); flex-shrink: 0; } .pill.active .icon { color: var(--primary); }
  .label { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .dur { margin-left: auto; font-size: var(--fs-xs); font-family: var(--font-mono); opacity: 0.55; }
  .empty { padding: 1rem; font-size: var(--fs-md); color: var(--text-dim); }
</style>
