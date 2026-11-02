// The finished split, in two views:
// - the person who split it: a summary, one WhatsApp message for the group (or any chats), and
//   whether each payment has been paid;
// - a friend opening that request (?for=Arun): their own share first, with a UPI pay button and
//   "I've paid".

import { useState } from 'react'
import { useSearchParams } from 'react-router'
import { saveFriendUpiId, saveMyUpiId } from '../api'
import type { Payment, PaymentMark, Split } from '../api'
import { formatRupees, toRupeesText } from '../money'
import { ErrorText, Paper, Screen } from '../ui'
import { useMe } from '../useMe'
import { BreakdownList, BreakdownPaper, Payments } from './Summary'

type Result = NonNullable<Split['result']>
type Base = { result: Result; people: string[] }
type Props = Base & { onMark: (mark: PaymentMark) => void; busy: boolean; error: string | null }

// A UPI ID looks like name@bank.
const UPI_ID = /^[\w.-]{2,256}@[a-zA-Z]{2,64}$/

export function Done(props: Props) {
  const [params] = useSearchParams()
  const friend = params.get('for')
  if (friend && props.people.includes(friend)) {
    return <FriendView {...props} friend={friend} upiIds={readUpiIds(params)} />
  }
  return <SplitterView {...props} />
}

function SplitterView({ result, people, onMark, busy, error }: Props) {
  // Only people still waiting on money need their UPI ID in the requests.
  const waiting = result.payments.filter((payment) => !payment.marked_paid_by)
  const receivers = [...new Set(waiting.map((payment) => payment.receiver))]
  const [typedIds, setTypedIds] = useState<Record<string, string>>({})
  const [me, setMe] = useMe()

  /** A UPI ID saved earlier: your own, or a friend's. */
  function savedUpiId(person: string): string {
    if (me.user && person.toLowerCase() === me.user.name.toLowerCase()) return me.user.upi_id
    return me.friends.find((friend) => friend.name.toLowerCase() === person.toLowerCase())?.upi_id ?? ''
  }

  /** Signed in: remember a new UPI ID so it's filled in next time. */
  function remember(person: string) {
    const upiId = (typedIds[person] ?? '').trim()
    if (!me.user || !UPI_ID.test(upiId) || upiId === savedUpiId(person)) return
    const isMe = person.toLowerCase() === me.user.name.toLowerCase()
    const save = isMe ? saveMyUpiId(upiId) : saveFriendUpiId(person, upiId)
    save.then(setMe).catch(() => {}) // saving is a convenience; the requests work either way
  }

  const shownIds = Object.fromEntries(receivers.map((person) => [person, typedIds[person] ?? savedUpiId(person)]))
  const upiIds = validUpiIds(shownIds)
  const paidCount = result.payments.filter((payment) => payment.marked_paid_by).length

  return (
    <Screen
      title="Split done"
      action={
        waiting.length > 0 && (
          <a
            href={`https://wa.me/?text=${encodeURIComponent(summaryMessage(result, people, upiIds))}`}
            target="_blank"
            rel="noreferrer"
            className="block w-full rounded-2xl bg-brand px-5 py-4 text-center font-display text-lg font-semibold text-white active:scale-[0.98]"
          >
            Share on WhatsApp
          </a>
        )
      }
    >
      <BillSummary result={result} people={people} />

      {result.payments.length > 0 && (
        <>
          <h2 className="mt-8 font-display text-xl font-semibold">Who pays whom</h2>
          <p className="mb-3 text-muted">
            {paidCount === result.payments.length
              ? 'Everyone has paid.'
              : `${paidCount} of ${result.payments.length} paid`}
          </p>
        </>
      )}
      {receivers.map((receiver) => (
        <label key={receiver} className="mb-3 block rounded-2xl bg-white p-4">
          <span className="block text-sm text-muted">{receiver}’s UPI ID, so friends can pay in one tap</span>
          <input
            value={shownIds[receiver]}
            onChange={(event) => setTypedIds({ ...typedIds, [receiver]: event.target.value })}
            onBlur={() => remember(receiver)}
            placeholder="name@okbank"
            autoCapitalize="none"
            autoCorrect="off"
            className="mt-1 w-full rounded-lg bg-steel px-3 py-2"
          />
        </label>
      ))}
      <Payments
        payments={result.payments}
        people={people}
        action={(payment) =>
          payment.marked_paid_by ? (
            // The person being paid can undo a mistaken mark.
            <PaidRow payment={payment} busy={busy} onUndo={() => onMark(markFor(payment, false, payment.receiver))} />
          ) : (
            <button
              type="button"
              disabled={busy}
              onClick={() => onMark(markFor(payment, true, payment.receiver))}
              className="mt-2 text-sm font-semibold text-muted"
            >
              Mark as paid
            </button>
          )
        }
      />
      {error && <ErrorText>{error}</ErrorText>}

      <h2 className="mt-8 mb-3 font-display text-xl font-semibold">How it adds up</h2>
      <BreakdownList breakdown={result.breakdown} people={people} />
    </Screen>
  )
}

function FriendView(props: Props & { friend: string; upiIds: Record<string, string> }) {
  const { friend, result, people, upiIds, onMark, busy, error } = props
  const mine = result.payments.filter((payment) => payment.sender === friend || payment.receiver === friend)
  const payable = mine.filter(
    (payment) => payment.sender === friend && !payment.marked_paid_by && upiIds[payment.receiver],
  )
  const part = result.breakdown[friend]

  return (
    <Screen
      title={`${friend}’s share`}
      action={
        payable.length > 0 && (
          <div className="space-y-2">
            {payable.map((payment) => (
              <a
                key={payment.receiver}
                href={upiLink(upiIds[payment.receiver], payment.receiver, payment.amount_paise)}
                className="block w-full rounded-2xl bg-brand px-5 py-4 text-center font-display text-lg font-semibold text-white active:scale-[0.98]"
              >
                Pay {payment.receiver} {formatRupees(payment.amount_paise)}
              </a>
            ))}
          </div>
        )
      }
    >
      {mine.length > 0 ? (
        <Payments
          payments={mine}
          people={people}
          action={(payment) =>
            payment.marked_paid_by ? (
              <PaidRow payment={payment} busy={busy} onUndo={() => onMark(markFor(payment, false, friend))} />
            ) : (
              <button
                type="button"
                disabled={busy}
                onClick={() => onMark(markFor(payment, true, friend))}
                className="mt-3 w-full rounded-xl bg-steel py-2.5 font-display font-semibold"
              >
                {payment.sender === friend ? 'I’ve paid' : `${payment.sender} paid me`}
              </button>
            )
          }
        />
      ) : (
        <p className="rounded-2xl bg-white p-4">You’re all square. Nothing to pay.</p>
      )}
      {error && <ErrorText>{error}</ErrorText>}

      {part && (
        <>
          <h2 className="mt-8 mb-3 font-display text-xl font-semibold">What you had</h2>
          <BreakdownPaper part={part} />
        </>
      )}

      <h2 className="mt-8 mb-3 font-display text-xl font-semibold">The whole bill</h2>
      <BillSummary result={result} people={people} />
      <div className="mt-3">
        <BreakdownList breakdown={result.breakdown} people={people} />
      </div>
    </Screen>
  )
}

/** A paid payment: who marked it, and a way to undo a mistake. */
function PaidRow({ payment, busy, onUndo }: { payment: Payment; busy: boolean; onUndo: () => void }) {
  return (
    <div className="mt-3 flex items-center justify-between rounded-xl bg-steel px-3 py-2.5">
      <span className="font-display font-semibold">
        ✓ Paid
        <span className="font-body font-normal text-muted"> (marked by {payment.marked_paid_by})</span>
      </span>
      <button type="button" disabled={busy} onClick={onUndo} className="text-sm font-semibold text-muted">
        Undo
      </button>
    </div>
  )
}

function markFor(payment: Payment, paid: boolean, by: string): PaymentMark {
  return { sender: payment.sender, receiver: payment.receiver, paid, by }
}

/** The bill at a glance: where, how much, how many people, who paid. */
function BillSummary({ result, people }: Base) {
  return (
    <Paper>
      <div className="text-center">
        <p className="font-display text-xl font-semibold">{result.title || 'The bill'}</p>
        <p className="amount text-4xl font-bold">{formatRupees(result.total_paise)}</p>
        <p className="mt-1 text-muted">
          Split between {people.length} people, paid by {joinNames(Object.keys(result.paid))}
        </p>
      </div>
    </Paper>
  )
}

/** One WhatsApp message for everyone: who pays whom, and one link. Each friend opens it, picks
 * their name, and sees their own share with a pay button. Sent to a group or to several chats. */
function summaryMessage(result: Result, people: string[], upiIds: Record<string, string>): string {
  const params = new URLSearchParams({ who: '' })
  // Every UPI ID typed in goes in the link as name:id, so friends get pay buttons.
  Object.entries(upiIds).forEach(([person, id]) => params.append('upi', `${person}:${id}`))
  const link = `${window.location.origin}${window.location.pathname}?${params}`
  const waiting = result.payments.filter((payment) => !payment.marked_paid_by)

  return [
    `*${result.title || 'The bill'}*: ${formatRupees(result.total_paise)}, split between ${people.length}`,
    '',
    ...waiting.map((payment) => `${payment.sender} pays ${payment.receiver} ${formatRupees(payment.amount_paise)}`),
    '',
    'Open your share and pay in one tap:',
    link,
  ].join('\n')
}

/** Reads the name:id pairs that requestMessage put in the link, ignoring any that aren't valid. */
function readUpiIds(params: URLSearchParams): Record<string, string> {
  const pairs = params.getAll('upi').map((entry) => {
    const colon = entry.lastIndexOf(':') // a UPI ID never has a colon; a name might
    return [entry.slice(0, colon), entry.slice(colon + 1)]
  })
  return validUpiIds(Object.fromEntries(pairs))
}

function validUpiIds(ids: Record<string, string>): Record<string, string> {
  return Object.fromEntries(
    Object.entries(ids)
      .map(([person, id]) => [person, id.trim()])
      .filter(([person, id]) => person && UPI_ID.test(id)),
  )
}

/** ["Priya"] -> "Priya"; ["Priya", "Arun", "Ravi"] -> "Priya, Arun and Ravi". */
function joinNames(names: string[]): string {
  return new Intl.ListFormat('en-IN', { type: 'conjunction' }).format(names)
}

/** Opens any UPI app (GPay, PhonePe, Paytm…) with the payee and amount filled in. */
function upiLink(upiId: string, name: string, paise: number): string {
  // encodeURIComponent, not URLSearchParams: some UPI apps show a "+" for a space literally.
  const params = { pa: upiId, pn: name, am: toRupeesText(paise), cu: 'INR', tn: 'Split Rupya' }
  const query = Object.entries(params)
    .map(([key, value]) => `${key}=${encodeURIComponent(value)}`)
    .join('&')
  return `upi://pay?${query}`
}
