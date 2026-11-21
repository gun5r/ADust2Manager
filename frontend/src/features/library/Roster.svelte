<script lang="ts">
  import Icon from '../../ui/Icon.svelte'
  import { characterPortraits } from '../../lib/portraits'
  import { neverHasPortrait } from '../../lib/grouping'
  import type { Character } from '../../lib/api'
  import Avatar from '../../ui/Avatar.svelte'
  import Badge from '../../ui/Badge.svelte'
  import type { ModBadges } from '../../lib/badges'

  let { entries, roster, columns, query, active, lit, onQuery, onColumns, onSelect }: {
    entries: ({ name: string; count: number } & ModBadges)[]
    roster: Character[]
    columns: 2 | 3
    query: string
    active: string | null
    /** The character of the costume clicked in Costume mode (lit blue while the list is not isolated). */
    lit: string | null
    onQuery: (value: string) => void
    onColumns: () => void
    onSelect: (name: string) => void
  } = $props()

  const imageOf = (name: string) => characterPortraits(roster.find((c) => c.name === name))
</script>

<aside class="panel" data-ui="roster">
  <div class="head">
    <div class="title">
      <h4><Icon name="users" size={15} color="currentColor" /> Characters</h4>
      <div class="actions">
        <button class="cols" title="Switch between 2-column and 3-column character view" onclick={onColumns}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><rect x="3" y="3" width="7" height="18" rx="1"></rect><rect x="14" y="3" width="7" height="18" rx="1"></rect></svg>
        </button>
        <span class="count">{entries.length}</span>
      </div>
    </div>
    <div class="search">
      <span class="mag"><Icon name="search" size={13} /></span>
      <input type="text" placeholder="Search…" value={query} oninput={(e) => onQuery(e.currentTarget.value)} />
      <button class="reset" title="Reset search" aria-label="Reset search" onclick={() => onQuery('')}><Icon name="x" size={13} /></button>
    </div>
  </div>
  <div class="list" class:two={columns === 2}>
    {#each entries as entry (entry.name)}
      <div class="card" class:nomods={!entry.count} class:isolated={active === entry.name} class:lit={lit === entry.name} role="button" tabindex="0" title={entry.count ? `Jump to ${entry.name} (${entry.count} mod${entry.count > 1 ? 's' : ''})` : `${entry.name} (no mods)`}
           onclick={() => entry.count && onSelect(entry.name)} onkeydown={(e) => e.key === 'Enter' && entry.count && onSelect(entry.name)}>
        <div class="art">
          <Avatar name={entry.name} urls={imageOf(entry.name)} variant="card" />
          {#if entry.queued}<span class="corner left"><Badge kind="queued" n={entry.queued} small={columns === 3} /></span>{/if}
          <span class="corner right">
            {#if entry.installed}<Badge kind="installed" n={entry.installed} small={columns === 3} />{/if}
            <span class="cascade">
              {#if entry.idle}<Badge kind="idle" n={entry.idle} small={columns === 3} />{/if}
              {#if entry.cut}<Badge kind="cut" n={entry.cut} small={columns === 3} />{/if}
              {#if entry.rest}<Badge kind="rest" n={entry.rest} small={columns === 3} />{/if}
            </span>
          </span>
        </div>
        {#if !neverHasPortrait(entry.name)}<span class="name">{entry.name}</span>{/if}
      </div>
    {:else}
      <span class="empty">No matching characters.</span>
    {/each}
  </div>
</aside>

<style>
  .panel { display: flex; flex-direction: column; min-height: 0; padding: 0.65rem; background: var(--surface-1); border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md); overflow: hidden; }
  .head { display: flex; flex-direction: column; gap: 0.45rem; padding-bottom: 0.45rem; border-bottom: 1px solid var(--border-subtle); flex-shrink: 0; }
  .title { display: flex; justify-content: space-between; align-items: center; min-height: 21px; }
  h4 { font-size: var(--fs-md); font-weight: 700; color: var(--text-main); display: flex; align-items: center; gap: 0.35rem; }
  .actions { display: flex; align-items: center; gap: 0.4rem; }
  .cols { display: inline-flex; align-items: center; justify-content: center; padding: 2px 7px; border-radius: 4px; background: transparent;
    border: 0; color: var(--text-dim); transition: all 0.15s ease; }
  .cols:hover { background: var(--tint-3); color: var(--text-main); }
  .count { font-size: var(--fs-sm); font-weight: 600; padding: 2px 4px; color: var(--text-dim); }
  .search { position: relative; display: flex; align-items: center; gap: 0.35rem; }
  .mag { position: absolute; left: 0.6rem; top: 50%; transform: translateY(-50%); display: flex; color: var(--text-dim); pointer-events: none; z-index: 1; }
  .search input { flex: 1; min-width: 0; height: 28px; padding: 0 0.65rem 0 1.85rem; background: color-mix(in srgb, var(--surface-2) 85%, transparent); border: 1px solid var(--border-subtle);
    border-radius: 6px; color: var(--text-main); font-size: var(--fs-sm); outline: none; transition: all 0.2s ease; }
  .search input:focus { border-color: var(--primary); box-shadow: none; background: color-mix(in srgb, var(--surface-2) 95%, transparent); }
  .reset { width: 28px; height: 28px; flex-shrink: 0; display: inline-flex; align-items: center; justify-content: center; font-size: var(--fs-sm); color: var(--text-muted);
    background: transparent; border: 0; border-radius: 6px; transition: all 0.15s ease; }
  .reset:hover { background: var(--tint-3); color: var(--text-main); }

  .list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.65rem; overflow-y: auto; overflow-x: hidden; padding: 0.2rem 0.35rem 0.5rem 0.2rem;
    flex: 1 1 0; min-height: 0; align-content: start; scrollbar-color: var(--tint-4) transparent; }
  .list:not(.two) { grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0.4rem; }
  .list::-webkit-scrollbar { width: 12px; }
  .list::-webkit-scrollbar-track { background: color-mix(in srgb, var(--surface-2) 85%, transparent); border-radius: 8px; box-shadow: none; }
  .list::-webkit-scrollbar-thumb { background: var(--tint-4); border-radius: 8px; border: 2px solid color-mix(in srgb, var(--surface-2) 85%, transparent); background-clip: padding-box; min-height: 52px; box-shadow: none; }
  .empty { grid-column: 1 / -1; padding: 1rem; text-align: center; font-size: var(--fs-sm); color: var(--text-dim); }

  .card { position: relative; display: flex; flex-direction: column; width: 100%; min-width: 0; height: 98px; padding: 2px; overflow: hidden; cursor: pointer;
    background: color-mix(in srgb, var(--surface-2) 95%, transparent); border: 1px solid var(--border-subtle); border-radius: 8px;
    transition: border-color 0.15s, transform 0.15s, box-shadow 0.15s; user-select: none; }
  .two .card { height: 142px; }
  /* a character nobody made a mod for: grey until the pointer is over it */
  .card.nomods:not(:hover) { filter: grayscale(1) brightness(0.8); opacity: 0.7; }
  .card:hover { border-color: var(--border-focus); transform: var(--lift); box-shadow: var(--shadow-card); }
  .card.isolated { border: 1.5px solid color-mix(in srgb, var(--cat-dating) 50%, var(--cat-multi)); background: color-mix(in srgb, var(--cat-dating) 12%, var(--cat-multi) 10%); }
  .art { position: relative; flex: 1 1 100%; min-height: 0; display: flex; align-items: center; justify-content: center; overflow: hidden; border-radius: 7px;
    background: linear-gradient(180deg, color-mix(in srgb, var(--surface-3) 65%, transparent) 0%, color-mix(in srgb, var(--surface-2) 90%, transparent) 100%); }
  .card:hover .art :global(img) { transform: scale(1.1); }
  .art :global(img) { transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1); }
  .corner { position: absolute; z-index: 2; top: 4px; display: flex; align-items: flex-start; gap: 3px; }
  .corner.left { left: 4px; }
  .corner.right { right: 4px; }
  .cascade { display: flex; flex-direction: column; align-items: flex-end; gap: 3px; }
  .name { position: absolute; bottom: 3px; left: 50%; transform: translateX(-50%); width: max-content; max-width: calc(100% - 8px); padding: 1px 5px; font-size: var(--fs-sm);
    font-weight: 700; color: var(--text-main); text-align: center; background: var(--scrim-soft); border: 0; border-radius: 4px; line-height: 1.15;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; z-index: 2; }
  .list:not(.two) .name { font-size: var(--fs-xs); padding: 1px 4px; bottom: 2px; }
  .card.lit { border-color: var(--primary); animation: lit 1.8s ease-in-out infinite; }
  @keyframes lit {
    0%, 100% { box-shadow: 0 0 0 2px rgba(var(--primary-rgb), 0.55); }
    50% { box-shadow: 0 0 0 2px rgba(var(--primary-rgb), 1); }
  }
</style>
