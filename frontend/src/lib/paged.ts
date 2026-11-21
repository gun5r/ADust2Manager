import type { Mod, ModPage, ModQuery } from './api'

export const PAGE_SIZE = 120

type Fetcher = (query: ModQuery, offset: number, limit: number) => Promise<ModPage>

/** Sparse, page-backed list: callers ask for index ranges and get items as pages arrive. */
export class PagedMods {
  total = 0
  items: (Mod | undefined)[] = []
  private pending = new Set<number>()
  private generation = 0

  constructor(
    private fetcher: Fetcher,
    private query: ModQuery,
    private onChange: () => void,
  ) {}

  /** Start over for a new query; returns after the first page so `total` is known. */
  async reset(query: ModQuery): Promise<void> {
    this.query = query
    this.generation++
    this.items = []
    this.pending.clear()
    const generation = this.generation
    const page = await this.fetcher(query, 0, PAGE_SIZE)
    if (generation !== this.generation) return
    this.total = page.total
    this.items = new Array(page.total)
    this.store(page)
  }

  ensure(start: number, end: number): void {
    const last = Math.min(end, this.total - 1)
    for (let page = Math.floor(Math.max(0, start) / PAGE_SIZE); page * PAGE_SIZE <= last; page++) this.load(page)
  }

  private load(page: number): void {
    const offset = page * PAGE_SIZE
    if (this.pending.has(page) || this.items[offset]) return
    this.pending.add(page)
    const generation = this.generation
    this.fetcher(this.query, offset, PAGE_SIZE)
      .then((result) => generation === this.generation && this.store(result))
      .catch(() => this.pending.delete(page))
  }

  private store(page: ModPage): void {
    page.mods.forEach((mod, i) => (this.items[page.offset + i] = mod))
    this.pending.delete(page.offset / PAGE_SIZE)
    this.onChange()
  }
}
