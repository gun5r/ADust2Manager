/** True when the frame is (nearly) transparent or black: sampled from a 16x16 copy. */
export function isBlank(canvas: HTMLCanvasElement): boolean {
  const probe = document.createElement('canvas')
  probe.width = probe.height = 16
  const ctx = probe.getContext('2d')
  if (!ctx) return false
  ctx.drawImage(canvas, 0, 0, 16, 16)
  const px = ctx.getImageData(0, 0, 16, 16).data
  let lit = 0
  for (let i = 0; i < px.length; i += 4) if (px[i + 3] > 20 && px[i] + px[i + 1] + px[i + 2] > 45) lit++
  return lit < 6
}
