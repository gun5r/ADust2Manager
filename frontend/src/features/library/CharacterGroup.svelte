<script lang="ts">
  import { characterPortraits } from '../../lib/portraits'
  import type { Character } from '../../lib/api'
  import type { IndexMod } from '../../lib/classify'
  import type { CharacterGroup } from '../../lib/grouping'
  import Avatar from '../../ui/Avatar.svelte'
  import { modKey } from '../../lib/selection'
  import ModRow from './ModRow.svelte'

  let { group, lit = false, roster, selected, installed, onToggle, onSelectGroup, onMark, onMerge, onPreview, onPrepare, onChoose }: {
    group: CharacterGroup
    /** The character clicked in the roster: the section is framed with a breathing blue glow. */
    lit?: boolean
    roster: Character[]
    selected: Set<string>
    installed: Set<string>
    onToggle: (mod: IndexMod) => void
    onSelectGroup: (mods: IndexMod[], on: boolean) => void
    onMark: (mod: IndexMod) => void
    onMerge: (mod: IndexMod) => void
    onPreview: (mod: IndexMod) => void
    onPrepare: (mod: IndexMod) => void
    onChoose: (mod: IndexMod) => void
  } = $props()

  const image = $derived(characterPortraits(roster.find((c) => c.name === group.name)))
  const selectedCount = $derived(group.mods.filter((m) => selected.has(modKey(m))).length)
  const isInstalled = (m: IndexMod) => installed.has(m.name) || (m.id !== undefined && installed.has(m.id))
</script>

<section class="group" class:lit data-ui="char-group" id="char-section-{group.name}">
  <div class="header">
    <div class="left">
      <Avatar name={group.name} urls={image} />
      <h3>{group.name}</h3>
      {#if selectedCount > 0}<span class="sel" title="{selectedCount} selected for batch" aria-label="{selectedCount} selected">{selectedCount} selected</span>{/if}
      <span class="count">{group.mods.length} mod{group.mods.length > 1 ? 's' : ''}</span>
    </div>
    <div class="links">
      <button class="link" onclick={() => onSelectGroup(group.mods, true)}>Select All</button>
      <span class="bar">|</span>
      <button class="link" onclick={() => onSelectGroup(group.mods, false)}>Deselect</button>
    </div>
  </div>
  <div class="rows">
    {#each group.sections as section (section.key)}
      {#if group.name !== 'Others'}
        <div class="separator" class:illust={section.isIllustrations}>
          <span class="light"></span><span class="title">{section.title}</span><span class="line"></span>
        </div>
      {/if}
      {#each section.mods as mod (modKey(mod))}
        <ModRow {mod} selected={selected.has(modKey(mod))} installed={isInstalled(mod)}
                onToggle={() => onToggle(mod)} onMark={() => onMark(mod)} onMerge={() => onMerge(mod)}
                onPreview={() => onPreview(mod)} onPrepare={() => onPrepare(mod)} onChoose={() => onChoose(mod)} />
      {/each}
    {/each}
  </div>
</section>

<style>
  .group.lit { animation: lit 1.8s ease-in-out infinite; }
  @keyframes lit {
    0%, 100% { box-shadow: inset 0 0 0 2px rgba(var(--primary-rgb), 0.55); }
    50% { box-shadow: inset 0 0 0 2px rgba(var(--primary-rgb), 1); }
  }
  .group { padding: 0.55rem 0.2rem; background: transparent; border: 0; border-bottom: 1px solid var(--border-subtle); border-radius: 0; }
  .header { display: flex; justify-content: space-between; align-items: center; padding-bottom: 0.5rem; border-bottom: 1px solid var(--border-subtle); }
  .left { display: flex; align-items: center; gap: 0.65rem; }
  h3 { font-size: var(--fs-lg); font-weight: 700; color: var(--text-main); }
  .count { font-size: var(--fs-sm); font-weight: 600; padding: 0.15rem 0.55rem; background: var(--tint-2); color: var(--text-muted); } /* square on purpose: classic's --radius-full is undefined here */
  .sel { font-size: var(--fs-xs); font-weight: 700; padding: 0.1rem 0.45rem; border-radius: var(--radius-full); background: var(--primary-solid); color: var(--on-primary); }
  .links { display: flex; align-items: center; gap: 0.5rem; opacity: 0; transition: opacity 0.12s; }
  .header:hover .links, .header:focus-within .links { opacity: 1; }
  @media (hover: none) { .links { opacity: 1; } }
  .bar { color: var(--border-subtle); }
  .link { font-size: var(--fs-sm); font-weight: 600; color: var(--text-muted); transition: color 0.15s ease; }
  .link:hover { color: var(--primary); text-decoration: underline; }
  .rows { display: flex; flex-direction: column; gap: 0.45rem; }
  .separator { display: flex; align-items: center; gap: 0.65rem; padding: 0.3rem 0; margin: 0.1rem 0 0.1rem; }
  .light { display: none; }
  .title { font-size: var(--fs-md); font-weight: 700; color: var(--text-muted); }
  .line { flex: 1; height: 1px; background: var(--border-subtle); }
</style>
