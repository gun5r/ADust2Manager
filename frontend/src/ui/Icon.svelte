<script lang="ts">
  import { ICONS } from './icons'
  /** A Lucide icon (see scripts/make-icons.mjs); it takes the text colour unless `color` is given. */
  let { name, size = 16, color, stroke = 2 }: { name: string; size?: number; color?: string; stroke?: number } = $props()
</script>

<svg class="icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color ?? 'currentColor'} stroke-width={stroke} stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{@html ICONS[name] ?? ''}</svg>

<style>
  .icon { flex: none; vertical-align: -0.15em; }
</style>
