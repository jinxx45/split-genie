// Choosing people: typing names (with recent friends a tap away), or picking from a group's members.

import { useState } from 'react'
import { personColor } from './colors'
import { formatRupees } from './money'
import { Avatar, ErrorText } from './ui'

/** Names as removable chips, a box to add more, and recent friends to add with one tap. */
export function PeoplePicker(props: { people: string[]; onChange: (people: string[]) => void; suggestions: string[] }) {
  const { people, onChange } = props
  const [name, setName] = useState('')
  const [error, setError] = useState<string | null>(null)

  const included = (person: string) => people.some((p) => p.toLowerCase() === person.toLowerCase())
  const suggestions = props.suggestions.filter((person) => !included(person)).slice(0, 8)

  function add(person = name) {
    const trimmed = person.trim()
    if (!trimmed) return
    if (included(trimmed)) {
      setError(`${trimmed} is already added.`)
      return
    }
    onChange([...people, trimmed])
    setName('')
    setError(null)
  }

  return (
    <>
      <div className="flex flex-wrap gap-2">
        {people.map((person) => (
          <button
            key={person}
            type="button"
            onClick={() => onChange(people.filter((p) => p !== person))}
            aria-label={`Remove ${person}`}
            className="flex items-center gap-2 rounded-full bg-white py-1 pr-3 pl-1 font-semibold"
          >
            <Avatar name={person} color={personColor(people, person)} />
            {person}
            <span aria-hidden className="text-muted">×</span>
          </button>
        ))}
      </div>

      <div className="mt-3 flex gap-2">
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault()
              add()
            }
          }}
          placeholder={people.length ? 'Add another name' : 'Add a name'}
          maxLength={40}
          enterKeyHint="done"
          className="min-w-0 flex-1 rounded-2xl bg-white px-4 py-3"
        />
        <button
          type="button"
          onClick={() => add()}
          disabled={!name.trim()}
          className="rounded-2xl bg-white px-5 font-display font-semibold text-brand disabled:text-muted/50"
        >
          Add
        </button>
      </div>

      {suggestions.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2" aria-label="Recent friends">
          {suggestions.map((person) => (
            <button
              key={person}
              type="button"
              onClick={() => add(person)}
              className="rounded-full border-2 border-dashed border-steel-dark px-3 py-1 text-sm font-semibold text-muted"
            >
              + {person}
            </button>
          ))}
        </div>
      )}
      {error && <ErrorText>{error}</ErrorText>}
    </>
  )
}

/** A group's members as chips: tap to include or leave out. `members` sets each person's colour. */
export function MemberToggles(props: { members: string[]; chosen: string[]; onChange: (chosen: string[]) => void }) {
  const { members, chosen, onChange } = props
  return (
    <div className="flex flex-wrap gap-2">
      {members.map((member) => {
        const on = chosen.includes(member)
        const color = personColor(members, member)
        return (
          <button
            key={member}
            type="button"
            aria-pressed={on}
            onClick={() => onChange(on ? chosen.filter((p) => p !== member) : members.filter((p) => p === member || chosen.includes(p)))}
            className="rounded-full border-2 px-3 py-1.5 text-sm font-semibold transition active:scale-95"
            style={{
              borderColor: on ? color : 'var(--color-steel-dark)',
              background: on ? color : '#fff',
              color: on ? '#fff' : 'var(--color-muted)',
            }}
          >
            {member}
          </button>
        )
      })}
    </div>
  )
}

/** "Who paid?": one person, picked from `people`. `you` gets "(you)" after their name. */
export function PayerPicker(props: { people: string[]; paidBy: string; onChange: (person: string) => void; you?: string }) {
  return (
    <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Who paid">
      {props.people.map((person) => {
        const on = props.paidBy === person
        const color = personColor(props.people, person)
        return (
          <button
            key={person}
            type="button"
            role="radio"
            aria-checked={on}
            onClick={() => props.onChange(person)}
            className="rounded-full border-2 px-3 py-1.5 text-sm font-semibold"
            style={{ borderColor: on ? color : 'var(--color-steel-dark)', background: on ? color : '#fff', color: on ? '#fff' : 'var(--color-muted)' }}
          >
            {person === props.you ? `${person} (you)` : person}
          </button>
        )
      })}
    </div>
  )
}

/** Uneven shares: e.g. a bigger room pays 2 shares. Shows what each share comes to. */
export function ShareSteppers(props: {
  people: string[]
  members: string[]
  weights: Record<string, number>
  onChange: (person: string, weight: number) => void
  paise: number | null
}) {
  const total = Object.values(props.weights).reduce((sum, weight) => sum + weight, 0)
  return (
    <ul className="mt-3 divide-y divide-steel rounded-2xl bg-white px-4">
      {props.people.map((person) => {
        const weight = props.weights[person]
        return (
          <li key={person} className="flex items-center gap-3 py-2">
            <span className="size-2.5 rounded-full" style={{ background: personColor(props.members, person) }} aria-hidden />
            <span className="flex-1">
              {person}
              {props.paise ? (
                <span className="block text-sm text-muted">about {formatRupees(Math.round((props.paise * weight) / total))}</span>
              ) : null}
            </span>
            <button
              type="button"
              aria-label={`One share less for ${person}`}
              disabled={weight <= 1}
              onClick={() => props.onChange(person, weight - 1)}
              className="flex size-9 items-center justify-center rounded-full bg-steel font-display text-xl font-semibold disabled:opacity-35"
            >
              −
            </button>
            <span className="amount w-18 text-center whitespace-nowrap">
              {weight} share{weight > 1 ? 's' : ''}
            </span>
            <button
              type="button"
              aria-label={`One share more for ${person}`}
              disabled={weight >= 9}
              onClick={() => props.onChange(person, weight + 1)}
              className="flex size-9 items-center justify-center rounded-full bg-steel font-display text-xl font-semibold disabled:opacity-35"
            >
              +
            </button>
          </li>
        )
      })}
    </ul>
  )
}
