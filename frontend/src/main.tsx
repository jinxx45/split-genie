import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// Fonts are bundled with the app (no request to Google). Browsers fetch only the character
// subsets a page uses: latin, plus the one holding the rupee sign.
import '@fontsource-variable/bricolage-grotesque/wght.css'
import '@fontsource-variable/dm-sans/wght.css'
import '@fontsource-variable/figtree/wght.css' // the Clean theme
import '@fontsource-variable/manrope/wght.css' // the Midnight theme
import '@fontsource/sora/latin-300.css'
import '@fontsource/sora/latin-700.css'
import './index.css'
import App from './App.tsx'
import { applyTheme, savedTheme } from './theme'

applyTheme(savedTheme()) // before the first paint, so the page doesn't flash another theme

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

hideSplash()

/** The splash in index.html: keep it up long enough to see the logo split (timed from when the
 * page started loading, so a slow load doesn't add to it), then fade it out and remove it. */
function hideSplash() {
  const splash = document.getElementById('splash')
  if (!splash) return
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  const minimumMs = reducedMotion ? 400 : 1100
  setTimeout(() => {
    splash.classList.add('done')
    splash.addEventListener('transitionend', () => splash.remove(), { once: true })
  }, Math.max(0, minimumMs - performance.now()))
}
