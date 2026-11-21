/** The overlay that draws the touch spots of a dating scene over the player: numbered areas, or a dot with a soft glow. */
import { FIXED_RADIUS, HUGE_ZONE, spotArea, spotSize, type Hotspot } from '../../lib/dating'

export interface PlacedSpot { spot: Hotspot; x: number; y: number }

export interface MarkerOptions {
  opacity: number
  /** Opaque markers: the fills hide what is behind them. */
  solid: boolean
  hitRadius: number
  /** Every zone one small fixed circle, else the game's own size times `scale`. */
  fixed: boolean
  scale: number
  dots: boolean
  /** Plain dots without the soft zone glow. */
  plain: boolean
  /** Bone of the spot under the pointer, and of the one being dragged (it shrinks to a dot so it hides nothing around the cursor). */
  hover: string | null
  grabbed: string | null
  /** Which way a drag spot goes (null: any direction). */
  direction: (spot: Hotspot) => { x: number; y: number } | null
}

export const COLOURS = { touch: '56,189,248', follow: '74,222,128', drag: '168,85,247', hidden: '148,163,184', gyro: '251,146,60' }

/** A bone that travels faster than this (world units per second) is being parked or brought in by the game: its marker waits at the end. */
const JUMP_SPEED = 15000
const GUIDE = '253,224,71'
const GUIDE_RADIUS = 34

import type { GuideStyle } from '../../lib/touchPrefs'
import type { SpineCamera } from './spineTypes'
export type { GuideStyle }

/** Remembers where each bone was a frame ago, to tell a jump from the slow wiggle of a bone that follows the animation. */
class Travel {
  private seen = new Map<string, { x: number; y: number; at: number }>()

  jumped(bone: string, x: number, y: number): boolean {
    const now = performance.now(), before = this.seen.get(bone)
    this.seen.set(bone, { x, y, at: now })
    return !!before && (Math.hypot(x - before.x, y - before.y) * 1000) / Math.max(now - before.at, 1) > JUMP_SPEED
  }
}

export class SpotMarkers {
  private el: HTMLElement | undefined
  private travel = new Travel()

  get count(): number { return this.el?.children.length ?? 0 }

  /** Draw `spots` (world positions) over `stage`; with no spots every marker is removed. */
  draw(stage: HTMLElement, camera: SpineCamera, spots: PlacedSpot[], o: MarkerOptions): void {
    const canvas = stage.querySelector('canvas')
    if (!canvas) return
    if (!this.el) {
      this.el = document.createElement('div')
      this.el.style.cssText = 'position:absolute;inset:0;pointer-events:none;overflow:hidden'
      stage.appendChild(this.el)
    }
    const root = this.el
    root.style.opacity = String(o.solid ? 1 : o.opacity)
    const box = canvas.getBoundingClientRect(), origin = stage.getBoundingClientRect()
    const viewW = camera.viewportWidth * camera.zoom, viewH = camera.viewportHeight * camera.zoom
    const perWorld = box.width / viewW
    // big zones first so the small ones they hold stay visible on top
    const sorted = [...spots].sort((a, b) => spotArea(b.spot, o.hitRadius) - spotArea(a.spot, o.hitRadius))
    while (root.children.length > sorted.length) root.lastChild!.remove()
    while (root.children.length < sorted.length) root.appendChild(document.createElement('div'))
    sorted.forEach(({ spot, x, y }, i) => {
      const el = root.children[i] as HTMLElement
      let [w, h] = (o.fixed || Math.max(...spotSize(spot, o.hitRadius)) >= HUGE_ZONE ? [2 * FIXED_RADIUS, 2 * FIXED_RADIUS] : spotSize(spot, o.hitRadius).map((v) => v * o.scale)).map((v) => (v / 2) * perWorld)
      const px = box.left - origin.left + ((x - camera.position.x) / viewW + 0.5) * box.width
      const py = box.top - origin.top + (0.5 - (y - camera.position.y) / viewH) * box.height
      if (spot.bone === o.grabbed) { w = Math.min(w, 9); h = Math.min(h, 9) }
      const live = spot.reactions.length > 0 || !!spot.rule?.motion || !!spot.rule?.next, c = COLOURS[spot.kind]
      const away = this.travel.jumped(spot.bone, x, y) && spot.bone !== o.grabbed
      const hovered = live && spot.bone === o.hover
      const round = spot.kind !== 'drag' || o.fixed
      el.title = `${spot.bone} (${spot.reactions.length} reaction${spot.reactions.length === 1 ? '' : 's'})`
      const base = `position:absolute;left:${px - w}px;top:${py - h}px;width:${2 * w}px;height:${2 * h}px;border-radius:${round ? '50%' : '12px'};display:flex;align-items:center;justify-content:center;${away ? 'visibility:hidden;' : ''}`
      if (o.dots || o.plain) {
        // a dot marks the spot, an arrow the direction of a drag, a soft disc a drag in any direction. The area around it is a glow that
        // fades outward and gets fainter the bigger the area is; under the pointer the glow only gets stronger; no borders anywhere
        el.textContent = ''
        const d = 2 * Math.max(w, h), a = o.solid ? 1 : 0.34 * Math.min(1, Math.max(0.25, 90 / Math.max(d, 1))) * (hovered ? 1.6 : 1)
        el.style.cssText = base + (o.plain ? '' : `background:radial-gradient(closest-side,rgba(${c},${a}) 0%,rgba(${c},${a * 0.55}) 50%,rgba(${c},0) 100%)`) + (hovered ? ';z-index:5' : '')
        el.appendChild(glyph(spot, c, live || o.solid, o.direction, o.plain && hovered))
      } else {
        el.textContent = String(spot.id)
        el.style.cssText = base + `font:700 ${o.fixed ? 11 : 18}px var(--font-mono,monospace);color:${o.solid ? '#0b1220' : `rgb(${c})`};border:${hovered ? 3 : 1.5}px ${live ? 'solid' : 'dashed'} rgba(${c},${live || o.solid ? 0.9 : 0.4});background:rgba(${c},${o.solid ? 1 : hovered ? 0.4 : live ? 0.14 : 0.04})${hovered ? `;box-shadow:0 0 12px rgb(${c});z-index:5` : ''}`
      }
    })
  }
}

const GUIDE_CSS = `@keyframes bd2-guide-pulse{0%,100%{transform:scale(.7);opacity:.95}50%{transform:scale(1.2);opacity:.55}}
@keyframes bd2-guide-ring{0%{transform:scale(2.6);opacity:0}25%{opacity:1}100%{transform:scale(1);opacity:.9}}`

/** The guide circle (see lib/guide.ts) over the spot to touch next: `on` a circle that grows and shrinks, `alt` a ring that closes in on the spot. */
export class GuideMarker {
  private el: HTMLElement | undefined
  private travel = new Travel()

  get shown(): boolean { return !!this.el }

  /** Put the circle over `target` (a world position), or remove it. */
  draw(stage: HTMLElement, camera: SpineCamera, target: { bone: string; x: number; y: number } | null, style: GuideStyle): void {
    const canvas = stage.querySelector('canvas')
    if (!canvas || !target || style === 'off') return this.clear()
    const away = this.travel.jumped(target.bone, target.x, target.y)
    if (!this.el || this.el.dataset.style !== style) {
      this.clear()
      this.el = document.createElement('div')
      this.el.dataset.style = style
      const ring = `position:absolute;inset:0;border-radius:50%;border:4px solid rgb(${GUIDE});box-shadow:0 0 14px rgb(${GUIDE}),inset 0 0 10px rgba(${GUIDE},.6);`
      this.el.innerHTML = `<style>${GUIDE_CSS}</style>` + (style === 'on'
        ? `<div style="${ring}animation:bd2-guide-pulse 1.1s ease-in-out infinite"></div>`
        : `<div style="${ring}animation:bd2-guide-ring 1.3s ease-in infinite"></div><div style="position:absolute;left:42%;top:42%;width:16%;height:16%;border-radius:50%;background:rgb(${GUIDE});box-shadow:0 0 8px rgb(${GUIDE})"></div>`)
      stage.appendChild(this.el)
    }
    const box = canvas.getBoundingClientRect(), origin = stage.getBoundingClientRect()
    const viewW = camera.viewportWidth * camera.zoom, viewH = camera.viewportHeight * camera.zoom
    const px = box.left - origin.left + ((target.x - camera.position.x) / viewW + 0.5) * box.width
    const py = box.top - origin.top + (0.5 - (target.y - camera.position.y) / viewH) * box.height
    this.el.style.cssText = `position:absolute;left:${px - GUIDE_RADIUS}px;top:${py - GUIDE_RADIUS}px;width:${2 * GUIDE_RADIUS}px;height:${2 * GUIDE_RADIUS}px;pointer-events:none;z-index:6;${away ? 'visibility:hidden' : ''}`
  }

  clear(): void {
    this.el?.remove()
    this.el = undefined
  }
}

/** The small icon of the "dots" style: the dot, plus an arrow (drag with a direction) or a soft disc (drag in any direction). */
function glyph(spot: Hotspot, colour: string, live: boolean, direction: MarkerOptions['direction'], emphasized = false): HTMLElement {
  const root = document.createElement('div')
  root.style.cssText = 'position:relative;width:0;height:0'
  const part = (css: string, text = '') => {
    const el = document.createElement('div')
    el.style.cssText = `position:absolute;display:flex;align-items:center;justify-content:center;${css}`
    el.textContent = text
    root.appendChild(el)
  }
  const size = emphasized ? 18 : 14
  part(`left:-${size / 2}px;top:-${size / 2}px;width:${size}px;height:${size}px;border-radius:50%;background:rgba(${colour},${live || emphasized ? 0.85 : 0.25});box-shadow:0 0 ${emphasized ? 10 : 6}px rgba(${colour},${emphasized ? 1 : 0.8})`)
  if (spot.kind === 'drag' || spot.kind === 'follow') {
    const dir = direction(spot)
    if (dir) {
      // screen y points down; the arrow glyph points right at angle 0
      const angle = (-Math.atan2(dir.y, dir.x) * 180) / Math.PI
      part(`left:-14px;top:-9px;width:28px;height:18px;transform:rotate(${angle}deg) translateX(16px);font:700 16px sans-serif;color:rgb(${colour});text-shadow:0 0 3px #000`, '➤')
    } else part(`left:-15px;top:-15px;width:30px;height:30px;border-radius:50%;background:radial-gradient(closest-side,rgba(${colour},0.35),rgba(${colour},0))`)
  }
  return root
}
