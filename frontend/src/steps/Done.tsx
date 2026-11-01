// The finished split, in two views:
// - the person who split it: a summary, then a WhatsApp request for each friend who owes money;
// - a friend opening that request (?for=Arun): their own share first, with a UPI pay button.

import { useState } from 'react'
import { useSearchParams } from 'react-router'
import type { Payment, Split } from '../api'
import { formatRupees, toRupeesText } from '../money'
import { Paper, Screen } from '../ui'
import { BreakdownList, BreakdownPaper, Payments } from './Summary'

type Result = NonNullable<Split['result']>
type Props = { result: Result; people: string[] }

// A UPI ID looks like name@bank.
const UPI_ID = /^[\w.-]{2,256}@[a-zA-Z]{2,64}$/

export function Done({ result, people }: Props) {
  const [params] = useSearchParams()
  const friend = params.get('for')
  if (friend && people.includes(friend)) {
    return <FriendView friend={friend} result={result} people={people} upiIds={readUpiIds(params)} />
  }
  return <SplitterView result={result} people={people} />
}

function SplitterView({ result, people }: Props) {
  const receivers = [...new Set(result.payments.map((payment) => payment.receiver))]
  const [typedIds, setTypedIds] = useState<Record<string, string>>({})
  const upiIds = validUpiIds(typedIds)

  return (
    <Screen title="Split done">
      <BillSummary result={result} people={people} />

      {result.payments.length > 0 && (
        <h2 className="mt-8 mb-3 font-display text-xl font-semibold">Send each friend their share</h2>
      )}
      {receivers.map((receiver) => (
        <label key={receiver} className="mb-3 block rounded-2xl bg-white p-4">
          <span className="block text-sm text-muted">{receiver}’s UPI ID, so friends can pay in one tap</span>
          <input
            value={typedIds[receiver] ?? ''}
            onChange={(event) => setTypedIds({ ...typedIds, [receiver]: event.target.value })}
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
        action={(payment) => (
          <a
            href={`https://wa.me/?text=${encodeURIComponent(requestMessage(payment, result.title, upiIds))}`}
            target="_blank"
            rel="noreferrer"
            className="mt-3 block rounded-xl bg-steel py-2.5 text-center font-display font-semibold"
          >
            Send to {payment.sender} on WhatsApp
          </a>
        )}
      />

      <h2 className="mt-8 mb-3 font-display text-xl font-semibold">How it adds up</h2>
      <BreakdownList breakdown={result.breakdown} people={people} />
    </Screen>
  )
}

function FriendView({ friend, result, people, upiIds }: Props & { friend: string; upiIds: Record<string, string> }) {
  const mine = result.payments.filter((payment) => payment.sender === friend || payment.receiver === friend)
  const payable = mine.filter((payment) => payment.sender === friend && upiIds[payment.receiver])
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
        <Payments payments={mine} people={people} />
      ) : (
        <p className="rounded-2xl bg-white p-4">You’re all square. Nothing to pay.</p>
      )}

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

/** The bill at a glance: where, how much, how many people, who paid. */
function BillSummary({ result, people }: Props) {
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

/** The WhatsApp message for one payment. Its link opens the sender's own view of the split. */
function requestMessage(payment: Payment, title: string, upiIds: Record<string, string>): string {
  const params = new URLSearchParams({ for: payment.sender })
  // Every UPI ID typed in goes in the link as name:id, so the friend gets pay buttons.
  Object.entries(upiIds).forEach(([person, id]) => params.append('upi', `${person}:${id}`))
  const link = `${window.location.origin}${window.location.pathname}?${params}`

  return [
    `${payment.receiver} requests a split of ${formatRupees(payment.amount_paise)} for ${title || 'the bill'}.`,
    'Tap this link for your breakdown:',
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
  const params = { pa: upiId, pn: name, am: toRupeesText(paise), cu: 'INR', tn: 'Split Genie' }
  const query = Object.entries(params)
    .map(([key, value]) => `${key}=${encodeURIComponent(value)}`)
    .join('&')
  return `upi://pay?${query}`
}
