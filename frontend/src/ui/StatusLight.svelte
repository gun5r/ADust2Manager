<script lang="ts">
  import { LIGHT_COLOR, type ActivityStatus } from '../lib/activity'

  /** The program's status as a coloured light: blue standby, green running, orange errors but still running, red stopped by an error. */
  let { status, compact = false, label = true }: { status: ActivityStatus; compact?: boolean; label?: boolean } = $props()
</script>

<span class="light" class:compact title={status.text} role="status" aria-label={`${status.label}: ${status.text}`}>
  <span class="dot" class:pulse={status.state === 'running' || status.state === 'warning'} style:--c={LIGHT_COLOR[status.state]}></span>
  {#if label}<span class="label" style:color={LIGHT_COLOR[status.state]}>{status.label}</span>{/if}
</span>

<style>
  .light { display: inline-flex; align-items: center; gap: 0.5rem; font-size: var(--fs-sm); font-weight: 700; white-space: nowrap; }
  .compact { font-size: var(--fs-xs); gap: 0.4rem; }
  .dot { width: 11px; height: 11px; border-radius: 50%; background: var(--c); box-shadow: 0 0 9px var(--c); flex-shrink: 0; }
  .compact .dot { width: 9px; height: 9px; }
  .pulse { animation: light-pulse 1.6s ease-in-out infinite; }
  @keyframes light-pulse { 50% { opacity: 0.45; } }
  @media (prefers-reduced-motion: reduce) { .pulse { animation: none; } }
</style>
