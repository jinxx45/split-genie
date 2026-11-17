// Settling up in a group, the Google Pay way: each pair of people settles on its own.
// "You pay" lists who you owe, "They pay" who owes you; open a person to see the expenses behind
// it and pay or mark it. You can only mark payments you make or receive.

import { useState } from 'react'
import { addRepayment, setGroupUpiId } from '../api'
import type { Debt, Group } from '../api'
import { personColor } from '../colors'
import { findEntry, groupLink, whoPaysWhom } from '../groups'
import type { GroupCtx } from '../groups'
import { formatRupees } from '../money'
import { UPI_ID, upiLink } from '../upi'
import { Avatar } from '../ui'

type Tab = 'pay' | 'get'

export function SettleTabs(ctx: GroupCtx) {
  const { group, you } = ctx
  const youPay = group.debts.filter((debt) => debt.sender === you)
  const theyPay = group.debts.filter((debt) => debt.receiver === you)
  // Open on whichever side has something, "You pay" first.
  const [tab, setTab] = useState<Tab>(youPay.length > 0 || theyPay.length === 0 ? 'pay' : 'get')
  const [open, setOpen] = useState<string | null>(null) // the person whose details are showing
  const debts = tab === 'pay' ? youPay : theyPay
  const total = (list: Debt[]) => list.reduce((sum, debt) => sum + debt.amount_paise, 0)

  return (
    <section>
      <div role="tablist" aria-label="Settle up" className="mr-1 grid grid-cols-2 gap-3">
        {(
          [
            { id: 'pay', label: 'You pay', list: youPay },
            { id: 'get', label: 'They pay', list: theyPay },
          ] as const
        ).map((option) => {
          const on = tab === option.id
          return (
            <button
              key={option.id}
              type="button"
              role="tab"
              aria-selected={on}
              onClick={() => {
                setTab(option.id)
                setOpen(null)
              }}
              className={`rounded-[1.25rem] border-2 border-line p-3.5 text-left transition ${on ? 'bg-saffron text-coal pop-shadow' : 'bg-white'}`}
            >
              <span className={`block text-sm font-bold ${on ? '' : 'text-muted'}`}>{option.label}</span>
              <span className={`amount block text-2xl ${on ? 'font-extrabold' : 'font-bold'}`}>
                {formatRupees(total(option.list))}
              </span>
            </button>
          )
        })}
      </div>

      <ul role="tabpanel" className="mt-3 space-y-2">
        {debts.length === 0 && (
          <li className="tile-soft p-4 text-center text-muted">
            {tab === 'pay' ? 'You don’t owe anyone here.' : 'Nobody owes you here.'}
          </li>
        )}
        {debts.map((debt) => {
          const other = tab === 'pay' ? debt.receiver : debt.sender
          return (
            <DebtRow
              key={other}
              {...ctx}
              debt={debt}
              other={other}
              open={open === other}
              onToggle={() => setOpen(open === other ? null : other)}
            />
          )
        })}
      </ul>
      {tab === 'get' && (theyPay.length > 0 || group.upi_ids[you]) && <MyUpiId {...ctx} />}
    </section>
  )
}

/** One person you owe (or who owes you). Opens to show the expenses behind it, and what to do. */
function DebtRow(
  props: GroupCtx & {
    debt: Debt
    other: string
    open: boolean
    onToggle: () => void
  },
) {
  const { group, you, busy, act, debt, other, open } = props
  const youOwe = debt.sender === you
  const otherUpi = group.upi_ids[other]
  const record = () =>
    act(() =>
      addRepayment(group.id, {
        sender: debt.sender,
        receiver: debt.receiver,
        amount_paise: debt.amount_paise,
        by: you,
      }),
    )

  return (
    <li className="tile">
      <button
        type="button"
        onClick={props.onToggle}
        aria-expanded={open}
        className="flex w-full items-center gap-3 p-4 text-left"
      >
        <Avatar name={other} color={personColor(group.members, other)} />
        <span className="min-w-0 flex-1">
          <span className="block font-semibold">{other}</span>
          <span className="text-sm text-muted">
            {debt.entries.length} {debt.entries.length === 1 ? 'entry' : 'entries'}
          </span>
        </span>
        <span className="amount text-xl font-bold">{formatRupees(debt.amount_paise)}</span>
        <Chevron open={open} />
      </button>

      {open && (
        <div className="px-4 pb-4">
          <ul className="border-t border-dashed border-steel-dark pt-2 text-sm">
            {debt.entries.map((entry) => (
              <EntryLine key={entry.ref} group={group} entryRef={entry.ref} amount={entry.amount_paise} />
            ))}
            <li className="mt-1 flex justify-between border-t border-steel pt-2 font-semibold">
              <span>{youOwe ? `You pay ${other}` : `${other} pays you`}</span>
              <span className="amount">{formatRupees(debt.amount_paise)}</span>
            </li>
          </ul>

          <div className="mt-3 flex flex-wrap items-center gap-2">
            {youOwe && otherUpi && (
              <a
                href={upiLink(otherUpi, other, debt.amount_paise, group.name)}
                className="flex-1 rounded-xl bg-brand py-3 text-center font-display font-semibold text-white"
              >
                Pay {formatRupees(debt.amount_paise)}
              </a>
            )}
            {!youOwe && (
              <a
                href={`https://wa.me/?text=${encodeURIComponent(reminder(group, debt))}`}
                target="_blank"
                rel="noreferrer"
                className="flex-1 rounded-xl bg-brand py-3 text-center font-display font-semibold text-white"
              >
                Remind on WhatsApp
              </a>
            )}
            <button
              type="button"
              disabled={busy}
              onClick={record}
              className="rounded-xl bg-steel px-4 py-3 font-display font-semibold"
            >
              {youOwe ? 'I’ve paid' : 'I got it'}
            </button>
          </div>
          {youOwe && !otherUpi && (
            <p className="mt-2 text-sm text-muted">
              {other} hasn’t added a UPI ID yet. Pay them your usual way, then tap “I’ve paid”.
            </p>
          )}
        </div>
      )}
    </li>
  )
}

/** One reason behind a debt: the expense's name and what it adds (+) or takes off (−). The row
 * is already inside one person, so it doesn't repeat who paid. */
function EntryLine(props: { group: Group; entryRef: string; amount: number }) {
  const entry = findEntry(props.group, props.entryRef)
  if (!entry) return null
  return (
    <li className="flex justify-between gap-3 py-1">
      {entry.type === 'expense' ? (
        <span className="min-w-0 font-semibold">{entry.title}</span>
      ) : (
        <span className="min-w-0 text-muted">Paid back</span>
      )}
      <span className={`amount shrink-0 ${props.amount < 0 ? 'text-muted' : ''}`}>
        {props.amount < 0 ? '−' : '+'}
        {formatRupees(Math.abs(props.amount))}
      </span>
    </li>
  )
}

/** "They pay": a WhatsApp nudge listing what it's for, with the group's link to pay from. */
function reminder(group: Group, debt: Debt): string {
  const lines = debt.entries.flatMap((item) => {
    const entry = findEntry(group, item.ref)
    if (!entry) return []
    const what = entry.type === 'expense' ? entry.title : 'Paid back'
    return [`• ${what}: ${item.amount_paise < 0 ? '−' : ''}${formatRupees(Math.abs(item.amount_paise))}`]
  })
  return [
    `Hi ${debt.sender}, for *${group.name}* you pay ${debt.receiver} ${formatRupees(debt.amount_paise)}:`,
    ...lines,
    '',
    'See it and pay in one tap:',
    groupLink(group),
  ].join('\n')
}

/** Your UPI ID in this group, so the others get a Pay button. Once saved it shows with
 * "Change", which brings the box back with the saved ID in it. */
function MyUpiId({ group, you, busy, act }: GroupCtx) {
  const saved = group.upi_ids[you] ?? ''
  // While changing: the ID that was saved when the box was opened. Saving a new one changes
  // `saved`, so the box closes by itself; null means it's closed.
  const [changing, setChanging] = useState<string | null>(null)
  const [upiId, setUpiId] = useState('')
  const typed = upiId.trim()

  if (saved && changing !== saved) {
    return (
      <p className="tile mt-3 flex items-center gap-3 px-4 py-3 text-sm">
        <span className="min-w-0 flex-1">
          <span className="block text-muted">They pay you at</span>
          <span className="block truncate font-semibold">{saved}</span>
        </span>
        <button
          type="button"
          onClick={() => {
            setUpiId(saved)
            setChanging(saved)
          }}
          className="font-semibold underline"
        >
          Change
        </button>
      </p>
    )
  }
  return (
    <div className="tile mt-3 p-4">
      <label className="block text-sm text-muted" htmlFor="my-upi">
        Your UPI ID, so they get a Pay button
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
          disabled={busy || !UPI_ID.test(typed) || typed === saved}
          onClick={() => act(() => setGroupUpiId(group.id, you, typed))}
          className="rounded-lg bg-brand px-4 font-display font-semibold text-white disabled:bg-muted/40"
        >
          Save
        </button>
      </div>
      {saved && (
        <button type="button" onClick={() => setChanging(null)} className="mt-2 text-sm font-semibold text-muted underline">
          Keep {saved}
        </button>
      )}
    </div>
  )
}

/** Share who pays whom on WhatsApp: for everyone, or one person's own summary. */
export function ShareSummary({ group }: { group: Group }) {
  const [person, setPerson] = useState<string | null>(null) // null: everyone
  const text = person ? personSummary(group, person) : everyoneSummary(group)

  return (
    <section className="mt-8">
      <h2 className="mb-1 font-display text-xl font-semibold">Share who pays whom</h2>
      <p className="mb-3 text-sm text-muted">For everyone, or just one person’s own list.</p>
      <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Whose summary">
        {[null, ...group.members].map((option) => {
          const on = person === option
          return (
            <button
              key={option ?? 'everyone'}
              type="button"
              role="radio"
              aria-checked={on}
              onClick={() => setPerson(option)}
              className={`rounded-full border-2 px-3 py-1.5 text-sm font-semibold ${
                on ? 'border-brand bg-brand text-white' : 'border-steel-dark bg-white text-muted'
              }`}
            >
              {option ?? 'Everyone'}
            </button>
          )
        })}
      </div>
      <pre className="mt-3 tile p-4 font-body text-sm whitespace-pre-wrap">{text}</pre>
      <a
        href={`https://wa.me/?text=${encodeURIComponent(text)}`}
        target="_blank"
        rel="noreferrer"
        className="mt-2 block tile px-4 py-3 text-center font-display font-semibold ring-2 ring-brand"
      >
        Send on WhatsApp
      </a>
    </section>
  )
}

function everyoneSummary(group: Group): string {
  const lines = whoPaysWhom(group.debts)
  return [
    `*${group.name}*: who pays whom`,
    ...(lines.length ? lines : ['Everyone is square.']),
    '',
    'See the details and pay in one tap:',
    groupLink(group),
  ].join('\n')
}

/** "Ravi pays: • Priya ₹636.00 • Arun ₹448.00" and who pays Ravi, for one person. */
function personSummary(group: Group, person: string): string {
  const pays = group.debts.filter((debt) => debt.sender === person)
  const gets = group.debts.filter((debt) => debt.receiver === person)
  const lines = [`*${group.name}*, ${person}’s summary`]
  if (pays.length) lines.push(`${person} pays:`, ...pays.map((d) => `• ${d.receiver} ${formatRupees(d.amount_paise)}`))
  if (gets.length) lines.push(`${person} gets back:`, ...gets.map((d) => `• from ${d.sender} ${formatRupees(d.amount_paise)}`))
  if (!pays.length && !gets.length) lines.push(`${person} is all square.`)
  return [...lines, '', 'See the details and pay in one tap:', groupLink(group)].join('\n')
}

export function Chevron({ open }: { open: boolean }) {
  return (
    <span
      aria-hidden
      className={`flex size-8 shrink-0 items-center justify-center rounded-[10px] border-2 border-line transition-transform ${open ? 'rotate-180 bg-ink text-paper' : ''}`}
    >
      <svg
        viewBox="0 0 24 24"
        className="size-4"
        fill="none"
        stroke="currentColor"
        strokeWidth={2.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="m6 9 6 6 6-6" />
      </svg>
    </span>
  )
}
