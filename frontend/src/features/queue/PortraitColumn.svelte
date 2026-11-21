<script lang="ts">
  /** A side column of a conflict window: mods as portraits with a small name below, two per row, scrolling, each with an aura in the colour of its role. */
  export interface Tile { key: string; name: string; folder?: string }
  export interface Section { title: string; tone: 'green' | 'blue' | 'amber'; tiles: Tile[] }

  let { sections, portraitOf, onOpen }: {
    sections: Section[]
    portraitOf: (folder: string | undefined) => string | null
    onOpen: (src: string) => void
  } = $props()
</script>

<aside class="column" aria-label={sections.map((s) => s.title).join(' ')}>
  {#each sections.filter((s) => s.tiles.length) as section (section.title)}
    <h4 class={section.tone}>{section.title}</h4>
    <div class="tiles">
      {#each section.tiles as t (t.key)}
        {@const src = portraitOf(t.folder)}
        <div class="tile {section.tone}" title={t.name}>
          {#if src}
            <button type="button" class="pic" title="Click to enlarge" onclick={() => onOpen(src)}><img {src} alt="" loading="lazy" /></button>
          {:else}
            <span class="pic blank" aria-hidden="true"></span>
          {/if}
          <span class="tname">{t.name}</span>
        </div>
      {/each}
    </div>
  {/each}
</aside>

<style>
  /* as tall as the window's body: the pictures scroll inside the column and reach its bottom */
  .column { flex: 0 0 230px; min-height: 0; display: flex; flex-direction: column; gap: 0.5rem; overflow-y: auto; padding: 0.5rem; background: var(--surface-panel); border: 1px solid var(--border-subtle); border-radius: var(--radius-md); }
  h4 { position: sticky; top: 0; z-index: 1; padding: 0.2rem 0; background: var(--surface-2); font-size: var(--fs-sm); font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; }
  h4.green { color: var(--ok-text); } h4.blue { color: var(--primary); } h4.amber { color: var(--warn-text); }
  .tiles { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.6rem; padding: 0.35rem; }
  .tile { display: flex; flex-direction: column; gap: 0.3rem; padding: 0.3rem; border-radius: var(--radius-sm); background: rgba(0, 0, 0, 0.25); border: 1.5px solid var(--c); box-shadow: none; }
  .tile.green { --c: var(--ok-text); --glow: color-mix(in srgb, var(--ok) 35%, transparent); }
  .tile.blue { --c: var(--primary); --glow: rgba(var(--primary-rgb), 0.35); }
  .tile.amber { --c: var(--warn-text); --glow: color-mix(in srgb, var(--warn) 35%, transparent); }
  .pic { display: block; width: 100%; aspect-ratio: 4 / 5; padding: 0; overflow: hidden; border-radius: 4px; background: var(--tint-1); cursor: zoom-in; }
  .pic.blank { cursor: default; border: 1px dashed var(--border-subtle); }
  .pic img { width: 100%; height: 100%; object-fit: cover; display: block; }
  .tname { font-size: var(--fs-xs); line-height: 1.25; color: var(--text-muted); display: -webkit-box; -webkit-line-clamp: 2; line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; word-break: break-word; }
  @media (max-width: 900px) { .column { flex-basis: 150px; } }
</style>
