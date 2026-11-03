// The account parts of the home screen: signing in (optional), who's signed in, and their
// splits and groups.

import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { getAuthConfig, getMyGroups, getMySplits, signInWithGoogle, signOut } from '../api'
import type { GroupSummary, Me, SplitSummary } from '../api'
import { GoogleButton } from '../GoogleButton'
import { formatRupees } from '../money'
import { balanceWords, KIND_NAMES } from '../groups'
import { Avatar, ErrorText, KindIcon } from '../ui'

/** Shows who's signed in, so it's clear the splits below are being saved, and a way out. */
export function SignedInBar({ me, setMe }: { me: Me; setMe: (me: Me) => void }) {
  if (!me.user) return null
  return (
    <div className="flex items-center gap-3 rounded-2xl bg-white/60 p-3">
      <Avatar name={me.user.name} color="var(--color-brand)" />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-semibold">Signed in as {me.user.name}</span>
        <span className="block truncate text-xs text-muted">{me.user.email}</span>
      </span>
      <button type="button" onClick={() => signOut().then(setMe)} className="text-sm font-semibold underline">
        Sign out
      </button>
    </div>
  )
}

/** Google's sign-in button with a line on why. Shows nothing if sign-in isn't set up on the server. */
export function SignInBox(props: { title: string; why: string; setMe: (me: Me) => void }) {
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
      props.setMe(await signInWithGoogle(credential))
      setError(null)
    } catch {
      setError('Couldn’t sign you in. Please try again.')
    }
  }

  if (!clientId) return null
  return (
    <section className="mt-10 rounded-2xl bg-white/60 p-4">
      <p className="font-display text-lg font-semibold">{props.title}</p>
      <p className="mb-3 text-sm text-muted">{props.why}</p>
      <GoogleButton clientId={clientId} onCredential={signIn} />
      {error && <ErrorText>{error}</ErrorText>}
    </section>
  )
}

/** The signed-in user's groups, with where they stand in each, and a way to start one. */
export function MyGroups() {
  const [groups, setGroups] = useState<GroupSummary[] | null>(null)
  useEffect(() => {
    getMyGroups()
      .then((response) => setGroups(response.groups))
      .catch(() => setGroups([]))
  }, [])

  return (
    <div className="mb-8">
      <div className="mb-3 flex items-baseline justify-between">
        <h2 className="font-display text-xl font-semibold">Your groups</h2>
        <Link to="/groups/new" className="font-display font-semibold underline">
          New group
        </Link>
      </div>
      {groups?.length === 0 && (
        <p className="rounded-2xl bg-white/60 p-4 text-sm text-muted">
          A group keeps a running tab for a trip, your flat, or friends you eat out with.
        </p>
      )}
      <ul className="space-y-2">
        {groups?.map((group) => (
          <li key={group.id}>
            <Link to={`/groups/${group.id}`} className="flex items-center gap-3 rounded-2xl bg-white p-4">
              <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-steel">
                <KindIcon kind={group.kind} />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate font-semibold">{group.name}</span>
                <span className="text-sm text-muted">
                  {KIND_NAMES[group.kind]}
                  {group.closed ? ', ended' : ''}
                </span>
              </span>
              <span className={`text-right text-sm ${group.balance_paise < 0 ? 'font-semibold' : 'text-muted'}`}>
                {balanceWords(group.balance_paise)}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function History() {
  const [splits, setSplits] = useState<SplitSummary[] | null>(null)
  useEffect(() => {
    getMySplits()
      .then((response) => setSplits(response.splits))
      .catch(() => setSplits([]))
  }, [])

  return (
    <div className="mb-8">
      <h2 className="mb-3 font-display text-xl font-semibold">Your splits</h2>
      {splits?.length === 0 && (
        <p className="rounded-2xl bg-white/60 p-4 text-sm text-muted">Bills you split show here, with who has paid.</p>
      )}
      <ul className="space-y-2">
        {splits?.map((split) => (
          <li key={split.id}>
            <Link to={`/split/${split.id}`} className="flex items-center gap-3 rounded-2xl bg-white p-4">
              <span className="min-w-0 flex-1">
                <span className="block truncate font-semibold">{split.name || split.people.join(', ')}</span>
                <span className="text-sm text-muted">
                  {shortDate(split.created_at)}, {status(split)}
                </span>
              </span>
              {split.total_paise !== null && <span className="amount text-lg font-semibold">{formatRupees(split.total_paise)}</span>}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}

function status(split: SplitSummary): string {
  if (split.status !== 'done') return 'not finished'
  if (split.payments === 0) return 'nobody owes anything'
  if (split.paid === split.payments) return 'everyone has paid'
  return `${split.paid} of ${split.payments} paid`
}

/** "2026-11-02T09:14:05.123456Z" (UTC from the server) -> "2 Nov" in the viewer's time zone.
 * Only the first 19 characters are read, so the older "2026-11-02 09:14:05" format works too. */
function shortDate(utc: string): string {
  const seconds = utc.slice(0, 19).replace(' ', 'T')
  return new Date(`${seconds}Z`).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
}
