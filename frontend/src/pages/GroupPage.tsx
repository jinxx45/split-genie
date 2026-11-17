// One group, at /groups/:id. You pay / They pay (settled pair by pair, like Google Pay), sharing
// who pays whom, and every expense, each of which you can open and pay your part of.
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
  stopRecurring,
} from '../api'
import type { ActivityEntry, Group } from '../api'
import { capitalise, dateRange, findEntry, groupLink, KIND_NAMES, nameOrYou, rememberedMember, rememberMember, whoPaysWhom } from '../groups'
import type { GroupCtx } from '../groups'
import { formatRupees, parseRupees } from '../money'
import { upiLink } from '../upi'
import { ErrorText, KindIcon, Screen, WhoAreYou } from '../ui'
import { Chevron, SettleTabs, ShareSummary } from './GroupSettle'
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

      <SettleTabs {...ctx} />
      <Cost {...ctx} />
      {group.kind === 'flat' && <DueBills {...ctx} />}
      <Activity {...ctx} />
      {group.debts.length > 0 && <ShareSummary group={group} />}
      {group.kind === 'flat' && <MonthlyBills {...ctx} addLink={`${addLink}?monthly`} />}
      {group.kind === 'flat' && <Months {...ctx} />}
      <Invite group={group} />
      {group.kind === 'trip' && group.is_owner && <TripControls {...ctx} />}
      {error && <ErrorText>{error}</ErrorText>}
    </Screen>
  )
}

type Ctx = GroupCtx

/** What it's cost you so far, and everyone together. */
function Cost({ group, you }: Ctx) {
  if (group.total_paise === 0) return null
  return (
    <p className="mt-3 text-center text-sm text-muted">
      {group.kind === 'trip' ? 'The trip cost you' : 'Your share so far'}{' '}
      <span className="amount font-semibold text-ink">{formatRupees(group.spent[you] ?? 0)}</span>, everyone together{' '}
      <span className="amount">{formatRupees(group.total_paise)}</span>
    </p>
  )
}

/** One WhatsApp message with the group's link; each member picks their name when they open it. */
function Invite({ group }: { group: Group }) {
  const link = groupLink(group)
  const lines = group.closed
    ? [
        `*${group.name}* has ended. Here's how to settle up:`,
        ...whoPaysWhom(group.debts),
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

/** Everything in the tab, newest first. Open an expense to see everyone's part and pay yours. */
function Activity(ctx: Ctx) {
  const { group, act } = ctx
  const [removing, setRemoving] = useState<string | null>(null)
  if (group.activity.length === 0) {
    return (
      <Section title="Activity">
        <p className="rounded-2xl bg-white/60 p-4 text-center text-muted">Nothing added yet. Add the first expense below.</p>
      </Section>
    )
  }

  function remove(entry: ActivityEntry) {
    if (removing !== entry.id) return setRemoving(entry.id)
    act(() => (entry.type === 'expense' ? deleteExpense(group.id, entry.id) : deleteRepayment(group.id, entry.id)))
  }

  return (
    <Section title="Activity">
      <ul className="space-y-2">
        {group.activity.map((entry) =>
          entry.type === 'repayment' ? (
            <RepaymentLine key={entry.id} {...ctx} entry={entry} removing={removing === entry.id} onRemove={() => remove(entry)} />
          ) : (
            <ExpenseCard key={entry.id} {...ctx} entry={entry} removing={removing === entry.id} onRemove={() => remove(entry)} />
          ),
        )}
      </ul>
    </Section>
  )
}

type Expense = Extract<ActivityEntry, { type: 'expense' }>
type Repayment = Extract<ActivityEntry, { type: 'repayment' }>

/** Money paid back. Only the two people in it can undo it. */
function RepaymentLine(props: Ctx & { entry: Repayment; removing: boolean; onRemove: () => void }) {
  const { group, you, busy, entry } = props
  const paidFor = entry.expense_id ? findEntry(group, entry.expense_id) : undefined
  return (
    <li className="flex items-center gap-3 rounded-2xl bg-white/60 px-4 py-3 text-sm">
      <span className="flex-1">
        <span className="font-semibold">{capitalise(nameOrYou(entry.sender, you))}</span> paid{' '}
        <span className="font-semibold">{nameOrYou(entry.receiver, you)}</span>{' '}
        <span className="amount">{formatRupees(entry.amount_paise)}</span>
        {paidFor?.type === 'expense' && <span className="text-muted"> for {paidFor.title}</span>}
      </span>
      {(entry.sender === you || entry.receiver === you) && (
        <button
          type="button"
          disabled={busy}
          onClick={props.onRemove}
          className={`font-semibold ${props.removing ? 'text-chilli' : 'text-muted'}`}
        >
          {props.removing ? 'Tap to undo' : 'Undo'}
        </button>
      )}
    </li>
  )
}

/** One expense: a summary with your status, opening to everyone's parts and a way to pay yours. */
function ExpenseCard(props: Ctx & { entry: Expense; removing: boolean; onRemove: () => void }) {
  const { group, you, busy, act, entry } = props
  const [open, setOpen] = useState(false)
  const yours = entry.owes.filter((owe) => owe.sender === you) // what you owe for this one
  const owedToYou = entry.owes.filter((owe) => owe.receiver === you)
  // Paid already: repayments recorded against this expense, from you to that person.
  const paidTo = (receiver: string) =>
    group.activity.reduce(
      (sum, item) =>
        item.type === 'repayment' && item.expense_id === entry.id && item.sender === you && item.receiver === receiver
          ? sum + item.amount_paise
          : sum,
      0,
    )
  // What's left to pay for this expense: never more than you still owe that person overall, so
  // settling up with them (or what they owe you back) shows here too.
  const stillOwe = (receiver: string) => group.debts.find((debt) => debt.sender === you && debt.receiver === receiver)?.amount_paise ?? 0
  const left = (owe: { receiver: string; amount_paise: number }) =>
    Math.max(0, Math.min(owe.amount_paise - paidTo(owe.receiver), stillOwe(owe.receiver)))
  const unpaid = yours.filter((owe) => left(owe) > 0)
  const payers = Object.keys(entry.paid).map((person) => nameOrYou(person, you))

  return (
    <li className="rounded-2xl bg-white">
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open} className="flex w-full items-center gap-3 p-4 text-left">
        <span className="min-w-0 flex-1">
          <span className="block truncate font-semibold">{entry.title}</span>
          <span className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted">
            {[
              `${capitalise(payers.join(' and '))} paid`,
              owedToYou.length > 0 && `you get back ${formatRupees(owedToYou.reduce((sum, owe) => sum + owe.amount_paise, 0))}`,
              !entry.owed[you] && !entry.paid[you] && 'not in it',
            ]
              .filter(Boolean)
              .join(', ')}
            {yours.length > 0 &&
              (unpaid.length ? (
                <span className="rounded-full bg-saffron-soft px-2 font-semibold text-[#6b4200]">
                  you owe {formatRupees(unpaid.reduce((sum, owe) => sum + left(owe), 0))}
                </span>
              ) : (
                <span className="rounded-full bg-[#e3efe7] px-2 font-semibold text-[#1e5c3c]">settled</span>
              ))}
          </span>
        </span>
        <span className="amount text-lg font-semibold">{formatRupees(entry.total_paise)}</span>
        <Chevron open={open} />
      </button>

      {open && (
        <div className="px-4 pb-4 text-sm">
          <ul className="border-t border-dashed border-steel-dark pt-2">
            {Object.entries(entry.owed).map(([person, amount]) => (
              <li key={person} className={`flex justify-between py-0.5 ${person === you ? 'font-semibold' : ''}`}>
                <span>
                  {person === you ? 'Your part' : `${person}’s part`}
                  {entry.paid[person] ? <span className="font-normal text-muted"> (paid {formatRupees(entry.paid[person])})</span> : null}
                </span>
                <span className="amount">{formatRupees(amount)}</span>
              </li>
            ))}
          </ul>

          {unpaid.map((owe) => {
            const upi = group.upi_ids[owe.receiver]
            return (
              <div key={owe.receiver} className="mt-3 flex items-center gap-2">
                {upi && (
                  <a
                    href={upiLink(upi, owe.receiver, left(owe), `${group.name}: ${entry.title}`)}
                    className="flex-1 rounded-xl bg-brand py-2.5 text-center font-display font-semibold text-white"
                  >
                    Pay {owe.receiver} {formatRupees(left(owe))}
                  </a>
                )}
                <button
                  type="button"
                  disabled={busy}
                  onClick={() =>
                    act(() =>
                      addRepayment(group.id, { sender: you, receiver: owe.receiver, amount_paise: left(owe), by: you, expense_id: entry.id }),
                    )
                  }
                  className={`rounded-xl bg-steel px-3 py-2.5 font-display font-semibold ${upi ? '' : 'flex-1'}`}
                >
                  {upi ? 'I’ve paid' : `I’ve paid ${owe.receiver} ${formatRupees(left(owe))}`}
                </button>
              </div>
            )
          })}

          <p className="mt-3 flex items-center gap-3 text-muted">
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
              <button type="button" disabled={busy} onClick={props.onRemove} className={`font-semibold ${props.removing ? 'text-chilli' : ''}`}>
                {props.removing ? 'Tap to remove' : 'Remove'}
              </button>
            )}
          </p>
        </div>
      )}
    </li>
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
