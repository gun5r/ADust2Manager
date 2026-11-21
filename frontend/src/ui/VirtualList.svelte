<script lang="ts" generics="T">
  import type { Snippet } from 'svelte'

  /**
   * Windowed list of variable-height items. Heights start as estimates and are replaced by measured values once an
   * item has been rendered, so scrolling stays smooth for thousands of rows without knowing every height up front.
   */
  let { items, key, estimate, gap = 0, overscan = 600, endPadding = 0, children, class: className = '' }: {
    items: T[]
    key: (item: T) => string
    estimate: (item: T) => number
    gap?: number
    overscan?: number
    /** Extra empty space after the last item (room for floating controls). */
    endPadding?: number
    children: Snippet<[T, number]>
    class?: string
  } = $props()

  let viewport: HTMLDivElement | undefined = $state()
  let scrollTop = $state(0)
  let viewportHeight = $state(800)
  let measured = $state<Record<string, number>>({})

  const heights = $derived(items.map((item) => measured[key(item)] ?? estimate(item)))
  const offsets = $derived.by(() => {
    const result: number[] = []
    let y = 0
    for (const h of heights) {
      result.push(y)
      y += h + gap
    }
    return result
  })
  const total = $derived(items.length ? offsets[items.length - 1] + heights[items.length - 1] : 0)

  const range = $derived.by(() => {
    const from = scrollTop - overscan
    const to = scrollTop + viewportHeight + overscan
    let start = 0
    while (start < items.length - 1 && offsets[start] + heights[start] < from) start++
    let end = start
    while (end < items.length && offsets[end] < to) end++
    return { start, end }
  })
  const visible = $derived(items.slice(range.start, range.end))
  const bottomSpace = $derived(range.end >= items.length ? 0 : total - (offsets[range.end - 1] + heights[range.end - 1]))

  // Remember real heights of rendered items (batched into one update per frame).
  let pending: Record<string, number> = {}
  let frame = 0
  const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver((entries) => {
    for (const entry of entries) {
      const id = (entry.target as HTMLElement).dataset.key
      if (id) pending[id] = entry.target.getBoundingClientRect().height
    }
    cancelAnimationFrame(frame)
    frame = requestAnimationFrame(() => {
      const changed = Object.entries(pending).filter(([id, h]) => Math.abs((measured[id] ?? -1) - h) > 0.5)
      if (changed.length) measured = { ...measured, ...Object.fromEntries(changed) }
      pending = {}
    })
  })
  function track(node: HTMLElement) {
    observer?.observe(node)
    return { destroy: () => observer?.unobserve(node) }
  }

  /** Bring an item to the top of the viewport (used when jumping to a character). */
  export function scrollToKey(id: string) {
    const index = items.findIndex((item) => key(item) === id)
    if (index >= 0 && viewport) viewport.scrollTo({ top: offsets[index], behavior: 'smooth' })
  }
  export function scrollToTop() {
    viewport?.scrollTo({ top: 0 })
  }
</script>

<div class="viewport {className}" bind:this={viewport} bind:clientHeight={viewportHeight} onscroll={(e) => (scrollTop = e.currentTarget.scrollTop)}>
  <div class="spacer" style:height="{range.start ? offsets[range.start] : 0}px"></div>
  <div class="items" style:gap="{gap}px">
    {#each visible as item, i (key(item))}
      <div class="item" data-key={key(item)} use:track>{@render children(item, range.start + i)}</div>
    {/each}
  </div>
  <div class="spacer" style:height="{Math.max(0, bottomSpace) + endPadding}px"></div>
</div>

<style>
  .viewport { overflow-y: auto; height: 100%; min-height: 0; }
  .items { display: flex; flex-direction: column; }
</style>
