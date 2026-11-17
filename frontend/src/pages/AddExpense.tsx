// Add to a group's tab, at /groups/:id/add: scan a bill, add a quick expense (a cab, tickets),
// or, for flatmates (/groups/:id/add?monthly), a monthly bill like rent or electricity.
// With ?edit=<expense id> the same form corrects an expense that's already there.

import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, Navigate, useNavigate, useParams, useSearchParams } from 'react-router'
import { ApiError, addQuickExpense, addRecurring, editExpense, getGroup } from '../api'
import type { ActivityEntry, Group } from '../api'
import { rememberedMember } from '../groups'
import { parseRupees, toRupeesText } from '../money'
import { MemberToggles, PayerPicker, ShareSteppers } from '../people'
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

  // Editing: the expense to correct. A scanned bill keeps its item-by-item split, so it can't be.
  const editing = group.activity.find(
    (entry): entry is Expense => entry.type === 'expense' && entry.id === params.get('edit') && entry.source !== 'bill',
  )
  if (params.has('edit') && !editing) return <Navigate to={`/groups/${id}`} replace />

  const monthly = group.kind === 'flat' && params.has('monthly') && !editing
  // key: switching between a quick expense, a monthly bill and an edit starts a fresh form.
  return (
    <ExpenseForm
      key={editing?.id ?? String(monthly)}
      group={group}
      you={you}
      monthly={monthly}
      editing={editing}
      onDone={() => navigate(`/groups/${id}`)}
    />
  )
}

type Expense = Extract<ActivityEntry, { type: 'expense' }>

/** The shares behind an expense's amounts, as whole numbers: ₹300, ₹300, ₹600 -> 1, 1, 2.
 * Only the amounts are stored, so this reads them back against the smallest one. */
function sharesOf(owed: Record<string, number>): Record<string, number> {
  const smallest = Math.min(...Object.values(owed))
  return Object.fromEntries(
    Object.entries(owed).map(([person, amount]) => [person, Math.min(9, Math.max(1, Math.round(amount / smallest)))]),
  )
}

function ExpenseForm(props: { group: Group; you: string; monthly: boolean; editing?: Expense; onDone: () => void }) {
  const { group, you, monthly, editing } = props
  const was = editing && sharesOf(editing.owed) // the shares it had, when editing
  const [title, setTitle] = useState(editing?.title ?? '')
  const [amount, setAmount] = useState(editing ? toRupeesText(editing.total_paise).replace(/\.00$/, '') : '')
  const [changesMonthly, setChangesMonthly] = useState(false) // monthly bills: electricity rather than rent
  const [day, setDay] = useState(1)
  const [paidBy, setPaidBy] = useState(editing ? Object.keys(editing.paid)[0] : you)
  const [sharedBy, setSharedBy] = useState<string[]>(was ? group.members.filter((member) => member in was) : group.members)
  const [uneven, setUneven] = useState(was ? Object.values(was).some((share) => share !== 1) : false)
  const [weights, setWeights] = useState<Record<string, number>>(was ?? {})
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
        const expense = { title: title.trim(), amount_paise: paise, paid_by: paidBy, weights: shares, added_by: you }
        await (editing ? editExpense(group.id, editing.id, expense) : addQuickExpense(group.id, expense))
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
        title={editing ? 'Edit expense' : monthly ? 'Add a monthly bill' : `Add to ${group.name}`}
        action={
          <PrimaryButton type="submit" busy={busy} disabled={missing !== null}>
            {missing ?? (editing ? 'Save changes' : monthly ? 'Add monthly bill' : 'Add expense')}
          </PrimaryButton>
        }
      >
        {!monthly && !editing && (
          <Link
            to={`/scan?group=${group.id}`}
            className="mb-6 flex items-center gap-4 rounded-2xl border-2 border-dashed border-steel-dark bg-white/60 p-4"
          >
            <span aria-hidden className="text-3xl">🧾</span>
            <span>
              <span className="block font-display text-lg font-semibold">Scan a bill</span>
              <span className="text-sm text-muted">A restaurant bill, read item by item.</span>
            </span>
          </Link>
        )}

        <p className="mb-3 font-display text-lg font-semibold">{monthly ? 'The bill' : editing ? 'What and how much' : 'Or a quick expense'}</p>
        <div className="grid grid-cols-[1fr_8rem] gap-2">
          <input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder={monthly ? 'Rent' : 'Cab to Baga'}
            maxLength={60}
            aria-label="What it was for"
            className="min-w-0 tile px-4 py-3"
          />
          {needsAmount ? (
            <input
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
              inputMode="decimal"
              placeholder="₹ 0"
              aria-label="Amount in rupees"
              className="amount min-w-0 tile px-4 py-3 text-right"
            />
          ) : (
            <span className="flex items-center justify-center tile-soft px-2 text-center text-sm text-muted">
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
        <PayerPicker people={group.members} paidBy={paidBy} onChange={setPaidBy} you={you} />

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
