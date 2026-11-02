// Step 2: who had what. Every item, with the people Split Rupya suggests.
// Shared items: tap a name to change their share. Items ordered several times ("Cold Coffee x3")
// can instead be split by count: who had how many. Unfinished items are highlighted.
// At the top, "Ask friends" sends each friend a link to tap what they had, and "Anyone eat less?"
// gives a person half a share of every shared food item in one tap.

import { useState } from 'react'
import type { Assignment, Item, Question, ReviewItem } from '../api'
import { itemLabel } from '../items'
import { formatRupees } from '../money'
import type { StepProps } from '../pages/SplitPage'
import { Avatar, ErrorText, PrimaryButton, Screen, ShareChip } from '../ui'
import { personColor } from '../colors'

type Props = StepProps<Extract<Question, { step: 'review_assignments' }>>

export function ReviewItems({ question, people, answer, busy, error }: Props) {
  const [assignments, setAssignments] = useState<Assignment[]>(question.items.map((entry) => entry.suggested))
  const [lightEaters, setLightEaters] = useState<string[]>(question.light_eaters)

  function toggleLightEater(person: string) {
    const eatsLess = !lightEaters.includes(person)
    setLightEaters(people.filter((p) => (p === person ? eatsLess : lightEaters.includes(p))))
    setAssignments(assignments.map((assignment, i) => eatLess(question.items[i].item, assignment, person, eatsLess)))
  }

  function update(index: number, assignment: Assignment) {
    setAssignments(assignments.map((current, i) => (i === index ? assignment : current)))
  }

  function applyClaims() {
    // The server has already merged the claims into the suggestions (apply_claims).
    setAssignments(question.claimed)
  }

  const unfinished = question.items.filter((entry, index) => !isFinished(assignments[index], entry.item.quantity)).length

  function submit() {
    // Send only what the user changed; untouched items keep Split Rupya's suggestion.
    const changes: Record<number, Assignment> = {}
    question.items.forEach((entry, index) => {
      if (!sameAssignment(entry.suggested, assignments[index])) changes[entry.index] = assignments[index]
    })
    const lightEatersChanged = lightEaters.join() !== question.light_eaters.join()
    answer(lightEatersChanged ? { changes, light_eaters: lightEaters } : { changes })
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
      <AskFriends people={people} place={question.place} claims={question.claims} onUse={applyClaims} />
      <LightEaters people={people} lightEaters={lightEaters} onToggle={toggleLightEater} />
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

/** One WhatsApp message with one link for the group: each friend picks their name and taps what
 * they had. Then see who has answered, and use their answers. */
function AskFriends(props: {
  people: string[]
  place: string
  claims: Record<string, Record<string, number>>
  onUse: () => void
}) {
  const { people, place, claims, onUse } = props
  const answered = people.filter((person) => claims[person] !== undefined)

  const link = `${window.location.origin}${window.location.pathname}?who`
  const message = `Splitting the bill${place ? ` for ${place}` : ''}. Tap what you had:\n${link}`

  return (
    <details open={answered.length > 0} className="group mb-3 rounded-2xl bg-white p-4">
      <summary className="flex cursor-pointer list-none items-center justify-between font-display text-lg font-semibold">
        Ask friends what they had
        <span aria-hidden className="text-muted transition group-open:rotate-180">⌄</span>
      </summary>
      <p className="text-sm text-muted">One link for the group: each friend taps their own items. You check before anything is final.</p>
      <a
        href={`https://wa.me/?text=${encodeURIComponent(message)}`}
        target="_blank"
        rel="noreferrer"
        className="mt-3 block rounded-xl bg-steel py-2.5 text-center font-display font-semibold"
      >
        Send the link on WhatsApp
      </a>
      <div className="mt-3 flex flex-wrap gap-2" aria-label="Who has answered">
        {people.map((person) => (
          <span
            key={person}
            className={`rounded-full px-3 py-1 text-sm font-semibold ${claims[person] ? 'bg-brand text-white' : 'bg-steel text-muted'}`}
          >
            {claims[person] ? `✓ ${person}` : person}
          </span>
        ))}
      </div>
      {answered.length > 0 && (
        <button
          type="button"
          onClick={onUse}
          className="mt-3 w-full rounded-xl bg-brand py-2.5 font-display font-semibold text-white"
        >
          Use their answers ({answered.length} of {people.length})
        </button>
      )}
    </details>
  )
}

/** One tap per person who ate less than the others: they pay half a share of shared food. */
function LightEaters(props: { people: string[]; lightEaters: string[]; onToggle: (person: string) => void }) {
  const { people, lightEaters, onToggle } = props
  return (
    <section className="mb-6 rounded-2xl bg-white p-4">
      <h2 className="font-display text-lg font-semibold">Anyone eat less?</h2>
      <p className="text-sm text-muted">They pay half a share of shared food. Drinks stay as they are.</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {people.map((person) => {
          const color = personColor(people, person)
          const on = lightEaters.includes(person)
          return (
            <button
              key={person}
              type="button"
              aria-pressed={on}
              onClick={() => onToggle(person)}
              className="rounded-full border-2 px-3 py-1.5 text-sm font-semibold transition active:scale-95"
              style={{
                borderColor: on ? color : 'var(--color-steel-dark)',
                background: on ? `linear-gradient(90deg, ${color}66 50%, #fff 50%)` : '#fff',
                color: on ? 'var(--color-ink)' : 'var(--color-muted)',
              }}
            >
              {person}
              {on && <span className="ml-1">½</span>}
            </button>
          )
        })}
      </div>
    </section>
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
    <li className={`rounded-2xl p-4 transition-colors ${unfinished ? 'bg-saffron-soft ring-2 ring-saffron' : 'bg-white'}`}>
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

/** The same rule as eat_less in the backend: on shared food and desserts, a light eater's full
 * share becomes half (or, when they're no longer a light eater, half goes back to full). */
function eatLess(item: Item, assignment: Assignment, person: string, eatsLess: boolean): Assignment {
  const [from, to] = eatsLess ? [2, 1] : [1, 2]
  if (assignment.by_count || !['food', 'dessert'].includes(item.category) || assignment.weights[person] !== from) {
    return assignment
  }
  return { ...assignment, weights: { ...assignment.weights, [person]: to } }
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
