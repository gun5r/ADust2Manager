<script lang="ts">
  import Icon from '../../ui/Icon.svelte'
  import type { SharedBundleGroup } from '../../lib/api'
  import Modal from '../../ui/Modal.svelte'
  import Lightbox from '../../ui/Lightbox.svelte'
  import PortraitColumn, { type Tile } from './PortraitColumn.svelte'

  let { groups, portraitOf, onAddAll, onAlone, onCancel }: {
    groups: SharedBundleGroup[]
    /** The portrait kept for a mod folder (none: a blank space). */
    portraitOf: (folder: string | undefined) => string | null
    onAddAll: () => void
    onAlone: () => void
    onCancel: () => void
  } = $props()
  let enlarged = $state<string | null>(null)
  /** Installed (left) and new / queued (right) mods of every shared bundle, each once, as portraits. */
  const unique = (mods: { name: string; folder_path: string; source_folder?: string }[]): Tile[] =>
    [...new Map(mods.map((m) => [m.folder_path, { key: m.folder_path, name: m.name, folder: m.source_folder ?? m.folder_path }])).values()]
  const installedTiles = $derived(unique(groups.flatMap((g) => g.installed_mods ?? [])))
  const newTiles = $derived(unique(groups.flatMap((g) => g.new_mods ?? [])))
  const queueTiles = $derived(unique(groups.flatMap((g) => g.queue_mods ?? [])))
</script>

<Modal label="Shared Game Bundle Detected" width="1200px" footerJustify="flex-end" onClose={onCancel}>
  {#snippet title()}<span class="icon"><Icon name="package" size={18} color="var(--cat-illust)" /></span> Shared Game Bundle Detected{/snippet}
  <div class="frame">
  <PortraitColumn sections={[{ title: 'Mods Marked as Installed:', tone: 'green', tiles: installedTiles }]} {portraitOf} onOpen={(src) => (enlarged = src)} />
  <div class="body">
    <div class="alert">
      <div class="alert-icon"><Icon name="lightbulb" size={20} color="var(--warn-text)" /></div>
      <div class="alert-text">
        <strong>Smart Batch Merging Available:</strong><br />
        The mod(s) you are preparing share the exact same game asset bundle (e.g. dating scene package) with <strong>already installed mods</strong>.
        Installing without merging will overwrite the in-game bundle, which causes previously installed mods in this bundle to revert to default game textures!
      </div>
    </div>
    <div class="actions" role="group" aria-label="What to do">
      <button class="choice primary" onclick={onAddAll}>
        <Icon name="package" size={16} color="var(--primary)" />
        <span class="ctext"><strong>Add All Shared Installed Mods to Queue</strong><span class="sub blue">(Rebuilds the installed mods of this bundle together with the new mod(s), so none of them reverts.)</span></span>
      </button>
      <button class="choice alone" title="Install new mod(s) alone without adding installed mods." onclick={onAlone}>
        <Icon name="zap" size={16} color="var(--warn-text)" />
        <span class="ctext"><strong>Install Alone</strong><span class="sub amber">(Only the new mod(s): installed mods of this bundle may go back to the game's default.)</span></span>
      </button>
      <button class="choice" onclick={onCancel}>
        <Icon name="circle-x" size={16} />
        <span class="ctext"><strong>Cancel</strong><span class="sub">(Nothing is added to the queue.)</span></span>
      </button>
    </div>
    {#each groups as g (g.bundle_hash)}
      <div class="card">
        <div class="head">
          <span><Icon name="package" size={14} color="var(--cat-illust)" /> Shared Asset Bundle</span>
          <div class="head-right"><span class="count">{g.total_mods_count} mods share this bundle</span><span class="hash">{g.bundle_hash.substring(0, 16)}...</span></div>
        </div>
        <div class="list">
          {#if g.new_mods?.length}
            <div class="label blue"><Icon name="sparkles" size={12} /> New Mod(s) to Prepare:</div>
            {#each g.new_mods as m}<div class="item"><span class="mname"><span class="blue"><Icon name="sparkles" size={11} /></span> {m.name}</span><span class="badge new">New</span></div>{/each}
          {/if}
          {#if g.queue_mods?.length}
            <div class="label amber">⏳ In Queue / Cache (Waiting to Transfer):</div>
            {#each g.queue_mods as m}<div class="item"><span class="mname"><span class="amber">⏳</span> {m.name}</span><span class="badge queue">In Queue</span></div>{/each}
          {/if}
          {#if g.installed_mods?.length}
            <div class="label green"><Icon name="check" size={12} /> Already Installed on Phone:</div>
            {#each g.installed_mods as m}<div class="item"><span class="mname"><span class="green"><Icon name="check" size={12} /></span> {m.name}</span><span class="badge installed">Installed</span></div>{/each}
          {/if}
        </div>
      </div>
    {/each}
  </div>
  <PortraitColumn sections={[{ title: 'New Mods:', tone: 'blue', tiles: newTiles }, { title: 'In the Queue:', tone: 'amber', tiles: queueTiles }]} {portraitOf} onOpen={(src) => (enlarged = src)} />
  </div>
  {#if enlarged}<Lightbox src={enlarged} onClose={() => (enlarged = null)} />{/if}
</Modal>

<style>
  .icon { font-size: var(--fs-2xl); }
  .frame { flex: 1; min-height: 0; display: flex; gap: 1rem; align-items: stretch; }
  .body { flex: 1; min-width: 0; min-height: 0; overflow-y: auto; display: flex; flex-direction: column; gap: 1.1rem; padding: 0.85rem; background: var(--surface-panel); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); }
  .alert { display: flex; gap: 0.85rem; padding: 0.9rem 1.1rem; background: transparent; border: 1px solid var(--border-subtle); border-radius: var(--radius-md); }
  .alert-icon { font-size: var(--fs-2xl); line-height: 1; }
  .alert-text { font-size: var(--fs-md); line-height: 1.5; color: var(--text-muted); }
  .card { display: flex; flex-direction: column; gap: 0.6rem; padding: 0.85rem 1rem; background: transparent; border: 1px solid var(--border-subtle); border-radius: var(--radius-md); }
  .head { display: flex; align-items: center; justify-content: space-between; font-size: var(--fs-md); font-weight: 700; color: var(--text-main); }
  .head-right { display: flex; align-items: center; gap: 0.5rem; }
  .count { padding: 2px 6px; font-size: var(--fs-sm); font-weight: 600; background: var(--tint-2); border-radius: 4px; }
  .hash { padding: 0.15rem 0.45rem; font-family: var(--font-mono); font-size: var(--fs-sm); color: var(--text-muted); background: var(--tint-2); border-radius: 4px; }
  .list { display: flex; flex-direction: column; gap: 0.4rem; }
  .label { margin-top: 0.45rem; font-size: var(--fs-sm); font-weight: 700; text-transform: uppercase; }
  .label:first-child { margin-top: 0.25rem; }
  .blue { color: var(--text-muted); } .amber { color: var(--warn-text); } .green { color: var(--ok-text); }
  .item { display: flex; align-items: center; justify-content: space-between; padding: 0.45rem 0.75rem; font-size: var(--fs-md); background: var(--tint-1); border: 0; border-radius: var(--radius-sm); }
  .mname { display: flex; align-items: center; gap: 0.5rem; font-weight: 600; color: var(--text-main); }
  .badge { padding: 0.15rem 0.5rem; font-size: var(--fs-xs); font-weight: 600; border-radius: 12px; border: 1px solid; }
  .badge.installed { color: var(--ok-text); background: color-mix(in srgb, var(--ok) 15%, transparent); border-color: color-mix(in srgb, var(--ok) 35%, transparent); }
  .badge.new { color: var(--text-muted); background: transparent; border-color: var(--border-subtle); }
  .badge.queue { color: var(--warn-text); background: color-mix(in srgb, var(--warn) 15%, transparent); border-color: color-mix(in srgb, var(--warn) 35%, transparent); }
  .actions { display: flex; flex-direction: column; gap: 0.45rem; }
  .choice { display: flex; align-items: center; gap: 0.65rem; width: 100%; padding: 0.55rem 0.8rem; text-align: left; background: var(--tint-1); border: 1px solid transparent; border-radius: var(--radius-sm); transition: background 0.12s; }
  .choice:hover { background: var(--tint-2); }
  .choice.primary { background: var(--selected-bg); border-color: var(--primary); }
  .choice.primary:hover { background: var(--selected-bg); }
  .choice.alone { border-color: color-mix(in srgb, var(--warn) 40%, transparent); }
  .ctext { display: flex; flex-direction: column; gap: 2px; font-size: var(--fs-md); color: var(--text-main); }
  .sub { font-size: var(--fs-sm); color: var(--text-dim); } .sub.blue { color: var(--text-muted); } .sub.amber { color: var(--warn-text); }
</style>
