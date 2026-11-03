// Add to a group's tab, at /groups/:id/add: scan a bill, add a quick expense (a cab, tickets),
// or, for flatmates (/groups/:id/add?monthly), a monthly bill like rent or electricity.

import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, Navigate, useNavigate, useParams, useSearchParams } from 'react-router'
import { ApiError, addQuickExpense, addRecurring, getGroup } from '../api'
import type { Group } from '../api'
import { personColor } from '../colors'
import { rememberedMember } from '../groups'
import { formatRupees, parseRupees } from '../money'
import { MemberToggles } from '../people'
import { ErrorText, PrimaryButton, Screen } from '../ui'
import { Reading } from './Reading'

export function AddExpense() {
  const { id = '' } = useParams()
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const [group, setGroup] = useState<Group | null>(null)
  const [error, setError] = useState<string | null>(null)
  const you = rememberedMember(id)

  useEffect(() => {
    getGroup(id)
      .then(setGroup)
      .catch((problem) => setError(problem instanceof ApiError ? problem.message : 'Couldn’t open the group.'))
  }, [id])

  if (!group) {
    return error ? (
      <Screen title="We couldn’t open this group">
        <p className="text-muted">{error}</p>
      </Screen>
    ) : (
      <Reading message="Opening your group…" />
    )
  }
  if (!you || !group.members.includes(you)) {
    return <Navigate to={`/groups/${id}`} replace /> // the group page asks who they are first
  }

  const monthly = group.kind === 'flat' && params.has('monthly')
  // key: switching between a quick expense and a monthly bill starts a fresh form.
  return (
    <ExpenseForm key={String(monthly)} group={group} you={you} monthly={monthly} onDone={() => navigate(`/groups/${id}`)} />
  )
}

function ExpenseForm(props: { group: Group; you: string; monthly: boolean; onDone: () => void }) {
  const { group, you, monthly } = props
  const [title, setTitle] = useState('')
  const [amount, setAmount] = useState('')
  const [changesMonthly, setChangesMonthly] = useState(false) // monthly bills: electricity rather than rent
  const [day, setDay] = useState(1)
  const [paidBy, setPaidBy] = useState(you)
  const [sharedBy, setSharedBy] = useState<string[]>(group.members)
  const [uneven, setUneven] = useState(false)
  const [weights, setWeights] = useState<Record<string, number>>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const paise = parseRupees(amount)
  const needsAmount = !monthly || !changesMonthly
  const shares = Object.fromEntries(sharedBy.map((person) => [person, uneven ? (weights[person] ?? 1) : 1]))
  const missing = !title.trim()
    ? 'Say what it was for'
    : needsAmount && !paise
      ? 'Enter the amount'
      : sharedBy.length === 0
        ? 'Pick who shares it'
        : null

  async function save(event: FormEvent) {
    event.preventDefault()
    if (missing !== null) return
    setBusy(true)
    setError(null)
    try {
      if (monthly) {
        const bill = { title: title.trim(), amount_paise: changesMonthly ? null : paise, paid_by: paidBy, weights: shares, day_of_month: day }
        await addRecurring(group.id, bill)
      } else {
        if (paise === null) return // can't happen: the button stays off until there's an amount
        await addQuickExpense(group.id, { title: title.trim(), amount_paise: paise, paid_by: paidBy, weights: shares, added_by: you })
      }
      props.onDone()
    } catch (problem) {
      setError(problem instanceof ApiError ? problem.message : 'Couldn’t reach Split Rupya. Check your connection.')
      setBusy(false)
    }
  }

  return (
    <form onSubmit={save}>
      <Screen
        title={monthly ? 'Add a monthly bill' : `Add to ${group.name}`}
        action={
          <PrimaryButton type="submit" busy={busy} disabled={missing !== null}>
            {missing ?? (monthly ? 'Add monthly bill' : 'Add expense')}
          </PrimaryButton>
        }
      >
        {!monthly && (
          <Link
            to={`/?group=${group.id}`}
            className="mb-6 flex items-center gap-4 rounded-2xl border-2 border-dashed border-steel-dark bg-white/60 p-4"
          >
            <span aria-hidden className="text-3xl">🧾</span>
            <span>
              <span className="block font-display text-lg font-semibold">Scan a bill</span>
              <span className="text-sm text-muted">A restaurant bill, read item by item.</span>
            </span>
          </Link>
        )}

        <p className="mb-3 font-display text-lg font-semibold">{monthly ? 'The bill' : 'Or a quick expense'}</p>
        <div className="grid grid-cols-[1fr_8rem] gap-2">
          <input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder={monthly ? 'Rent' : 'Cab to Baga'}
            maxLength={60}
            aria-label="What it was for"
            className="min-w-0 rounded-2xl bg-white px-4 py-3"
          />
          {needsAmount ? (
            <input
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
              inputMode="decimal"
              placeholder="₹ 0"
              aria-label="Amount in rupees"
              className="amount min-w-0 rounded-2xl bg-white px-4 py-3 text-right"
            />
          ) : (
            <span className="flex items-center justify-center rounded-2xl bg-white/60 px-2 text-center text-sm text-muted">
              Asked each month
            </span>
          )}
        </div>

        {monthly && (
          <div className="mt-4 space-y-3">
            <div role="radiogroup" aria-label="Amount" className="inline-flex rounded-full bg-white p-1 text-sm font-semibold">
              {[
                { value: false, label: 'Same every month' },
                { value: true, label: 'Changes each month' },
              ].map((option) => (
                <button
                  key={option.label}
                  type="button"
                  role="radio"
                  aria-checked={changesMonthly === option.value}
                  onClick={() => setChangesMonthly(option.value)}
                  className={`rounded-full px-3 py-1 ${changesMonthly === option.value ? 'bg-brand text-white' : 'text-muted'}`}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <label className="flex items-center gap-3">
              <span className="text-muted">Due on the</span>
              <select
                value={day}
                onChange={(event) => setDay(Number(event.target.value))}
                className="rounded-xl bg-white px-3 py-2"
              >
                {Array.from({ length: 28 }, (_, index) => index + 1).map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
              <span className="text-muted">of each month</span>
            </label>
          </div>
        )}

        <p className="mt-6 mb-2 font-display text-lg font-semibold">Who paid?</p>
        <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Who paid">
          {group.members.map((member) => {
            const on = paidBy === member
            const color = personColor(group.members, member)
            return (
              <button
                key={member}
                type="button"
                role="radio"
                aria-checked={on}
                onClick={() => setPaidBy(member)}
                className="rounded-full border-2 px-3 py-1.5 text-sm font-semibold"
                style={{ borderColor: on ? color : 'var(--color-steel-dark)', background: on ? color : '#fff', color: on ? '#fff' : 'var(--color-muted)' }}
              >
                {member === you ? `${member} (you)` : member}
              </button>
            )
          })}
        </div>

        <div className="mt-6 mb-2 flex items-baseline justify-between">
          <p className="font-display text-lg font-semibold">Split between</p>
          <button type="button" onClick={() => setUneven(!uneven)} className="text-sm font-semibold underline">
            {uneven ? 'Split equally' : 'Uneven shares'}
          </button>
        </div>
        <MemberToggles members={group.members} chosen={sharedBy} onChange={setSharedBy} />

        {uneven && sharedBy.length > 0 && (
          <ShareSteppers
            people={sharedBy}
            members={group.members}
            weights={shares}
            onChange={(person, weight) => setWeights({ ...weights, [person]: weight })}
            paise={needsAmount ? paise : null}
          />
        )}

        {error && <ErrorText>{error}</ErrorText>}
      </Screen>
    </form>
  )
}

/** Uneven shares: e.g. a bigger room pays 2 shares. Shows what each share comes to. */
function ShareSteppers(props: {
  people: string[]
  members: string[]
  weights: Record<string, number>
  onChange: (person: string, weight: number) => void
  paise: number | null
}) {
  const total = Object.values(props.weights).reduce((sum, weight) => sum + weight, 0)
  return (
    <ul className="mt-3 divide-y divide-steel rounded-2xl bg-white px-4">
      {props.people.map((person) => {
        const weight = props.weights[person]
        return (
          <li key={person} className="flex items-center gap-3 py-2">
            <span className="size-2.5 rounded-full" style={{ background: personColor(props.members, person) }} aria-hidden />
            <span className="flex-1">
              {person}
              {props.paise ? (
                <span className="block text-sm text-muted">about {formatRupees(Math.round((props.paise * weight) / total))}</span>
              ) : null}
            </span>
            <button
              type="button"
              aria-label={`One share less for ${person}`}
              disabled={weight <= 1}
              onClick={() => props.onChange(person, weight - 1)}
              className="flex size-9 items-center justify-center rounded-full bg-steel font-display text-xl font-semibold disabled:opacity-35"
            >
              −
            </button>
            <span className="amount w-18 text-center whitespace-nowrap">
              {weight} share{weight > 1 ? 's' : ''}
            </span>
            <button
              type="button"
              aria-label={`One share more for ${person}`}
              disabled={weight >= 9}
              onClick={() => props.onChange(person, weight + 1)}
              className="flex size-9 items-center justify-center rounded-full bg-steel font-display text-xl font-semibold disabled:opacity-35"
            >
              +
            </button>
          </li>
        )
      })}
    </ul>
  )
}
