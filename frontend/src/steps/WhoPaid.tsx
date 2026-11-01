// Step 3: who paid. Usually one tap; "split the payment" if several people paid.

import { useState } from 'react'
import type { Question } from '../api'
import { formatRupees, parseRupees } from '../money'
import type { StepProps } from '../pages/SplitPage'
import { Avatar, ErrorText, PrimaryButton, Screen } from '../ui'
import { personColor } from '../colors'

type Props = StepProps<Extract<Question, { step: 'payer' }>>

export function WhoPaid({ question, people, answer, busy, error }: Props) {
  const total = question.total_paise
  const [payer, setPayer] = useState<string | null>(null)
  const [several, setSeveral] = useState(false)
  const [amounts, setAmounts] = useState<Record<string, string>>({})

  const parsed = Object.entries(amounts)
    .map(([person, text]) => [person, parseRupees(text)] as const)
    .filter((entry): entry is readonly [string, number] => entry[1] !== null && entry[1] > 0)
  const paidSoFar = parsed.reduce((sum, [, paise]) => sum + paise, 0)
  const left = total - paidSoFar

  function submit() {
    answer({ paid: several ? Object.fromEntries(parsed) : { [payer as string]: total } })
  }

  const ready = several ? left === 0 && parsed.length > 0 : payer !== null
  const label = several
    ? left === 0
      ? 'Next'
      : left > 0
        ? `${formatRupees(left)} still to account for`
        : `${formatRupees(-left)} more than the bill`
    : 'Next'

  return (
    <Screen
      title={`Who paid ${formatRupees(total)}?`}
      step={3}
      action={
        <PrimaryButton busy={busy} disabled={!ready} onClick={submit}>
          {label}
        </PrimaryButton>
      }
    >
      <ul className="space-y-2">
        {people.map((person) => (
          <li key={person}>
            {several ? (
              <label className="flex items-center gap-3 rounded-2xl bg-white p-3">
                <Avatar name={person} color={personColor(people, person)} />
                <span className="flex-1 font-semibold">{person}</span>
                <span className="text-muted">₹</span>
                <input
                  value={amounts[person] ?? ''}
                  onChange={(event) => setAmounts({ ...amounts, [person]: event.target.value })}
                  inputMode="decimal"
                  placeholder="0"
                  aria-label={`Amount ${person} paid`}
                  className="amount w-28 rounded-lg bg-steel px-2 py-1.5 text-right"
                />
              </label>
            ) : (
              <button
                type="button"
                onClick={() => setPayer(person)}
                aria-pressed={payer === person}
                className={`flex w-full items-center gap-3 rounded-2xl p-3 text-left transition ${
                  payer === person ? 'bg-leaf text-white' : 'bg-white'
                }`}
              >
                <Avatar name={person} color={personColor(people, person)} />
                <span className="flex-1 font-semibold">{person}</span>
                {payer === person && <span aria-hidden>✓</span>}
              </button>
            )}
          </li>
        ))}
      </ul>

      <button
        type="button"
        onClick={() => setSeveral(!several)}
        className="mt-4 font-display font-semibold text-leaf"
      >
        {several ? 'One person paid' : 'More than one person paid'}
      </button>
      {error && <ErrorText>{error}</ErrorText>}
    </Screen>
  )
}
