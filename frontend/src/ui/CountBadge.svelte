<script lang="ts">
  let { count, tone = 'info' }: { count: number | string; tone?: 'info' | 'danger' } = $props()
</script>

<span class="badge {tone}">{count}</span>

<style>
  .badge { font-size: var(--fs-xs); font-weight: 700; padding: 0.1rem 0.45rem; border-radius: 999px; line-height: 1.2; }
  .info { background: var(--primary-solid); color: var(--on-primary); }
  .danger { background: var(--danger); color: var(--text-main); }
</style>
