export interface ToolMessage { text: string; kind: 'ok' | 'error' }

/** Server messages are already readable; anything that looks like a network or file failure gets a hint on what to do. */
export function friendly(e: unknown): string {
  const text = e instanceof Error ? e.message : String(e)
  if (/failed to fetch|networkerror|^\d{3} \//i.test(text)) return 'Could not reach the manager. Is it still running?'
  if (/catalog|download|cdn|timed? ?out|connection/i.test(text)) return `Could not get the data from the game servers (${text}). Check your internet connection and try again.`
  return text.replace(/^Error:\s*/, '')
}

/**
 * What the Tools window shows for the tool in progress: one job at a time, a label for what it is doing, the elapsed seconds, the
 * newest server log line, and how it ended. Every tool panel runs its work through `run`, so none repeats this bookkeeping.
 */
export class ToolRun {
  working = $state<string | null>(null)
  message = $state<ToolMessage | null>(null)
  private startedAt = $state(0)
  private now = $state(0)
  private timer: ReturnType<typeof setInterval> | undefined
  private logs: () => { message: string; at: number }[]

  constructor(logs: () => { message: string; at: number }[]) {
    this.logs = logs
  }

  get busy(): boolean { return this.working !== null }
  get latest(): string { return this.busy ? (this.logs().filter((l) => l.at >= this.startedAt).at(-1)?.message ?? '') : '' }
  get elapsed(): string { return this.busy ? `${Math.max(0, Math.round((this.now - this.startedAt) / 1000))} s` : '' }

  /** Say what a longer job is doing now (a step of a run); the elapsed time starts again. */
  step(label: string): void {
    this.working = label
    this.startedAt = this.now = Date.now()
  }

  /**
   * Run `job` under `label`. A returned text (or text + kind) becomes the outcome, an error becomes a readable error outcome; a job
   * that returns nothing leaves no outcome (it reported through its own panel).
   */
  async run(label: string, job: () => Promise<string | ToolMessage | void>): Promise<void> {
    this.message = null
    this.step(label)
    clearInterval(this.timer)
    this.timer = setInterval(() => (this.now = Date.now()), 500)
    try {
      const result = await job()
      if (result) this.message = typeof result === 'string' ? { kind: 'ok', text: result } : result
    } catch (e) {
      this.message = { kind: 'error', text: friendly(e) }
    } finally {
      clearInterval(this.timer)
      this.working = null
    }
  }
}
