/** Library state: indexed mods, active folder, filters, isolation and selection, with everything derived once. */
import { COSTUME_MAX, COSTUME_MIN } from '../lib/columns'
import { api, type Character, type Config, type FolderTab } from '../lib/api'
import { type CategoryFilter, type IndexMod } from '../lib/classify'
import { filterCounts, filterMods, modsOfTab, tabRoot, type StatusFilter } from '../lib/filters'
import { groupByCharacter, withEmptyCharacters } from '../lib/grouping'
import { modKey } from '../lib/selection'

const SYNC_KEY = 'ui.syncView'

function readSyncPreference(): boolean {
  try {
    return localStorage.getItem(SYNC_KEY) !== 'false'
  } catch {
    return true
  }
}

function readPref(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function writePref(key: string, value: string) {
  try {
    localStorage.setItem(key, value)
  } catch {
    /* private window: the choice just does not persist */
  }
}

export class LibraryState {
  // Declared first: the $derived fields below read it lazily, after the constructor has run.
  private config: () => Config | null = () => null
  mods = $state<IndexMod[]>([])
  roster = $state<Character[]>([])
  loading = $state(false)
  // Like classic, the library opens with every folder combined (Sync View) unless the user turned it off.
  syncView = $state(readSyncPreference())
  status = $state<StatusFilter>('all')
  category = $state<CategoryFilter>('all')
  rosterQuery = $state('')
  isolated = $state<string | null>(null)
  rosterColumns = $state<2 | 3>(2)
  selected = $state<Set<string>>(new Set())
  /** The central list shows costume and mod portraits; List mode (the button on the roster) shows the plain rows instead. */
  listMode = $state(readPref('ui.listMode') === 'true')
  costumeClustered = $state(readPref('ui.costumeClustered') !== 'false') // clusters unless the user chose the list
  costumeOverlay = $state(readPref('ui.costumeOverlay') !== 'false') // the mod box covers the list unless the user chose the inline box
  costumeSize = $state(Math.min(COSTUME_MAX, Math.max(COSTUME_MIN, Number(readPref('ui.costumeSize')) || COSTUME_MIN)))
  modSize = $state(Math.min(460, Math.max(90, Number(readPref('ui.modSize')) || 200)))

  constructor(config: () => Config | null) {
    this.config = config
  }

  tabs = $derived<FolderTab[]>(this.config()?.folder_tabs ?? [])
  activeTab = $derived(this.tabs.find((t) => t.id === this.config()?.active_tab_id) ?? this.tabs[0])
  installedNames = $derived(new Set(this.config()?.installed_mods ?? []))
  tabMods = $derived(modsOfTab(this.mods, this.activeTab, this.syncView))
  counts = $derived(filterCounts(this.tabMods, this.installedNames))
  visible = $derived(filterMods(this.tabMods, this.installedNames, this.status, this.category, this.status === 'selected' ? this.selected : undefined)) // the selection is only read (so only tracked) for the Selected tab
  groups = $derived(groupByCharacter(this.visible, this.roster))
  /** The groups the roster and Costume mode show: with the setting on (and no filter narrowing the list), every character and costume, mods or not. */
  displayGroups = $derived(this.config()?.settings?.show_empty_characters === true && this.status === 'all' && this.category === 'all' ? withEmptyCharacters(this.groups, this.roster) : this.groups)
  shownDisplayGroups = $derived(this.isolated ? this.displayGroups.filter((g) => g.name === this.isolated) : this.displayGroups)
  shownGroups = $derived(this.isolated ? this.groups.filter((g) => g.name === this.isolated) : this.groups)
  shownCount = $derived(this.shownGroups.reduce((sum, g) => sum + g.mods.length, 0))

  setListMode(on: boolean) {
    this.listMode = on
    writePref('ui.listMode', String(on))
  }

  setCostumeOverlay(on: boolean) {
    this.costumeOverlay = on
    writePref('ui.costumeOverlay', String(on))
  }

  setCostumeClustered(on: boolean) {
    this.costumeClustered = on
    writePref('ui.costumeClustered', String(on))
  }

  setModSize(px: number) {
    this.modSize = px
    writePref('ui.modSize', String(px))
  }

  setCostumeSize(px: number) {
    this.costumeSize = px
    writePref('ui.costumeSize', String(px))
  }

  async load() {
    this.loading = true
    try {
      const [index, roster] = await Promise.all([api.modsIndex(), api.characters()])
      this.mods = index.mods as IndexMod[]
      this.roster = roster.characters
    } finally {
      this.loading = false
    }
  }

  isSelected = (mod: IndexMod) => this.selected.has(modKey(mod))

  toggle(mod: IndexMod) {
    const next = new Set(this.selected)
    if (!next.delete(modKey(mod))) next.add(modKey(mod))
    this.selected = next
  }

  setMany(mods: IndexMod[], on: boolean) {
    const next = new Set(this.selected)
    for (const m of mods) on ? next.add(modKey(m)) : next.delete(modKey(m))
    this.selected = next
  }

  /** Classic behaviour: clicking the isolated character again shows everyone. */
  isolate(name: string) {
    this.isolated = this.isolated === name ? null : name
  }

  setSyncView(on: boolean) {
    this.syncView = on
    try {
      localStorage.setItem(SYNC_KEY, String(on))
    } catch {
      /* the preference is optional */
    }
  }

  resetFilters() {
    this.status = 'all'
    this.category = 'all'
    this.rosterQuery = ''
    this.isolated = null
  }

  scanTargets = $derived(this.syncView ? this.tabs.map(tabRoot) : this.activeTab ? [tabRoot(this.activeTab)] : [])
}
