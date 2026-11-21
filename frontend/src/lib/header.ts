/** Header status texts, kept identical to the classic UI. */
import type { Device } from './api'

export type AdbState = 'connected' | 'disconnected' | 'unauthorized'

export function adbStatus(devices: Device[]): { state: AdbState; label: string } {
  const device = devices[0]
  if (!device) return { state: 'disconnected', label: 'No Phone Connected' }
  if (device.status === 'device') {
    const game = device.game_installed ? ' • BD2 Detected' : ''
    return { state: 'connected', label: `${device.model ?? device.id} (Ready${game})` }
  }
  if (device.status === 'unauthorized') return { state: 'unauthorized', label: `${device.id} (Check Phone for USB prompt)` }
  return { state: 'disconnected', label: `${device.id} (${device.status})` }
}

export const cacheLabel = (bytes: number, quality: string): string => `${(bytes / 1024 ** 3).toFixed(2)}GB - ${quality || 'HD'}`
