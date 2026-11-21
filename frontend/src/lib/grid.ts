export interface GridLayout {
  columns: number
  rows: number
  rowHeight: number
  totalHeight: number
}

export function layoutGrid(width: number, total: number, minCard = 190, gap = 12, cardHeight = 250): GridLayout {
  const columns = Math.max(1, Math.floor((width + gap) / (minCard + gap)))
  const rows = Math.ceil(total / columns)
  const rowHeight = cardHeight + gap
  return { columns, rows, rowHeight, totalHeight: rows * rowHeight }
}

/** Item index range [start, end] to render for a scroll position, with `buffer` extra rows each side. */
export function visibleRange(layout: GridLayout, scrollTop: number, viewport: number, total: number, buffer = 2) {
  if (total === 0) return { start: 0, end: -1 }
  const firstRow = Math.max(0, Math.floor(scrollTop / layout.rowHeight) - buffer)
  const lastRow = Math.min(layout.rows - 1, Math.ceil((scrollTop + viewport) / layout.rowHeight) + buffer)
  return { start: firstRow * layout.columns, end: Math.min(total - 1, (lastRow + 1) * layout.columns - 1) }
}
