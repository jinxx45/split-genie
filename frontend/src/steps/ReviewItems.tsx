// Step 2: who had what. Every item, with the people Split Genie suggests.
// Shared items: tap a name to change their share. Items ordered several times ("Cold Coffee x3")
// can instead be split by count: who had how many. Unfinished items are highlighted.

import { useState } from 'react'
import type { Assignment, Question, ReviewItem } from '../api'
import { itemLabel } from '../items'
import { formatRupees } from '../money'
import type { StepProps } from '../pages/SplitPage'
import { Avatar, ErrorText, PrimaryButton, Screen, ShareChip } from '../ui'
import { personColor } from '../colors'

type Props = StepProps<Extract<Question, { step: 'review_assignments' }>>

export function ReviewItems({ question, people, answer, busy, error }: Props) {
  const [assignments, setAssignments] = useState<Assignment[]>(question.items.map((entry) => entry.suggested))

  function update(index: number, assignment: Assignment) {
    setAssignments(assignments.map((current, i) => (i === index ? assignment : current)))
  }

  const unfinished = question.items.filter((entry, index) => !isFinished(assignments[index], entry.item.quantity)).length

  function submit() {
    // Send only what the user changed; untouched items keep Split Genie's suggestion.
    const changes: Record<number, Assignment> = {}
    question.items.forEach((entry, index) => {
      if (!sameAssignment(entry.suggested, assignments[index])) changes[entry.index] = assignments[index]
    })
    answer({ changes })
  }

  return (
    <Screen
      title="Who had what?"
      step={2}
      action={
        <PrimaryButton busy={busy} disabled={unfinished > 0} onClick={submit}>
          {unfinished === 1 ? '1 item still needs a name' : unfinished > 1 ? `${unfinished} items still need a name` : 'Next'}
        </PrimaryButton>
      }
    >
      <p className="mb-5 text-muted">Tap a name: once for a full share, again for half, again to remove.</p>
      <ul className="space-y-3">
        {question.items.map((entry, index) => (
          <ItemCard
            key={entry.index}
            entry={entry}
            people={people}
            assignment={assignments[index]}
            onChange={(assignment) => update(index, assignment)}
          />
        ))}
      </ul>
      {error && <ErrorText>{error}</ErrorText>}
    </Screen>
  )
}

function ItemCard(props: {
  entry: ReviewItem
  people: string[]
  assignment: Assignment
  onChange: (assignment: Assignment) => void
}) {
  const { entry, people, assignment, onChange } = props
  const { quantity } = entry.item
  const unfinished = !isFinished(assignment, quantity)

  function switchMode(byCount: boolean) {
    // Back to the suggested way: restore the suggestion. The other way: start empty.
    onChange(byCount === entry.suggested.by_count ? entry.suggested : { weights: {}, by_count: byCount })
  }

  function setWeight(person: string, weight: number | undefined) {
    const weights = { ...assignment.weights }
    if (weight) weights[person] = weight
    else delete weights[person]
    onChange({ ...assignment, weights })
  }

  return (
    <li className={`rounded-2xl p-4 transition-colors ${unfinished ? 'bg-turmeric-soft ring-2 ring-turmeric' : 'bg-white'}`}>
      <div className="flex items-baseline justify-between gap-3">
        <span className="font-semibold">{itemLabel(entry.item)}</span>
        <span className="amount">{formatRupees(entry.item.amount_paise)}</span>
      </div>
      <p className="text-sm text-muted">{entry.reason}</p>

      {quantity > 1 && <ModeSwitch byCount={assignment.by_count} onChange={switchMode} />}

      {assignment.by_count ? (
        <CountPicker people={people} quantity={quantity} weights={assignment.weights} onChange={setWeight} />
      ) : (
        <div className="mt-3 flex flex-wrap gap-2">
          {people.map((person) => (
            <ShareChip
              key={person}
              name={person}
              color={personColor(people, person)}
              weight={assignment.weights[person]}
              onChange={(weight) => setWeight(person, weight)}
            />
          ))}
        </div>
      )}
    </li>
  )
}

/** "Shared" or "Who had how many", for an item ordered more than once. */
function ModeSwitch(props: { byCount: boolean; onChange: (byCount: boolean) => void }) {
  const options = [
    { byCount: false, label: 'Shared' },
    { byCount: true, label: 'Who had how many' },
  ]
  return (
    <div role="radiogroup" aria-label="How to split this item" className="mt-3 inline-flex rounded-full bg-steel p-1 text-sm font-semibold">
      {options.map((option) => (
        <button
          key={option.label}
          type="button"
          role="radio"
          aria-checked={props.byCount === option.byCount}
          onClick={() => props.onChange(option.byCount)}
          className={`rounded-full px-3 py-1 transition ${props.byCount === option.byCount ? 'bg-white shadow-sm' : 'text-muted'}`}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}

/** A − count + row per person, and how many are still unassigned. */
function CountPicker(props: {
  people: string[]
  quantity: number
  weights: Record<string, number>
  onChange: (person: string, count: number | undefined) => void
}) {
  const { people, quantity, weights, onChange } = props
  const left = quantity - Object.values(weights).reduce((sum, count) => sum + count, 0)

  return (
    <div className="mt-3">
      <ul className="divide-y divide-steel">
        {people.map((person) => {
          const count = weights[person] ?? 0
          return (
            <li key={person} className="flex items-center gap-3 py-1.5">
              <Avatar name={person} color={personColor(people, person)} />
              <span className={`flex-1 ${count ? 'font-semibold' : 'text-muted'}`}>{person}</span>
              <StepButton label={`One less for ${person}`} disabled={count === 0} onClick={() => onChange(person, count - 1 || undefined)}>
                −
              </StepButton>
              <span className="amount w-6 text-center text-lg font-semibold" aria-live="polite">
                {count}
              </span>
              <StepButton label={`One more for ${person}`} disabled={left <= 0} onClick={() => onChange(person, count + 1)}>
                +
              </StepButton>
            </li>
          )
        })}
      </ul>
      <p className={`mt-1 text-sm ${left === 0 ? 'text-muted' : 'font-semibold'}`}>
        {left === 0 ? `All ${quantity} have a name` : `${left} of ${quantity} still need a name`}
      </p>
    </div>
  )
}

function StepButton(props: { label: string; disabled: boolean; onClick: () => void; children: string }) {
  return (
    <button
      type="button"
      aria-label={props.label}
      disabled={props.disabled}
      onClick={props.onClick}
      className="flex size-9 items-center justify-center rounded-full bg-steel font-display text-xl font-semibold transition active:scale-90 disabled:opacity-35"
    >
      {props.children}
    </button>
  )
}

/** Someone has the item and, when split by count, the counts add up to how many were ordered.
 * The backend checks the same thing (assignment_problem) and explains what's missing. */
function isFinished(assignment: Assignment, quantity: number): boolean {
  const counts = Object.values(assignment.weights)
  if (counts.length === 0) return false
  return !assignment.by_count || counts.reduce((sum, count) => sum + count, 0) === quantity
}

function sameAssignment(a: Assignment, b: Assignment): boolean {
  const keys = Object.keys(a.weights)
  return (
    a.by_count === b.by_count &&
    keys.length === Object.keys(b.weights).length &&
    keys.every((key) => a.weights[key] === b.weights[key])
  )
}
