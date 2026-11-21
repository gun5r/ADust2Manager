/** Reactive state of the Viewer Studio; the imperative Spine work is delegated to SpineController. */
import type { CategoryFilter, IndexMod } from '../../lib/classify'
import { defaultPlayback, cutSequence, pickSpineFiles, skeletonParts } from '../../lib/spine'
import { countVisible, filterLayers, layerRows, nextAllHidden, slotsForAnimation, type LayerRow } from '../../lib/layers'
import { api, type DatingAudio, type PackCategory, type PackPreview, type PackVariant } from '../../lib/api'
import { layersFor, type SoundManifest } from '../../lib/datingAudio'
import { SoundPlayer, type Playback } from '../../lib/soundPlayer'

type FitMode = 'off' | 'on' | 'snap'
const FIT_KEY = 'adust2.fitMode'
const BAR_KEY = 'adust2.playbackBar'
const readPlaybackBar = () => { try { return localStorage.getItem(BAR_KEY) !== 'false' } catch { return true } }
const readFit = (): FitMode => {
  try { const v = localStorage.getItem(FIT_KEY); return v === 'off' || v === 'snap' ? v : 'on' } catch { return 'on' }
}
import { allVariants, filterCategories, preparedAsMod, toggleVariant, variantAsMod } from '../../lib/multi'
import { SpineController, type Clip } from './controller'
import { DEFAULT_PREFS, readPrefs, type GuideStyle, type TouchPrefs } from '../../lib/touchPrefs'
import { untrack } from 'svelte'
import { phasesOf, withOverrides, type Hotspot, type SceneRules } from '../../lib/dating'
import { followForScene } from '../../lib/follow'

export type Background = 'default' | 'black' | 'white' | 'skyblue' | 'custom'

export class ViewerState {
  mod = $state<IndexMod | null>(null)
  status = $state<'loading' | 'ready' | 'error'>('loading')
  message = $state('')
  clips = $state<Clip[]>([])
  current = $state<string | null>(null)
  sequencePlaying = $state(false)
  paused = $state(false)
  speed = $state(1)
  loop = $state(true)
  playbackBar = $state(readPlaybackBar())
  follow = $state(true)
  /** The user's own follow choice; until they make one, dating scenes start without the follow camera. */
  private followChoice: boolean | undefined
  /** Dating scenes: fit the picture to the view's height (and glide there on phase changes). */
  fitMode = $state<FitMode>(readFit())
  /** The Portrait button is hovered: show which part of the view it keeps. */
  portraitGuide = $state(false)
  premultipliedAlpha = $state(false)
  background = $state<Background>('default')
  customBackground = $state('#172136')
  zoomPercent = $state(100)
  layers = $state<LayerRow[]>([])
  hidden = $state<Set<string>>(new Set())
  layerQuery = $state('')
  skeleton = $state<string | undefined>(undefined)
  showShortcuts = $state(false)
  // Right-hand character browser
  browserQuery = $state('')
  expanded = $state<string | null>(null)
  filesOpen = $state(false)
  // Pack mode: `mod` is the previewed variant, `pack` the multi mod it belongs to
  pack = $state<IndexMod | null>(null)
  /** A multimod picked in the normal preview's list: the stage asks to open the multimod selector instead of playing it. */
  multiPrompt = $state<IndexMod | null>(null)
  categories = $state<PackCategory[]>([])
  variant = $state<PackVariant | null>(null)
  chosen = $state<PackVariant[]>([])
  packQuery = $state('')
  packLoading = $state(false)
  packError = $state('')
  collapsed = $state<Record<string, boolean>>({})
  packPreviews = $state<PackPreview[]>([])
  /** Dating-scene touch simulation: spots read from the skeleton, the live phase, and whether they are drawn. */
  spots = $state<Hotspot[]>([])
  interact = $state(true)
  phase = $state(1)
  /** The phase's score gauge (null: none) and the tool in use; the tools of the phase come from the game's rules. */
  gauge = $state<{ score: number; max: number } | null>(null)
  tool = $state(0)
  /** Whether the dating data the simulator needs is there for the scene on screen, and whether the warning about it was hidden. */
  datingData = $state<'ok' | 'missing' | 'unknown-scene'>('ok')
  datingWarningHidden = $state(false)
  /** The tool the touch guide wants picked (it points at that button), or null. */
  guideTool = $state<number | null>(null)
  guideTilts = $state<number[]>([])
  /** The tilts of the phase (the game's gyro spots, tilting the phone): one button each; those that end the phase, else the one that plays a reaction. */
  tilts = $derived.by(() => {
    const gyros = this.spots.filter((s) => s.kind === 'gyro' && s.phase === this.phase && (s.reactions.length > 0 || !!s.rule?.motion || !!s.rule?.next))
    const enders = gyros.filter((s) => s.rule?.next), shown = enders.length ? enders : gyros.slice(0, 1)
    return shown.map((s, i) => ({ id: s.rule?.id ?? s.id, tool: s.rule?.tool ?? null, label: shown.length > 1 ? `Tilt ${i + 1}` : 'Tilt' }))
  })
  private rules = $state<SceneRules | null>(null)
  /** The phase's tool buttons, minus the tool only the tilt spots use: that icon sits on the tilt button instead. */
  tools = $derived.by(() => {
    const all = this.rules?.groups.find((g) => g.group === this.phase)?.tools ?? []
    const tiltTools = new Set(this.tilts.map((t) => t.tool).filter((t) => t !== null))
    const others = this.spots.filter((s) => s.phase === this.phase && s.kind !== 'gyro').map((s) => s.rule?.tool)
    return all.filter((t) => !(tiltTools.has(t.id) && !others.includes(t.id)))
  })
  /** The touch menu is open (false: only a small "Menu" button stays). */
  menuOpen = $state(true)
  /** A scene split over one skeleton per phase (see skeletonParts): the phase buttons switch the skeleton. */
  parts = $derived(skeletonParts(this.mod?.files ?? []))
  phases = $derived(this.parts.size ? [...this.parts.keys()].sort((a, b) => a - b) : phasesOf(this.spots))
  /** Sounds of the dating scene on screen: status of the downloaded clips, and whether to play them. */
  audio = $state<DatingAudio | null>(null)
  audioBusy = $state(false)
  audioError = $state('')
  private audioScene: string | null = null
  /** Sound plans of the scene (downloaded), the voice language used, and the engine that plays them. */
  manifest = $state<SoundManifest | null>(null)
  private sounds = new SoundPlayer()
  /** The sound each spot has started and that may still be playing: it ends with the spot's animation (it is let go, started again, interrupted, or the phase changes). */
  private held = new Map<string, Playback[]>()
  /** Right panel while a pack is open: its variants, or the list of other packs to switch to. */
  panel = $state<'variants' | 'packs'>('variants')
  previewsOpen = $state(false)
  /** The picture the user chose for the canvas corner: undefined = the option's own preview, null = cleared. */
  previewPick = $state<string | null | undefined>(undefined)
  previewExpanded = $state(false)

  private controller: SpineController
  private stage: HTMLElement | undefined

  constructor() {
    this.controller = new SpineController({
      ready: (clips) => this.onReady(clips),
      error: (message) => ((this.status = 'error'), (this.message = message)),
      reaction: (animation, spot) => this.playReaction(animation, `${spot.phase}_${spot.id}`),
      released: (spot) => this.endHeld(`${spot.phase}_${spot.id}`),
      phase: (n) => { this.phase = n; this.enterPart(n) },
      state: (s) => { this.tool = s.tool; this.gauge = s.gauge; this.guideTool = s.guideTool; this.guideTilts = s.guideTilts },
      animation: (name) => {
        this.current = name
        this.sequencePlaying = name === null
        this.refreshLayers()
      },
    })
  }

  /** The touch menu's preferences: the app keeps them in its config (see `connectPrefs`), so they outlive the browser and its cache. */
  prefs = $state<TouchPrefs>({ ...DEFAULT_PREFS })
  private prefsTimer: ReturnType<typeof setTimeout> | undefined
  private prefsSaver: ((prefs: TouchPrefs) => void) | undefined
  private prefsSaved = JSON.stringify(DEFAULT_PREFS)

  /** Take the saved preferences and, from then on, hand every change to `save` a moment after it was made. Only the first call counts. */
  connectPrefs(saved: unknown, save: (prefs: TouchPrefs) => void): void {
    if (this.prefsSaver) return
    this.prefsSaver = save
    Object.assign(this.prefs, readPrefs(saved))
    this.prefsSaved = JSON.stringify(this.prefs)
    this.sounds.setVolume(this.prefs.soundVolume)
    this.syncSpots()
    $effect.root(() => {
      $effect(() => {
        const now = JSON.stringify(this.prefs)
        untrack(() => {
          clearTimeout(this.prefsTimer)
          if (now === this.prefsSaved) return
          this.prefsTimer = setTimeout(() => { this.prefsSaved = now; save(JSON.parse(now)) }, 400)
        })
      })
    })
  }

  open = $derived(this.mod !== null)
  files = $derived(pickSpineFiles(this.mod?.files ?? []))
  skeletonFiles = $derived((this.mod?.files ?? []).filter((f) => /\.(skel|skel\.bytes|json)$/i.test(f)))
  sequence = $derived(cutSequence(this.clips.map((c) => c.name)))
  visibleLayers = $derived(filterLayers(this.layers, this.layerQuery))
  visibleLayerCount = $derived(countVisible(this.layers, this.hidden))
  visibleCategories = $derived(filterCategories(this.categories, this.packQuery))
  /** Previews of the option the active variant belongs to (shown in the canvas corner). */
  previews = $derived(
    this.categories.flatMap((c) => c.options).find((o) => o.variants.some((v) => v.full_path === this.variant?.full_path))?.previews ?? [],
  )

  shownPreview = $derived(this.previewPick === undefined ? (this.previews[0]?.full_path ?? null) : this.previewPick)

  /** Click a picture in the list: show it in the corner; click the one already shown to clear the player. */
  togglePreview(fullPath: string) {
    const clearing = this.shownPreview === fullPath
    this.previewPick = clearing ? null : fullPath
    if (clearing) this.previewExpanded = false // picking another one keeps the expanded state, so flipping through is quick
  }

  /** Show a mod. Switching mods keeps the playback preferences (speed, loop, background, follow, PMA). */
  show(mod: IndexMod) {
    if (mod.is_multi) return void this.showPack(mod)
    this.pack = null
    this.multiPrompt = null
    this.packPreviews = []
    this.previewPick = undefined
    this.previewExpanded = false
    this.mod = mod
    this.expanded = mod.character
    this.skeleton = undefined
    this.hidden = new Set()
    this.controller.hidden.clear()
    this.layerQuery = ''
    this.reload()
  }

  /** Pick a mod in the normal preview's list (click or stepping keys): a multimod is not played, it asks to open the multimod selector. */
  pick(mod: IndexMod) {
    if (!mod.is_multi) return this.show(mod)
    this.stopSounds()
    this.controller.dispose() // nothing keeps playing behind the question
    this.pack = null
    this.mod = mod // the list marks it, the stepping keys go on from it and any other mod can be picked again
    this.expanded = mod.character // the character panel follows, as for any other mod
    this.multiPrompt = mod
    this.clips = []
    this.layers = []
    this.spots = []
    this.gauge = null
    this.current = null
    this.audioScene = null
    this.audio = null
    this.manifest = null
    this.status = 'ready'
  }

  close() {
    this.stopSounds()
    this.audioScene = null
    this.audio = null
    this.manifest = null
    this.controller.dispose()
    this.mod = null
    this.pack = null
    this.multiPrompt = null
  }

  // ---- pack mode ----------------------------------------------------------------------------------------------

  showPack(pack: IndexMod) {
    if (!this.pack) this.panel = 'variants' // switching packs from the Packs list keeps that list open
    this.expanded = pack.character
    this.pack = pack
    this.multiPrompt = null
    this.mod = pack
    this.categories = []
    this.variant = null
    this.chosen = []
    this.packQuery = ''
    this.packError = ''
    this.packPreviews = []
    this.previewPick = undefined
    this.previewExpanded = false
    this.packLoading = true
    this.status = 'loading'
    this.controller.dispose()
    api.multiTree(pack.folder_path, pack.name).then(
      (tree) => {
        if (this.pack !== pack) return
        this.categories = tree.categories
        this.packPreviews = tree.previews ?? []
        this.packError = tree.error ?? ''
        this.packLoading = false
        const first = allVariants(tree.categories)[0]
        if (first) this.pickVariant(first)
        else {
          this.status = 'error'
          this.message = tree.error || 'This pack has no variants.'
        }
      },
      (e) => {
        if (this.pack !== pack) return
        this.packLoading = false
        this.packError = String(e)
        this.status = 'error'
        this.message = String(e)
      },
    )
  }

  pickVariant(variant: PackVariant) {
    if (!this.pack) return
    this.variant = variant
    this.mod = variantAsMod(variant, this.pack.character) as unknown as IndexMod
    this.skeleton = undefined
    this.hidden = new Set()
    this.controller.hidden.clear()
    this.layerQuery = ''
    this.reload()
  }

  toggleChosen(variant: PackVariant) {
    this.chosen = toggleVariant(this.chosen, variant)
  }

  /** Shift+F: choose every variant of the open variant's option, or drop them all when they are all chosen already (variants of the same asset still replace each other). */
  toggleOptionChosen() {
    const current = this.variant
    const option = current && this.visibleCategories.flatMap((c) => c.options).find((o) => o.variants.some((v) => v.full_path === current.full_path))
    if (!option) return
    const has = (list: PackVariant[], v: PackVariant) => list.some((c) => c.full_path === v.full_path)
    this.chosen = option.variants.every((v) => has(this.chosen, v))
      ? this.chosen.filter((c) => !has(option.variants, c))
      : option.variants.reduce((list, v) => (has(list, v) ? list : toggleVariant(list, v)), this.chosen)
  }

  /** Previous/next variant in the (filtered) tree. */
  stepVariant(direction: -1 | 1) {
    const list = allVariants(this.visibleCategories)
    if (!list.length) return
    const at = list.findIndex((v) => v.full_path === this.variant?.full_path)
    this.pickVariant(list[(at + direction + list.length) % list.length])
  }

  /** Extract the chosen variants on the server; returns them as mods ready for the queue. */
  async prepareChosen(quality: string): Promise<IndexMod[]> {
    const pack = this.pack
    if (!pack) return []
    const { items } = await api.prepareSelections(
      this.chosen.map((v) => ({ full_path: v.full_path, name: v.name, character: pack.character })),
      pack.name,
      quality,
    )
    return items.map(preparedAsMod) as unknown as IndexMod[]
  }

  /** The stage element appears after the first render; (re)start loading once it exists. */
  attach(stage: HTMLElement): () => void {
    this.stage = stage
    if (this.mod && (!this.pack || this.variant)) this.reload()
    const detach = this.controller.attachInteraction(stage, () => (this.zoomPercent = this.controller.zoomPercent))
    return () => {
      detach()
      this.controller.dispose()
      this.stage = undefined
    }
  }

  reload() {
    if (!this.mod || !this.stage || this.multiPrompt) return
    this.status = 'loading'
    this.message = ''
    this.clips = []
    this.layers = []
    this.current = null
    this.sequencePlaying = false
    this.paused = false
    this.controller.paused = false
    this.controller.speed = this.speed
    this.controller.loop = this.loop
    this.follow = followForScene(this.mod.category === 'dating', this.followChoice) // the first frame is still centred by the controller
    this.controller.follow = this.follow
    this.syncFit()
    this.controller.load(this.stage, this.mod, { skeleton: this.skeleton, premultipliedAlpha: this.premultipliedAlpha })
  }

  private onReady(clips: Clip[]) {
    this.clips = clips
    this.status = 'ready'
    this.spots = this.controller.sim.hotspots
    void this.loadScene()
    this.syncSpots()
    this.controller.sim.interact = this.interact && this.spots.length > 0
    if (this.controller.sim.interact) {
      if (!this.phases.includes(this.phase)) this.phase = this.phases[0]
      if (this.enterPart(this.phase)) return
      return this.controller.sim.setPhase(this.phase)
    }
    const choice = defaultPlayback(clips.map((c) => c.name))
    if (choice.sequence.length) this.playSequence()
    else if (choice.animation) this.play(choice.animation)
  }

  // ---- dating touch simulation ---------------------------------------------------------------------------------

  private get sceneKey(): string | null {
    const key = this.mod?.asset_key
    return this.spots.length && key && /^illust_dating\d+/i.test(key) ? key.toLowerCase() : null
  }

  /** Ask the server for the game's touch rules and the sounds of this scene (only for dating scenes with touch spots). */
  private async loadScene() {
    const scene = this.sceneKey
    if (scene === this.audioScene) return
    this.audioScene = scene
    this.audio = null
    this.manifest = null
    this.audioError = ''
    if (!scene) return
    const [rules, audio, info] = await Promise.all([api.datingRules(scene).catch(() => null), api.datingAudio(scene).catch(() => null), api.datingDataInfo().catch(() => null)])
    if (this.audioScene !== scene) return
    this.datingData = rules ? 'ok' : info && info.files > 0 ? 'unknown-scene' : 'missing'
    this.audio = audio
    void this.loadManifest(scene)
    if (rules) {
      const full = withOverrides(scene, rules)
      this.controller.sim.setRules(full)
      this.rules = full
      this.spots = this.controller.sim.hotspots
    }
  }

  async downloadAudio() {
    const scene = this.audioScene
    if (!scene || this.audioBusy) return
    this.audioBusy = true
    this.audioError = ''
    try {
      const status = await api.downloadDatingAudio(scene)
      if (this.audioScene === scene) { this.audio = status; await this.loadManifest(scene) }
    } catch (e) {
      this.audioError = `Could not download the audio: ${e}`
    } finally {
      this.audioBusy = false
    }
  }

  /** The voice language to use: the only one present (the interaction banks hold Korean). */
  private get voiceLanguage(): string | null {
    return this.prefs.voiceOn ? (this.audio?.voice?.[0] ?? null) : null
  }

  private async loadManifest(scene: string) {
    if (!this.audio?.cached) return
    const manifest = await api.datingManifest(scene).catch(() => null)
    if (this.audioScene !== scene || !manifest) return
    this.manifest = manifest
    void this.sounds.preload(scene, manifest, this.voiceLanguage)
  }

  stopSounds() {
    this.sounds.stop()
    this.held.clear()
  }

  setSoundVolume(volume: number) {
    this.prefs.soundVolume = volume
    this.sounds.setVolume(volume)
  }

  /** A drag or hold was let go, or its animation was interrupted: the sounds it started end (the game stops that event), the release clip's sounds follow. */
  private endHeld(key: string) {
    this.held.get(key)?.forEach((playback) => playback.stop(0.15))
    this.held.delete(key)
  }

  /** A clip started: play the event the game assigns to it (effects, plus the voice line when the scene has one). */
  private playReaction(animation: string, spotKey: string) {
    const scene = this.audioScene
    if (!scene || !this.manifest || !this.prefs.soundOn || !this.interact) return
    const layers = layersFor(this.manifest, animation, this.voiceLanguage, this.rules?.soundFrom)
    if (!layers.length) return
    this.sounds.setVolume(this.prefs.soundVolume)
    for (const key of [...this.held.keys()]) if (key !== spotKey) this.endHeld(key) // one touch reaction at a time: another spot's sounds end with its animation
    // the animation starts again (a fast second click): its earlier sound ends instead of stacking on the new one
    this.held.get(spotKey)?.forEach((playback) => playback.stop(0.05))
    this.held.set(spotKey, [this.sounds.play(scene, layers)])
  }

  toggleInteract() {
    this.interact = !this.interact
    this.controller.sim.setInteract(this.interact && this.spots.length > 0)
  }

  setPhase(phase: number) {
    this.stopSounds()
    this.phase = phase
    if (!this.enterPart(phase)) this.controller.sim.setPhase(phase)
  }

  /** In a scene split over skeletons: load the one that holds `phase` (true when that means loading another). */
  private enterPart(phase: number): boolean {
    const file = this.parts.get(phase)
    if (!file || file === (this.skeleton ?? this.skeletonFiles[0])) return false
    this.setSkeleton(file)
    return true
  }

  private syncSpots() {
    Object.assign(this.controller.sim, {
      spotsOn: this.prefs.spotsOn, spotsIdle: this.prefs.spotsIdle, spotStyle: this.prefs.spotStyle, spotsFixed: this.prefs.spotsFixed, spotsHover: this.prefs.spotsHover,
      spotScale: this.prefs.spotScale, spotOpacity: this.prefs.spotOpacity, spotsSolid: this.prefs.spotsSolid, guide: this.prefs.guide,
    })
  }

  setSpotsOn(on: boolean) { this.prefs.spotsOn = on; this.syncSpots() }
  toggleSpotsIdle() { this.prefs.spotsIdle = !this.prefs.spotsIdle; this.syncSpots() }
  setSpotStyle(style: 'numbers' | 'dots' | 'plain') { this.prefs.spotStyle = style; this.syncSpots() }
  toggleSpotsHover() { this.prefs.spotsHover = !this.prefs.spotsHover; this.syncSpots() }
  toggleSpotsFixed() { this.prefs.spotsFixed = !this.prefs.spotsFixed; this.syncSpots() }
  tilt(id?: number) { this.controller.sim.tilt(id) }
  setTool(id: number) { this.tool = id; this.controller.sim.setTool(id) }
  setSpotScale(v: number) { this.prefs.spotScale = v; this.syncSpots() }
  setSpotOpacity(v: number) { this.prefs.spotOpacity = v; this.syncSpots() }
  toggleSpotsSolid() { this.prefs.spotsSolid = !this.prefs.spotsSolid; this.syncSpots() }
  setGuide(style: GuideStyle) { this.prefs.guide = style; this.syncSpots() }

  // ---- playback ----------------------------------------------------------------------------------------------

  play(name: string) {
    this.controller.play(name)
    this.paused = false
  }

  playSequence() {
    this.controller.playSequence(this.sequence)
    this.paused = false
  }

  togglePause() {
    this.paused = this.controller.togglePause()
  }

  setSpeed(speed: number) {
    this.speed = speed
    this.controller.setSpeed(speed)
  }

  toggleLoop() {
    this.loop = !this.loop
    this.controller.setLoop(this.loop)
  }

  togglePlaybackBar() {
    this.playbackBar = !this.playbackBar
    try { localStorage.setItem(BAR_KEY, String(this.playbackBar)) } catch { /* the choice still applies this session */ }
  }

  playbackTime() {
    const track = this.controller.player?.animationState.getCurrent(0)
    const duration = track?.animation?.duration ?? 0, raw = track?.trackTime ?? 0
    // trackTime keeps counting on a loop: show the time inside the current pass
    return { time: duration ? (track?.loop ? raw % duration : Math.min(raw, duration)) : 0, duration }
  }

  seekPlayback(time: number) {
    const player = this.controller.player
    const track = player?.animationState.getCurrent(0)
    if (!player || !track) return
    track.trackTime = Math.max(0, Math.min(track.animation?.duration ?? 0, time))
    if (this.paused) player.animationState.apply(player.skeleton)
  }

  /** Previous/next clip in the list (the A / D keys). */
  stepAnimation(direction: -1 | 1) {
    if (!this.clips.length) return
    const index = Math.max(0, this.clips.findIndex((c) => c.name === this.current))
    this.play(this.clips[(index + direction + this.clips.length) % this.clips.length].name)
  }

  // ---- view ----------------------------------------------------------------------------------------------------

  resetView() {
    this.controller.resetView()
    this.zoomPercent = 100
  }

  toggleFollow() {
    this.follow = this.controller.toggleFollow()
    if (this.mod?.category !== 'dating') this.followChoice = this.follow
  }

  /** Off -> On (glides) -> Snap (jumps) -> Off; kept between mods and sessions. */
  cycleFit() {
    this.fitMode = this.fitMode === 'off' ? 'on' : this.fitMode === 'on' ? 'snap' : 'off'
    try { localStorage.setItem(FIT_KEY, this.fitMode) } catch { /* the choice still applies this session */ }
    this.syncFit()
    this.controller.refit()
  }

  private syncFit() {
    this.controller.fit.enabled = this.fitMode !== 'off'
    this.controller.fit.snap = this.fitMode === 'snap'
  }

  /** Premultiplied textures (Settings / Tools > Troubleshooting); a preview that is open loads again with it. */
  setPma(on: boolean) {
    if (on === this.premultipliedAlpha) return
    this.premultipliedAlpha = on
    this.reload()
  }

  setSkeleton(file: string) {
    this.skeleton = file
    this.reload()
  }

  captureFrame() {
    return this.controller.captureFrame()
  }

  snapshot() {
    this.controller.snapshot(this.mod?.name ?? 'character')
  }

  // ---- layers ----------------------------------------------------------------------------------------------------

  refreshLayers() {
    const skeleton = this.controller.player?.skeleton
    this.layers = layerRows(slotsForAnimation(skeleton, this.current ?? this.sequence[0] ?? undefined))
  }

  toggleLayer(name: string) {
    const hide = !this.hidden.has(name)
    this.controller.setLayerHidden(name, hide)
    const next = new Set(this.hidden)
    if (hide) next.add(name)
    else next.delete(name)
    this.hidden = next
  }

  toggleAllLayers() {
    const hide = nextAllHidden(this.layers, this.hidden)
    for (const row of this.layers) this.controller.setLayerHidden(row.name, hide)
    this.hidden = hide ? new Set(this.layers.map((l) => l.name)) : new Set()
  }

  resetLayers() {
    for (const name of [...this.controller.hidden]) this.controller.setLayerHidden(name, false)
    this.hidden = new Set()
  }
}
