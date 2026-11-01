// Step 2: who had what. Every item, with the people Split Genie suggests; tap a name to change
// their share. Items it couldn't work out are highlighted and must be answered.

import { useState } from 'react'
import type { Question, Weight, Weights } from '../api'
import { formatRupees } from '../money'
import type { StepProps } from '../pages/SplitPage'
import { ErrorText, PrimaryButton, Screen, ShareChip } from '../ui'
import { personColor } from '../colors'

type Props = StepProps<Extract<Question, { step: 'review_assignments' }>>

export function ReviewItems({ question, people, answer, busy, error }: Props) {
  const [weights, setWeights] = useState<Weights[]>(question.items.map((entry) => entry.suggested))

  function setShare(index: number, person: string, weight: Weight | undefined) {
    const next = { ...weights[index] }
    if (weight) next[person] = weight
    else delete next[person]
    setWeights(weights.map((current, i) => (i === index ? next : current)))
  }

  const unanswered = weights.filter((itemWeights) => Object.keys(itemWeights).length === 0).length

  function submit() {
    // Send only what the user changed; untouched items keep Split Genie's suggestion.
    const changes: Record<number, Weights> = {}
    question.items.forEach((entry, index) => {
      if (!sameWeights(entry.suggested, weights[index])) changes[entry.index] = weights[index]
    })
    answer({ changes })
  }

  return (
    <Screen
      title="Who had what?"
      step={2}
      action={
        <PrimaryButton busy={busy} disabled={unanswered > 0} onClick={submit}>
          {unanswered === 1 ? '1 item still needs a name' : unanswered > 1 ? `${unanswered} items still need a name` : 'Next'}
        </PrimaryButton>
      }
    >
      <p className="mb-5 text-muted">Tap a name: once for a full share, again for half, again to remove.</p>
      <ul className="space-y-3">
        {question.items.map((entry, index) => {
          const empty = Object.keys(weights[index]).length === 0
          return (
            <li
              key={entry.index}
              className={`rounded-2xl p-4 transition-colors ${empty ? 'bg-turmeric-soft ring-2 ring-turmeric' : 'bg-white'}`}
            >
              <div className="flex items-baseline justify-between gap-3">
                <span className="font-semibold">{entry.item.name}</span>
                <span className="amount">{formatRupees(entry.item.amount_paise)}</span>
              </div>
              <p className="text-sm text-muted">{entry.reason}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {people.map((person) => (
                  <ShareChip
                    key={person}
                    name={person}
                    color={personColor(people, person)}
                    weight={weights[index][person]}
                    onChange={(weight) => setShare(index, person, weight)}
                  />
                ))}
              </div>
            </li>
          )
        })}
      </ul>
      {error && <ErrorText>{error}</ErrorText>}
    </Screen>
  )
}

function sameWeights(a: Weights, b: Weights): boolean {
  const keys = Object.keys(a)
  return keys.length === Object.keys(b).length && keys.every((key) => a[key] === b[key])
}
