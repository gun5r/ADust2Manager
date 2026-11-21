import { api, type Mascot, type MascotDiagnostics, type MascotLaunch } from '../lib/api'

/** Desktop mascots (separate always-on-top windows): the list, the one being edited, and the actions. */
export class MascotState {
  open = $state(false)
  list = $state<Mascot[]>([])
  selectedId = $state<string | null>(null)
  diagnostics = $state<MascotDiagnostics | null>(null)

  constructor(private log: (message: string, level?: string) => void) {}

  selected = $derived(this.list.find((m) => m.id === this.selectedId) ?? this.list[0] ?? null)

  async refresh() {
    try {
      this.list = (await api.mascots()).mascots
    } catch {
      /* the badge simply keeps its last value */
    }
  }

  async show() {
    this.open = true
    void this.refresh()
    this.diagnostics = await api.mascotDiagnostics().catch(() => null)
  }

  async launch(payload: MascotLaunch) {
    try {
      const { mascot } = await api.launchMascot(payload)
      this.selectedId = mascot.id
      this.log(`Desktop Mascot launched: ${payload.mod_name}`, 'success')
      await this.refresh()
    } catch (e) {
      this.log(`Failed to launch mascot: ${e}`, 'error')
    }
  }

  /** Optimistic: the sliders and checkboxes feel instant, the server value replaces it. */
  async update(id: string, patch: Partial<Mascot>) {
    this.list = this.list.map((m) => (m.id === id ? { ...m, ...patch } : m))
    try {
      const { mascot } = await api.updateMascot(id, patch)
      this.list = this.list.map((m) => (m.id === id ? mascot : m))
    } catch (e) {
      this.log(`Could not update the mascot: ${e}`, 'error')
      void this.refresh()
    }
  }

  async close(id: string) {
    await api.closeMascot(id).catch(() => {})
    await this.refresh()
  }

  async closeAll() {
    await api.resetMascots().catch(() => {})
    await this.refresh()
  }

  async configureKwin() {
    try {
      const r = await api.mascotKwinRule()
      this.log(`KWin Window Rule: ${r.message}`, r.status === 'ok' ? 'success' : 'warning')
    } catch (e) {
      this.log(`KWin rule error: ${e}`, 'error')
    }
  }
}
