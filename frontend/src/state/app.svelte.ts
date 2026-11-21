/** Application-wide state for the new layout: config, devices, cache size and the queue runner. */
import { api, type CacheStats, type Config, type Device, type ExactDuplicate, type FolderTab, type NameCollision, type Settings } from '../lib/api'
import type { IndexMod } from '../lib/classify'
import { connectLogs, type LogLine } from '../lib/logs'
import { QUIET, tabTitle, type ActivitySnapshot } from '../lib/activity'
import { badgeUi } from '../lib/badgeStyle.svelte'
import { newJob } from '../lib/queue'
import { tabRoot } from '../lib/filters'
import { createTab, forceMultiMap, moveTab, needsScan, removeTab, updateTab } from '../lib/tabs'
import { modKey } from '../lib/selection'
import { LibraryState } from './library.svelte'
import { ViewerState } from '../features/viewer/viewer.svelte'
import { effectiveCategory } from '../lib/classify'
import { PortraitState } from './portraits.svelte'
import { adbStatus, cacheLabel } from '../lib/header'
import { summarize } from '../lib/queue'
import { QueueRunner } from '../lib/runner'
import { QueueFlow } from './queueFlow.svelte'
import { MascotState } from './mascots.svelte'
import { forgetPrefetch } from '../lib/prefetch'
import { lacksSkeleton } from '../lib/skeleton'

export class AppState {
  config = $state<Config | null>(null)
  devices = $state<Device[]>([])
  cacheBytes = $state(0)
  queueVersion = $state(0)
  logs = $state<LogLine[]>([])
  private localLine = 0
  error = $state('')

  readonly library = new LibraryState(() => this.config)
  readonly viewer = new ViewerState()
  readonly portraits = new PortraitState((message, level) => this.log(message, level))
  readonly mascots = new MascotState((message, level) => this.log(message, level))
  scanning = $state(false)
  settingsOpen = $state(false)
  toolsOpen = $state(false)
  /** The tab Settings / Tools opens on (taken once, then back to Settings). */
  toolsTab = $state('settings')
  /** The mod whose skeleton dialog is open (opened from the viewer's Skeleton Fix button). */
  skeletonFix = $state<IndexMod | null>(null)
  /** Folder tab waiting for the remove confirmation. */
  tabDeleting = $state<FolderTab | null>(null)
  /** Result of the duplicate check; the inspector window is open while this is set. */
  inspector = $state<{ duplicates: ExactDuplicate[]; collisions: NameCollision[]; tabs: FolderTab[] } | null>(null)
  /** What the program is doing (from the server, so it is the same after a reload and in every browser). */
  activity = $state<ActivitySnapshot>(QUIET)
  /** Seconds on the server's clock, kept ticking while something runs. */
  clock = $state(0)
  online = $state(true)
  /** The status bar's open panel: the task list, the combined console, or none. */
  barPanel = $state<'tasks' | 'console' | null>(null)
  activityOpen = $state(false)
  /** Console lines before this sequence number are hidden (Clear). */
  consoleFrom = $state(0)
  template = $state('')
  tabEditor = $state<{ tab: FolderTab | null } | null>(null)
  readonly runner = new QueueRunner(api, () => this.queueVersion++, (message, level = 'info') => this.log(message, level))
  readonly flow = new QueueFlow(this)

  adb = $derived(adbStatus(this.devices))
  cache = $derived(cacheLabel(this.cacheBytes, this.config?.quality ?? 'HD'))
  queue = $derived(this.queueVersion >= 0 ? summarize(this.runner.jobs) : summarize([]))

  /** Folders of the mods with an active queue job (the purple badge on the portraits). */
  queuedFolders = $derived.by(() => {
    const folders = new Set<string>()
    if (this.queueVersion >= 0) {
      for (const job of this.runner.jobs) {
        if (!['queued', 'preparing', 'prepared', 'transferring'].includes(job.status)) continue
        for (const f of job.mod_folders ?? [job.mod_folder]) folders.add(f)
      }
    }
    return folders
  })
  templates = $derived(Object.keys(this.config?.templates?.[this.library.activeTab?.id ?? ''] ?? {}).sort())
  isolatedList = $derived(this.config?.settings?.isolated_character_list === true)
  costumeWrap = $derived(this.config?.settings?.costume_wrap !== false)
  costumeOptions = $derived(this.config?.settings?.costume_options !== false)
  seamlessViewer = $derived(this.config?.settings?.seamless_viewer !== false)
  showLegend = $derived(this.config?.settings?.show_legend !== false)

  /** Settings that change how things look or render, applied to the live objects (called after the config loads and on every change). */
  private applyAppearance() {
    const s = this.config?.settings
    if (s) this.viewer.connectPrefs(s.touch_menu, (prefs) => void this.saveSettings({ touch_menu: prefs })) // takes the saved ones once, then saves every change
    badgeUi.icons = s?.badge_icons !== false
    const theme = s?.theme === 'black' ? 'black' : 'graphite'
    document.documentElement.dataset.theme = theme
    try { localStorage.setItem('adust2.theme', theme) } catch { /* private window: the theme comes from the saved settings on load */ }
    this.viewer.setPma(s?.pma_textures === true)
  }

  /** Persist preference changes straight away (classic applies each checkbox on change). */
  async saveSettings(patch: Settings) {
    if (!this.config) return
    const settings = { ...this.config.settings, ...patch }
    this.config = { ...this.config, settings }
    this.applyAppearance()
    if ('expand_console_default' in patch) this.barPanel = patch.expand_console_default ? 'console' : null
    if (patch.isolated_character_list === false) this.library.isolated = null
    try {
      await api.updateConfig({ settings })
    } catch (e) {
      this.error = String(e)
    }
  }

  async saveQuality(quality: string) {
    if (!this.config) return
    this.config = { ...this.config, quality }
    try {
      await api.updateConfig({ quality })
    } catch (e) {
      this.error = String(e)
    }
  }

  async refreshConfig() {
    this.config = await api.config()
  }

  clearSelection() {
    this.library.selected = new Set()
  }

  log(message: string, level = 'info') {
    this.logs = [...this.logs.slice(-499), { seq: --this.localLine, message, level, at: Date.now() }]
  }

  async refreshDevices() {
    try {
      this.devices = (await api.devices()).devices
    } catch {
      this.devices = []
    }
  }

  async refreshCache() {
    try {
      const stats: CacheStats = await api.cacheInfo()
      this.cacheBytes = stats.total_bytes
    } catch {
      /* the pill keeps its last value */
    }
  }

  /** Load everything the shell needs and start polling the phone; returns a function that stops the polling. */
  async init(): Promise<() => void> {
    try {
      this.config = await api.config()
    } catch (e) {
      this.error = String(e)
    }
    this.barPanel = this.config?.settings?.expand_console_default ? 'console' : null
    this.applyAppearance()
    void this.refreshDevices()
    void this.refreshCache()
    void this.mascots.refresh()
    void this.firstRunHint()
    void this.library.load().catch((e) => (this.error = String(e)))
    let arrived = Date.now()
    const stopLogs = connectLogs({
      onLine: (line) => (this.logs = [...this.logs.slice(-499), line]),
      onHistory: (lines) => (this.logs = lines),
      onActivity: (snapshot) => {
        this.activity = snapshot
        this.clock = snapshot.now
        arrived = Date.now()
        document.title = tabTitle(snapshot.status)
      },
      onConnection: (online) => (this.online = online),
    })
    const tick = setInterval(() => {
      if (this.activity.status.running > 0) this.clock = this.activity.now + (Date.now() - arrived) / 1000
    }, 1000)
    this.runner.load().catch((e) => this.log(`Could not load the queue: ${e}`, 'error'))
    const timer = setInterval(() => void this.refreshDevices(), 5000)
    return () => {
      clearInterval(timer)
      clearInterval(tick)
      stopLogs()
    }
  }

  /** A computer with no character list or dating tables yet (nothing is bundled with the program): point at Settings / Tools > Initial Setup. */
  private async firstRunHint() {
    try {
      const [chars, dating] = await Promise.all([api.charactersInfo(), api.datingDataInfo()])
      if (!chars.count || !dating.files) this.log('First run: open Settings / Tools > Initial Setup to get the character list, the dating simulator data and the sounds from the game.', 'warning')
    } catch { /* the server is not ready yet; the hint is only a convenience */ }
  }

  // ---- library actions ------------------------------------------------------------------------------------------

  /** Index the folders in view (all folders in Sync View), then reload the list. */
  async scan() {
    if (!this.config || this.scanning) return
    this.scanning = true
    try {
      await api.scanAll(this.library.scanTargets, forceMultiMap(this.library.tabs))
      await this.library.load()
      this.error = ''
      void this.checkDuplicates()
    } catch (e) {
      this.error = String(e)
    } finally {
      this.scanning = false
    }
  }

  /** Re-index and reload without opening the inspector again (used by the inspector itself). */
  async refreshLibrary() {
    await api.scanAll(this.library.scanTargets, forceMultiMap(this.library.tabs))
    await this.library.load()
  }

  /** Open the inspector when the library holds identical copies or clashing folder names (classic does this after every scan). */
  async checkDuplicates() {
    try {
      const result = await api.checkDuplicates()
      if (result.exact_duplicates.length || result.name_collisions.length) {
        this.inspector = { duplicates: result.exact_duplicates, collisions: result.name_collisions, tabs: result.folder_tabs }
      }
    } catch (e) {
      this.log(`Duplicate check skipped: ${e}`, 'warning')
    }
  }

  async switchTab(id: string) {
    if (!this.config) return
    this.library.setSyncView(false)
    this.library.isolated = null
    if (this.config.active_tab_id === id) return
    this.config = { ...this.config, active_tab_id: id }
    await api.saveTabs(this.library.tabs, id).catch((e) => (this.error = String(e)))
  }

  async toggleInstalled(mod: IndexMod) {
    const result = await api.toggleInstalled(mod.name, !this.library.installedNames.has(mod.name))
    if (this.config) this.config = { ...this.config, installed_mods: result.installed_mods }
  }

  categoryLabel(mod: IndexMod): string {
    return { idle: 'Idle', cut: 'Skill', illust: 'Illust', dating: 'Dating', multi: 'Multi', other: 'Other' }[effectiveCategory(mod)]
  }

  /** Re-index the mod's folder, reload the library, and refresh the viewer if it shows that mod. */
  private async refreshMod(mod: IndexMod) {
    forgetPrefetch(mod.folder_path) // merging or renaming rewrote its files
    await api.scanAll([mod.root ?? tabRoot(this.library.activeTab ?? { path: '' })], forceMultiMap(this.library.tabs))
    await this.library.load()
    if (this.viewer.mod?.folder_path === mod.folder_path) {
      const fresh = this.library.mods.find((m) => m.folder_path === mod.folder_path && m.name === mod.name) ?? this.library.mods.find((m) => m.folder_path === mod.folder_path)
      if (fresh) this.viewer.show(fresh)
    }
  }

  /** The skeleton dialog of the viewer: pick a donor or the game's original even when the mod already has one. */
  async fixSkeleton(mod: IndexMod, donor?: string) {
    const result = await api.fixSkeleton(mod.folder_path, donor)
    this.log(result.message, 'success')
    forgetPrefetch(mod.folder_path)
    const viewing = this.viewer.mod?.folder_path === mod.folder_path
    if (viewing && !this.viewer.mod?.files.includes(result.file)) this.viewer.mod?.files.push(result.file) // pack variants are not re-read from the library
    await this.refreshMod(mod)
    if (viewing && this.viewer.pack) this.viewer.reload()
  }

  /** Re-read the roots of these mod folders (after files changed on disk) and reload the library. */
  async rescanFolders(folders: string[]) {
    const wanted = new Set(folders)
    const roots = [...new Set(this.library.mods.filter((m) => wanted.has(m.folder_path)).map((m) => m.root ?? tabRoot(this.library.activeTab ?? { path: '' })))]
    for (const f of folders) forgetPrefetch(f)
    await api.scanAll(roots, forceMultiMap(this.library.tabs))
    await this.library.load()
  }

  /** Re-read one folder tab's root (after files were added to it by a tool). */
  async rescanRoot(root: string) {
    await api.scanAll([root], forceMultiMap(this.library.tabs))
    await this.library.load()
  }

  /** Merge a mod's Spine textures, or restore the originals if it is already merged; then refresh its flags. */
  async toggleMerge(mod: IndexMod) {
    const merging = !mod.has_backup
    const ok = confirm(merging
      ? `Merge Spine textures for "${mod.name}"?\n\nThis will horizontally stitch PNG textures together, recalculate .atlas coordinates (both Spine 4 bounds & Spine 3.8 xy), and back up originals in .old/.\nThis resolves character loading crashes in-game.`
      : `Revert merged textures for "${mod.name}"?\n\nThis will restore the original unmerged PNGs and .atlas file from the .old/ backup folder.`)
    if (!ok) return
    try {
      const result = await (merging ? api.mergeSpine(mod.folder_path) : api.revertMerge(mod.folder_path))
      this.log(result.message, 'success')
      await this.refreshMod(mod)
    } catch (e) {
      this.log(`Merge failed for ${mod.name}: ${e}`, 'error')
    }
  }

  /** Queue mods for preparation: conflict and shared-bundle checks first, then the processing queue. */
  prepare(mods: IndexMod[]) {
    const bare = mods.filter(lacksSkeleton)
    if (bare.length) {
      this.log(`${bare.length === 1 ? `"${bare[0].name}" has` : `${bare.length} mods have`} no skeleton file: fix it with the Skeleton Fix button in the preview or the Skeleton fix tool, then prepare again.`, 'warning')
      return
    }
    void this.flow.queueMods(mods)
  }

  prepareSelected() {
    this.prepare(this.library.tabMods.filter((m) => this.library.selected.has(modKey(m))))
  }

  // ---- templates (per folder tab: name -> mod names) ------------------------------------------------------------

  /** `names` defaults to the selected mods ("Save installed" passes the mods marked installed). */
  async saveTemplate(name: string, mods?: string[]) {
    const tab = this.library.activeTab
    if (!tab || !this.config || !name.trim()) return
    const names = mods ?? this.library.tabMods.filter((m) => this.library.selected.has(modKey(m))).map((m) => m.name)
    if (!names.length) return void this.log('Select some mods before saving a template.', 'warning')
    const { templates } = await api.saveTemplate(tab.id, name.trim(), names)
    this.config = { ...this.config, templates }
    this.template = name.trim()
  }

  async deleteTemplate() {
    const tab = this.library.activeTab
    if (!tab || !this.config || !this.template) return
    const { templates } = await api.deleteTemplate(tab.id, this.template)
    this.config = { ...this.config, templates }
    this.template = ''
  }

  loadTemplate() {
    if (!this.template) return void this.log('Choose a template to load first.', 'warning')
    const names = new Set(this.config?.templates?.[this.library.activeTab?.id ?? '']?.[this.template] ?? [])
    this.library.selected = new Set(this.library.tabMods.filter((m) => names.has(m.name)).map(modKey))
  }

  // ---- characters ---------------------------------------------------------------------------------------------

  /** Tools > Characters: refresh names/costumes/portraits from the community database, then re-match the library. */
  async updateCharacters() {
    const result = await api.updateCharacters()
    this.library.roster = (await api.characters()).characters
    this.log(`Characters updated: ${result.added} added, ${result.updated} updated (${result.total} total).`, 'success')
    await this.refreshLibrary() // mods are matched to characters while scanning
    return result
  }

  /** Forget all character data (names, costumes, dating links, costume portraits); mods fall back to Others until the next update. */
  async deleteCharacters() {
    await api.deleteCharacters()
    this.library.roster = (await api.characters()).characters
    this.log('Character data deleted. Use Update Characters to rebuild it.', 'info')
    await this.refreshLibrary()
    await this.portraits.refresh()
  }

  // ---- folder tabs --------------------------------------------------------------------------------------------

  async persistTabs(tabs: FolderTab[], activeId: string, scan: FolderTab | null = null) {
    if (!this.config) return
    this.scanning = true
    try {
      this.config = (await api.saveTabs(tabs, activeId)).config
      if (scan?.path) await api.scanAll([scan.path], forceMultiMap(tabs))
      await this.library.load()
    } catch (e) {
      this.error = String(e)
    } finally {
      this.scanning = false
    }
  }

  saveTabEdit(draft: Omit<FolderTab, 'id'>) {
    if (!this.config || !this.tabEditor) return
    const editing = this.tabEditor.tab
    this.tabEditor = null
    const tabs = this.library.tabs
    if (editing) {
      const next = updateTab(tabs, editing.id, draft)
      const after = next.find((t) => t.id === editing.id)!
      void this.persistTabs(next, this.config.active_tab_id, needsScan(editing, after) ? after : null)
    } else {
      const tab = createTab(draft, tabs)
      this.library.setSyncView(false)
      void this.persistTabs([...tabs, tab], tab.id, tab)
    }
  }

  /** Ask first (classic's "Remove Folder Tab?" dialog). */
  askRemoveTab(tab: FolderTab) {
    this.tabDeleting = tab
  }

  /** Show a folder tab's folder in the system's file manager (double-click on the tab). */
  async openTabFolder(tab: FolderTab) {
    try { await api.openFolder(tab.path) } catch (e) { this.log(e instanceof Error ? e.message : String(e), 'warning') }
  }

  removeTab(tab: FolderTab) {
    if (!this.config) return
    this.tabEditor = null
    this.tabDeleting = null
    const result = removeTab(this.library.tabs, tab.id, this.config.active_tab_id)
    void this.persistTabs(result.tabs, result.activeId)
  }

  moveTab(tab: FolderTab, delta: -1 | 1) {
    if (this.config) void this.persistTabs(moveTab(this.library.tabs, tab.id, delta), this.config.active_tab_id)
  }
}
