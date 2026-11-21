/** Icon (Lucide, see ui/icons.ts) and colour of each mod category, shared by every category menu. */
export const CATEGORY_ICON: Record<string, { icon: string; color: string }> = {
  idle: { icon: 'armchair', color: 'var(--cat-idle)' },
  cut: { icon: 'clapperboard', color: 'var(--cat-cut)' },
  dating: { icon: 'heart', color: 'var(--cat-dating)' },
  illust: { icon: 'palette', color: 'var(--cat-illust)' },
  multi: { icon: 'trees', color: 'var(--cat-multi)' },
  other: { icon: 'package', color: 'var(--cat-other)' },
}

/** The badges on character and costume portraits: one look (icon + number) and one set of colours for both lists. */
export type BadgeKind = 'idle' | 'cut' | 'rest' | 'installed' | 'queued'
export const BADGE_STYLE: Record<BadgeKind, { icon: string; color: string; label: string }> = {
  idle: { ...CATEGORY_ICON.idle, label: 'idle mods' },
  cut: { ...CATEGORY_ICON.cut, label: 'skills' },
  rest: { ...CATEGORY_ICON.other, label: 'illustrations and other mods' },
  installed: { icon: 'circle-check', color: 'var(--cat-installed)', label: 'marked as installed' },
  queued: { icon: 'list-checks', color: 'var(--cat-queued)', label: 'in the processing queue' },
}
