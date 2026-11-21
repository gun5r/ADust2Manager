/** What the program is doing, as the server reports it (core/activity.py). */
export type LightState = 'idle' | 'running' | 'warning' | 'error'
export type TaskState = 'running' | 'done' | 'error' | 'cancelled'

export interface ActivityTask {
  id: number
  title: string
  kind: string
  state: TaskState
  detail: string
  /** 0..1, or null when the task cannot tell. */
  progress: number | null
  errors: number
  error: string
  started: number
  ended: number | null
  updated: number
}

export interface ActivityStatus { state: LightState; label: string; text: string; running: number }
export interface ActivitySnapshot { tasks: ActivityTask[]; status: ActivityStatus; now: number }

/** The short labels the server sends (core/activity.py status()); the player reserves room for the longest of them. */
export const LABELS: LightState[] = ['idle', 'running', 'warning', 'error']
export const LABEL_TEXT: Record<LightState, string> = { idle: 'Standby', running: 'Running', warning: 'Errors, running', error: 'Critical Failure' }

export const QUIET: ActivitySnapshot = { tasks: [], status: { state: 'idle', label: 'Standby', text: 'Nothing is running.', running: 0 }, now: 0 }

/** Light colours: blue standby, green running, orange errors but still running, red stopped. */
export const LIGHT_COLOR: Record<LightState, string> = { idle: 'var(--text-muted)', running: 'var(--ok)', warning: 'var(--warn)', error: 'var(--danger)' }

export function duration(seconds: number): string {
  const s = Math.max(0, Math.round(seconds))
  if (s < 60) return `${s} s`
  const m = Math.floor(s / 60)
  return m < 60 ? `${m} min ${String(s % 60).padStart(2, '0')} s` : `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, '0')} min`
}

/** Seconds a task has run (or ran). `now` is the server clock of the snapshot plus the time since it arrived, so a page whose clock differs still counts right. */
export function taskSeconds(task: ActivityTask, now: number): number {
  return (task.ended ?? now) - task.started
}

export function percent(task: ActivityTask): string {
  return task.progress === null ? '' : `${Math.round(task.progress * 100)}%`
}

export function stateText(task: ActivityTask): string {
  return { running: 'Running', done: task.errors ? 'Done, with errors' : 'Done', error: 'Failed', cancelled: 'Cancelled' }[task.state]
}

/** The window title carries what is going on, so a minimised tab still says so. */
export function tabTitle(status: ActivityStatus): string {
  return status.running > 0 ? `(${status.running}) ADust2Manager` : status.state === 'error' ? '(!) ADust2Manager' : 'ADust2Manager'
}
