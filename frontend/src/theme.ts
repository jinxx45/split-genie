// The app's look: Pop (default), Clean or Midnight. A theme is a set of CSS variables in
// index.css, switched by a data-theme attribute on <html> and remembered on this phone.

export const THEMES = ['pop', 'clean', 'midnight'] as const
export type Theme = (typeof THEMES)[number]

export const THEME_NAMES: Record<Theme, string> = { pop: 'Pop', clean: 'Clean', midnight: 'Midnight' }

const KEY = 'split-rupya:theme'

/** The theme chosen earlier on this phone. Storage can be blocked (private mode): then Pop. */
export function savedTheme(): Theme {
  try {
    const saved = localStorage.getItem(KEY)
    return THEMES.find((theme) => theme === saved) ?? 'pop'
  } catch {
    return 'pop'
  }
}

/** Switch the look now, and remember it. */
export function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme
  // The browser's own bar (address bar, status bar) follows the page colour.
  const page = getComputedStyle(document.documentElement).getPropertyValue('--color-paper').trim()
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', page)
  try {
    localStorage.setItem(KEY, theme)
  } catch {
    // Not saved: it lasts until the page is closed, which is fine.
  }
}
