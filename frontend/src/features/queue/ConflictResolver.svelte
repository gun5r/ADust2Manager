<script lang="ts">
  import Icon from '../../ui/Icon.svelte'
  import Modal from '../../ui/Modal.svelte'
  import type { ConflictGroup } from '../../lib/conflictView'
  import { KEEP_INSTALLED, SKIP_ALL } from '../../lib/queue'
  import Lightbox from '../../ui/Lightbox.svelte'
  import PortraitColumn, { type Tile } from './PortraitColumn.svelte'

  let { groups, portraitOf, onConfirm, onCancel }: {
    groups: ConflictGroup[]
    /** The portrait of the mod whose portrait folder is given (none: a blank space). */
    portraitOf: (folder: string | undefined) => string | null
    onConfirm: (choices: Record<string, string>) => void
    onCancel: () => void
  } = $props()

  let picked = $state<Record<string, string>>({})
  let enlarged = $state<string | null>(null)
  const choice = (g: ConflictGroup) => picked[g.key] ?? g.options[0].id
  const queueMode = $derived(groups.some((g) => g.queue))
  /** The mods already on the phone (left) and the ones being added (right), each once, shown as portraits so they can be told apart without reading names. */
  const installedTiles = $derived([...new Map(groups.filter((g) => g.installed).map((g) => [g.installedFolder || g.installed!, { key: g.installedFolder || g.installed!, name: g.installed!, folder: g.installedFolder ?? undefined }])).values()] as Tile[])
  const newTiles = $derived([...new Map(groups.flatMap((g) => g.options).map((o) => [o.id, { key: o.id, name: o.name, folder: o.folder }])).values()] as Tile[])
</script>

<Modal label="Mod Conflict Resolver" width={installedTiles.length ? '1200px' : '940px'} onClose={onCancel}>
  {#snippet title()}<span class="warn"><Icon name="triangle-alert" size={18} color="var(--warn-text)" /></span> Mod Conflict Resolver{/snippet}
  <div class="frame">
  {#if installedTiles.length}<PortraitColumn sections={[{ title: 'Mods Marked as Installed:', tone: 'green', tiles: installedTiles }]} {portraitOf} onOpen={(src) => (enlarged = src)} />{/if}
  <div class="body">
    <p class="intro">
      {#if queueMode}The following mods in your queue modify the <strong>same in-game mod file name</strong> (asset), or conflict with installed mods. Only one can be active on the phone for each asset. Choose which one to keep:
      {:else}The following selected mods modify the <strong>same in-game character asset or animation</strong>. Only one mod can be active on the phone for each asset. Please choose which mod to prepare:{/if}
    </p>
    {#each groups as g (g.key)}
      <div class="group">
        <div class="group-title">
          <span><Icon name="triangle-alert" size={14} color="var(--warn-text)" /> {g.character} ({g.key})</span>
          {#if g.installed}<span class="tag amber">Conflict with Installed Mod</span>
          {:else}<span class="tag subtle">{g.options.length} competing mods{g.queue ? ' in queue' : ''}</span>{/if}
        </div>
        {#if g.installed}<p class="notice">Mod <strong>"{g.installed}"</strong> is currently installed on your phone for this asset. Choose which mod to keep:</p>{/if}
        <div class="options">
          {#each g.options as o (o.id)}
            <label class="option" class:selected={choice(g) === o.id}>
              <input type="radio" name={g.key} checked={choice(g) === o.id} onchange={() => (picked[g.key] = o.id)} />
              <div class="text">
                <div class="line">
                  <span class="oname"><Icon name="sparkles" size={14} color="var(--primary)" /> {g.queue ? 'Keep in Queue' : 'Install New Mod'}: <strong>{o.name}</strong></span>
                  {#each o.badges ?? [] as b}<span class="tag {b.tone}">{b.text}</span>{/each}
                </div>
                {#if g.installed}<span class="sub blue">(Will replace "{g.installed}". Installed mark switches upon phone transfer.)</span>
                {:else}<span class="sub">{g.character} • {g.key}</span>{/if}
              </div>
            </label>
          {/each}
          {#if g.installed}
            <label class="option" class:selected={choice(g) === KEEP_INSTALLED}>
              <input type="radio" name={g.key} checked={choice(g) === KEEP_INSTALLED} onchange={() => (picked[g.key] = KEEP_INSTALLED)} />
              <div class="text"><span class="oname"><Icon name="shield" size={14} color="var(--ok-text)" /> Keep Installed Mod: <strong>{g.installed}</strong></span><span class="sub green">(Keep currently installed mod active on phone, skip installing new mod)</span></div>
            </label>
          {/if}
          {#if !g.queue}
            <label class="option" class:selected={choice(g) === SKIP_ALL}>
              <input type="radio" name={g.key} checked={choice(g) === SKIP_ALL} onchange={() => (picked[g.key] = SKIP_ALL)} />
              <span class="oname dim"><Icon name="ban" size={14} /> Disable / Skip all competing mods for this asset</span>
            </label>
          {/if}
        </div>
      </div>
    {/each}
  </div>
  <PortraitColumn sections={[{ title: queueMode ? 'Mods in the Queue:' : 'New Mods:', tone: 'blue', tiles: newTiles }]} {portraitOf} onOpen={(src) => (enlarged = src)} />
  </div>
  {#if enlarged}<Lightbox src={enlarged} onClose={() => (enlarged = null)} />{/if}
  {#snippet footer()}
    <button class="btn" onclick={onCancel}>Cancel</button>
    <button class="btn primary" onclick={() => onConfirm(Object.fromEntries(groups.map((g) => [g.key, choice(g)])))}>Proceed with Selected</button>
  {/snippet}
</Modal>

<style>
  .warn { font-size: var(--fs-2xl); }
  .frame { flex: 1; min-height: 0; display: flex; gap: 1rem; align-items: stretch; }
  .body { flex: 1; min-width: 0; min-height: 0; overflow-y: auto; display: flex; flex-direction: column; gap: 1rem; padding: 0.85rem; background: var(--surface-panel); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); }
  .intro { font-size: var(--fs-md); line-height: 1.5; color: var(--text-muted); }
  .group { display: flex; flex-direction: column; gap: 0.65rem; padding: 0.85rem 1rem; background: transparent; border: 1px solid var(--border-subtle); border-radius: var(--radius-md); }
  .group-title { display: flex; align-items: center; justify-content: space-between; font-size: var(--fs-md); font-weight: 700; color: var(--warn-text); }
  .notice { margin: 0.2rem 0 0.5rem; font-size: var(--fs-md); line-height: 1.45; color: var(--text-muted); }
  .notice strong { color: var(--ok-text); }
  .options { display: flex; flex-direction: column; gap: 0.45rem; }
  .option { display: flex; align-items: center; gap: 0.65rem; padding: 0.5rem 0.75rem; cursor: pointer; background: var(--tint-1); border: 1px solid transparent; border-radius: var(--radius-sm); transition: background 0.12s; }
  .option:hover { background: var(--tint-2); }
  .option.selected { background: var(--selected-bg); border-color: var(--primary); }
  .text { display: flex; flex-direction: column; gap: 2px; flex: 1; }
  .line { display: flex; align-items: center; gap: 6px; }
  .oname { flex: 1; font-size: var(--fs-md); font-weight: 600; color: var(--text-main); }
  .oname.dim { font-style: italic; color: var(--text-dim); }
  .sub { font-size: var(--fs-sm); color: var(--text-dim); } .sub.blue { color: var(--text-dim); } .sub.green { color: var(--ok-text); }
  .tag { padding: 2px 6px; font-size: var(--fs-sm); font-weight: 600; border-radius: 4px; border: 1px solid transparent; }
  .tag.amber { color: var(--warn-text); background: color-mix(in srgb, var(--warn) 20%, transparent); border-color: color-mix(in srgb, var(--warn) 35%, transparent); }
  .tag.subtle { font-family: var(--font-mono); color: var(--text-muted); background: transparent; border-color: var(--border-subtle); }
  .tag.src { color: var(--text-muted); background: rgba(148, 163, 184, 0.2); } .tag.multi { color: var(--cat-multi); background: color-mix(in srgb, var(--cat-multi) 20%, transparent); }
  .tag.cache { color: var(--text-muted); background: var(--tint-2); } .tag.ok { color: var(--ok-text); background: color-mix(in srgb, var(--ok) 15%, transparent); border-color: color-mix(in srgb, var(--ok) 30%, transparent); }
  .tag.plain { color: var(--text-dim); font-weight: 500; }
  .btn { padding: 0.4rem 0.85rem; font-size: var(--fs-md); font-weight: 600; color: var(--text-main); background: var(--tint-2); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); }
  .btn:hover { background: var(--tint-3); }
  .btn.primary { color: var(--on-primary); border: none; background: var(--primary-solid); box-shadow: none; }
</style>
