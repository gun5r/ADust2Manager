import type { ActivitySnapshot } from './activity'

export interface LogLine {
  /** Server sequence number (unique); lines the page wrote itself have a negative one. */
  seq: number
  message: string
  level: string
  progress?: number | null
  at: number
  /** The activity task the line belongs to. */
  task?: number | null
}

export interface LogHandlers {
  onLine: (line: LogLine) => void
  /** Sent when the page connects (also after a reconnect): the server's recent lines, which replace what the page has. */
  onHistory: (lines: LogLine[]) => void
  onActivity: (snapshot: ActivitySnapshot) => void
  /** The connection to the manager was lost / is back. */
  onConnection?: (online: boolean) => void
}

/** Subscribe to the server's live stream (/ws): log lines and the activity state; reconnects until `stop()` is called. */
export function connectLogs(handlers: LogHandlers): () => void {
  let socket: WebSocket | undefined
  let stopped = false
  let retry: ReturnType<typeof setTimeout>
  const open = () => {
    socket = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`)
    socket.onopen = () => handlers.onConnection?.(true)
    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'log') handlers.onLine({ seq: data.seq, message: data.message, level: data.level ?? 'info', progress: data.progress, at: data.at ?? Date.now(), task: data.task })
        else if (data.type === 'history') handlers.onHistory(data.logs)
        else if (data.type === 'activity') handlers.onActivity(data)
      } catch {
        /* ignore malformed frames */
      }
    }
    socket.onclose = () => {
      handlers.onConnection?.(false)
      if (!stopped) retry = setTimeout(open, 2000)
    }
  }
  open()
  return () => {
    stopped = true
    clearTimeout(retry)
    socket?.close()
  }
}
