// Scan a bill, at /scan: what it's for, who was there, an optional note, and photos of the bill.
// Signed in, you're added for you and recent friends are a tap away. Opened as
// /scan?group=<id>, it scans a bill into that group instead.

import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { ApiError, createSplit, getGroup } from '../api'
import type { Group } from '../api'
import { rememberedMember } from '../groups'
import { MemberToggles, PeoplePicker } from '../people'
import { ErrorText, PrimaryButton, Screen } from '../ui'
import { Reading } from './Reading'
import { useMe } from '../useMe'

export function NewSplit() {
  const navigate = useNavigate()
  const [splitName, setSplitName] = useState('') // what the split is for
  const [people, setPeople] = useState<string[]>([])
  const [note, setNote] = useState('')
  const [photos, setPhotos] = useState<File[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [me] = useMe()

  // Scanning into a group: its members are the people, and the bill is added to its tab when done.
  const [params] = useSearchParams()
  const groupId = params.get('group')
  const [group, setGroup] = useState<Group | null>(null)
  const member = groupId ? rememberedMember(groupId) : null
  useEffect(() => {
    if (!groupId) return
    getGroup(groupId)
      .then((loaded) => {
        setGroup(loaded)
        setPeople(loaded.members)
      })
      .catch((problem) => setError(problem instanceof ApiError ? problem.message : 'Couldn’t open the group.'))
  }, [groupId])

  // Once we know who's signed in, put them in the split, only while it's still empty, so a name
  // they removed on purpose doesn't come back. Done during render when the name changes (React's
  // pattern for adjusting state to new input), which avoids an extra render from an effect.
  const myName = me.user?.name
  const [seenName, setSeenName] = useState(myName)
  if (myName !== seenName) {
    setSeenName(myName)
    if (myName && people.length === 0 && !groupId) setPeople([myName])
  }

  async function start(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const inGroup = group && member ? { id: group.id, addedBy: member } : undefined
      const split = await createSplit(splitName.trim(), people, note, photos, inGroup)
      navigate(`/split/${split.id}`)
    } catch (problem) {
      setError(problem instanceof ApiError ? problem.message : 'Couldn’t reach Split Rupya. Check your connection.')
      setBusy(false)
    }
  }

  if (busy) return <Reading />
  if (groupId && !group) {
    return error ? (
      <Screen title="We couldn’t open this group">
        <p className="text-muted">{error}</p>
      </Screen>
    ) : (
      <Reading message="Opening your group…" />
    )
  }
  if (group && !member) {
    // They need to say who they are in the group first; the group page asks.
    return (
      <Screen title="Who are you?">
        <p className="text-muted">
          Open{' '}
          <Link to={`/groups/${group.id}`} className="font-semibold underline">
            {group.name}
          </Link>{' '}
          and pick your name first.
        </p>
      </Screen>
    )
  }

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
        title={group ? `Scan a bill into ${group.name}` : 'Scan a bill'}
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
        {group ? (
          <MemberToggles members={group.members} chosen={people} onChange={setPeople} />
        ) : (
          <PeoplePicker people={people} onChange={setPeople} suggestions={me.friends.map((friend) => friend.name)} />
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
      </Screen>
    </form>
  )
}
