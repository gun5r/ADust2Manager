<script lang="ts">
  import Button from '../../ui/Button.svelte'
  import Icon from '../../ui/Icon.svelte'
  import IconButton from '../../ui/IconButton.svelte'
  import CountBadge from '../../ui/CountBadge.svelte'
  import StatusDot from '../../ui/StatusDot.svelte'
  import type { AdbState } from '../../lib/header'
  import { api } from '../../lib/api'

  /** Stops the manager (it runs without a window of its own) and says so on the page. */
  async function quit() {
    if (!confirm('Quit the manager? Anything still preparing or transferring is stopped.')) return
    await api.quit().catch(() => {})
    document.body.innerHTML = '<p style="font:16px system-ui;padding:2rem;color:#ccc">ADust2Manager has stopped. You can close this tab.</p>'
  }

  let { adb, cache, queueCount, queueText, queueFailed, onQueue, onRefreshAdb, onSettings, mascotCount = 0, onMascots, onTools }: {
    adb: { state: AdbState; label: string }
    cache: string
    queueCount: number
    /** Badge text when it is not just the count (classic shows "2 ready / 1 fail"). */
    queueText?: string
    queueFailed: boolean
    onQueue?: () => void
    onRefreshAdb: () => void
    onSettings?: () => void
    mascotCount?: number
    onMascots?: () => void
    onTools?: () => void
  } = $props()
</script>

<header>
  <div class="brand">
    <div class="icon">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polygon points="12 2 2 7 12 12 22 7 12 2"></polygon>
        <polyline points="2 17 12 22 22 17"></polyline>
        <polyline points="2 12 12 17 22 12"></polyline>
      </svg>
    </div>
    <div class="text">
      <h1>ADust2Manager</h1>
    </div>
  </div>

  <div class="actions">
    <Button variant="ghost" size="header" aria-label="Manage Desktop Mascots (DMascot)" title="Manage Desktop Mascots (DMascot)" onclick={onMascots}>
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect><line x1="8" y1="21" x2="16" y2="21"></line><line x1="12" y1="17" x2="12" y2="21"></line></svg>
      <span class="qlabel">DMascot</span>
      {#if mascotCount > 0}<CountBadge count={mascotCount} tone="info" />{/if}
    </Button>
    <Button variant="ghost" size="header" aria-label="Settings and tools" title="Settings and tools: preferences, game data, characters, portraits and more" onclick={onTools}>
      <Icon name="settings" size={15} />
      <span class="qlabel">Settings</span>
    </Button>
    <Button variant="ghost" size="header" aria-label="Queue" title={onQueue ? 'View background processing queue and active transfers' : 'Queue window arrives in phase 3'} onclick={onQueue}>
      <Icon name="list-checks" size={15} />
      <span class="qlabel">Queue</span>
      {#if queueCount > 0}<CountBadge count={queueText ?? queueCount} tone={queueFailed ? 'danger' : 'info'} />{/if}
    </Button>

    <span class="sep"></span>
    <div class="adb">
      <div class="status" title={adb.label} aria-label={adb.label}><StatusDot state={adb.state} /><span class="slabel">{adb.label}</span></div>
      <IconButton title="Refresh ADB devices" aria-label="Refresh ADB devices" onclick={onRefreshAdb}>
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="23 4 23 10 17 10"></polyline>
          <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
        </svg>
      </IconButton>
    </div>

    <button class="cache" aria-label="Preferences, quality and cache settings" title="Preferences, quality and cache settings" onclick={onSettings}>
      <Icon name="wrench" size={15} />
      <span class="label clabel">Cache:</span>
      <strong>{cache}</strong>
    </button>
    <IconButton title="Quit the manager" aria-label="Quit the manager" onclick={quit}><Icon name="power" size={15} /></IconButton>
  </div>
</header>

<style>
  header { position: sticky; top: 0; z-index: 50; display: flex; justify-content: space-between; align-items: center;
    height: 48px; padding: 0 1rem; gap: 1rem; background: var(--surface-header); border-bottom: 1px solid var(--border-subtle); }
  .brand { display: flex; align-items: center; gap: 0.6rem; flex-shrink: 0; }
  .icon { display: flex; align-items: center; color: var(--text-main); }
  h1 { font-size: var(--fs-md); font-weight: 700; letter-spacing: 0; color: var(--text-main); }
  .actions { display: flex; align-items: center; gap: 0.25rem; }
  .sep { width: 1px; height: 18px; margin: 0 0.6rem; background: var(--border-subtle); }
  .adb { display: flex; align-items: center; gap: 0.15rem; }
  .status { display: flex; align-items: center; gap: 0.45rem; font-size: var(--fs-sm); font-weight: 500; color: var(--text-muted); padding: 0 0.3rem; }
  .cache { display: flex; align-items: center; gap: 0.4rem; padding: 0.35rem 0.6rem; border-radius: var(--radius-sm); font-size: var(--fs-sm); color: var(--text-dim); }
  .cache:hover { background: var(--tint-2); color: var(--text-muted); }
  .cache strong { color: var(--text-muted); font-weight: 600; }
  @media (max-width: 1100px) {
    .qlabel, .slabel, .clabel, .cache strong { display: none; }
    .actions :global(.btn.header) { width: 32px; padding: 0; }
    .cache { width: 32px; height: 32px; justify-content: center; padding: 0; }
    .sep { margin: 0 0.25rem; }
  }
  @media (max-width: 950px) {
    .text, .qlabel, .slabel, .clabel { display: none; }
    header { padding: 0 0.5rem; }
  }
</style>
