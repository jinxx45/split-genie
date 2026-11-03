// Start a split: who was there, an optional note, and photos of the bill.
// Signed in, you're added for you, recent friends are a tap away, and past splits are below.

import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { ApiError, createSplit } from '../api'
import { Avatar, ErrorText, PrimaryButton, Screen } from '../ui'
import { Reading } from './Reading'
import { personColor } from '../colors'
import { useMe } from '../useMe'
import { Account } from './Account'

export function NewSplit() {
  const navigate = useNavigate()
  const [splitName, setSplitName] = useState('') // what the split is for
  const [people, setPeople] = useState<string[]>([])
  const [name, setName] = useState('') // the person's name being typed
  const [note, setNote] = useState('')
  const [photos, setPhotos] = useState<File[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [me, setMe] = useMe()

  // Once we know who's signed in, put them in the split, only while it's still empty, so a name
  // they removed on purpose doesn't come back. Done during render when the name changes (React's
  // pattern for adjusting state to new input), which avoids an extra render from an effect.
  const myName = me.user?.name
  const [seenName, setSeenName] = useState(myName)
  if (myName !== seenName) {
    setSeenName(myName)
    if (myName && people.length === 0) setPeople([myName])
  }

  const inSplit = (person: string) => people.some((p) => p.toLowerCase() === person.toLowerCase())
  const recentFriends = me.friends.filter((friend) => !inSplit(friend.name)).slice(0, 8)

  function addPerson(person = name) {
    const trimmed = person.trim()
    if (!trimmed) return
    if (inSplit(trimmed)) {
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
      const split = await createSplit(splitName.trim(), people, note, photos)
      navigate(`/split/${split.id}`)
    } catch (problem) {
      setError(problem instanceof ApiError ? problem.message : 'Couldn’t reach Split Rupya. Check your connection.')
      setBusy(false)
    }
  }

  if (busy) return <Reading />

  const missing = !splitName.trim()
    ? 'Name the split first'
    : people.length < 2
      ? 'Add at least two people'
      : photos.length === 0
        ? 'Add a photo of the bill'
        : null
  const ready = missing === null

  return (
    <form onSubmit={start}>
      <Screen
        title="Split a bill"
        action={
          <PrimaryButton type="submit" disabled={!ready}>
            {missing ?? 'Read the bill'}
          </PrimaryButton>
        }
      >
        <label className="block">
          <span className="font-display text-lg font-semibold">What’s it for?</span>
          <input
            value={splitName}
            onChange={(event) => setSplitName(event.target.value)}
            placeholder="Saturday lunch"
            maxLength={60}
            required
            enterKeyHint="next"
            className="mt-2 w-full rounded-2xl bg-white px-4 py-3"
          />
        </label>

        <p className="mt-6 mb-2 font-display text-lg font-semibold">Who was there?</p>
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
            onClick={() => addPerson()}
            disabled={!name.trim()}
            className="rounded-2xl bg-white px-5 font-display font-semibold text-brand disabled:text-muted/50"
          >
            Add
          </button>
        </div>

        {recentFriends.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2" aria-label="Recent friends">
            {recentFriends.map((friend) => (
              <button
                key={friend.name}
                type="button"
                onClick={() => addPerson(friend.name)}
                className="rounded-full border-2 border-dashed border-steel-dark px-3 py-1 text-sm font-semibold text-muted"
              >
                + {friend.name}
              </button>
            ))}
          </div>
        )}

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

        <Account me={me} setMe={setMe} />

        <p className="mt-10 text-center text-sm text-muted">
          <Link to="/privacy" className="underline">
            Privacy
          </Link>
          {' · '}
          <Link to="/terms" className="underline">
            Terms
          </Link>
        </p>
      </Screen>
    </form>
  )
}
