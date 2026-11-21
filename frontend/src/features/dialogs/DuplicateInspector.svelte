<script lang="ts">
  import Icon from '../../ui/Icon.svelte'
  import { api, type DuplicateSide, type ExactDuplicate, type NameCollision } from '../../lib/api'
  import { keepPlans, tabOf } from '../../lib/duplicates'
  import type { AppState } from '../../state/app.svelte'
  import Modal from '../../ui/Modal.svelte'

  let { app, onClose }: { app: AppState; onClose: () => void } = $props()
  // svelte-ignore state_referenced_locally
  const found = app.inspector!
  let duplicates = $state<ExactDuplicate[]>(found.duplicates)
  let collisions = $state<NameCollision[]>(found.collisions)
  const tabs = found.tabs
  let names = $state<Record<string, string>>(Object.fromEntries(found.collisions.map((c) => [c.mod2.folder_path, c.suggested_name])))
  let resolved = $state<Record<string, string>>({}) // key -> message, shown in place of a resolved card
  let busy = $state('')

  const plans = $derived(keepPlans(duplicates, tabs))
  const tabBadge = (side: DuplicateSide) => tabOf(side.folder_path, tabs)?.name
  const key = (d: ExactDuplicate) => `${d.mod1.folder_path}|${d.mod2.folder_path}`

  async function remove(paths: string[], doneText: string, pairs: ExactDuplicate[]) {
    const result = await api.deleteFolders(paths)
    for (const pair of pairs) resolved[key(pair)] = doneText
    app.log(`${doneText} (${result.deleted.length} folder(s) deleted).`, 'success')
    await app.refreshLibrary()
  }

  async function deleteOne(side: DuplicateSide, pair: ExactDuplicate) {
    if (!confirm(`Are you sure you want to permanently delete this duplicate folder from disk?\n\n${side.folder_path}`)) return
    try {
      await remove([side.folder_path], 'Duplicate folder deleted successfully.', [pair])
    } catch (e) {
      alert(`Could not delete folder: ${e}`)
    }
  }

  async function saveAll(plan: (typeof plans)[number]) {
    const unique = [...new Set(plan.deletePaths)]
    const sample = unique.slice(0, 5).map((p) => `• ${p}`).join('\n')
    const more = unique.length > 5 ? `\n...and ${unique.length - 5} more folder(s)` : ''
    if (!confirm(`Save all "${plan.tab.name}" mods?\n\nThis will KEEP all original mods inside:\n${plan.tab.path}\n\nAnd PERMANENTLY DELETE ${unique.length} duplicate copy/copies located in other folders:\n${sample}${more}\n\nProceed with permanent deletion?`)) return
    busy = plan.tab.id
    try {
      const gone = new Set(unique)
      const pairs = duplicates.filter((d) => gone.has(d.mod1.folder_path) || gone.has(d.mod2.folder_path))
      await remove(unique, `Duplicate resolved: preserved in "${plan.tab.name}" and deleted from other folder.`, pairs)
    } catch (e) {
      alert(`Error deleting duplicate copies: ${e}`)
    } finally {
      busy = ''
    }
  }

  async function rename(c: NameCollision, refresh = true) {
    const next = (names[c.mod2.folder_path] ?? '').trim()
    if (!next) return
    try {
      await api.renameFolder(c.mod2.folder_path, next)
      resolved[c.mod2.folder_path] = `Renamed to "${next}".`
      app.log(`Renamed collision folder to "${next}".`, 'success')
      if (refresh) await app.refreshLibrary()
    } catch (e) {
      alert(`Could not rename folder: ${e}`)
    }
  }

  async function renameAll() {
    busy = 'rename-all'
    for (const c of collisions) if (!resolved[c.mod2.folder_path]) await rename(c, false)
    await app.refreshLibrary()
    busy = ''
  }
</script>

<Modal label="Duplicate & Collision Inspector" width="760px" onClose={onClose}>
  {#snippet icon()}<span class="icon"><Icon name="search" size={18} /></span>{/snippet}
  {#snippet title()}Duplicate &amp; Collision Inspector{/snippet}
  <div class="body" data-ui="inspector">
    <div class="banner"><Icon name="triangle-alert" size={14} color="var(--warn-text)" /> Detected <strong>{found.duplicates.length}</strong> exact duplicate(s) and <strong>{found.collisions.length}</strong> name collision(s) across folders.</div>
    <div class="sections">
      {#if found.duplicates.length}
        <div>
          <div class="section-head">
            <div class="section-title"><span class="red">●</span> Exact Duplicates ({found.duplicates.length})</div>
            <div class="save-buttons">
              {#each plans.filter((p) => p.deletePaths.length >= 2) as plan, i (plan.tab.id)}
                <button class="save" class:first={i === 0} disabled={busy === plan.tab.id} title="Keep all original mods inside '{plan.tab.name}' ({plan.tab.path}) and delete {plan.deletePaths.length} duplicate copy/copies from other folders" onclick={() => saveAll(plan)}>
                  <span><Icon name="shield" size={14} color="var(--ok-text)" /></span><span>{busy === plan.tab.id ? `Saving ${plan.tab.name} mods...` : `Save all ${plan.tab.name} mods (${plan.deletePaths.length})`}</span>
                </button>
              {/each}
            </div>
          </div>
          <p class="help">These mods have identical files. Choose which copy to delete or use the button above to save all mods in your main folder:</p>
          <div class="cards">
            {#each found.duplicates as d (key(d))}
              <div class="card duplicate">
                {#if resolved[key(d)]}
                  <div class="done"><Icon name="check" size={12} /> {resolved[key(d)]}</div>
                {:else}
                  <div class="card-head">
                    <span class="card-title"><Icon name="folder" size={14} color="var(--warn-text)" /> {d.name}</span>
                    <div class="head-tags">
                      {#if d.different_names}<span class="tag purple">Different Folder Names</span>{/if}
                      <span class="hash">{d.mod1.file_count} Identical Files (Hash Verified)</span>
                    </div>
                  </div>
                  <div class="locs">
                    {#each [d.mod1, d.mod2] as side, i}
                      <div class="loc">
                        <div class="loc-info">
                          <span class="loc-tag">Location {i + 1}: {side.name}{#if tabBadge(side)}<span class="tag blue">{tabBadge(side)}</span>{/if}</span>
                          <span class="loc-path" title={side.folder_path}>{side.folder_path}</span>
                        </div>
                        <button class="delete" onclick={() => deleteOne(side, d)}>Delete This</button>
                      </div>
                    {/each}
                  </div>
                {/if}
              </div>
            {/each}
          </div>
        </div>
      {/if}

      {#if found.collisions.length}
        <div>
          <div class="section-head top">
            <div class="section-title"><span class="amber">●</span> Name Collisions ({found.collisions.length})</div>
            <button class="warn" disabled={busy === 'rename-all'} onclick={renameAll}>{busy === 'rename-all' ? 'Renaming All...' : `Rename All (${found.collisions.length})`}</button>
          </div>
          <p class="help">These folders have the same name but different mod contents. Rename them to resolve collision:</p>
          <div class="cards">
            {#each found.collisions as c (c.mod2.folder_path)}
              <div class="card collision">
                {#if resolved[c.mod2.folder_path]}
                  <div class="done"><Icon name="check" size={12} /> {resolved[c.mod2.folder_path]}</div>
                {:else}
                  <div class="card-head"><span class="card-title"><Icon name="triangle-alert" size={14} color="var(--warn-text)" /> {c.name}</span><span class="diff">Different Mod Contents</span></div>
                  <div class="locs">
                    {#each [c.mod1, c.mod2] as side, i}
                      <div class="loc"><div class="loc-info"><span class="loc-tag">Location {i + 1} ({side.file_count} files)</span><span class="loc-path" title={side.folder_path}>{side.folder_path}</span></div></div>
                    {/each}
                  </div>
                  <div class="rename">
                    <span class="rename-label">Rename Location 2:</span>
                    <input type="text" bind:value={names[c.mod2.folder_path]} />
                    <button class="warn small" onclick={() => rename(c)}>Rename</button>
                  </div>
                {/if}
              </div>
            {/each}
          </div>
        </div>
      {/if}
    </div>
  </div>
  {#snippet footer()}<button class="btn" onclick={onClose}>Close</button>{/snippet}
</Modal>

<style>
  .icon { font-size: var(--fs-2xl); }
  .body { display: flex; flex-direction: column; gap: 1.2rem; }
  .banner { display: flex; align-items: center; gap: 0.5rem; padding: 0.75rem 1rem; font-size: var(--fs-md); font-weight: 600; color: var(--warn-text); background: transparent; border: 1px solid color-mix(in srgb, var(--warn) 35%, transparent); border-radius: var(--radius-md); }
  .sections { display: flex; flex-direction: column; gap: 1.2rem; }
  .section-head { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 0.4rem; }
  .section-head.top { margin-top: 0.5rem; }
  .section-title { display: flex; align-items: center; gap: 0.5rem; font-size: var(--fs-md); font-weight: 700; color: var(--text-main); }
  .red { color: var(--danger); } .amber { color: var(--warn); }
  .save-buttons { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
  .save { display: inline-flex; align-items: center; gap: 5px; padding: 4px 10px; font-size: var(--fs-sm); font-weight: 600; color: var(--text-main); background: transparent; border: 1px solid var(--tint-4); border-radius: 6px; }
  .save.first { color: var(--on-primary); font-weight: 700; border: none; background: var(--primary-solid); }
  .help { margin-bottom: 0.6rem; font-size: var(--fs-md); color: var(--text-muted); }
  .cards { display: flex; flex-direction: column; gap: 0.75rem; }
  .card { display: flex; flex-direction: column; gap: 0.65rem; padding: 0.85rem 1rem; background: var(--tint-1); border-radius: var(--radius-md); }
  .card.duplicate, .card.collision { border: 1px solid var(--border-subtle); }
  .card-head { display: flex; align-items: center; justify-content: space-between; }
  .card-title { display: flex; align-items: center; gap: 0.45rem; font-size: var(--fs-md); font-weight: 700; color: var(--text-main); }
  .head-tags { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
  .hash { font-size: var(--fs-sm); color: var(--danger-text); } .diff { font-size: var(--fs-sm); color: var(--warn-text); }
  .tag { padding: 1px 6px; font-size: var(--fs-xs); border-radius: 4px; border: 1px solid; }
  .tag.purple { color: var(--text-muted); background: transparent; border-color: var(--border-subtle); }
  .tag.blue { margin-left: 4px; color: var(--text-dim); background: transparent; border-color: var(--border-subtle); }
  .locs { display: flex; flex-direction: column; gap: 0.5rem; }
  .loc { display: flex; align-items: center; justify-content: space-between; gap: 0.75rem; padding: 0.5rem 0.75rem; background: var(--tint-1); border: 0; border-radius: var(--radius-sm); }
  .loc-info { display: flex; flex-direction: column; gap: 0.15rem; overflow: hidden; }
  .loc-tag { font-size: var(--fs-sm); font-weight: 600; color: var(--text-main); }
  .loc-path { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-family: var(--font-mono); font-size: var(--fs-sm); color: var(--text-dim); }
  .delete { padding: 0.3rem 0.65rem; font-size: var(--fs-sm); font-weight: 600; color: var(--text-main); background: transparent; border: 0; border-radius: var(--radius-sm); white-space: nowrap; }
  .delete:hover { color: var(--danger-text); background: color-mix(in srgb, var(--danger) 15%, transparent); }
  .done { padding: 0.5rem; font-size: var(--fs-md); color: var(--ok-text); opacity: 0.8; }
  .rename { display: flex; align-items: center; gap: 0.5rem; margin-top: 0.4rem; padding: 0.5rem 0.75rem; background: rgba(0, 0, 0, 0.3); border: 1px dashed color-mix(in srgb, var(--warn) 30%, transparent); border-radius: var(--radius-sm); }
  .rename-label { font-size: var(--fs-sm); color: var(--warn-text); white-space: nowrap; }
  .rename input { flex: 1; padding: 0.4rem 0.65rem; font-size: var(--fs-md); color: var(--text-main); background: color-mix(in srgb, var(--surface-2) 85%, transparent); border: 1px solid var(--border-subtle); border-radius: 4px; }
  .warn { padding: 0.3rem 0.65rem; font-size: var(--fs-sm); font-weight: 600; color: var(--warn-text); background: color-mix(in srgb, var(--warn) 12%, transparent); border: 1px solid color-mix(in srgb, var(--warn) 40%, transparent); border-radius: var(--radius-sm); }
  .warn.small { padding: 0.3rem 0.65rem; }
  .btn { padding: 0.4rem 0.85rem; font-size: var(--fs-md); font-weight: 600; color: var(--text-main); background: var(--tint-2); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); }
  .btn:hover { background: var(--tint-3); }
</style>
