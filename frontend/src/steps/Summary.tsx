// The payments and each person's breakdown: shown on the approval screen and the final one.

import type { ReactNode } from 'react'
import type { Breakdown, Payment } from '../api'
import { formatRupees } from '../money'
import { Avatar, Paper } from '../ui'
import { personColor } from '../colors'

/** Who pays whom. `action` adds something under a payment, such as a share button. */
export function Payments(props: {
  payments: Payment[]
  people: string[]
  action?: (payment: Payment) => ReactNode
}) {
  const { payments, people, action } = props
  if (payments.length === 0) {
    return <p className="rounded-2xl bg-white p-4">Everyone is already square. Nobody needs to pay.</p>
  }
  return (
    <ul className="space-y-2">
      {payments.map((payment) => (
        <li key={`${payment.sender}-${payment.receiver}`} className="rounded-2xl bg-white p-4">
          <div className="flex items-center gap-3">
            <Avatar name={payment.sender} color={personColor(people, payment.sender)} />
            <span className="flex-1 leading-snug">
              <span className="font-semibold">{payment.sender}</span>
              <span className="text-muted"> pays </span>
              <span className="font-semibold">{payment.receiver}</span>
            </span>
            <span className="amount text-xl font-bold">{formatRupees(payment.amount_paise)}</span>
          </div>
          {action?.(payment)}
        </li>
      ))}
    </ul>
  )
}

/** Each person's total, which opens into their part of every item plus tax and charges. */
export function BreakdownList({ breakdown, people }: { breakdown: Record<string, Breakdown>; people: string[] }) {
  return (
    <div className="space-y-2">
      {Object.entries(breakdown).map(([person, part]) => (
        <details key={person} className="group rounded-2xl bg-white">
          <summary className="flex cursor-pointer list-none items-center gap-3 p-4">
            <Avatar name={person} color={personColor(people, person)} />
            <span className="flex-1 font-semibold">{person}</span>
            <span className="amount text-lg font-semibold">{formatRupees(part.total_paise)}</span>
            <span aria-hidden className="text-muted transition group-open:rotate-180">⌄</span>
          </summary>
          <div className="px-2 pb-2">
            <BreakdownPaper part={part} />
          </div>
        </details>
      ))}
    </div>
  )
}

/** One person's part of every item they had, plus their share of tax and charges. */
export function BreakdownPaper({ part }: { part: Breakdown }) {
  return (
    <Paper>
      <ul className="text-sm">
        {part.items.map((share, index) => (
          <li key={index} className="flex items-baseline justify-between gap-3 py-1">
            <span>
              {share.item}
              <span className="block text-xs text-muted">
                {share.shared_by === 1 ? 'just them' : `shared by ${share.shared_by}`}
                {share.half && ', half share'}
              </span>
            </span>
            <span className="amount">{formatRupees(share.amount_paise)}</span>
          </li>
        ))}
        <li className="mt-1 flex justify-between border-t border-dashed border-steel-dark pt-2 text-muted">
          <span>Tax and charges</span>
          <span className="amount">{formatRupees(part.charges_paise)}</span>
        </li>
      </ul>
    </Paper>
  )
}
