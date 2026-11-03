// The home screen: two ways to split, then (signed in) your splits and your groups, or (signed
// out) a sign-in box. Scanning a bill is at /scan, an instant split at /instant.

import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { History, MyGroups, SignedInBar, SignInBox } from './Account'
import { Screen } from '../ui'
import { useMe } from '../useMe'

export function Home() {
  const [me, setMe] = useMe()
  const user = me.user

  return (
    <Screen title={user ? `Hi, ${user.name.split(' ')[0]}` : 'Split a bill'}>
      <SignedInBar me={me} setMe={setMe} />

      <div className={`space-y-3 ${user ? 'mt-4' : ''}`}>
        <StartLink
          to="/scan"
          title="Take a photo of the bill"
          about="We read every item and work out who had what."
          icon={<CameraIcon />}
          dark
        />
        <StartLink to="/instant" title="Instant split" about="Just the amount. Split in seconds." icon={<BoltIcon />} />
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

/** One of the two big ways to start. `dark` is the main one: black, like the app's main buttons. */
function StartLink(props: { to: string; title: string; about: string; icon: ReactNode; dark?: boolean }) {
  return (
    <Link
      to={props.to}
      className={`flex items-center gap-4 rounded-2xl p-4 transition active:scale-[0.98] ${
        props.dark ? 'bg-brand text-paper' : 'border-2 border-brand bg-white'
      }`}
    >
      <span
        aria-hidden
        className={`flex size-12 shrink-0 items-center justify-center rounded-full ${
          props.dark ? 'bg-saffron text-brand' : 'bg-saffron-soft'
        }`}
      >
        {props.icon}
      </span>
      <span>
        <span className="block font-display text-xl font-semibold">{props.title}</span>
        <span className={`text-sm ${props.dark ? 'text-paper/75' : 'text-muted'}`}>{props.about}</span>
      </span>
    </Link>
  )
}

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

function BoltIcon() {
  return (
    <svg {...iconProps}>
      <path d="M13 2 4 14h7l-1 8 9-12h-7l1-8Z" />
    </svg>
  )
}
