import { api } from '../../lib/api'

/** Files of the mod on show that are cut off (an incomplete download): the model looks broken, and this says why. One check per mod folder. */
export class ModHealth {
  damaged = $state<{ file: string; reason: string }[]>([])
  hidden = $state(false)
  private folder: string | null = null

  async load(folder: string | null): Promise<void> {
    if (folder === this.folder) return
    this.folder = folder
    this.damaged = []
    this.hidden = false
    if (!folder) return
    try {
      const { damaged } = await api.modHealth(folder)
      if (this.folder === folder) this.damaged = damaged // the mod may have changed while the check ran
    } catch { /* the preview works without this hint */ }
  }
}
