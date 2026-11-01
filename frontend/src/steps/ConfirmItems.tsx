// Step 1: check what was read off the bill, and fix any line by tapping it.

import { useState } from 'react'
import type { Question, Receipt } from '../api'
import { formatRupees, parseRupees, toRupeesText } from '../money'
import type { StepProps } from '../pages/SplitPage'
import { ErrorText, Paper, PrimaryButton, Screen } from '../ui'

type Props = StepProps<Extract<Question, { step: 'confirm_items' }>>

export function ConfirmItems({ question, answer, busy, error }: Props) {
  const [receipt, setReceipt] = useState<Receipt>(question.receipt)
  const [editing, setEditing] = useState<number | null>(null)

  const itemsTotal = receipt.items.reduce((sum, item) => sum + item.amount_paise, 0)
  const total = itemsTotal + receipt.tax_paise + receipt.service_charge_paise
  const matches = total === receipt.printed_total_paise

  function update(index: number, name: string, amountPaise: number, quantity: number) {
    const items = receipt.items.map((item, i) =>
      i === index ? { ...item, name, amount_paise: amountPaise, quantity } : item,
    )
    setReceipt({ ...receipt, items })
    setEditing(null)
  }

  return (
    <Screen
      title="Is this the bill?"
      step={1}
      action={
        <PrimaryButton busy={busy} onClick={() => answer(receipt)}>
          Looks right
        </PrimaryButton>
      }
    >
      <p className="mb-4 text-muted">Tap any line to fix it.</p>
      <Paper>
        <input
          value={receipt.place}
          onChange={(event) => setReceipt({ ...receipt, place: event.target.value })}
          placeholder="Restaurant name"
          aria-label="Restaurant name"
          maxLength={100}
          className="mb-2 w-full border-b border-dashed border-steel-dark pb-2 text-center font-display text-xl font-semibold"
        />
        <ul>
          {receipt.items.map((item, index) =>
            editing === index ? (
              <EditLine
                key={index}
                name={item.name}
                amountPaise={item.amount_paise}
                quantity={item.quantity}
                onSave={(name, amount, quantity) => update(index, name, amount, quantity)}
                onCancel={() => setEditing(null)}
              />
            ) : (
              <li key={index}>
                <button
                  type="button"
                  onClick={() => setEditing(index)}
                  className="flex w-full items-baseline justify-between gap-3 py-2 text-left"
                >
                  <span>{item.name}</span>
                  <span className="amount">{formatRupees(item.amount_paise)}</span>
                </button>
              </li>
            ),
          )}
        </ul>
        <div className="mt-2 border-t border-dashed border-steel-dark pt-2 text-muted">
          <Line label="Tax and adjustments" paise={receipt.tax_paise} />
          {receipt.service_charge_paise > 0 && <Line label="Service charge" paise={receipt.service_charge_paise} />}
        </div>
        <div className="mt-2 flex items-baseline justify-between border-t border-dashed border-steel-dark pt-2">
          <span className="font-display text-lg font-semibold">Total</span>
          <span className="amount text-2xl font-bold">{formatRupees(total)}</span>
        </div>
      </Paper>

      {matches ? (
        <p className="mt-4 text-brand">✓ Matches the total printed on the bill.</p>
      ) : (
        <p className="mt-4 rounded-xl bg-turmeric-soft px-3 py-2">
          The bill says {formatRupees(receipt.printed_total_paise)}. Check the lines above for a misread price.
        </p>
      )}
      {error && <ErrorText>{error}</ErrorText>}
    </Screen>
  )
}

function Line({ label, paise }: { label: string; paise: number }) {
  return (
    <div className="flex justify-between py-0.5">
      <span>{label}</span>
      <span className="amount">{formatRupees(paise)}</span>
    </div>
  )
}

function EditLine(props: {
  name: string
  amountPaise: number
  quantity: number
  onSave: (name: string, amountPaise: number, quantity: number) => void
  onCancel: () => void
}) {
  const [name, setName] = useState(props.name)
  const [amount, setAmount] = useState(toRupeesText(props.amountPaise))
  const [quantity, setQuantity] = useState(String(props.quantity))
  const paise = parseRupees(amount)
  const count = /^\d{1,3}$/.test(quantity) && Number(quantity) > 0 ? Number(quantity) : null
  const valid = name.trim() !== '' && paise !== null && count !== null

  return (
    <li className="-mx-2 my-1 rounded-xl bg-steel p-2">
      <div className="flex gap-2">
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          aria-label="Item name"
          className="min-w-0 flex-1 rounded-lg bg-white px-2 py-1.5"
        />
        <label className="flex items-center rounded-lg bg-white pl-2">
          <span aria-hidden className="text-muted">×</span>
          <input
            value={quantity}
            onChange={(event) => setQuantity(event.target.value)}
            inputMode="numeric"
            aria-label="How many were ordered"
            className="amount w-8 bg-transparent py-1.5 text-center"
          />
        </label>
        <input
          value={amount}
          onChange={(event) => setAmount(event.target.value)}
          inputMode="decimal"
          aria-label="Amount in rupees"
          className="amount w-24 rounded-lg bg-white px-2 py-1.5 text-right"
        />
      </div>
      <div className="mt-2 flex justify-end gap-2 text-sm font-semibold">
        <button type="button" onClick={props.onCancel} className="px-3 py-1 text-muted">
          Cancel
        </button>
        <button
          type="button"
          disabled={!valid}
          onClick={() => valid && props.onSave(name.trim(), paise, count)}
          className="rounded-lg bg-brand px-3 py-1 text-white disabled:bg-muted/40"
        >
          Save
        </button>
      </div>
    </li>
  )
}
