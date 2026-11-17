// The home screen: three start tiles (photo of the bill, instant split, new group), then, signed
// in, your splits and your groups, or, signed out, a sign-in box. The photo tile opens the
// phone's camera or gallery, then the scan page (/scan) with the photos attached.

import { Link, useNavigate } from 'react-router'
import { MAX_PHOTOS } from '../api'
import { History, MyGroups, SignedInBar, SignInBox } from './Account'
import { Screen } from '../ui'
import { useMe } from '../useMe'

export function Home() {
  const navigate = useNavigate()
  const [me, setMe] = useMe()
  const user = me.user

  // Photos travel to the scan page in the navigation's state: File objects can be kept there, so
  // nothing is uploaded until the split is started.
  function scanPhotos(files: FileList | null) {
    const photos = Array.from(files ?? []).slice(0, MAX_PHOTOS)
    if (photos.length) navigate('/scan', { state: { photos } })
  }

  return (
    <Screen title={user ? `Hi, ${user.name.split(' ')[0]}` : 'Split a bill'}>
      <SignedInBar me={me} setMe={setMe} />

      <div className={`mr-1 grid grid-cols-2 gap-3 ${user ? 'mt-4' : ''}`}>
        {/* A label around a hidden file input: tapping it opens the phone's own "Camera or Gallery"
            chooser, with no extra screen first. */}
        <label className={`${TILE} col-span-2 cursor-pointer items-center gap-4 bg-saffron text-coal pop-shadow`}>
          <span aria-hidden className="flex size-13 shrink-0 items-center justify-center rounded-2xl bg-coal text-saffron">
            <CameraIcon />
          </span>
          <span>
            <span className="block font-display text-[1.35rem] leading-tight font-extrabold">Snap the bill</span>
            <span className="text-sm">Take a photo. We work out who had what.</span>
          </span>
          <input
            type="file"
            accept="image/*"
            multiple
            className="sr-only"
            onChange={(event) => scanPhotos(event.target.files)}
          />
        </label>
        <Link to="/instant" className={`${TILE} min-h-26 flex-col justify-between bg-ink text-paper`}>
          <span aria-hidden className="text-saffron">
            <BoltIcon />
          </span>
          <span className="font-display text-lg font-bold">Instant split</span>
        </Link>
        <Link to="/groups/new" className={`${TILE} min-h-26 flex-col justify-between bg-white`}>
          <GroupIcon />
          <span className="font-display text-lg font-bold">New group</span>
        </Link>
      </div>

      {user ? (
        <div className="mt-10">
          <History />
          <MyGroups />
        </div>
      ) : (
        <SignInBox
          title="Sign in to keep your splits"
          why="Optional. See past splits, start groups for trips and flatmates, and add friends with a tap."
          setMe={setMe}
        />
      )}

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
  )
}

/** The start tiles share this shape: outlined, and they press in when tapped. */
const TILE = 'flex rounded-[1.25rem] border-2 border-line p-4 transition active:scale-[0.98]'

const iconProps = {
  viewBox: '0 0 24 24',
  className: 'size-6',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
} as const

function CameraIcon() {
  return (
    <svg {...iconProps}>
      <path d="M4 8h3l2-3h6l2 3h3a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1Z" />
      <circle cx="12" cy="13.5" r="3.5" />
    </svg>
  )
}

function GroupIcon() {
  return (
    <svg {...iconProps} aria-hidden>
      <circle cx="9" cy="8" r="3.5" />
      <path d="M2.5 20a6.5 6.5 0 0 1 13 0M19 8v6M16 11h6" />
    </svg>
  )
}

function BoltIcon() {
  return (
    <svg {...iconProps}>
      <path d="M13 2 4 14h7l-1 8 9-12h-7l1-8Z" />
    </svg>
  )
}
