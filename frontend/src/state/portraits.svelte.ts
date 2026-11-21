/** Mod portraits: which mods have a generated thumbnail, and the job that renders the missing ones in an off-screen player. */
import { api } from '../lib/api'
import { prefetchMod } from '../lib/prefetch'
import { SpineController } from '../features/viewer/controller'
import type { IndexMod } from '../lib/classify'
import { cropsBody, IDLE_CROP, modPortraitUrl, portraitEligible } from '../lib/portraits'
import { allVariants, variantAsMod } from '../lib/multi'

const SIZE = { width: 320, height: 400 }
const TIMEOUT_MS = 30000
/** Mods drawn at once (each has its own off-screen player), and how many ahead have their files fetched meanwhile. */
/** Longest texture side the portrait renders load (the picture is only 320x400); 4096 sheets shrink 4x, 2048 sheets 2x. */
const TEXTURE = 1024
const WORKERS = 3
const LOOKAHEAD = 3

export class PortraitState {
  /** folder -> version of its thumbnail (the server only lists current ones). */
  versions = $state<Record<string, number>>({})
  running = $state(false)
  done = $state(0)
  total = $state(0)
  failed = $state(0)
  private cancelled = false

  constructor(private log: (message: string, level?: string) => void) {}

  async refresh() {
    try {
      this.versions = (await (await fetch('/api/portraits/mods')).json()).mods
    } catch {
      /* keeps the last list */
    }
  }

  /** Replace a mod's portrait with a picture (a pack is a mod folder too). */
  async set(mod: IndexMod, blob: Blob) {
    const res = await fetch(`/api/portraits/mod?folder=${encodeURIComponent(mod.folder_path)}`, { method: 'POST', body: blob })
    if (!res.ok) throw new Error(`upload failed (${res.status})`)
    await this.refresh()
  }

  /** A portrait by its folder (the conflict windows know folders, not mods); null when there is none. */
  urlOfFolder(folder: string | undefined): string | null {
    const v = folder ? this.versions[folder] : undefined
    return v ? modPortraitUrl(folder!, v) : null
  }

  urlOf(mod: IndexMod): string | null {
    const v = this.versions[mod.folder_path]
    return v ? modPortraitUrl(mod.folder_path, v) : null
  }

  cancel() {
    this.cancelled = true
  }

  /** Render and upload a portrait for each eligible mod (only the missing ones unless `all`), one at a time. */
  async generate(mods: IndexMod[], all: boolean, withVariants = false) {
    if (this.running) return
    const todo = mods.filter((m) => portraitEligible(m) && (all || !this.versions[m.folder_path]))
    if (withVariants) {
      // The variants of multimods are not listed as mods, but the conflict windows show their portraits.
      this.running = true
      this.total = 0
      try {
        for (const pack of mods.filter((m) => m.is_multi)) {
          try {
            const tree = await api.multiTree(pack.folder_path, pack.name)
            for (const variant of allVariants(tree.categories)) {
              const mod = variantAsMod(variant, pack.character) as unknown as IndexMod
              if (portraitEligible(mod) && (all || !this.versions[mod.folder_path])) todo.push(mod)
            }
          } catch (e) {
            this.log(`Could not read the multimod ${pack.name}: ${e instanceof Error ? e.message : e}`, 'warning')
          }
        }
      } finally {
        this.running = false
      }
    }
    this.running = true
    this.cancelled = false
    this.done = this.failed = 0
    this.total = todo.length
    // The server shows this work in the status bar too (it runs here, in the browser, so it reports in).
    const task = await api.reportTask({ title: 'Generating mod portraits', detail: `0 of ${todo.length}` }).then((r) => r.id).catch(() => null)
    const report = (state: 'running' | 'done' | 'cancelled' = 'running') => {
      if (task !== null) void api.reportTask({ id: task, state, detail: `${this.done} of ${this.total}${this.failed ? `, ${this.failed} failed` : ''}`, progress: this.total ? this.done / this.total : 1 }).catch(() => {})
    }
    const queue = [...todo]
    const worker = async () => {
      const stage = document.createElement('div')
      stage.style.cssText = `position:fixed;left:-10000px;top:0;width:${SIZE.width}px;height:${SIZE.height}px;pointer-events:none`
      document.body.appendChild(stage)
      try {
        for (let mod = queue.shift(); mod && !this.cancelled; mod = queue.shift()) {
          for (const next of queue.slice(0, LOOKAHEAD)) prefetchMod(next, TEXTURE)
          try {
            const blob = await this.render(stage, mod)
            if (!blob) throw new Error('nothing to draw')
            const res = await fetch(`/api/portraits/mod?folder=${encodeURIComponent(mod.folder_path)}`, { method: 'POST', body: blob })
            if (!res.ok) throw new Error(`upload failed (${res.status})`)
          } catch (e) {
            this.failed++
            this.log(`No portrait for ${mod.name}: ${e instanceof Error ? e.message : e}`, 'warning')
          }
          this.done++
          if (this.done % 5 === 0) report()
          if (this.done % 25 === 0) await this.refresh()
        }
      } finally {
        stage.remove()
      }
    }
    try {
      await Promise.all(Array.from({ length: Math.min(WORKERS, todo.length) }, worker))
    } finally {
      this.running = false
      report(this.cancelled ? 'cancelled' : 'done')
      await this.refresh()
    }
  }

  private render(stage: HTMLElement, mod: IndexMod): Promise<Blob | null> {
    return new Promise((resolve, reject) => {
      let settled = false
      const finish = (fn: () => void) => { if (!settled) { settled = true; clearTimeout(timer); controller.dispose(); fn() } }
      const controller: SpineController = new SpineController({
        ready: () => void controller.portrait(cropsBody(mod), IDLE_CROP).then((b) => finish(() => resolve(b)), (e) => finish(() => reject(e))),
        error: (message) => finish(() => reject(new Error(message))),
        animation: () => {},
      })
      const timer = setTimeout(() => finish(() => reject(new Error('timed out'))), TIMEOUT_MS)
      controller.load(stage, mod, { premultipliedAlpha: false, quiet: true, maxTexture: TEXTURE })
    })
  }
}
