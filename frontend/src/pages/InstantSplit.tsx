// Instant split, at /instant: one amount, no photo and no AI. A cab, movie tickets, a gift.
// It's saved like a scanned bill, so it opens on the same result page with UPI buttons.

import { useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { ApiError, createInstantSplit } from '../api'
import { parseRupees } from '../money'
import { MemberToggles, PayerPicker, PeoplePicker, ShareSteppers } from '../people'
import { ErrorText, PrimaryButton, Screen } from '../ui'
import { useMe } from '../useMe'

export function InstantSplit() {
  const navigate = useNavigate()
  const [me] = useMe()
  const [name, setName] = useState('')
  const [amount, setAmount] = useState('')
  const [people, setPeople] = useState<string[]>([])
  const [payer, setPayer] = useState<string | null>(null) // null: whoever is first in the list
  const [leftOut, setLeftOut] = useState<string[]>([]) // people who don't share it, e.g. a gift for them
  const [uneven, setUneven] = useState(false)
  const [weights, setWeights] = useState<Record<string, number>>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Signed in: put them in first, while the list is still empty (same as the scan page).
  const myName = me.user?.name
  const [seenName, setSeenName] = useState(myName)
  if (myName !== seenName) {
    setSeenName(myName)
    if (myName && people.length === 0) setPeople([myName])
  }

  // Worked out from the lists on every render, so removing a person can't leave a stale choice.
  const paidBy = payer && people.includes(payer) ? payer : people[0]
  const sharedBy = people.filter((person) => !leftOut.includes(person))
  const shares = Object.fromEntries(sharedBy.map((person) => [person, uneven ? (weights[person] ?? 1) : 1]))
  const paise = parseRupees(amount)

  const missing = !name.trim()
    ? 'Say what it was for'
    : !paise
      ? 'Enter the amount'
      : people.length < 2
        ? 'Add at least two people'
        : sharedBy.length === 0
          ? 'Pick who shares it'
          : null

  async function save(event: FormEvent) {
    event.preventDefault()
    if (missing !== null || paise === null) return
    setBusy(true)
    setError(null)
    try {
      const split = await createInstantSplit({ name: name.trim(), amount_paise: paise, people, paid_by: paidBy, shares })
      navigate(`/split/${split.id}`)
    } catch (problem) {
      setError(problem instanceof ApiError ? problem.message : 'Couldn’t reach Split Rupya. Check your connection.')
      setBusy(false)
    }
  }

  return (
    <form onSubmit={save}>
      <Screen
        title="Instant split"
        action={
          <PrimaryButton type="submit" busy={busy} disabled={missing !== null}>
            {missing ?? 'Split it'}
          </PrimaryButton>
        }
      >
        <div className="grid grid-cols-[1fr_8rem] gap-2">
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Cab to the airport"
            maxLength={60}
            aria-label="What it was for"
            enterKeyHint="next"
            className="min-w-0 rounded-2xl bg-white px-4 py-3"
          />
          <input
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
            inputMode="decimal"
            placeholder="₹ 0"
            aria-label="Amount in rupees"
            className="amount min-w-0 rounded-2xl bg-white px-4 py-3 text-right"
          />
        </div>

        <p className="mt-6 mb-2 font-display text-lg font-semibold">Who’s in?</p>
        <PeoplePicker people={people} onChange={setPeople} suggestions={me.friends.map((friend) => friend.name)} />

        {people.length >= 2 && (
          <>
            <p className="mt-6 mb-2 font-display text-lg font-semibold">Who paid?</p>
            <PayerPicker people={people} paidBy={paidBy} onChange={setPayer} you={myName} />

            <div className="mt-6 mb-2 flex items-baseline justify-between">
              <p className="font-display text-lg font-semibold">Split between</p>
              <button type="button" onClick={() => setUneven(!uneven)} className="text-sm font-semibold underline">
                {uneven ? 'Split equally' : 'Uneven shares'}
              </button>
            </div>
            <MemberToggles
              members={people}
              chosen={sharedBy}
              onChange={(chosen) => setLeftOut(people.filter((person) => !chosen.includes(person)))}
            />
            {uneven && sharedBy.length > 0 && (
              <ShareSteppers
                people={sharedBy}
                members={people}
                weights={shares}
                onChange={(person, weight) => setWeights({ ...weights, [person]: weight })}
                paise={paise}
              />
            )}
          </>
        )}

        {error && <ErrorText>{error}</ErrorText>}
      </Screen>
    </form>
  )
}
