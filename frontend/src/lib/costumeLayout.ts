/** Layout of the costume clusters on the shared column grid (`capacity` columns, one per costume card). */
export interface Piece<T> {
  /** Unique: the character's name, or `name#n` for the extra pieces of a wrapped character. */
  id: string
  name: string
  items: T[]
  /** Wrapped layout only: this piece goes on with a character whose first costumes sit earlier (it shows a back arrow). */
  continued: boolean
  /** Wrapped layout only: the character's other costumes go on further ahead (the piece shows a forward arrow). */
  continues: boolean
}

/**
 * One piece per character, or, with `wrap`, the costumes of all characters poured into rows of exactly `capacity` cards
 * (nothing is left blank at the end of a row except the last) so a character may be cut between two rows.
 */
export function clusterPieces<T>(groups: { name: string; items: T[] }[], capacity: number, wrap: boolean): Piece<T>[] {
  if (!wrap) return groups.map((g) => ({ id: g.name, name: g.name, items: g.items, continued: false, continues: false }))
  const cells = groups.flatMap((g) => g.items.map((item, index) => ({ name: g.name, item, index })))
  const pieces: Piece<T>[] = []
  const seen = new Map<string, number>()
  const width = Math.max(1, capacity)
  for (let at = 0; at < cells.length; at += width) {
    cells.slice(at, at + width).forEach((cell, i) => {
      const last = pieces.at(-1)
      if (i > 0 && last && last.name === cell.name) return void last.items.push(cell.item)
      const n = seen.get(cell.name) ?? 0
      seen.set(cell.name, n + 1)
      pieces.push({ id: n ? `${cell.name}#${n}` : cell.name, name: cell.name, items: [cell.item], continued: cell.index > 0, continues: false })
    })
  }
  const total = new Map(groups.map((g) => [g.name, g.items.length]))
  const taken = new Map<string, number>()
  for (const piece of pieces) {
    const done = (taken.get(piece.name) ?? 0) + piece.items.length
    taken.set(piece.name, done)
    piece.continues = done < (total.get(piece.name) ?? 0)
  }
  return pieces
}

/** The rows the pieces form (a piece spans min(its costumes, capacity) columns); used to put the mod box under the focused piece's row. */
export function pieceRows<T>(pieces: Piece<T>[], capacity: number): Piece<T>[][] {
  const rows: Piece<T>[][] = [[]]
  let used = 0
  for (const piece of pieces) {
    const span = Math.min(piece.items.length, capacity)
    if (used + span > capacity) { rows.push([]); used = 0 }
    used += span
    rows.at(-1)!.push(piece)
  }
  return rows
}
