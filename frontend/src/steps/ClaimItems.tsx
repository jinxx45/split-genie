// A friend's screen while the split asks "who had what" (?for=Arun): tap what you had.
// Their answer goes to the person splitting the bill, who checks it before any money is worked out.

import { useState } from 'react'
import type { Question } from '../api'
import { itemLabel } from '../items'
import { formatRupees } from '../money'
import { ErrorText, PrimaryButton, Screen, SecondaryButton } from '../ui'

type Props = {
  question: Extract<Question, { step: 'review_assignments' }>
  friend: string
  onClaim: (items: Record<number, number>) => void
  busy: boolean
  error: string | null
}

export function ClaimItems({ question, friend, onClaim, busy, error }: Props) {
  const previous = question.claims[friend]
  const [claimed, setClaimed] = useState<Record<number, number>>(previous ?? {})
  const [editing, setEditing] = useState(previous === undefined)

  function set(index: number, weight: number) {
    const next = { ...claimed }
    if (weight > 0) next[index] = weight
    else delete next[index]
    setClaimed(next)
  }

  const chosen = question.items.filter((entry) => claimed[entry.index])

  if (!editing) {
    return (
      <Screen
        title={`Thanks, ${friend}`}
        action={<SecondaryButton onClick={() => setEditing(true)}>Change my answer</SecondaryButton>}
      >
        <p className="text-muted">Your answer has been sent. Open this link again later to see what you owe.</p>
        <ul className="mt-5 space-y-1 rounded-2xl bg-white p-4">
          {chosen.length === 0 && <li className="text-muted">You said you had none of these items.</li>}
          {chosen.map((entry) => (
            <li key={entry.index}>{describeClaim(entry.item.name, entry.item.quantity, claimed[entry.index])}</li>
          ))}
        </ul>
      </Screen>
    )
  }

  return (
    <Screen
      title={`What did you have, ${friend}?`}
      action={
        // After a successful send the screen is rebuilt and opens on "Thanks" (the answer is saved).
        <PrimaryButton busy={busy} onClick={() => onClaim(claimed)}>
          {chosen.length === 0 ? 'I had none of these' : `Send (${chosen.length} item${chosen.length > 1 ? 's' : ''})`}
        </PrimaryButton>
      }
    >
      <p className="mb-5 text-muted">
        Tap what you had{question.place ? ` at ${question.place}` : ''}. The person splitting the bill checks it before
        working out who pays.
      </p>
      <ul className="space-y-3">
        {question.items.map((entry) => (
          <li key={entry.index} className="rounded-2xl bg-white p-4">
            <div className="flex items-baseline justify-between gap-3">
              <span className="font-semibold">{itemLabel(entry.item)}</span>
              <span className="amount">{formatRupees(entry.item.amount_paise)}</span>
            </div>
            {entry.item.quantity > 1 ? (
              <HowMany
                count={claimed[entry.index] ?? 0}
                quantity={entry.item.quantity}
                onChange={(count) => set(entry.index, count)}
              />
            ) : (
              <HadIt weight={claimed[entry.index] ?? 0} onChange={(weight) => set(entry.index, weight)} />
            )}
          </li>
        ))}
      </ul>
      {error && <ErrorText>{error}</ErrorText>}
    </Screen>
  )
}

/** "Had it" (a full share) or "A little" (a half share); tap the chosen one again to clear it. */
function HadIt({ weight, onChange }: { weight: number; onChange: (weight: number) => void }) {
  const options = [
    { weight: 2, label: 'Had it' },
    { weight: 1, label: 'A little' },
  ]
  return (
    <div className="mt-3 flex gap-2">
      {options.map((option) => {
        const on = weight === option.weight
        return (
          <button
            key={option.weight}
            type="button"
            aria-pressed={on}
            onClick={() => onChange(on ? 0 : option.weight)}
            className={`rounded-full border-2 px-4 py-1.5 text-sm font-semibold transition active:scale-95 ${
              on ? 'border-brand bg-brand text-white' : 'border-steel-dark bg-white text-muted'
            }`}
          >
            {option.label}
          </button>
        )
      })}
    </div>
  )
}

/** For an item ordered several times: how many of them were yours. */
function HowMany(props: { count: number; quantity: number; onChange: (count: number) => void }) {
  const { count, quantity, onChange } = props
  return (
    <div className="mt-3 flex items-center gap-3">
      <span className="flex-1 text-sm text-muted">How many were yours?</span>
      <button
        type="button"
        aria-label="One less"
        disabled={count === 0}
        onClick={() => onChange(count - 1)}
        className="flex size-9 items-center justify-center rounded-full bg-steel font-display text-xl font-semibold disabled:opacity-35"
      >
        −
      </button>
      <span className="amount w-6 text-center text-lg font-semibold" aria-live="polite">
        {count}
      </span>
      <button
        type="button"
        aria-label="One more"
        disabled={count >= quantity}
        onClick={() => onChange(count + 1)}
        className="flex size-9 items-center justify-center rounded-full bg-steel font-display text-xl font-semibold disabled:opacity-35"
      >
        +
      </button>
    </div>
  )
}

function describeClaim(name: string, quantity: number, weight: number): string {
  if (quantity > 1) return `${weight} × ${name}`
  return weight === 1 ? `A little of the ${name}` : name
}
