// Start a split: who was there, an optional note, and photos of the bill.

import { useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router'
import { ApiError, createSplit } from '../api'
import { Avatar, ErrorText, PrimaryButton, Screen } from '../ui'
import { Reading } from './Reading'
import { personColor } from '../colors'

export function NewSplit() {
  const navigate = useNavigate()
  const [people, setPeople] = useState<string[]>([])
  const [name, setName] = useState('')
  const [note, setNote] = useState('')
  const [photos, setPhotos] = useState<File[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function addPerson() {
    const trimmed = name.trim()
    if (!trimmed) return
    if (people.some((person) => person.toLowerCase() === trimmed.toLowerCase())) {
      setError(`${trimmed} is already in the split.`)
      return
    }
    setPeople([...people, trimmed])
    setName('')
    setError(null)
  }

  async function start(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const split = await createSplit(people, note, photos)
      navigate(`/split/${split.id}`)
    } catch (problem) {
      setError(problem instanceof ApiError ? problem.message : 'Couldn’t reach Split Genie. Check your connection.')
      setBusy(false)
    }
  }

  if (busy) return <Reading />

  const ready = people.length >= 2 && photos.length > 0
  const missing =
    people.length < 2 ? 'Add at least two people' : photos.length === 0 ? 'Add a photo of the bill' : null

  return (
    <form onSubmit={start}>
      <Screen
        title="Who’s splitting the bill?"
        action={
          <PrimaryButton type="submit" disabled={!ready}>
            {missing ?? 'Read the bill'}
          </PrimaryButton>
        }
      >
        <div className="flex flex-wrap gap-2">
          {people.map((person) => (
            <button
              key={person}
              type="button"
              onClick={() => setPeople(people.filter((p) => p !== person))}
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
                addPerson()
              }
            }}
            placeholder={people.length ? 'Add another name' : 'Add a name'}
            maxLength={40}
            enterKeyHint="done"
            className="min-w-0 flex-1 rounded-2xl bg-white px-4 py-3"
          />
          <button
            type="button"
            onClick={addPerson}
            disabled={!name.trim()}
            className="rounded-2xl bg-white px-5 font-display font-semibold text-leaf disabled:text-muted/50"
          >
            Add
          </button>
        </div>

        <label className="mt-8 block">
          <span className="font-display text-lg font-semibold">Anything we should know?</span>
          <span className="block text-sm text-muted">Optional. We’ll use it to work out who had what.</span>
          <textarea
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="Ravi doesn’t drink. Meena left before dessert."
            maxLength={500}
            rows={2}
            className="mt-2 w-full resize-none rounded-2xl bg-white px-4 py-3"
          />
        </label>

        <label className="mt-6 flex cursor-pointer items-center gap-4 rounded-2xl border-2 border-dashed border-steel-dark bg-white/60 p-4">
          <span aria-hidden className="text-3xl">🧾</span>
          <span>
            <span className="block font-display text-lg font-semibold">
              {photos.length ? `${photos.length} photo${photos.length > 1 ? 's' : ''} added` : 'Add the bill'}
            </span>
            <span className="text-sm text-muted">
              {photos.length ? 'Tap to choose again' : 'Take a photo or pick one. Several for a trip.'}
            </span>
          </span>
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp,image/heic,image/heif"
            multiple
            className="sr-only"
            onChange={(event) => setPhotos(Array.from(event.target.files ?? []).slice(0, 5))}
          />
        </label>

        {error && <ErrorText>{error}</ErrorText>}
      </Screen>
    </form>
  )
}
