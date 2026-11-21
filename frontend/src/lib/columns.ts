/** Zoom sliders that only stop where the layout really changes: one stop per distinct number of columns that fits the field. */
export interface ColumnStop {
  cols: number
  /** Tile width that fills exactly `cols` columns. */
  size: number
}

export const columnsFor = (width: number, gap: number, size: number): number => Math.max(1, Math.floor((width + gap) / (size + gap)))

/** Stops from the smallest tile (most columns) to the largest (fewest), for tile sizes between `min` and `max` px. */
export function columnStops(width: number, gap: number, min: number, max: number): ColumnStop[] {
  const most = columnsFor(width, gap, min), fewest = columnsFor(width, gap, max)
  const stops: ColumnStop[] = []
  for (let cols = most; cols >= fewest; cols--) stops.push({ cols, size: Math.floor((width + gap) / cols) - gap })
  return stops
}

/** Index of the stop whose column count the current size produces. */
export function stopIndex(stops: ColumnStop[], width: number, gap: number, size: number): number {
  const cols = columnsFor(width, gap, size)
  const at = stops.findIndex((s) => s.cols <= cols)
  return at < 0 ? stops.length - 1 : at
}

/** Costume card sizes (px): below the minimum the three category counters and the installed number no longer fit on the picture. */
export const COSTUME_MIN = 130
export const COSTUME_MAX = 260
