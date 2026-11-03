// Small building blocks shared by every screen.

import type { ReactNode } from 'react'
import { Link } from 'react-router'
import type { GroupKind, Weight } from './api'
import { personColor } from './colors'

/** The page frame: small header, an optional step indicator, content, and one pinned action. */
export function Screen(props: {
  title: string
  step?: number // 1-4 while answering questions
  children: ReactNode
  action?: ReactNode
}) {
  return (
    <div className="mx-auto flex min-h-dvh max-w-md flex-col">
      <header className="flex items-center justify-between px-4 pt-4">
        <Link to="/" aria-label="Split Rupya, start a new split">
          <Logo />
        </Link>
        {props.step && <Steps current={props.step} />}
      </header>
      <main className="flex-1 px-4 pt-6 pb-48">
        <h1 className="font-display text-[2rem] leading-tight font-semibold">{props.title}</h1>
        <div className="mt-5">{props.children}</div>
      </main>
      {props.action && (
        <div className="fixed inset-x-0 bottom-0 bg-gradient-to-t from-steel from-60% to-transparent pt-6 pb-[max(1rem,env(safe-area-inset-bottom))]">
          <div className="mx-auto max-w-md px-4">{props.action}</div>
        </div>
      )}
    </div>
  )
}

/** The Split Rupya logo: the split rupee in its black tile, and the wordmark (brand/BRAND.md). */
export function Logo() {
  return (
    <span className="flex items-center gap-2 text-brand">
      <img src="/favicon.svg" alt="" className="size-7" />
      <span className="font-brand text-lg tracking-[-0.02em]">
        <span className="font-bold">Split</span> <span className="font-light">Rupya</span>
      </span>
    </span>
  )
}

const STEP_NAMES = ['Check items', 'Who had what', 'Who paid', 'Approve']

function Steps({ current }: { current: number }) {
  return (
    <div className="flex items-center gap-1.5" aria-label={`Step ${current} of 4: ${STEP_NAMES[current - 1]}`}>
      {STEP_NAMES.map((name, index) => (
        <span
          key={name}
          className={`h-1.5 rounded-full transition-all ${
            index + 1 === current ? 'w-6 bg-brand' : index + 1 < current ? 'w-3 bg-brand/50' : 'w-3 bg-steel-dark'
          }`}
        />
      ))}
    </div>
  )
}

export function PrimaryButton(props: {
  children: ReactNode
  onClick?: () => void
  disabled?: boolean
  busy?: boolean
  type?: 'button' | 'submit'
}) {
  return (
    <button
      type={props.type ?? 'button'}
      onClick={props.onClick}
      disabled={props.disabled || props.busy}
      className="w-full rounded-2xl bg-brand px-5 py-4 font-display text-lg font-semibold text-white transition active:scale-[0.98] disabled:bg-muted/40"
    >
      {props.busy ? 'Working on it…' : props.children}
    </button>
  )
}

export function SecondaryButton(props: { children: ReactNode; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={props.onClick}
      className="w-full rounded-2xl px-5 py-3 font-display font-semibold text-brand"
    >
      {props.children}
    </button>
  )
}

/** White paper with a torn edge: used wherever we show the bill itself. */
export function Paper({ children }: { children: ReactNode }) {
  return <div className="receipt rounded-t-xl px-4 pt-4">{children}</div>
}

export function ErrorText({ children }: { children: ReactNode }) {
  return (
    <p role="alert" className="mt-3 rounded-xl bg-chilli/10 px-3 py-2 text-sm text-chilli">
      {children}
    </p>
  )
}

export function Avatar({ name, color }: { name: string; color: string }) {
  return (
    <span
      aria-hidden
      className="inline-flex size-8 shrink-0 items-center justify-center rounded-full font-display font-semibold text-white"
      style={{ background: color }}
    >
      {name.slice(0, 1).toUpperCase()}
    </span>
  )
}

const NEXT_WEIGHT: Record<string, Weight | undefined> = { none: 2, '2': 1, '1': undefined }

/** A name that cycles full share -> half share -> not included. The fill shows the share. */
export function ShareChip(props: {
  name: string
  color: string
  weight: number | undefined // FULL (2), HALF (1) or not included
  onChange: (weight: Weight | undefined) => void
}) {
  const { name, color, weight } = props
  const label = weight === 2 ? 'full share' : weight === 1 ? 'half share' : 'not included'
  const background =
    // Half share: the left half is tinted (40% alpha), so dark text stays readable across it.
    weight === 2 ? color : weight === 1 ? `linear-gradient(90deg, ${color}66 50%, #fff 50%)` : '#fff'
  return (
    <button
      type="button"
      aria-label={`${name}: ${label}`}
      onClick={() => props.onChange(NEXT_WEIGHT[weight ? String(weight) : 'none'])}
      className="rounded-full border-2 px-3 py-1.5 text-sm font-semibold transition active:scale-95"
      style={{
        borderColor: weight ? color : 'var(--color-steel-dark)',
        background,
        color: weight === 2 ? '#fff' : weight === 1 ? 'var(--color-ink)' : 'var(--color-muted)',
      }}
    >
      {name}
      {weight === 1 && <span className="ml-1">½</span>}
    </button>
  )
}

/** "Pick your name": how someone opening a shared link says who they are. */
export function WhoAreYou(props: { people: string[]; why: string; onChoose: (person: string) => void }) {
  return (
    <Screen title="Who are you?">
      <p className="mb-5 text-muted">Pick your name to {props.why}.</p>
      <div className="flex flex-wrap gap-2">
        {props.people.map((person) => (
          <button
            key={person}
            type="button"
            onClick={() => props.onChoose(person)}
            className="flex items-center gap-2 rounded-full bg-white py-1.5 pr-4 pl-1.5 font-semibold"
          >
            <Avatar name={person} color={personColor(props.people, person)} />
            {person}
          </button>
        ))}
      </div>
    </Screen>
  )
}

/** A simple outline icon for each kind of group. */
export function KindIcon({ kind, className = 'size-5' }: { kind: GroupKind; className?: string }) {
  const paths: Record<GroupKind, string> = {
    // two people
    friends: 'M9 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm7 0a2.5 2.5 0 1 0 0-5M3 19c0-3 2.7-5 6-5s6 2 6 5m2-5c2.4.3 4 2 4 5',
    // a plane
    trip: 'M3 13l7-2 4-7 2 1-2 6 5-1 2 2-6 2-3 6-2-1 1-5-6 1z',
    // a house
    flat: 'M4 11l8-6 8 6M6 10v9h4v-5h4v5h4v-9',
  }
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden className={className}>
      <path d={paths[kind]} />
    </svg>
  )
}
