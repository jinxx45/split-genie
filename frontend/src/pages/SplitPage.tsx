// One split, at /split/:id. Shows whichever screen the split is waiting on.
// The server is the source of truth: after every answer we show what it sends back.
// A friend's link (?for=Arun) shows their own screens: what they had, then what they owe.
// The group link shared on WhatsApp (?who) first asks "Who are you?", then becomes their link.

import { useEffect, useState } from 'react'
import { useParams, useSearchParams } from 'react-router'
import { ApiError, answerSplit, claimItems, getSplit, markPayment, retrySplit } from '../api'
import type { PaymentMark, Split } from '../api'
import { Approve } from '../steps/Approve'
import { ClaimItems } from '../steps/ClaimItems'
import { ConfirmItems } from '../steps/ConfirmItems'
import { Done } from '../steps/Done'
import { ReviewItems } from '../steps/ReviewItems'
import { WhoPaid } from '../steps/WhoPaid'
import { personColor } from '../colors'
import { Avatar, ErrorText, PrimaryButton, Screen } from '../ui'
import { Reading } from './Reading'

export type StepProps<Q> = {
  question: Q
  people: string[]
  answer: (body: unknown) => Promise<void>
  busy: boolean
  error: string | null
}

export function SplitPage() {
  const { id = '' } = useParams()
  const [params, setParams] = useSearchParams()
  const [split, setSplit] = useState<Split | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // Goes up with every reply from the server. Used as the screen's key, so each new question
  // starts on a fresh screen instead of keeping the last one's half-typed state.
  const [version, setVersion] = useState(0)

  useEffect(() => {
    getSplit(id)
      .then(setSplit)
      .catch((problem) => setError(message(problem)))
  }, [id])

  // Coming back to the tab (say, from WhatsApp or a UPI app): reload, so payments marked by
  // friends in the meantime show up.
  useEffect(() => {
    function reload() {
      if (document.visibilityState === 'visible') getSplit(id).then(setSplit).catch(() => {})
    }
    document.addEventListener('visibilitychange', reload)
    return () => document.removeEventListener('visibilitychange', reload)
  }, [id])

  async function send(call: () => Promise<Split>, scrollToTop = true) {
    setBusy(true)
    setError(null)
    try {
      setSplit(await call())
      setVersion((current) => current + 1)
      if (scrollToTop) window.scrollTo({ top: 0 })
    } catch (problem) {
      setError(message(problem))
    } finally {
      setBusy(false)
    }
  }

  const answer = (body: unknown) => send(() => answerSplit(id, body))

  if (!split) {
    return error ? (
      <Screen title="We couldn’t open this split">
        <p className="text-muted">{error}</p>
      </Screen>
    ) : (
      <Reading message="Opening your split…" />
    )
  }

  const friend = params.get('for')
  const isFriend = friend !== null && split.people.includes(friend)
  const asking = split.question?.step === 'review_assignments' ? split.question : null
  const done = split.status === 'done' ? split.result : null

  /** Turn the group link into this person's own link, keeping the rest (UPI IDs) as it is. */
  function choose(person: string) {
    const next = new URLSearchParams(params)
    next.delete('who')
    next.set('for', person)
    setParams(next)
  }

  // Asked from the group link, or a friend opened a split someone else is still working on.
  if ((params.has('who') && !isFriend && (done || asking)) || (asking && !split.can_answer && !isFriend)) {
    const why = done ? 'see what you owe and pay' : 'tap what you had'
    return <WhoAreYou people={split.people} why={why} onChoose={choose} />
  }

  if (done) {
    const mark = (body: PaymentMark) => send(() => markPayment(id, body), false)
    return <Done result={done} people={split.people} onMark={mark} busy={busy} error={error} />
  }

  if (asking && isFriend) {
    const claim = (items: Record<number, number>) => send(() => claimItems(id, friend, items))
    return <ClaimItems key={version} question={asking} friend={friend} onClaim={claim} busy={busy} error={error} />
  }

  if (isFriend || !split.can_answer) {
    return (
      <Screen title="This split isn’t finished yet">
        <p className="text-muted">The person who started it is still checking the bill. Open this link again once they’re done.</p>
      </Screen>
    )
  }

  if (split.status === 'failed' || !split.question) {
    return (
      <Screen
        title="That step didn’t finish"
        action={
          <PrimaryButton busy={busy} onClick={() => send(() => retrySplit(id))}>
            Try again
          </PrimaryButton>
        }
      >
        <p className="text-muted">Reading the bill can fail if the connection drops. Your answers so far are saved.</p>
        {error && <ErrorText>{error}</ErrorText>}
      </Screen>
    )
  }

  const props = { people: split.people, answer, busy, error }
  const question = split.question
  switch (question.step) {
    case 'confirm_items':
      return <ConfirmItems key={version} {...props} question={question} />
    case 'review_assignments':
      return <ReviewItems key={version} {...props} question={question} />
    case 'payer':
      return <WhoPaid key={version} {...props} question={question} />
    case 'approve':
      return <Approve key={version} {...props} question={question} />
  }
}

function WhoAreYou(props: { people: string[]; why: string; onChoose: (person: string) => void }) {
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

function message(problem: unknown): string {
  return problem instanceof ApiError ? problem.message : 'Couldn’t reach Split Rupya. Check your connection.'
}
