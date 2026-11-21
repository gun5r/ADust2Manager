<script lang="ts">
  import { effectiveCategory, type IndexMod } from '../../lib/classify'

  import { lacksSkeleton } from '../../lib/skeleton'
  import ModActions from './ModActions.svelte'
  let { mod, selected, installed, onToggle, onMark, onMerge, onPreview, onPrepare, onChoose }: {
    mod: IndexMod
    selected: boolean
    installed: boolean
    onToggle: () => void
    onMark: () => void
    onMerge: () => void
    onPreview: () => void
    onPrepare: () => void
    onChoose: () => void
  } = $props()

  const category = $derived(effectiveCategory(mod))
  const labels: Record<string, string> = { idle: 'Idle', cut: 'Skill', illust: 'Illust', dating: 'Dating', multi: 'Multi', other: 'Other' }
  const textures = $derived(mod.texture_count || 1)
</script>

<!-- Clicking anywhere on the row toggles selection; buttons stop the click. -->
<div class="row" style:--cat="var(--cat-{category})" data-ui="mod-row" class:selected role="button" tabindex="0" aria-pressed={selected} data-folder={mod.folder_path} onclick={onToggle}
     onkeydown={(e) => { if (e.target === e.currentTarget && (e.key === ' ' || e.key === 'Enter')) { e.preventDefault(); onToggle() } }}>
  <div class="check"><span class="box" class:on={selected}></span></div>
  <div class="name">
    <span class="full" title={mod.name}>{mod.name}</span>
    <span class="stem">{mod.asset_stem || mod.id}</span>
  </div>
  <div class="tags">
    <span class="tag {category}">{labels[category] ?? category}</span>
    <span class="tag textures">{textures} PNG{textures > 1 ? 's' : ''}</span>
    {#if lacksSkeleton(mod)}<span class="tag nosk" title="No skeleton file: Preview or Prepare offers to add one">No skeleton</span>
    {:else}<span class="tag {mod.has_json_anim ? 'json' : 'skel'}">{mod.has_json_anim ? '.json' : '.skel'}</span>{/if}
    {#if mod.has_backup}<span class="tag merged">Merged</span>{/if}
    {#if installed}<span class="tag merged">Installed</span>{/if}
  </div>
  <div class="actions" role="presentation" onclick={(e) => e.stopPropagation()}>
    <ModActions {mod} {installed} {onMark} {onMerge} {onPreview} {onPrepare} {onChoose} />
  </div>
</div>

<style>
  .row { position: relative; display: flex; align-items: center; gap: 0.85rem; padding: 0.45rem 0.85rem; background: var(--surface-row); border: 1px solid var(--border-subtle);
    border-left: 3px solid color-mix(in srgb, var(--cat) 75%, transparent); border-radius: var(--radius-sm); cursor: pointer; transition: background 0.12s, border-color 0.12s, transform 0.12s, box-shadow 0.12s; }
  .row { --row-bg: var(--surface-row); }
  .row:hover { --row-bg: var(--bg-card-hover); background: var(--bg-card-hover); border-color: var(--tint-4); box-shadow: var(--shadow-card); }
  .row.selected { --row-bg: color-mix(in srgb, var(--primary) 16%, var(--surface-2)); background: var(--row-bg); border-color: var(--primary); border-left-color: var(--primary); }
  .check { width: 18px; height: 18px; flex-shrink: 0; }
  .box { position: relative; display: block; width: 18px; height: 18px; border-radius: 5px; border: 2px solid var(--tint-4); background: color-mix(in srgb, var(--surface-2) 70%, transparent); transition: all 0.15s ease; }
  .box.on { background: var(--primary-solid); border-color: var(--primary); }
  .box.on::after { content: ''; position: absolute; width: 5px; height: 9px; border: solid var(--text-main); border-width: 0 2px 2px 0; top: 45%; left: 50%; transform: translate(-50%, -50%) rotate(45deg); }
  .name { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 0.15rem; }
  .full { font-size: var(--fs-lg); line-height: 1.35; font-weight: 700; color: var(--text-main); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .stem { font-family: var(--font-mono); font-size: var(--fs-sm); color: var(--text-dim); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .tags { display: flex; align-items: center; justify-content: flex-end; gap: 0.4rem; flex-shrink: 0; min-width: 15rem; }
  .tag { font-size: var(--fs-sm); font-weight: 600; padding: 0.2rem 0.55rem; border-radius: 4px; background: var(--tint-2); border: 1px solid var(--border-subtle); color: var(--text-muted); white-space: nowrap; }
  /* one colour per tag (--c); its tint and border derive from it */
  .tag.idle, .tag.cut, .tag.illust, .tag.dating, .tag.other, .tag.multi, .tag.nosk, .tag.merged { color: var(--c); background: color-mix(in srgb, var(--c) 12%, transparent); border-color: color-mix(in srgb, var(--c) 32%, transparent); }
  .tag.idle { --c: var(--cat-idle); } .tag.cut { --c: var(--cat-cut); } .tag.illust { --c: var(--cat-illust); } .tag.dating { --c: var(--cat-dating); }
  .tag.other { --c: var(--cat-other); } .tag.multi { --c: var(--cat-multi); } .tag.nosk { --c: var(--danger-text); } .tag.merged { --c: var(--cat-merged); }
  .tag.textures, .tag.skel, .tag.json { color: var(--text-dim); background: transparent; border-color: transparent; padding-inline: 0.25rem; }
  /* the actions float over the right end of the row, so they never take space from the name or move the tags */
  .actions { position: absolute; right: 0.55rem; top: 50%; transform: translateY(-50%); display: flex; align-items: center; gap: 0.4rem; padding: 0.3rem 0.3rem 0.3rem 1.6rem; background: linear-gradient(90deg, transparent, var(--row-bg) 1.2rem); opacity: 0; pointer-events: none; transition: opacity 0.12s; }
  /* actions appear on hover, keyboard focus or selection; touch screens have no hover, so they stay visible there */
  .row:hover .actions, .row:focus-within .actions, .row.selected .actions { opacity: 1; pointer-events: auto; }
  @media (hover: none) { .actions { opacity: 1; pointer-events: auto; } }
  /* keep the name clear of the floating buttons while they show */
  .row:hover .name, .row:focus-within .name, .row.selected .name { padding-right: 13rem; }
  @media (hover: none) { .name { padding-right: 13rem; } }
  /* narrow list: the secondary tags give way first */
  @container centerpanel (max-width: 620px) { .tag.textures, .tag.skel, .tag.json { display: none; } .tags { min-width: 0; } }
</style>
