// Google's own "Sign in with Google" button. Google's script draws it and hands us a signed
// token (the "credential"), which the backend checks before signing the user in.

import { useEffect, useRef, useState } from 'react'
import { getAuthConfig } from './api'

// The small part of Google's script that we use.
type GoogleIdentity = {
  accounts: {
    id: {
      initialize: (options: { client_id: string; callback: (response: { credential: string }) => void }) => void
      renderButton: (element: HTMLElement, options: Record<string, string | number>) => void
    }
  }
}
declare global {
  interface Window {
    google?: GoogleIdentity
  }
}

const SCRIPT_URL = 'https://accounts.google.com/gsi/client'

/** Renders nothing when sign-in isn't set up on the server (no client ID). */
export function GoogleButton({ onCredential }: { onCredential: (credential: string) => void }) {
  const container = useRef<HTMLDivElement>(null)
  const [clientId, setClientId] = useState('')
  // The latest callback, read when Google calls back. Kept in a ref so a new function on each
  // render doesn't redraw the button or load Google's script twice.
  const callback = useRef(onCredential)
  useEffect(() => {
    callback.current = onCredential
  })

  useEffect(() => {
    getAuthConfig()
      .then((config) => setClientId(config.google_client_id))
      .catch(() => setClientId(''))
  }, [])

  useEffect(() => {
    if (!clientId) return
    function draw() {
      if (!window.google || !container.current) return
      window.google.accounts.id.initialize({ client_id: clientId, callback: (response) => callback.current(response.credential) })
      window.google.accounts.id.renderButton(container.current, {
        theme: 'outline',
        size: 'large',
        shape: 'pill',
        text: 'signin_with',
        width: container.current.offsetWidth,
      })
    }
    if (window.google) return draw()
    const script = document.createElement('script')
    script.src = SCRIPT_URL
    script.async = true
    script.onload = draw
    document.head.appendChild(script)
  }, [clientId])

  return clientId ? <div ref={container} className="min-h-11 w-full" /> : null
}
