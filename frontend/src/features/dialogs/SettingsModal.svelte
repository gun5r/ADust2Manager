<script lang="ts">
  import { api, type CacheStats } from '../../lib/api'
  import type { AppState } from '../../state/app.svelte'
  import Modal from '../../ui/Modal.svelte'

  let { app, onClose }: { app: AppState; onClose: () => void } = $props()

  let stats = $state<CacheStats | null>(null)
  async function refresh() {
    try {
      stats = await api.cacheInfo()
      app.cacheBytes = stats.total_bytes
    } catch {
      /* keeps the last numbers */
    }
  }
  $effect(() => void refresh())

  async function clear() {
    if (!confirm('Are you sure you want to clean the download cache?\n\nThis will remove cached original game bundles and repacked outputs. When mods are installed in the future, original bundles will be downloaded again as needed.')) return
    app.log('Cleaning download cache & repacked outputs...')
    try {
      const { result } = await api.clearCache({ clear_originals: true, clear_repacked: true, clear_catalogs: false, clear_thumbs: false, clear_audio: false })
      app.log(`Cache cleaned successfully: Freed ${result.freed_formatted} (${result.deleted_count} items removed).`, 'success')
      alert(`Cache cleaned!\nFreed: ${result.freed_formatted}`)
      await refresh()
    } catch (e) {
      app.log(`Error cleaning cache: ${e}`, 'error')
      alert(`Failed to clean cache: ${e}`)
    }
  }

  async function clearAudio() {
    if (!confirm('Delete the downloaded dating-scene audio?\n\nThe touch simulator plays no sound until you download it again (one button per scene).')) return
    try {
      const { result } = await api.clearCache({ clear_originals: false, clear_repacked: false, clear_catalogs: false, clear_thumbs: false, clear_audio: true })
      app.log(`Dating audio deleted: freed ${result.freed_formatted}.`, 'success')
      await refresh()
    } catch (e) {
      app.log(`Error deleting the dating audio: ${e}`, 'error')
    }
  }

</script>

<Modal label="Cache & Quality" width="860px" onClose={onClose}>
  {#snippet icon()}
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" class="gear"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
  {/snippet}
  {#snippet title()}Cache &amp; Quality{/snippet}

  <div class="cards" data-ui="settings">
    <div class="card">
      <div class="options">
        <div class="quality">
          <div class="desc"><strong>Current Quality Target for Repacking:</strong></div>
          <select value={app.config?.quality ?? 'HD'} onchange={(e) => app.saveQuality(e.currentTarget.value)}>
            <option value="FHD">FHD (Ultra)</option>
            <option value="HD">HD (Default)</option>
            <option value="SD">SD (Standard)</option>
          </select>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-head">
        <h3>Download Cache &amp; Storage</h3>
        <button class="btn" onclick={refresh}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"></polyline><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path></svg>
          <span>Refresh Size</span>
        </button>
      </div>
      <div class="grid">
        <div class="stat"><span class="label">Original Game Bundles</span><strong>{stats?.originals.formatted ?? 'Loading...'}</strong><span class="sub">{stats?.originals.files ?? 0} bundle files</span></div>
        <div class="stat"><span class="label">Repacked Output Cache</span><strong>{stats?.repacked.formatted ?? 'Loading...'}</strong><span class="sub">{stats?.repacked.files ?? 0} files</span></div>
        <div class="stat"><span class="label">Catalog &amp; Index Data</span><strong>{stats?.catalogs.formatted ?? 'Loading...'}</strong><span class="sub">{stats?.catalogs.files ?? 0} files</span></div>
        <div class="stat"><span class="label">Dating Audio</span><strong>{stats?.audio?.formatted ?? 'Loading...'}</strong><span class="sub">{stats?.audio?.files ?? 0} files</span></div>
        <div class="stat highlight"><span class="label">Total Cache Usage</span><strong>{stats?.total_formatted ?? '0 MB'}</strong><span class="sub">Across all mod sessions</span></div>
      </div>
      <div class="action-row">
        <button class="btn danger" onclick={clear}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
          <span>Clean / Clear Cache</span>
        </button>
        <span class="muted">Removes cached original &amp; repacked bundles (dating audio is kept).</span>
      </div>
      <div class="action-row">
        <button class="btn danger" onclick={clearAudio} disabled={!stats?.audio?.files}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><line x1="23" y1="9" x2="17" y2="15"></line><line x1="17" y1="9" x2="23" y2="15"></line></svg>
          <span>Delete Dating Audio</span>
        </button>
        <span class="muted">Removes the sounds downloaded for the dating simulator.</span>
      </div>
    </div>
  </div>
  {#snippet footer()}<button class="btn primary" onclick={onClose}>Save &amp; Close</button>{/snippet}
</Modal>

<style>
  .cards { display: flex; flex-direction: column; gap: 0.5rem; }


  .card { padding: 0.45rem 0.85rem; background: color-mix(in srgb, var(--surface-2) 50%, transparent); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); }
  .options { display: flex; flex-direction: column; gap: 0.15rem; }
  .quality { display: flex; align-items: center; justify-content: space-between; padding: 0.3rem 0.5rem; }
  .quality select { padding: 0.35rem 0.85rem; font-size: var(--fs-md); font-weight: 700; color: var(--primary); height: 30.2px; box-sizing: border-box; background: var(--tint-2); border: 1px solid var(--border-subtle); border-radius: 6px; outline: none; cursor: pointer; }
  .desc { display: flex; flex-direction: column; gap: 0.08rem; }
  .desc strong { font-size: var(--fs-md); color: var(--text-main); }
  .card-head { display: flex; align-items: center; justify-content: space-between; gap: 0.75rem; margin-bottom: 0.4rem; }
  h3 { font-size: var(--fs-lg); font-weight: 700; color: var(--text-main); }
  .grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 0.4rem; margin: 0.35rem 0; }
  .stat { display: flex; flex-direction: column; gap: 0.12rem; padding: 0.45rem 0.55rem; background: color-mix(in srgb, var(--surface-2) 60%, transparent); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); }
  .stat.highlight { background: var(--selected-bg); border-color: rgba(var(--primary-rgb), 0.3); }
  .label { font-size: var(--fs-xs); font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase; color: var(--text-muted); }
  .stat strong { font-family: var(--font-mono); font-size: var(--fs-lg); color: var(--text-main); }

  .sub { font-size: var(--fs-xs); color: var(--text-muted); }
  .action-row { display: flex; align-items: center; gap: 0.75rem; margin-top: 0.25rem; padding-top: 0.25rem; border-top: 1px solid var(--border-subtle); }
  .muted { font-size: var(--fs-sm); color: var(--text-muted); }
  .btn { display: inline-flex; align-items: center; gap: 0.5rem; padding: 0.4rem 0.85rem; font-size: var(--fs-md); font-weight: 600; line-height: normal; color: var(--text-main); background: var(--tint-2); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); }
  .btn:hover { background: var(--tint-3); }
  .btn.danger { background: transparent; border: 0; } /* classic: .btn-danger has no rule, only the base button shows */
  .btn.primary { padding: 0.75rem 1.4rem; font-size: var(--fs-md); color: var(--on-primary); border: none; border-radius: var(--radius-md); background: var(--primary-solid); box-shadow: none; }
</style>
