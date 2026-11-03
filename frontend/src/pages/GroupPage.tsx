// One group, at /groups/:id. Where you stand, how to settle up, and everything in the tab.
// Trips add dates, trip cost and "End trip"; flatmates add monthly bills and a per-month view.
// Anyone with the link can use it: they pick their name once (remembered on this phone).

import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'
import {
  ApiError,
  addRepayment,
  deleteExpense,
  deleteRepayment,
  enterMonthAmount,
  getGroup,
  joinGroup,
  setGroupClosed,
  setGroupUpiId,
  stopRecurring,
} from '../api'
import type { ActivityEntry, Group } from '../api'
import { personColor } from '../colors'
import { balanceWords, dateRange, KIND_NAMES, rememberedMember, rememberMember } from '../groups'
import { formatRupees, parseRupees } from '../money'
import { UPI_ID, upiLink } from '../upi'
import { Avatar, ErrorText, KindIcon, Paper, Screen, WhoAreYou } from '../ui'
import { Reading } from './Reading'

export function GroupPage() {
  const { id = '' } = useParams()
  const [params, setParams] = useSearchParams()
  const [group, setGroup] = useState<Group | null>(null)
  const [member, setMember] = useState<string | null>(() => rememberedMember(id))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getGroup(id)
      .then(setGroup)
      .catch((problem) => setError(message(problem)))
    // Coming back to the app (from WhatsApp or a UPI app): show what others added meanwhile.
    function reload() {
      if (document.visibilityState === 'visible') getGroup(id).then(setGroup).catch(() => {})
    }
    document.addEventListener('visibilitychange', reload)
    return () => document.removeEventListener('visibilitychange', reload)
  }, [id])

  /** Run a change, then show the group the server sends back. */
  async function act(call: () => Promise<Group>) {
    setBusy(true)
    setError(null)
    try {
      setGroup(await call())
    } catch (problem) {
      setError(message(problem))
    } finally {
      setBusy(false)
    }
  }

  if (!group) {
    return error ? (
      <Screen title="We couldn’t open this group">
        <p className="text-muted">{error}</p>
      </Screen>
    ) : (
      <Reading message="Opening your group…" />
    )
  }

  if (!member || !group.members.includes(member) || params.has('who')) {
    const choose = (person: string) => {
      rememberMember(group.id, person)
      setMember(person)
      setParams({})
      joinGroup(group.id, person).then(setGroup).catch(() => {}) // if signed in, it joins "Your groups"
    }
    return <WhoAreYou people={group.members} why="see the group’s tab" onChoose={choose} />
  }

  const you = member
  const ctx = { group, you, busy, act }
  const addLink = `/groups/${group.id}/add`

  return (
    <Screen
      title={group.name}
      action={
        !group.closed && (
          <Link
            to={addLink}
            className="block w-full rounded-2xl bg-brand px-5 py-4 text-center font-display text-lg font-semibold text-white active:scale-[0.98]"
          >
            Add expense
          </Link>
        )
      }
    >
      <p className="-mt-3 mb-5 flex items-center gap-2 text-muted">
        <KindIcon kind={group.kind} className="size-4" />
        {KIND_NAMES[group.kind]}
        {group.kind === 'trip' && dateRange(group.start_date, group.end_date) && `, ${dateRange(group.start_date, group.end_date)}`}
        <span className="ml-auto text-sm">
          You’re {you}.{' '}
          <button type="button" onClick={() => setParams({ who: '' })} className="underline">
            Not you?
          </button>
        </span>
      </p>

      {group.closed && (
        <p className="mb-4 rounded-2xl bg-saffron-soft p-4">
          <span className="font-semibold">This trip has ended.</span> Settle up below; no new expenses can be added.
        </p>
      )}

      <Standing {...ctx} />
      {group.kind === 'flat' && <DueBills {...ctx} />}
      <SettleUp {...ctx} />
      <Invite group={group} />
      {group.kind === 'trip' && group.is_owner && <TripControls {...ctx} />}
      {group.kind === 'flat' && <MonthlyBills {...ctx} addLink={`${addLink}?monthly`} />}
      {group.kind === 'flat' && <Months {...ctx} />}
      <Activity {...ctx} />
      {error && <ErrorText>{error}</ErrorText>}
    </Screen>
  )
}

type Ctx = { group: Group; you: string; busy: boolean; act: (call: () => Promise<Group>) => void }

/** Your balance, and for trips what it cost you. */
function Standing({ group, you }: Ctx) {
  const balance = group.balances[you] ?? 0
  return (
    <Paper>
      <div className="text-center">
        <p className="text-muted">{group.activity.length ? 'Where you stand' : 'Nothing added yet'}</p>
        <p className={`amount text-3xl font-bold ${balance < 0 ? 'text-chilli' : ''}`}>{balanceWords(balance)}</p>
        {group.kind === 'trip' && group.total_paise > 0 && (
          <p className="mt-1 text-muted">
            The trip cost you {formatRupees(group.spent[you] ?? 0)}, everyone together {formatRupees(group.total_paise)}
          </p>
        )}
        {group.kind !== 'trip' && group.total_paise > 0 && (
          <p className="mt-1 text-muted">Your share so far {formatRupees(group.spent[you] ?? 0)}</p>
        )}
      </div>
    </Paper>
  )
}

/** The fewest payments that clear everyone, with pay and "mark as paid" buttons. */
function SettleUp({ group, you, busy, act }: Ctx) {
  const [upiId, setUpiId] = useState('')
  if (group.settle_up.length === 0) return null
  const youReceive = group.settle_up.some((payment) => payment.receiver === you)
  const mark = (sender: string, receiver: string, amount: number) =>
    act(() => addRepayment(group.id, { sender, receiver, amount_paise: amount, by: you }))

  return (
    <Section title="Settle up">
      <ul className="space-y-2">
        {group.settle_up.map((payment) => {
          const receiverUpi = group.upi_ids[payment.receiver]
          return (
            <li key={`${payment.sender}-${payment.receiver}`} className="rounded-2xl bg-white p-4">
              <div className="flex items-center gap-3">
                <Avatar name={payment.sender} color={personColor(group.members, payment.sender)} />
                <span className="flex-1 leading-snug">
                  <span className="font-semibold">{payment.sender === you ? 'You' : payment.sender}</span>
                  <span className="text-muted"> {payment.sender === you ? 'pay' : 'pays'} </span>
                  <span className="font-semibold">{payment.receiver === you ? 'you' : payment.receiver}</span>
                </span>
                <span className="amount text-xl font-bold">{formatRupees(payment.amount_paise)}</span>
              </div>
              <div className="mt-3 flex items-center gap-2">
                {payment.sender === you && receiverUpi && (
                  <a
                    href={upiLink(receiverUpi, payment.receiver, payment.amount_paise, group.name)}
                    className="flex-1 rounded-xl bg-brand py-2.5 text-center font-display font-semibold text-white"
                  >
                    Pay {formatRupees(payment.amount_paise)}
                  </a>
                )}
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => mark(payment.sender, payment.receiver, payment.amount_paise)}
                  className="rounded-xl bg-steel px-3 py-2.5 font-display font-semibold"
                >
                  {payment.receiver === you ? 'I got it' : payment.sender === you ? 'I’ve paid' : 'Mark as paid'}
                </button>
              </div>
            </li>
          )
        })}
      </ul>
      {youReceive && !group.upi_ids[you] && (
        <div className="mt-3 rounded-2xl bg-white p-4">
          <label className="block text-sm text-muted" htmlFor="my-upi">
            Your UPI ID, so others get a pay button
          </label>
          <div className="mt-1 flex gap-2">
            <input
              id="my-upi"
              value={upiId}
              onChange={(event) => setUpiId(event.target.value)}
              placeholder="name@okbank"
              autoCapitalize="none"
              autoCorrect="off"
              className="min-w-0 flex-1 rounded-lg bg-steel px-3 py-2"
            />
            <button
              type="button"
              disabled={busy || !UPI_ID.test(upiId.trim())}
              onClick={() => act(() => setGroupUpiId(group.id, you, upiId.trim()))}
              className="rounded-lg bg-brand px-4 font-display font-semibold text-white disabled:bg-muted/40"
            >
              Save
            </button>
          </div>
        </div>
      )}
    </Section>
  )
}

/** One WhatsApp message with the group's link; each member picks their name when they open it. */
function Invite({ group }: { group: Group }) {
  const link = `${window.location.origin}/groups/${group.id}?who`
  const lines = group.closed
    ? [
        `*${group.name}* has ended. Here's how to settle up:`,
        ...group.settle_up.map((p) => `${p.sender} pays ${p.receiver} ${formatRupees(p.amount_paise)}`),
        '',
        'Open it to pay in one tap:',
        link,
      ]
    : [`Join *${group.name}* on Split Rupya to add expenses and see who owes what:`, link]
  return (
    <a
      href={`https://wa.me/?text=${encodeURIComponent(lines.join('\n'))}`}
      target="_blank"
      rel="noreferrer"
      className="mt-6 block rounded-2xl bg-white px-4 py-3 text-center font-display font-semibold"
    >
      {group.closed ? 'Share the final settle-up on WhatsApp' : 'Invite on WhatsApp'}
    </a>
  )
}

/** Trips: end the trip (no new expenses, everyone settles up), or reopen it. Creator only. */
function TripControls({ group, busy, act }: Ctx) {
  const [confirming, setConfirming] = useState(false)
  if (group.closed) {
    return (
      <button
        type="button"
        disabled={busy}
        onClick={() => act(() => setGroupClosed(group.id, false))}
        className="mt-3 w-full py-2 text-sm font-semibold text-muted underline"
      >
        Reopen the trip
      </button>
    )
  }
  return (
    <button
      type="button"
      disabled={busy}
      onClick={() => (confirming ? act(() => setGroupClosed(group.id, true)) : setConfirming(true))}
      className={`mt-3 w-full rounded-2xl py-3 font-display font-semibold ${confirming ? 'bg-chilli text-white' : 'bg-white'}`}
    >
      {confirming ? 'Tap again to end the trip' : 'End trip and settle up'}
    </button>
  )
}

/** Flatmates: bills that change monthly and need this month's amount. */
function DueBills({ group, you, busy, act }: Ctx) {
  const [amounts, setAmounts] = useState<Record<string, string>>({})
  if (!group.due?.length) return null
  return (
    <Section title="Needs this month’s amount">
      <ul className="space-y-2">
        {group.due.map((due) => {
          const key = `${due.recurring_id}-${due.month}`
          const paise = parseRupees(amounts[key] ?? '')
          return (
            <li key={key} className="rounded-2xl bg-saffron-soft p-4">
              <p className="font-semibold">
                {due.title}, {due.label}
              </p>
              <p className="text-sm text-muted">{due.paid_by === you ? 'You pay it.' : `${due.paid_by} pays it.`}</p>
              <div className="mt-2 flex gap-2">
                <input
                  value={amounts[key] ?? ''}
                  onChange={(event) => setAmounts({ ...amounts, [key]: event.target.value })}
                  inputMode="decimal"
                  placeholder="₹ amount"
                  aria-label={`${due.title} amount for ${due.label}`}
                  className="amount min-w-0 flex-1 rounded-lg bg-white px-3 py-2"
                />
                <button
                  type="button"
                  disabled={busy || !paise}
                  onClick={() => paise && act(() => enterMonthAmount(group.id, due.recurring_id, due.month, paise, you))}
                  className="rounded-lg bg-brand px-4 font-display font-semibold text-white disabled:bg-muted/40"
                >
                  Add
                </button>
              </div>
            </li>
          )
        })}
      </ul>
    </Section>
  )
}

/** Flatmates: the monthly bills, and a way to add or stop one. */
function MonthlyBills({ group, busy, act, addLink }: Ctx & { addLink: string }) {
  const [stopping, setStopping] = useState<string | null>(null)
  return (
    <Section title="Monthly bills">
      {group.recurring?.length === 0 && (
        <p className="rounded-2xl bg-white/60 p-4 text-sm text-muted">Rent, electricity, internet: add them once.</p>
      )}
      <ul className="space-y-2">
        {group.recurring?.map((bill) => (
          <li key={bill.id} className="flex items-center gap-3 rounded-2xl bg-white p-4">
            <span className="min-w-0 flex-1">
              <span className="block font-semibold">{bill.title}</span>
              <span className="text-sm text-muted">
                {bill.amount_paise ? formatRupees(bill.amount_paise) : 'Changes monthly'}, {bill.paid_by} pays on the{' '}
                {ordinal(bill.day_of_month)}
              </span>
            </span>
            <button
              type="button"
              disabled={busy}
              onClick={() => (stopping === bill.id ? act(() => stopRecurring(group.id, bill.id)) : setStopping(bill.id))}
              className={`text-sm font-semibold ${stopping === bill.id ? 'text-chilli' : 'text-muted'}`}
            >
              {stopping === bill.id ? 'Tap to stop' : 'Stop'}
            </button>
          </li>
        ))}
      </ul>
      <Link to={addLink} className="mt-2 block py-2 text-center font-semibold underline">
        Add a monthly bill
      </Link>
    </Section>
  )
}

/** Flatmates: each month's total and your share of it. */
function Months({ group, you }: Ctx) {
  if (!group.months?.length) return null
  return (
    <Section title="By month">
      <ul className="divide-y divide-steel rounded-2xl bg-white px-4">
        {group.months.map((month) => (
          <li key={month.month} className="flex items-baseline justify-between py-3">
            <span className="font-semibold">{month.label}</span>
            <span className="text-right">
              <span className="amount block">Your share {formatRupees(month.owed[you] ?? 0)}</span>
              <span className="text-sm text-muted">of {formatRupees(month.total_paise)}</span>
            </span>
          </li>
        ))}
      </ul>
    </Section>
  )
}

/** Everything in the tab, newest first. Tap an entry for details, or to remove a mistake. */
function Activity({ group, you, busy, act }: Ctx) {
  const [removing, setRemoving] = useState<string | null>(null)
  if (group.activity.length === 0) return null

  function remove(entry: ActivityEntry) {
    if (removing !== entry.id) return setRemoving(entry.id)
    act(() => (entry.type === 'expense' ? deleteExpense(group.id, entry.id) : deleteRepayment(group.id, entry.id)))
  }

  return (
    <Section title="Activity">
      <ul className="space-y-2">
        {group.activity.map((entry) =>
          entry.type === 'repayment' ? (
            <li key={entry.id} className="flex items-center gap-3 rounded-2xl bg-white/60 px-4 py-3 text-sm">
              <span className="flex-1">
                <span className="font-semibold">{entry.sender}</span> paid <span className="font-semibold">{entry.receiver}</span>{' '}
                <span className="amount">{formatRupees(entry.amount_paise)}</span>
              </span>
              <button
                type="button"
                disabled={busy}
                onClick={() => remove(entry)}
                className={`font-semibold ${removing === entry.id ? 'text-chilli' : 'text-muted'}`}
              >
                {removing === entry.id ? 'Tap to undo' : 'Undo'}
              </button>
            </li>
          ) : (
            <li key={entry.id}>
              <details className="group rounded-2xl bg-white">
                <summary className="flex cursor-pointer list-none items-center gap-3 p-4">
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-semibold">{entry.title}</span>
                    <span className="text-sm text-muted">
                      {Object.keys(entry.paid).join(' and ')} paid
                      {entry.owed[you] ? `, your share ${formatRupees(entry.owed[you])}` : ', not in it'}
                    </span>
                  </span>
                  <span className="amount text-lg font-semibold">{formatRupees(entry.total_paise)}</span>
                </summary>
                <div className="px-4 pb-4 text-sm">
                  <ul className="border-t border-dashed border-steel-dark pt-2">
                    {Object.entries(entry.owed).map(([person, amount]) => (
                      <li key={person} className="flex justify-between py-0.5">
                        <span>{person}</span>
                        <span className="amount">{formatRupees(amount)}</span>
                      </li>
                    ))}
                  </ul>
                  <p className="mt-2 flex items-center gap-3 text-muted">
                    <span className="flex-1">
                      {entry.source === 'recurring' ? 'Monthly bill' : entry.added_by ? `Added by ${entry.added_by}` : ''}
                      {entry.split_id && (
                        <>
                          {', '}
                          <Link to={`/split/${entry.split_id}`} className="underline">
                            see the bill
                          </Link>
                        </>
                      )}
                    </span>
                    {!group.closed && (
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => remove(entry)}
                        className={`font-semibold ${removing === entry.id ? 'text-chilli' : ''}`}
                      >
                        {removing === entry.id ? 'Tap to remove' : 'Remove'}
                      </button>
                    )}
                  </p>
                </div>
              </details>
            </li>
          ),
        )}
      </ul>
    </Section>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mt-8">
      <h2 className="mb-3 font-display text-xl font-semibold">{title}</h2>
      {children}
    </section>
  )
}

/** 1 -> "1st", 2 -> "2nd", 23 -> "23rd". */
function ordinal(day: number): string {
  const suffix = day % 10 === 1 && day !== 11 ? 'st' : day % 10 === 2 && day !== 12 ? 'nd' : day % 10 === 3 && day !== 13 ? 'rd' : 'th'
  return `${day}${suffix}`
}

function message(problem: unknown): string {
  return problem instanceof ApiError ? problem.message : 'Couldn’t reach Split Rupya. Check your connection.'
}
