// The finished split: who pays whom, with UPI buttons and a WhatsApp summary.

import { useState } from 'react'
import type { Split } from '../api'
import { formatRupees, toRupeesText } from '../money'
import { Screen } from '../ui'
import { BreakdownList, Payments } from './Summary'

type Props = { result: NonNullable<Split['result']>; people: string[] }

// A UPI ID looks like name@bank.
const UPI_ID = /^[\w.-]{2,256}@[a-zA-Z]{2,64}$/

export function Done({ result, people }: Props) {
  const receivers = [...new Set(result.payments.map((payment) => payment.receiver))]
  const [upiIds, setUpiIds] = useState<Record<string, string>>({})

  const summary = [
    'Split Genie: who pays whom',
    ...result.payments.map(
      (payment) => `${payment.sender} → ${payment.receiver}: ${formatRupees(payment.amount_paise)}`,
    ),
    window.location.href,
  ].join('\n')

  return (
    <Screen title="Split done">
      <Payments payments={result.payments} people={people} />

      {receivers.length > 0 && (
        <div className="mt-6 space-y-3">
          {receivers.map((receiver) => {
            const upiId = (upiIds[receiver] ?? '').trim()
            return (
              <div key={receiver} className="rounded-2xl bg-white p-4">
                <label className="block text-sm text-muted" htmlFor={`upi-${receiver}`}>
                  {receiver}’s UPI ID, to show pay buttons
                </label>
                <input
                  id={`upi-${receiver}`}
                  value={upiIds[receiver] ?? ''}
                  onChange={(event) => setUpiIds({ ...upiIds, [receiver]: event.target.value })}
                  placeholder="name@okbank"
                  autoCapitalize="none"
                  autoCorrect="off"
                  className="mt-1 w-full rounded-lg bg-steel px-3 py-2"
                />
                {UPI_ID.test(upiId) && (
                  <div className="mt-3 space-y-2">
                    {result.payments
                      .filter((payment) => payment.receiver === receiver)
                      .map((payment) => (
                        <a
                          key={payment.sender}
                          href={upiLink(upiId, receiver, payment.amount_paise)}
                          className="block rounded-xl bg-leaf px-4 py-3 text-center font-display font-semibold text-white"
                        >
                          {payment.sender}: pay {formatRupees(payment.amount_paise)} with UPI
                        </a>
                      ))}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      <a
        href={`https://wa.me/?text=${encodeURIComponent(summary)}`}
        target="_blank"
        rel="noreferrer"
        className="mt-4 block rounded-2xl bg-white px-4 py-3 text-center font-display font-semibold text-leaf"
      >
        Share on WhatsApp
      </a>

      <h2 className="mt-8 mb-3 font-display text-xl font-semibold">How it adds up</h2>
      <BreakdownList breakdown={result.breakdown} people={people} />
    </Screen>
  )
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
