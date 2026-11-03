// Start a group: Friends, Trip or Flatmates. Needs sign-in, so the group belongs to an account.

import { useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { ApiError, createGroup } from '../api'
import type { GroupKind } from '../api'
import { KIND_NAMES, rememberMember } from '../groups'
import { PeoplePicker } from '../people'
import { ErrorText, KindIcon, PrimaryButton, Screen } from '../ui'
import { useMe } from '../useMe'
import { SignInBox } from './Account'

const KINDS: { kind: GroupKind; about: string; example: string }[] = [
  { kind: 'friends', about: 'An ongoing tab for people you often split with.', example: 'Lunch gang' },
  { kind: 'trip', about: 'Every bill of a trip, settled once at the end.', example: 'Goa 2026' },
  { kind: 'flat', about: 'Rent and bills, month after month.', example: 'Flat 4B' },
]

export function NewGroup() {
  const navigate = useNavigate()
  const [me, setMe] = useMe()
  const [kind, setKind] = useState<GroupKind>('friends')
  const [name, setName] = useState('')
  const [members, setMembers] = useState<string[]>([])
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Once signed in, add them as the first member (while the list is still empty).
  const myName = me.user?.name
  const [seenName, setSeenName] = useState(myName)
  if (myName !== seenName) {
    setSeenName(myName)
    if (myName && members.length === 0) setMembers([myName])
  }

  if (!me.user) {
    return (
      <Screen title="New group">
        <p className="text-muted">
          Groups keep a running tab for weeks or months, so they belong to an account. Sign in to start one. The others
          in the group never need to.
        </p>
        <SignInBox title="Sign in to start a group" why="With your Google account." setMe={setMe} />
      </Screen>
    )
  }
  const you = me.user.name

  async function create(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const dates = kind === 'trip' && start && end ? { start_date: start, end_date: end } : {}
      const group = await createGroup({ kind, name: name.trim(), members, me: you, ...dates })
      rememberMember(group.id, you)
      navigate(`/groups/${group.id}`)
    } catch (problem) {
      setError(problem instanceof ApiError ? problem.message : 'Couldn’t reach Split Rupya. Check your connection.')
      setBusy(false)
    }
  }

  const missing = !name.trim()
    ? 'Name the group'
    : members.length < 2
      ? 'Add at least one more person'
      : !members.includes(you)
        ? `Keep yourself (${you}) in the group`
        : null
  const example = KINDS.find((option) => option.kind === kind)?.example

  return (
    <form onSubmit={create}>
      <Screen
        title="New group"
        action={
          <PrimaryButton type="submit" busy={busy} disabled={missing !== null}>
            {missing ?? `Start ${KIND_NAMES[kind].toLowerCase()} group`}
          </PrimaryButton>
        }
      >
        <div role="radiogroup" aria-label="Kind of group" className="space-y-2">
          {KINDS.map((option) => (
            <button
              key={option.kind}
              type="button"
              role="radio"
              aria-checked={kind === option.kind}
              onClick={() => setKind(option.kind)}
              className={`flex w-full items-center gap-3 rounded-2xl border-2 p-4 text-left transition ${
                kind === option.kind ? 'border-brand bg-white' : 'border-transparent bg-white/60'
              }`}
            >
              <span
                className={`flex size-10 shrink-0 items-center justify-center rounded-full ${
                  kind === option.kind ? 'bg-brand text-paper' : 'bg-steel'
                }`}
              >
                <KindIcon kind={option.kind} />
              </span>
              <span>
                <span className="block font-display text-lg font-semibold">{KIND_NAMES[option.kind]}</span>
                <span className="text-sm text-muted">{option.about}</span>
              </span>
            </button>
          ))}
        </div>

        <label className="mt-6 block">
          <span className="font-display text-lg font-semibold">Name</span>
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder={example}
            maxLength={60}
            className="mt-2 w-full rounded-2xl bg-white px-4 py-3"
          />
        </label>

        {kind === 'trip' && (
          <div className="mt-6 grid grid-cols-2 gap-3">
            <label>
              <span className="font-display text-lg font-semibold">From</span>
              <input
                type="date"
                value={start}
                onChange={(event) => setStart(event.target.value)}
                className="mt-2 w-full rounded-2xl bg-white px-3 py-3"
              />
            </label>
            <label>
              <span className="font-display text-lg font-semibold">To</span>
              <input
                type="date"
                value={end}
                min={start || undefined}
                onChange={(event) => setEnd(event.target.value)}
                className="mt-2 w-full rounded-2xl bg-white px-3 py-3"
              />
            </label>
            <p className="col-span-2 -mt-1 text-sm text-muted">Optional.</p>
          </div>
        )}

        <p className="mt-6 mb-2 font-display text-lg font-semibold">Who’s in it?</p>
        <PeoplePicker people={members} onChange={setMembers} suggestions={me.friends.map((friend) => friend.name)} />
        <p className="mt-2 text-sm text-muted">They’ll join with a link you send on WhatsApp. No sign-in needed.</p>

        {error && <ErrorText>{error}</ErrorText>}
      </Screen>
    </form>
  )
}
