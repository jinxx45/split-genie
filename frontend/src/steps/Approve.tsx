// Step 4: approve the split, or say what's wrong and let Split Rupya fix it.

import { useState } from 'react'
import type { Assignment, Question } from '../api'
import type { StepProps } from '../pages/SplitPage'
import { ErrorText, PrimaryButton, Screen, SecondaryButton } from '../ui'
import { BreakdownList, Payments } from './Summary'

type Props = StepProps<Extract<Question, { step: 'approve' }>>

export function Approve({ question, people, answer, busy, error }: Props) {
  // If the last note couldn't be used, reopen the note box so the user can rephrase it.
  const [fixing, setFixing] = useState(question.error !== null)
  const [note, setNote] = useState('')

  const action = fixing ? (
    <>
      <PrimaryButton busy={busy} disabled={!note.trim()} onClick={() => answer({ approved: false, note })}>
        Fix it
      </PrimaryButton>
      <SecondaryButton onClick={() => setFixing(false)}>Cancel</SecondaryButton>
    </>
  ) : (
    <>
      <PrimaryButton busy={busy} onClick={() => answer({ approved: true })}>
        Approve
      </PrimaryButton>
      <SecondaryButton onClick={() => setFixing(true)}>Something’s wrong</SecondaryButton>
    </>
  )

  return (
    <Screen title="Here’s the split" step={4} action={action}>
      {question.changes.length > 0 && (
        <div className="mb-5 rounded-2xl bg-saffron-soft p-4">
          <p className="font-display text-lg font-semibold">Changed from your note</p>
          <ul className="mt-1 space-y-1">
            {question.changes.map((change, index) => (
              <li key={index}>
                <span className="font-semibold">{change.item}</span>: {names(change.before)} → {names(change.after)}
              </li>
            ))}
          </ul>
        </div>
      )}

      {fixing && (
        <label className="mb-6 block">
          <span className="font-display text-lg font-semibold">What’s wrong?</span>
          <textarea
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="Priya didn’t have the brownie"
            maxLength={500}
            rows={2}
            autoFocus
            className="mt-2 w-full resize-none rounded-2xl bg-white px-4 py-3"
          />
        </label>
      )}
      {(question.error || error) && <ErrorText>{question.error ?? error}</ErrorText>}

      <Payments payments={question.payments} people={people} />
      <h2 className="mt-8 mb-3 font-display text-xl font-semibold">How it adds up</h2>
      <BreakdownList breakdown={question.breakdown} people={people} />
    </Screen>
  )
}

/** Shared: "Arun, Priya (half)". By count: "Arun 2, Priya 1". */
function names({ weights, by_count }: Assignment): string {
  return Object.entries(weights)
    .map(([person, weight]) => (by_count ? `${person} ${weight}` : weight === 1 ? `${person} (half)` : person))
    .join(', ')
}
