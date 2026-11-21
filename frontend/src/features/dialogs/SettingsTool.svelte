<script lang="ts">
  import type { AppState } from '../../state/app.svelte'

  let { app }: { app: AppState } = $props()

  /** Preferences that apply as soon as they are changed (quality and the cache are in the Cache menu in the header). */
  const prefs: { group: 'Display' | 'Behaviour' | 'Console'; key: 'expand_console_default' | 'auto_expand_on_install' | 'auto_mark_installed' | 'isolated_character_list' | 'show_legend' | 'badge_icons' | 'costume_wrap' | 'costume_options' | 'seamless_viewer' | 'show_empty_characters'; fallback: boolean; label: string; help: string }[] = [
    // grouped as the page shows them; the explanation sits under each name
    { group: 'Display', key: 'show_legend', fallback: true, label: 'Show legend of color badges', help: '' },
    { group: 'Display', key: 'badge_icons', fallback: true, label: 'Icons on the color badges', help: '' },
    { group: 'Display', key: 'costume_wrap', fallback: true, label: 'Wrap costumes on mod list', help: '' },
    { group: 'Display', key: 'costume_options', fallback: true, label: 'Show Costumes List Options', help: '' },
    { group: 'Display', key: 'seamless_viewer', fallback: true, label: 'Seamless preview player', help: '' },
    { group: 'Display', key: 'show_empty_characters', fallback: false, label: 'Show characters without mods', help: '' },
    { group: 'Behaviour', key: 'isolated_character_list', fallback: false, label: 'Only show Selected character', help: '' },
    { group: 'Behaviour', key: 'auto_mark_installed', fallback: true, label: 'Auto-mark installed mods', help: '' },
    { group: 'Console', key: 'expand_console_default', fallback: false, label: 'Open the console at start', help: '' },
    { group: 'Console', key: 'auto_expand_on_install', fallback: false, label: 'Open the console when installing', help: '' },
  ]
  const pref = (key: (typeof prefs)[number]['key'], fallback: boolean) => (app.config?.settings?.[key] === undefined ? fallback : Boolean(app.config.settings[key]))
  const sections = ['Display', 'Behaviour', 'Console'] as const // the order the groups appear in the page
  const themes = [{ id: 'graphite', name: 'Graphite' }, { id: 'black', name: 'OLED Black' }] as const
  const theme = $derived(app.config?.settings?.theme === 'black' ? 'black' : 'graphite')
  const reset = () => app.saveSettings({ ...Object.fromEntries(prefs.map((p) => [p.key, p.fallback])), theme: 'graphite' })
</script>

<div class="s-page" data-ui="settings-tool">
  <section class="s-section">
    <h3 class="s-title">Appearance</h3>
    <div class="s-card">
      <div class="s-row">
        <div class="s-text"><strong>Theme</strong></div>
        <div class="s-choices" role="radiogroup" aria-label="Theme">
          {#each themes as t (t.id)}
            <button class="s-choice" class:on={theme === t.id} role="radio" aria-checked={theme === t.id} onclick={() => app.saveSettings({ theme: t.id })}>
              <span class="swatch {t.id}" aria-hidden="true"></span>{t.name}
            </button>
          {/each}
        </div>
      </div>
    </div>
  </section>

  {#each sections as section (section)}
    <section class="s-section">
      <h3 class="s-title">{section}</h3>
      <div class="s-card">
        {#each prefs.filter((p) => p.group === section) as p (p.key)}
          <label class="s-row">
            <span class="s-text"><strong>{p.label}</strong>{#if p.help}<span>{p.help}</span>{/if}</span>
            <input class="s-switch" type="checkbox" role="switch" checked={pref(p.key, p.fallback)} onchange={(e) => app.saveSettings({ [p.key]: e.currentTarget.checked })} />
          </label>
        {/each}
      </div>
    </section>
  {/each}

  <section class="s-section">
    <h3 class="s-title">Defaults</h3>
    <div class="s-card">
      <div class="s-row">
        <div class="s-text"><strong>Restore defaults</strong></div>
        <button class="tool-btn" onclick={reset}>Restore defaults</button>
      </div>
    </div>
  </section>
</div>

<style>
  /* a tiny preview of the theme: three diagonal bands (page, a lighter band, the accent). The ring is a shadow, not a border: a border
     would show the gradient repeating (blue lines on the top and left edges). The colours are the themes' own, written once here. */
  .swatch { width: 28px; height: 28px; flex: none; border-radius: var(--radius-sm); box-shadow: 0 0 0 1px var(--tint-4); background: linear-gradient(135deg, var(--a) 0 34%, var(--b) 34% 67%, var(--c) 67% 100%) no-repeat; }
  .swatch.graphite { --a: #0b0c0f; --b: #8a8f9c; --c: #5b9bff; }
  .swatch.black { --a: #000; --b: #121212; --c: #3b82f6; }
</style>
