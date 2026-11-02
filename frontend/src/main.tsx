import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// Fonts are bundled with the app (no request to Google). Browsers fetch only the character
// subsets a page uses: latin, plus the one holding the rupee sign.
import '@fontsource/baloo-2/500.css'
import '@fontsource/baloo-2/600.css'
import '@fontsource/baloo-2/700.css'
import '@fontsource/hind/400.css'
import '@fontsource/hind/500.css'
import '@fontsource/hind/600.css'
import '@fontsource/sora/latin-300.css'
import '@fontsource/sora/latin-700.css'
import './index.css'
import App from './App.tsx'

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
