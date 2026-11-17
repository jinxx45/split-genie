// One group, at /groups/:id. You pay / They pay (settled pair by pair, like Google Pay), sharing
// who pays whom, and every expense, each of which you can open and pay your part of.
// Trips add dates, trip cost and "End trip"; flatmates add monthly bills and a per-month view.
// Anyone with the link can use it: they pick their name once (remembered on this phone).

import { useEffect, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'
import {
  ApiError,
  addMember,
  addRepayment,
  deleteExpense,
  deleteRepayment,
  enterMonthAmount,
  getGroup,
  joinGroup,
  removeMember,
  setGroupClosed,
  setGroupDetails,
  stopRecurring,
} from '../api'
import type { ActivityEntry, Group } from '../api'
import { capitalise, dateRange, findEntry, groupLink, KIND_NAMES, nameOrYou, rememberedMember, rememberMember, whoPaysWhom } from '../groups'
import type { GroupCtx } from '../groups'
import { formatRupees, parseRupees } from '../money'
import { PayButton } from '../pay'
import { personColor } from '../colors'
import { Avatar, ErrorText, KindIcon, Screen, WhoAreYou } from '../ui'
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
  const dates = dateRange(group.start_date, group.end_date)

  return (
    <Screen
      title={group.name}
      note={
        <>
          <KindIcon kind={group.kind} className="size-4" />
          {KIND_NAMES[group.kind]}
          {group.kind === 'trip' && dates && `, ${dates}`}
        </>
      }
      action={
        !group.closed && (
          <Link
            to={addLink}
            className="btn-pop block w-full px-5 py-3.5 text-center text-lg active:translate-x-0.5 active:translate-y-0.5 active:shadow-none"
          >
            Add expense
          </Link>
        )
      }
      headerRight={<AddPeopleButton {...ctx} />}
    >
      <p className="-mt-3 mb-4 text-sm text-muted">
        You’re {you}.{' '}
        <button type="button" onClick={() => setParams({ who: '' })} className="underline">
          Not you?
        </button>
      </p>

      <EditDetails {...ctx} />

      {group.closed && (
        <p className="mb-4 rounded-2xl bg-accent-soft p-4">
          <span className="font-semibold">This trip has ended.</span> Settle up below; no new expenses can be added.
        </p>
      )}

      <MainTabs {...ctx} addLink={addLink} />
      <Members {...ctx} />
      <Invite group={group} />
      {group.kind === 'trip' && group.is_owner && <TripControls {...ctx} />}
      {error && <ErrorText>{error}</ErrorText>}
    </Screen>
  )
}

type Ctx = GroupCtx

/** Everything else, in two top-level tabs: the money (settling up, cost, leaderboard) and the
 * activity log, which can get long and used to push the settle-up boxes far down the page. */
function MainTabs(props: Ctx & { addLink: string }) {
  const { group } = props
  const [tab, setTab] = useState<'settle' | 'activity'>('settle')

  return (
    <section>
      <div role="tablist" aria-label="Group sections" className="mb-4 flex gap-2">
        {(
          [
            { id: 'settle', label: 'Settle up' },
            { id: 'activity', label: 'Activity' },
          ] as const
        ).map((option) => (
          <button
            key={option.id}
            type="button"
            role="tab"
            aria-selected={tab === option.id}
            onClick={() => setTab(option.id)}
            className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
              tab === option.id ? 'bg-ink text-paper' : 'bg-steel text-muted'
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>

      {tab === 'settle' ? (
        <div role="tabpanel">
          <SettleTabs {...props} />
          <Cost {...props} />
          {group.kind === 'flat' && <DueBills {...props} />}
          {group.debts.length > 0 && <ShareSummary group={group} />}
          {group.kind === 'flat' && <MonthlyBills {...props} addLink={`${props.addLink}?monthly`} />}
          {group.kind === 'flat' && <Months {...props} />}
          <Leaderboard {...props} />
          {group.kind === 'trip' && group.total_paise > 0 && <WrappedLink group={group} />}
        </div>
      ) : (
        <div role="tabpanel">
          <Activity {...props} />
        </div>
      )}
    </section>
  )
}

/** A quick way to add a friend without scrolling down to "People in this group". */
function AddPeopleButton({ group, busy, act }: Ctx) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')

  function submit(event: FormEvent) {
    event.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) return
    setName('')
    act(() => addMember(group.id, trimmed))
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-label="Add people"
        title="Add people"
        className={`flex size-9 items-center justify-center rounded-full border-2 border-line ${open ? 'bg-accent' : 'bg-white'}`}
      >
        <svg viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
          <circle cx="9" cy="8" r="3" />
          <path d="M3 19c0-3 2.7-5 6-5s6 2 6 5M17 8h4m-2-2v4" />
        </svg>
      </button>
      {open && (
        <form onSubmit={submit} className="tile pop-shadow absolute top-11 right-0 z-10 flex w-60 gap-1.5 bg-white p-2.5">
          <input
            autoFocus
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Friend's name"
            maxLength={40}
            aria-label="Add a friend by name"
            className="min-w-0 flex-1 rounded-lg bg-steel px-2.5 py-1.5 text-sm"
          />
          <button
            type="submit"
            disabled={busy || !name.trim()}
            className="rounded-lg bg-brand px-3 font-display text-sm font-semibold text-white disabled:bg-muted/40"
          >
            Add
          </button>
        </form>
      )}
    </div>
  )
}

/** What it's cost you so far. Opens to your part of each expense, e.g. "Petrol ₹2,000.00". */
function Cost({ group, you }: Ctx) {
  const [open, setOpen] = useState(false)
  if (group.total_paise === 0) return null
  // Your own parts, biggest first. Expenses you weren't in are left out.
  const mine = group.activity
    .flatMap((entry) => (entry.type === 'expense' && entry.owed[you] ? [{ id: entry.id, title: entry.title, part: entry.owed[you] }] : []))
    .sort((first, second) => second.part - first.part)

  return (
    <div className="tile mt-3">
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open} className="flex w-full items-center gap-3 p-3.5 text-left">
        <span className="min-w-0 flex-1">
          <span className="block font-semibold">{group.kind === 'trip' ? 'The trip cost you' : 'Your share so far'}</span>
          <span className="text-sm text-muted">Everyone together {formatRupees(group.total_paise)}</span>
        </span>
        <span className="amount shrink-0 text-xl font-bold whitespace-nowrap">{formatRupees(group.spent[you] ?? 0)}</span>
        <Chevron open={open} />
      </button>
      {open && (
        <ul className="px-4 pb-4 text-sm">
          {mine.map((item, index) => (
            <li key={item.id} className={`flex justify-between gap-3 py-1 ${index === 0 ? 'border-t border-dashed border-steel-dark pt-2' : ''}`}>
              <span className="min-w-0 truncate">{item.title}</span>
              <span className="amount shrink-0">{formatRupees(item.part)}</span>
            </li>
          ))}
          {mine.length === 0 && <li className="border-t border-dashed border-steel-dark pt-2 text-muted">You’re not in any expense yet.</li>}
        </ul>
      )}
    </div>
  )
}

/** Who spent the most, down to the least: each person's own share of everything, with what they
 * paid up front alongside. */
function Leaderboard({ group, you }: Ctx) {
  if (group.total_paise === 0) return null
  const paid = Object.fromEntries(group.members.map((member) => [member, 0]))
  for (const entry of group.activity) {
    if (entry.type !== 'expense') continue
    for (const [person, amount] of Object.entries(entry.paid)) paid[person] = (paid[person] ?? 0) + amount
  }
  const ranked = [...group.members].sort((first, second) => (group.spent[second] ?? 0) - (group.spent[first] ?? 0))
  const top = group.spent[ranked[0]] ?? 0

  return (
    <Section title="Who spent the most">
      <ol className="tile divide-y divide-steel px-4">
        {ranked.map((person, index) => {
          const spent = group.spent[person] ?? 0
          return (
            <li key={person} className="py-2.5">
              <div className="flex items-center gap-2.5">
                <span className="amount w-4 text-center font-bold text-muted">{index + 1}</span>
                <Avatar name={person} color={personColor(group.members, person)} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-semibold">{person === you ? 'You' : person}</span>
                  <span className="block truncate text-sm text-muted">Paid {formatRupees(paid[person] ?? 0)}</span>
                </span>
                <span className="amount shrink-0 text-lg font-bold whitespace-nowrap">{formatRupees(spent)}</span>
              </div>
              <div className="mt-2 ml-8 h-2 rounded-full bg-steel" aria-hidden>
                <div
                  className="h-full rounded-full"
                  style={{ width: `${top ? Math.round((spent / top) * 100) : 0}%`, background: personColor(group.members, person) }}
                />
              </div>
            </li>
          )
        })}
      </ol>
    </Section>
  )
}

/** Trips: the way in to the shareable picture of the trip's highlights. */
function WrappedLink({ group }: { group: Group }) {
  return (
    <Link
      to={`/groups/${group.id}/wrapped`}
      className="mt-6 mr-1 flex items-center gap-4 rounded-[1.25rem] border-2 border-line bg-coal p-4 text-snow pop-shadow"
    >
      <span aria-hidden className="flex size-12 shrink-0 items-center justify-center rounded-2xl bg-accent text-coal">
        <svg viewBox="0 0 24 24" className="size-6" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 3l2.2 5.6L20 9.3l-4.5 3.9L17 19l-5-3.1L7 19l1.5-5.8L4 9.3l5.8-.7Z" />
        </svg>
      </span>
      <span>
        <span className="block font-display text-lg font-bold">Trip Wrapped</span>
        <span className="text-sm text-snow/75">{group.closed ? 'Your trip in one picture. Share it with the group.' : 'Your trip so far, in one picture.'}</span>
      </span>
    </Link>
  )
}

/** Rename the group, or for a trip, change its dates. Collapsed behind a small link so it
 * doesn't compete with the group's name for attention. */
function EditDetails({ group, busy, act }: Ctx) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState(group.name)
  const [start, setStart] = useState(group.start_date ?? '')
  const [end, setEnd] = useState(group.end_date ?? '')

  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)} className="-mt-3 mb-4 text-sm font-semibold underline">
        Rename{group.kind === 'trip' ? ' or change dates' : ''}
      </button>
    )
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) return
    await act(() => setGroupDetails(group.id, trimmed, group.kind === 'trip' ? start || null : null, group.kind === 'trip' ? end || null : null))
    setOpen(false)
  }

  return (
    <form onSubmit={submit} className="-mt-1 mb-4 space-y-2 tile p-3.5">
      <input
        value={name}
        onChange={(event) => setName(event.target.value)}
        maxLength={60}
        aria-label="Group name"
        className="w-full rounded-lg bg-steel px-3 py-2 font-display text-lg font-semibold"
      />
      {group.kind === 'trip' && (
        <div className="grid grid-cols-2 gap-2">
          <input type="date" value={start} onChange={(event) => setStart(event.target.value)} aria-label="Start date" className="rounded-lg bg-steel px-3 py-2" />
          <input
            type="date"
            value={end}
            min={start || undefined}
            onChange={(event) => setEnd(event.target.value)}
            aria-label="End date"
            className="rounded-lg bg-steel px-3 py-2"
          />
        </div>
      )}
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={busy || !name.trim()}
          className="flex-1 rounded-lg bg-brand py-2 font-display font-semibold text-white disabled:bg-muted/40"
        >
          Save
        </button>
        <button type="button" onClick={() => setOpen(false)} className="rounded-lg bg-steel px-4 py-2 font-semibold">
          Cancel
        </button>
      </div>
    </form>
  )
}

/** Everyone in the group, with a way to add a friend who wasn't there when it was made, or take
 * off someone added by mistake (only while they haven't paid or owed anything yet). Members
 * still need the link to actually use the group; this just gets them onto the member list. */
function Members({ group, you, busy, act }: Ctx) {
  const [name, setName] = useState('')
  const [removing, setRemoving] = useState<string | null>(null)

  function submit(event: FormEvent) {
    event.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) return
    setName('')
    act(() => addMember(group.id, trimmed))
  }

  function remove(person: string) {
    if (removing !== person) return setRemoving(person)
    setRemoving(null)
    act(() => removeMember(group.id, person))
  }

  return (
    <Section title="People in this group">
      <ul className="flex flex-wrap gap-2">
        {group.members.map((person) => (
          <li key={person} className="flex items-center gap-1.5 rounded-full bg-steel py-1 pr-1.5 pl-1.5 text-sm font-semibold">
            <Avatar name={person} color={personColor(group.members, person)} />
            <span>{person}</span>
            {person !== you && (
              <button
                type="button"
                disabled={busy}
                onClick={() => remove(person)}
                aria-label={removing === person ? `Tap again to remove ${person}` : `Remove ${person}`}
                className={`ml-0.5 rounded-full px-1.5 font-bold ${removing === person ? 'bg-chilli text-white' : 'text-muted'}`}
              >
                {removing === person ? 'Sure?' : '×'}
              </button>
            )}
          </li>
        ))}
      </ul>
      <form onSubmit={submit} className="mt-3 flex gap-2">
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Add a friend by name"
          maxLength={40}
          aria-label="Add a friend by name"
          className="min-w-0 flex-1 rounded-lg bg-steel px-3 py-2"
        />
        <button
          type="submit"
          disabled={busy || !name.trim()}
          className="rounded-lg bg-brand px-4 font-display font-semibold text-white disabled:bg-muted/40"
        >
          Add
        </button>
      </form>
      <p className="mt-2 text-sm text-muted">
        New people show up once you share the group’s link below. Only someone with no activity yet can be removed.
      </p>
    </Section>
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
      className="mt-6 block tile px-4 py-3 text-center font-display font-semibold"
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
      className={`mt-3 w-full py-3 font-display font-semibold ${confirming ? 'rounded-[1.25rem] bg-chilli text-white' : 'tile'}`}
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
            <li key={key} className="rounded-2xl bg-accent-soft p-3.5">
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
        <p className="tile-soft p-4 text-sm text-muted">Rent, electricity, internet: add them once.</p>
      )}
      <ul className="space-y-2">
        {group.recurring?.map((bill) => (
          <li key={bill.id} className="flex items-center gap-3 tile p-3.5">
            <span className="min-w-0 flex-1">
              <span className="block truncate font-semibold">{bill.title}</span>
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
      <ul className="divide-y divide-steel tile px-4">
        {group.months.map((month) => (
          <li key={month.month} className="flex items-baseline justify-between gap-3 py-2.5">
            <span className="min-w-0 truncate font-semibold">{month.label}</span>
            <span className="shrink-0 text-right whitespace-nowrap">
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
        <p className="tile-soft p-4 text-center text-muted">Nothing added yet. Add the first expense below.</p>
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
    <li className="flex items-center gap-3 tile-soft px-3.5 py-2.5 text-sm">
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
    <li className="tile">
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open} className="flex w-full items-center gap-3 p-3.5 text-left">
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
                <span className="rounded-full bg-accent-soft px-2 font-semibold text-accent-deep">
                  you owe {formatRupees(unpaid.reduce((sum, owe) => sum + left(owe), 0))}
                </span>
              ) : (
                <span className="rounded-full bg-good-soft px-2 font-semibold text-good">settled</span>
              ))}
          </span>
        </span>
        <span className="amount shrink-0 text-lg font-semibold whitespace-nowrap">{formatRupees(entry.total_paise)}</span>
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
              <div key={owe.receiver} className="mt-3 flex flex-wrap items-center gap-2">
                {upi && (
                  <PayButton
                    upiId={upi}
                    name={owe.receiver}
                    paise={left(owe)}
                    note={`${group.name}: ${entry.title}`}
                    label={`Pay ${owe.receiver} ${formatRupees(left(owe))}`}
                    className="flex-1 rounded-xl bg-brand py-2.5 text-center font-display font-semibold text-white"
                  />
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
            {!group.closed && entry.source !== 'bill' && (
              <Link to={`/groups/${group.id}/add?edit=${entry.id}`} className="font-semibold text-ink underline">
                Edit
              </Link>
            )}
            {!group.closed && (
              <button type="button" disabled={busy} onClick={props.onRemove} className={`font-semibold ${props.removing ? 'text-chilli' : ''}`}>
                {props.removing ? 'Tap to remove' : 'Remove'}
              </button>
            )}
          </p>
          <AskAbout group={group} you={you} entry={entry} />
        </div>
      )}
    </li>
  )
}

/** A question about one expense, sent as a WhatsApp message with the expense named and the
 * group's link, to whichever chat the person picks (the group's, or one friend). */
function AskAbout({ group, you, entry }: { group: Group; you: string; entry: Expense }) {
  const [question, setQuestion] = useState('')
  const asked = question.trim()
  const payers = Object.keys(entry.paid).join(' and ')
  const text = [
    `*${group.name}*: ${you} has a question about *${entry.title}* (${formatRupees(entry.total_paise)}, ${payers} paid):`,
    asked,
    '',
    'See it here:',
    groupLink(group),
  ].join('\n')

  return (
    <div className="mt-3 border-t border-steel pt-3">
      <label htmlFor={`ask-${entry.id}`} className="block text-muted">
        Something not clear? Ask about it
      </label>
      <div className="mt-1 flex gap-2">
        <input
          id={`ask-${entry.id}`}
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Why is my part more?"
          maxLength={200}
          className="min-w-0 flex-1 rounded-lg bg-steel px-3 py-2"
        />
        {asked ? (
          <a
            href={`https://wa.me/?text=${encodeURIComponent(text)}`}
            target="_blank"
            rel="noreferrer"
            className="rounded-lg bg-brand px-3 py-2 font-display font-semibold whitespace-nowrap text-white"
          >
            Ask on WhatsApp
          </a>
        ) : (
          <span aria-disabled className="rounded-lg bg-muted/40 px-3 py-2 font-display font-semibold whitespace-nowrap text-white">
            Ask on WhatsApp
          </span>
        )}
      </div>
    </div>
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
