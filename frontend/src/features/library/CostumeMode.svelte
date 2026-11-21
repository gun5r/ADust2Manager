<script lang="ts">
  import Badge from '../../ui/Badge.svelte'
  import { modBadges } from '../../lib/badges'
  import Icon from '../../ui/Icon.svelte'
  import { tick, untrack } from 'svelte'
  import type { IndexMod } from '../../lib/classify'
  import { neverHasPortrait, type CharacterGroup } from '../../lib/grouping'
  import { columnStops, columnsFor, COSTUME_MAX, COSTUME_MIN, stopIndex } from '../../lib/columns'
  import { clusterPieces, pieceRows } from '../../lib/costumeLayout'
  import { costumeEntries, costumePortraitUrl, modSections, type CostumeEntry } from '../../lib/portraits'
  import { modKey } from '../../lib/selection'
  import type { PortraitState } from '../../state/portraits.svelte'

  let { groups, installed, queued, wrap, lit, portraits, size, onSize, modSize, onModSize, clustered, onCluster, overlay, onOverlay, showOptions, onHideOptions, resetKey, selected, onToggle, onMark, onPreview, onPrepare }: {
    groups: CharacterGroup[]
    installed: Set<string>
    /** The character clicked in the roster: all of its costumes are framed with a breathing blue glow. */
    lit: string | null
    /** Pour the clusters into full rows even when that splits a character (Settings). */
    wrap: boolean
    /** Folders of the mods in the processing queue. */
    queued: Set<string>
    portraits: PortraitState
    size: number
    onSize: (px: number) => void
    /** Size the mod portraits aim for; the box fits whole columns of them to its width, so they never leave a gap on the right. */
    modSize: number
    onModSize: (px: number) => void
    /** One flowing field of costumes, each character's costumes bracketed together, instead of a section per character. */
    clustered: boolean
    onCluster: () => void
    /** The mod box covers the whole list (and a click elsewhere closes it) instead of opening below the costume. */
    overlay: boolean
    onOverlay: () => void
    /** The options row (Mod view, the two sliders, Hide Options) is shown; off in Settings > Display. */
    showOptions: boolean
    onHideOptions: () => void
    /** Changes whenever the tab or a filter changes: the open mod box closes. */
    resetKey: string
    /** Mods picked for batch install (keys from `modKey`); a click on a mod tile toggles it. */
    selected: Set<string>
    onToggle: (m: IndexMod) => void
    onMark: (m: IndexMod) => void
    onPreview: (m: IndexMod) => void
    onPrepare: (m: IndexMod) => void
  } = $props()

  /** The costume in the spotlight (`character|costume key`). */
  let focus = $state<string | null>(null)
  let scroller: HTMLElement | undefined = $state()
  let scrollWidth = $state(0)
  let rawWidth = $state(0)
  let bodyWidth = $state(0)
  let saved = 0
  let notice = $state(false)
  function hideOptions() {
    onHideOptions()
    notice = true
    setTimeout(() => (notice = false), 9000)
  }

  const CARD_GAP = 10
  /** Costumes per row that fit the field at the chosen size; a cluster takes up to this many columns and is never split across sections. */
  // the list is hidden (width 0) while a mod box covers it: keep the last real width so its layout does not collapse meanwhile
  $effect(() => { if (rawWidth > 0) scrollWidth = rawWidth })
  const fieldWidth = $derived(Math.max(0, scrollWidth - 26)) // the scroll area's side padding (room for the frame around a lit character)
  const capacity = $derived(columnsFor(fieldWidth, CARD_GAP, size))
  // the sliders only stop where the layout changes (one stop per column count); the stored size follows the stop
  const costumeStops = $derived(columnStops(fieldWidth || 1000, CARD_GAP, COSTUME_MIN, COSTUME_MAX))
  const modWidth = $derived(Math.max(0, bodyWidth - 26)) // the box's padding
  const modCols = $derived(columnsFor(modWidth, CARD_GAP, modSize))
  const modStops = $derived(columnStops(modWidth || 800, CARD_GAP, 90, 460))
  const columnsOf = (n: number) => Math.min(n, capacity)
  const idOf = (character: string, key: string) => `${character}|${key}`
  const withCostumes = $derived(groups.map((g) => ({ group: g, costumes: costumeEntries(g.sections) })).filter((g) => g.costumes.length))
  const focused = $derived(withCostumes.flatMap((g) => g.costumes.map((c) => ({ id: idOf(g.group.name, c.key), name: g.group.name, c }))).find((x) => x.id === focus))
  const covering = $derived(overlay && !!focused)
  const heading = $derived(focused ? (focused.c.title || focused.name).replace(' - ', ' – ') : '')
  const initials = (name: string) => name.replace(/[^A-Za-z0-9 ]/g, '').split(' ').filter(Boolean).slice(0, 2).map((w) => w[0]).join('').toUpperCase() || '?'

  /** A costume with two ids has a portrait under only one of them: try the next, hide the image when none exists. */
  function nextPortrait(img: HTMLImageElement, ids: string[]) {
    const next = Number(img.dataset.try) + 1
    if (next < ids.length) { img.dataset.try = String(next); img.src = costumePortraitUrl(ids[next]) }
    else img.style.visibility = 'hidden'
  }
  /** The inline box shows fewer rows the larger the tiles: 3 when small, 2 in the middle, 1 when large. */
  const rows = $derived(modSize <= 200 ? 3 : modSize <= 320 ? 2 : 1)

  function open(id: string) {
    if (scroller && !covering) saved = scroller.scrollTop
    focus = id
  }
  /** Closing returns to exactly where the list was scrolled before the box opened. */
  async function close(restore = true) {
    const wasCovering = covering
    focus = null
    if (wasCovering && restore) {
      await tick()
      if (scroller) scroller.scrollTop = saved
      requestAnimationFrame(() => scroller && (scroller.scrollTop = saved)) // once the list has its width and height back
    }
  }
  /** Right-click on the open box: close it and bring the list back to the costume it belonged to. */
  async function closeToCostume() {
    const id = focus
    await close(false)
    await tick()
    if (id) scroller?.querySelector<HTMLElement>(`[data-cid="${CSS.escape(id)}"]`)?.scrollIntoView({ block: 'center' })
  }
  const toggle = (id: string) => (focus === id ? void close() : open(id))
  /** Clicking empty space (not a costume or the mod box) puts the colours back. */
  const clickAway = (e: MouseEvent) => { if (!(e.target as Element).closest('.costume, .panel')) void close() }

  /** A character picked in the roster: close the box and bring that character into view. */
  export async function jump(name: string) {
    await close(false) // no scroll restore: it would undo the jump
    await tick()
    await new Promise(requestAnimationFrame) // the list has its size back once the box no longer covers it
    scroller?.querySelector<HTMLElement>(`[data-char="${CSS.escape(name)}"]`)?.scrollIntoView({ block: 'start' })
  }

  // a different tab or filter closes the box (marking a mod does not: it is not part of the key)
  let lastKey: string | undefined
  $effect(() => {
    const key = resetKey
    if (lastKey !== undefined && key !== lastKey) untrack(() => { void close() })
    lastKey = key
  })

  /** What the cluster grid shows: a piece per character, or, wrapped, full rows that may cut a character in two. */
  const pieces = $derived(clusterPieces(withCostumes.map((g) => ({ name: g.group.name, items: g.costumes })), capacity, wrap))
  /** The mod box goes under the row of the piece that holds the focused costume (the last piece of that row). */
  const after = $derived.by(() => {
    if (!focused) return null
    const holder = pieces.find((p) => p.name === focused.name && p.items.some((c) => c.key === focused.c.key))
    return pieceRows(pieces, capacity).find((r) => holder && r.includes(holder))?.at(-1)?.id ?? null
  })
</script>

<div class="wrap" data-ui="costume-mode" style="--size:{size}px; --mod-size:{modSize}px; --rows:{rows}; --mcols:{modCols}; --cap:{capacity}">
  {#if showOptions}
  <div class="bar">
    <div class="seg" role="group" aria-label="Costume layout">
      <button class:on={clustered} aria-pressed={clustered} title="Grouped: costumes flow side by side, each group under its character name" aria-label="Grouped" onclick={onCluster}><Icon name="layout-grid" size={13} /> Grouped</button>
      <button class:on={!clustered} aria-pressed={!clustered} title="Flat: one section per character" aria-label="Flat" onclick={onCluster}><Icon name="list" size={13} /> Flat</button>
    </div>
    <span class="gap"></span>
    <button class="toggle chrome-toggle" class:on={overlay} aria-pressed={overlay} title={overlay ? 'The mod box covers the list: click to open it below the costume instead' : 'The mod box opens below the costume: click to let it cover the list'} onclick={onOverlay}>
      <Icon name="images" size={13} /> Mod view
    </button>
    <label title="Costume portrait size"><span>Costumes</span><input type="range" min="0" max={costumeStops.length - 1} step="1" value={stopIndex(costumeStops, fieldWidth || 1000, CARD_GAP, size)} oninput={(e) => onSize(costumeStops[Number(e.currentTarget.value)].size)} aria-label="Costume portrait size" /></label>
    <label class:off={!focus} title={focus ? 'Mod portrait size' : 'Select a costume to size its mods'}><span>Mods</span><input type="range" disabled={!focus} min="0" max={modStops.length - 1} step="1" value={stopIndex(modStops, modWidth || 800, CARD_GAP, modSize)} oninput={(e) => onModSize(modStops[Number(e.currentTarget.value)].size)} aria-label="Mod portrait size" /></label>
    <button class="clear" title="Hide this row (bring it back in Settings > Display)" onclick={hideOptions}><Icon name="eye-off" size={13} /> Hide Options</button>
  </div>
  {/if}
  {#if notice}<div class="notice" role="status">Costumes list options are hidden. To show them again: Settings &gt; Display &gt; Show Costumes List Options.<button aria-label="Dismiss" onclick={() => (notice = false)}><Icon name="x" size={13} /></button></div>{/if}

  {#snippet card(name: string, c: CostumeEntry)}
    {@const id = idOf(name, c.key)}
    {@const b = modBadges(c.mods, installed, queued)}
    <button class="costume" data-cid={id} class:nomods={!c.mods.length} class:dim={focus !== null && focus !== id} class:focus={focus === id} title={c.mods.length ? c.title || name : `${c.title || name} (no mods)`} onclick={() => c.mods.length && toggle(id)}>
      <span class="img">
        {#if c.costumeId}<img src={costumePortraitUrl(c.costumeId)} alt="" loading="lazy" data-try="0" onerror={(e) => nextPortrait(e.currentTarget as HTMLImageElement, c.costumeIds)} />{:else if neverHasPortrait(name)}<span class="ph word">{name}</span>{:else}<span class="ph"><Icon name="image" size={28} /></span>{/if}
        {#if b.queued}<span class="corner left"><Badge kind="queued" n={b.queued} /></span>{/if}
        {#if b.installed}<span class="corner right"><Badge kind="installed" n={b.installed} /></span>{/if}
        <span class="counts" title="Idle mods / skills / illustrations and others">
          {#if b.idle}<Badge kind="idle" n={b.idle} />{/if}{#if b.cut}<Badge kind="cut" n={b.cut} />{/if}{#if b.rest}<Badge kind="rest" n={b.rest} />{/if}
        </span>
      </span>
      <span class="label">{c.title.replace(`${name} - `, '') || c.title || name}</span>
    </button>
  {/snippet}
  {#snippet panel(c: CostumeEntry)}
    <div class="panel" role="presentation" oncontextmenu={(e) => { if (!covering) { e.preventDefault(); void closeToCostume() } }}>
      <div class="body" bind:clientWidth={bodyWidth}>
        {#each modSections(c) as section (section.title)}
          {#if section.title}<h4>{section.title}<span>{section.mods.length}</span></h4>{/if}
          <div class="mods">
            {#each section.mods as mod (modKey(mod))}
              {#if mod.is_multi}
                {@const shot = portraits.urlOf(mod)}
                <button class="mod" title="{mod.name} (opens the multi-mod window)" onclick={() => onPreview(mod)}>
                  <span class="thumb" class:multi={!shot}>
                    {#if shot}<img src={shot} alt="" loading="lazy" /><span class="tag-multi">MULTI</span>{:else}<strong>Multi</strong><small>Click to choose</small>{/if}
                  </span>
                  <span class="label">{mod.name}</span>
                </button>
              {:else}
                {@const url = portraits.urlOf(mod)}
                {@const sel = selected.has(modKey(mod))}
                {@const isInstalled = installed.has(mod.name)}
                <!-- a click anywhere on the tile (outside the three buttons) picks it for batch install -->
                <div class="mod" class:installed={isInstalled} class:selected={sel} role="button" tabindex="0" aria-pressed={sel} title="{mod.name}: click to {sel ? 'remove from' : 'select for'} install"
                     onclick={() => onToggle(mod)} ondblclick={() => onPreview(mod)}
                     onkeydown={(e) => { if (e.target === e.currentTarget && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); onToggle(mod) } }}>
                  <span class="thumb">
                    {#if url}<img src={url} alt="" loading="lazy" />{:else}<span class="ph">{initials(mod.name)}</span>{/if}
                    {#if sel}<span class="check" aria-hidden="true"><Icon name="check" size={13} /></span>{/if}
                    <span class="acts" role="group" aria-label="Actions for {mod.name}">
                      <button class="act" class:on={isInstalled} title={isInstalled ? 'Installed (click to mark as not installed)' : 'Mark as installed'} onclick={(e) => { e.stopPropagation(); onMark(mod) }} ondblclick={(e) => e.stopPropagation()}>
                        <Icon name={isInstalled ? 'circle-check' : 'circle'} size={13} /><span class="t">{isInstalled ? 'Installed' : 'Mark'}</span>
                      </button>
                      <button class="act" title="Live Spine 2D preview" onclick={(e) => { e.stopPropagation(); onPreview(mod) }} ondblclick={(e) => e.stopPropagation()}>
                        <Icon name="play" size={13} /><span class="t">Preview</span>
                      </button>
                      <button class="act primary" title="Repack and prepare for install" onclick={(e) => { e.stopPropagation(); onPrepare(mod) }} ondblclick={(e) => e.stopPropagation()}>
                        <Icon name="rocket" size={13} /><span class="t">Prepare</span>
                      </button>
                    </span>
                  </span>
                  <span class="label">{mod.name}</span>
                </div>
              {/if}
            {/each}
          </div>
        {/each}
      </div>
    </div>
  {/snippet}

  {#if covering && focused}
    <div class="full" role="presentation" oncontextmenu={(e) => { e.preventDefault(); void close() }}>
      <div class="title">
        <button class="back" onclick={() => close()} aria-label="Back to all costumes" title="Back to all costumes"><Icon name="arrow-left" size={16} /></button>
        <span class="name">{heading}</span><span class="count">{focused.c.mods.length} {focused.c.mods.length === 1 ? 'mod' : 'mods'}</span>
      </div>
      {@render panel(focused.c)}
    </div>
  {/if}
  <!-- hidden, not removed, while the box covers it: the scroll position and the loaded portraits stay -->
  <div class="scroll" class:clustered hidden={covering} bind:this={scroller} bind:clientWidth={rawWidth} role="presentation" onclick={clickAway}>
    {#if clustered}
      <div class="clusters">
        {#each pieces as piece (piece.id)}
          <div class="cluster" class:lit={lit === piece.name} data-char={piece.name} style="--c:{columnsOf(piece.items.length)}">
            <span class="cname" title={piece.continued || piece.continues ? `${piece.name}: ${piece.continued ? 'more costumes further back' : ''}${piece.continued && piece.continues ? ', ' : ''}${piece.continues ? 'more costumes further ahead' : ''}` : piece.name}>{#if piece.continued}<Icon name="arrow-left" size={15} />{/if}{piece.name}{#if piece.continues}<Icon name="arrow-right" size={15} />{/if}</span>
            <div class="cgrid">{#each piece.items as c (c.key)}{@render card(piece.name, c)}{/each}</div>
          </div>
          {#if !covering && focused && after === piece.id}<div class="inline">{@render panel(focused.c)}</div>{/if}
        {/each}
      </div>
    {:else}
      {#each withCostumes as { group, costumes } (group.name)}
        <section class:lit={lit === group.name} data-char={group.name}>
          <h3>{group.name}</h3>
          <div class="grid">{#each costumes as c (c.key)}{@render card(group.name, c)}{/each}</div>
          {#if !covering && focused && focused.name === group.name}<div class="inline">{@render panel(focused.c)}</div>{/if}
        </section>
      {:else}
        <p class="none">No costumes to show.</p>
      {/each}
    {/if}
  </div>
</div>

<style>
  .wrap { display: flex; flex-direction: column; height: 100%; min-height: 0; }
  .bar { display: flex; flex-wrap: wrap; align-items: center; gap: 0.5rem 1rem; flex: none; padding: 0.35rem 0.2rem 0.6rem; }
  .bar label { display: flex; align-items: center; gap: 0.5rem; font-size: var(--fs-sm); color: var(--text-muted); }
  .bar input { width: 90px; accent-color: var(--primary); }
  .seg { display: inline-flex; padding: 2px; gap: 2px; background: var(--surface-1); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); }
  .seg button, .toggle { display: inline-flex; align-items: center; gap: 0.35rem; padding: 0.25rem 0.65rem; font-size: var(--fs-sm); font-weight: 600; color: var(--text-muted); border-radius: 5px; white-space: nowrap; }
  .seg button:hover, .toggle:hover { color: var(--text-main); }
  .seg button.on { color: var(--text-main); background: var(--tint-3); }
  .gap { flex: 1; }
  .bar label.off { opacity: 0.45; }
  .notice { display: flex; align-items: center; gap: 0.6rem; flex: none; margin: 0 0.2rem 0.5rem; padding: 0.4rem 0.7rem; font-size: var(--fs-sm); color: var(--text-main); background: var(--tint-2); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); }
  .notice button { margin-left: auto; color: var(--text-muted); }
  .clear { display: inline-flex; align-items: center; gap: 0.35rem; padding: 0.25rem 0.65rem; font-size: var(--fs-sm); font-weight: 600; color: var(--text-muted); background: var(--surface-1); border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); cursor: pointer; } .clear:hover { color: var(--text-main); background: var(--tint-3); }
  .scroll { flex: 1; min-height: 0; overflow-y: auto; padding: 12px 14px 3rem 12px; }
  .scroll[hidden] { display: none; }
  section { margin-bottom: 1.4rem; }
  h3 { font-size: var(--fs-lg); color: var(--text-main); margin: 0 0 0.5rem; padding-bottom: 0.3rem; border-bottom: 1px solid var(--border-subtle); }
  /* costumes fill the row: whole columns of at least the chosen size, stretched to use the full width */
  .grid { display: grid; grid-template-columns: repeat(var(--cap), 1fr); gap: 10px; }
  .costume { min-width: 0; width: 100%; }
  .costume, .mod { display: flex; flex-direction: column; gap: 0.3rem; padding: 0; background: none; border: 0; color: var(--text-muted); font-size: var(--fs-xs); cursor: pointer; text-align: center; transition: filter 0.2s ease, opacity 0.2s ease, transform 0.15s ease; }
  .mod { min-width: 0; }
  .label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .img, .thumb { position: relative; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-sm); overflow: hidden; background: var(--tint-1); border: 1px solid var(--border-subtle); }
  .img { width: 100%; aspect-ratio: 1; }
  .img .ph { font-size: calc(var(--size) / 3); color: var(--text-dim); }
  .img .ph.word { padding: 0 6px; font-size: calc(var(--size) / 6); font-weight: 800; line-height: 1.1; overflow-wrap: anywhere; color: var(--text-muted); }
  .thumb { width: 100%; aspect-ratio: 4 / 5; background: color-mix(in srgb, var(--surface-2) 80%, transparent); }
  .thumb .ph { font-size: var(--fs-2xl); color: var(--text-dim); }
  .thumb.multi { flex-direction: column; gap: 0.2rem; border: 0; background: color-mix(in srgb, var(--cat-multi) 45%, var(--surface-2)); color: var(--text-main); box-shadow: 0 0 0 1px var(--cat-multi); }
  .thumb.multi strong { font-size: var(--fs-2xl); letter-spacing: 0.04em; }
  .thumb.multi small { font-size: var(--fs-xs); opacity: 0.85; }
  .tag-multi { position: absolute; right: 4px; bottom: 4px; padding: 2px 6px; border-radius: 6px; font-size: var(--fs-xs); font-weight: 800; letter-spacing: 0.05em; color: var(--text-main); background: color-mix(in srgb, var(--cat-multi) 60%, var(--surface-2)); box-shadow: 0 0 0 1px var(--cat-multi); }
  .mod:hover .thumb.multi { filter: brightness(1.15); }
  img { width: 100%; height: 100%; object-fit: contain; }
  .img, .thumb { transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease; }
  .costume:hover .img, .mod:hover .thumb { border-color: var(--primary); transform: var(--lift); box-shadow: var(--shadow-card); }
  /* the spotlight: everything else goes grey and dark */
  /* a costume nobody made a mod for: grey until the pointer is over it */
  .costume.nomods:not(:hover) { filter: grayscale(1) brightness(0.8); opacity: 0.7; }
  .costume.dim { filter: grayscale(1) brightness(0.45); opacity: 0.7; }
  .costume.focus .img { border-color: var(--primary); background: var(--selected-bg); box-shadow: 0 0 0 2px var(--primary), var(--shadow-card); }
  .costume.focus .label { color: var(--text-main); }
  /* idle (blue) / cutscenes (purple) / illustrations and others (rose), bottom left */
  .counts { position: absolute; left: 4px; bottom: 4px; display: flex; gap: 3px; }
  .corner { position: absolute; z-index: 2; top: 4px; display: flex; }
  .corner.left { left: 4px; }
  .corner.right { right: 4px; }
  .panel { display: flex; flex-direction: column; min-height: 0; border-radius: var(--radius-sm); background: transparent; border: 1px solid var(--border-subtle); }
  /* the box opens below the costume and takes up to three rows of mods (fewer when zoomed in); the rest scrolls */
  .inline { grid-column: 1 / -1; flex: 0 0 100%; min-width: 0; margin: 0.2rem 0 0.4rem; }
  /* the inline box shows every mod (no scrollbar of its own, so the wheel always scrolls the list) */
  .inline .body { overflow: visible; }
  .full { display: flex; flex-direction: column; flex: 1; min-height: 0; gap: 0.5rem; }
  .full .panel { flex: 1; }
  .title { display: flex; align-items: center; gap: 0.7rem; flex: none; padding: 0.4rem 0.9rem 0.4rem 0.5rem; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle); background: var(--tint-2); color: var(--text-main); font-size: var(--fs-lg); font-weight: 700; }
  .title .name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .title .count { font-size: var(--fs-sm); font-weight: 600; color: var(--text-muted); }
  .back { display: grid; place-items: center; width: 30px; height: 30px; color: var(--text-muted); background: transparent; border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); cursor: pointer; }
  .back:hover { color: var(--text-main); background: var(--tint-3); }
  .body { scrollbar-gutter: stable; display: flex; flex-direction: column; gap: 0.5rem; padding: 0.8rem; overflow-y: auto; min-height: 0; }
  /* whole columns that fill the row: the tiles stretch a little instead of leaving a gap on the right */
  .mods { display: grid; grid-template-columns: repeat(var(--mcols), 1fr); gap: 10px; }
  h4 { display: flex; align-items: baseline; gap: 0.5rem; margin: 0.4rem 0 0; padding-bottom: 0.25rem; border-bottom: 1px solid var(--border-subtle); font-size: var(--fs-md); color: var(--text-muted); }
  h4 span { font-size: var(--fs-xs); color: var(--text-dim); }
  h4:first-child { margin-top: 0; }
  .mod.installed .thumb { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent); }
  .mod.selected .thumb { border-color: var(--primary); background: var(--selected-bg); box-shadow: 0 0 0 3px var(--primary); }
  .mod.selected.installed .thumb { box-shadow: none; }
  .mod.selected.installed .thumb::after { content: ''; position: absolute; inset: 0; z-index: 1; padding: 3px; border-radius: inherit; pointer-events: none; background: linear-gradient(140deg, var(--ok) 50%, var(--primary) 50%); -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0); -webkit-mask-composite: xor; mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0); mask-composite: exclude; }
  .mod.selected .label { color: var(--text-main); }
  /* one grid of equal columns for the whole field: every card has the same size, a cluster spans its costumes, rows may keep blank space */
  .clusters { display: grid; grid-template-columns: repeat(var(--cap), 1fr); align-items: start; gap: 1.1rem 10px; }
  /* a cluster takes its costumes' columns and grows with the others on its row; it never splits, so the row may keep blank space */
  .cluster { display: flex; flex-direction: column; gap: 0.35rem; min-width: 0; grid-column: span var(--c); }
  /* the line under the name shows where the cluster starts and ends; the name is as big as in the list layout */
  .cname { display: flex; align-items: center; gap: 0.35rem; max-width: 100%; padding-bottom: 0.3rem; border-bottom: 3px solid var(--primary); font-size: var(--fs-lg); font-weight: 700; color: var(--text-main); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  /* the character of the clicked costume: a blue frame around all of its costumes (each piece of a wrapped character on its own) whose glow breathes */
  /* scrolling a character to the top leaves room for the frame (8px) but not for the row above (its labels end 17px higher) */
  .cluster, section[data-char] { scroll-margin-top: 10px; }
  .cluster.lit, section.lit { padding: 6px; margin: -6px; border-radius: 10px; animation: lit 1.8s ease-in-out infinite; }
  @keyframes lit {
    0%, 100% { box-shadow: 0 0 0 2px rgba(var(--primary-rgb), 0.55); }
    50% { box-shadow: 0 0 0 2px rgba(var(--primary-rgb), 1); }
  }
  .cgrid { display: grid; grid-template-columns: repeat(var(--c), 1fr); gap: 10px; }
  .none { padding: 3rem; text-align: center; color: var(--text-dim); }
  .mod { cursor: pointer; }
  .thumb { container-type: inline-size; }
  /* the three actions sit over the portrait, bottom left, one above the other (shown on hover or keyboard focus; always on touch screens) */
  .acts { position: absolute; left: 6px; bottom: 6px; z-index: 2; display: flex; flex-direction: column; align-items: flex-start; gap: 4px; opacity: 0; pointer-events: none; transition: opacity 0.12s; }
  /* hover only; :focus-visible keeps them reachable by keyboard without sticking after a mouse click */
  .mod:hover .acts, .mod:has(:focus-visible) .acts { opacity: 1; pointer-events: auto; }
  @media (hover: none) { .acts { opacity: 1; pointer-events: auto; } }
  .act { display: inline-flex; align-items: center; gap: 0.35rem; padding: 0.28rem 0.55rem; font-size: var(--fs-sm); font-weight: 700; line-height: 1; white-space: nowrap; color: var(--text-main); background: color-mix(in srgb, var(--surface-1) 88%, transparent); border: 1px solid var(--tint-4); border-radius: var(--radius-sm); }
  .act:hover { background: var(--surface-3); }
  .act.on { color: var(--ok-text); border-color: color-mix(in srgb, var(--ok) 55%, transparent); }
  .act.primary { color: var(--on-primary); background: var(--primary-solid); border-color: transparent; }
  .act.primary:hover { background: var(--primary-solid-hover); }
  @container (max-width: 135px) { .act .t { display: none; } .act { padding: 0.32rem; } }
  .check { position: absolute; top: 6px; right: 6px; z-index: 2; display: grid; place-items: center; width: 20px; height: 20px; color: var(--on-primary); background: var(--primary-solid); border-radius: 50%; }
</style>
