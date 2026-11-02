// The bottom of the home screen: sign in (optional), or, once signed in, your past splits.

import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { getAuthConfig, getMySplits, signInWithGoogle, signOut } from '../api'
import type { Me, SplitSummary } from '../api'
import { GoogleButton } from '../GoogleButton'
import { formatRupees } from '../money'
import { ErrorText } from '../ui'

export function Account({ me, setMe }: { me: Me; setMe: (me: Me) => void }) {
  const [error, setError] = useState<string | null>(null)
  // Google's client ID from the server; '' until it arrives, and when sign-in isn't set up.
  const [clientId, setClientId] = useState('')
  useEffect(() => {
    getAuthConfig()
      .then((config) => setClientId(config.google_client_id))
      .catch(() => setClientId(''))
  }, [])

  async function signIn(credential: string) {
    try {
      setMe(await signInWithGoogle(credential))
      setError(null)
    } catch {
      setError('Couldn’t sign you in. Please try again.')
    }
  }

  if (!me.user) {
    if (!clientId) return null // sign-in isn't set up on this server: nothing to offer
    return (
      <section className="mt-10 rounded-2xl bg-white/60 p-4">
        <p className="font-display text-lg font-semibold">Keep your splits and friends</p>
        <p className="mb-3 text-sm text-muted">Optional. Sign in to see past splits and add friends with a tap.</p>
        <GoogleButton clientId={clientId} onCredential={signIn} />
        {error && <ErrorText>{error}</ErrorText>}
      </section>
    )
  }

  return (
    <section className="mt-10">
      <History />
      <p className="mt-4 text-sm text-muted">
        Signed in as {me.user.email}.{' '}
        <button type="button" onClick={() => signOut().then(setMe)} className="font-semibold underline">
          Sign out
        </button>
      </p>
    </section>
  )
}

function History() {
  const [splits, setSplits] = useState<SplitSummary[] | null>(null)
  useEffect(() => {
    getMySplits()
      .then((response) => setSplits(response.splits))
      .catch(() => setSplits([]))
  }, [])

  if (!splits?.length) return null
  return (
    <>
      <h2 className="mb-3 font-display text-xl font-semibold">Your splits</h2>
      <ul className="space-y-2">
        {splits.map((split) => (
          <li key={split.id}>
            <Link to={`/split/${split.id}`} className="flex items-center gap-3 rounded-2xl bg-white p-4">
              <span className="min-w-0 flex-1">
                <span className="block truncate font-semibold">{split.title || split.people.join(', ')}</span>
                <span className="text-sm text-muted">
                  {shortDate(split.created_at)}, {status(split)}
                </span>
              </span>
              {split.total_paise !== null && <span className="amount text-lg font-semibold">{formatRupees(split.total_paise)}</span>}
            </Link>
          </li>
        ))}
      </ul>
    </>
  )
}

function status(split: SplitSummary): string {
  if (split.status !== 'done') return 'not finished'
  if (split.payments === 0) return 'nobody owes anything'
  if (split.paid === split.payments) return 'everyone has paid'
  return `${split.paid} of ${split.payments} paid`
}

/** "2026-11-02 09:14:05" (UTC from the server) -> "2 Nov" in the viewer's time zone. */
function shortDate(utc: string): string {
  return new Date(`${utc.replace(' ', 'T')}Z`).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
}
