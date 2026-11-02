// One split, at /split/:id. Shows whichever screen the split is waiting on.
// The server is the source of truth: after every answer we show what it sends back.

import { useEffect, useState } from 'react'
import { useParams } from 'react-router'
import { ApiError, answerSplit, getSplit, markPayment, retrySplit } from '../api'
import type { PaymentMark, Split } from '../api'
import { Approve } from '../steps/Approve'
import { ConfirmItems } from '../steps/ConfirmItems'
import { Done } from '../steps/Done'
import { ReviewItems } from '../steps/ReviewItems'
import { WhoPaid } from '../steps/WhoPaid'
import { ErrorText, PrimaryButton, Screen } from '../ui'
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

  if (split.status === 'done' && split.result) {
    const mark = (body: PaymentMark) => send(() => markPayment(id, body), false)
    return <Done result={split.result} people={split.people} onMark={mark} busy={busy} error={error} />
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

function message(problem: unknown): string {
  return problem instanceof ApiError ? problem.message : 'Couldn’t reach Split Genie. Check your connection.'
}
