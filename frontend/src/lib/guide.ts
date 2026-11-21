/**
 * The touch guide of a dating scene: which spot to touch next to reach the end of the phase.
 *
 * Touching a spot can bring other spots on screen (the game parks them far away until then): `reveals` maps a spot's bone to the bones
 * its reaction brings in. The way out of a phase is the chain of those links that ends at the spot whose action moves the scene on,
 * so the guide shows, among the spots that are on screen right now, the one closest to that end. A missed touch only changes which
 * spots are on screen, so the guide finds the way on from wherever the scene is.
 */
export interface GuideSpot { bone: string; id: number; ends: boolean; onScreen: boolean; /** The tool in use can touch it. */ usable: boolean }

export type Reveals = Map<string, string[]>

/** Touches left until the end of the phase, per bone (0 = the ending spot itself); bones with no way to the end are missing. */
export function stepsToEnd(spots: GuideSpot[], reveals: Reveals): Map<string, number> {
  const steps = new Map<string, number>(spots.filter((s) => s.ends).map((s) => [s.bone, 0]))
  // relax until nothing improves: chains are a handful of spots long
  for (let changed = true, round = 0; changed && round <= spots.length; round++) {
    changed = false
    for (const { bone } of spots) {
      const via = (reveals.get(bone) ?? []).map((b) => steps.get(b)).filter((n): n is number => n !== undefined)
      if (!via.length) continue
      const next = Math.min(...via) + 1
      if (next < (steps.get(bone) ?? Infinity)) { steps.set(bone, next); changed = true }
    }
  }
  return steps
}

/** The bone to point at: the on-screen spot with the fewest touches left (on a tie one the tool in use can touch, then the lowest id), or null when none leads to the end. */
export function guideTarget(spots: GuideSpot[], reveals: Reveals): string | null {
  const steps = stepsToEnd(spots, reveals)
  const options = spots.filter((s) => s.onScreen && steps.has(s.bone)).sort((a, b) => steps.get(a.bone)! - steps.get(b.bone)! || Number(b.usable) - Number(a.usable) || a.id - b.id)
  return options[0]?.bone ?? null
}
