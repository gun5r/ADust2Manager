<script lang="ts">
  let { state }: { state: 'connected' | 'disconnected' | 'unauthorized' } = $props()
</script>

<span class="dot {state}"></span>

<style>
  .dot { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }
  .connected { background: var(--accent); }
  .disconnected { background: var(--text-dim); }
  .unauthorized { background: var(--warning); }
</style>
