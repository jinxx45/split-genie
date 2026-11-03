// The privacy policy (/privacy) and terms of use (/terms), in plain words.

import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { getSite } from '../api'
import { Screen } from '../ui'

const UPDATED = '3 November 2026'

export function Privacy() {
  const contact = useContactEmail()
  return (
    <Screen title="Privacy">
      <Prose>
        <p className="text-muted">Last updated {UPDATED}.</p>
        <Section title="What Split Rupya keeps">
          <ul>
            <li>What you type: the split’s name, people’s names, notes, and UPI IDs.</li>
            <li>Photos of bills, and the items and amounts read from them.</li>
            <li>Who had what, who paid, and which payments were marked as paid.</li>
            <li>If you sign in with Google: your name, email address, and saved friends.</li>
          </ul>
        </Section>
        <Section title="How it’s used">
          <p>
            Only to work out the split and share it with the people in it. Bill photos and notes are sent to Google’s
            Gemini AI to read the bill and apply your notes, under Google’s Gemini API terms. The amounts are worked out
            by Split Rupya itself, not by the AI.
          </p>
        </Section>
        <Section title="Who can see it">
          <p>
            Anyone with a split’s or group’s link can see it, including names, items and amounts. Share links only with
            the people they’re for.
          </p>
        </Section>
        <Section title="Where it’s stored">
          <p>
            On Render (the app) and Neon (the database), in Singapore. There are no ads, no selling of data and no
            tracking. The one cookie keeps you signed in.
          </p>
        </Section>
        <Section title="Payments">
          <p>
            Split Rupya never holds or moves money. Pay buttons open your own UPI app, and the money goes straight to the
            person you pay.
          </p>
        </Section>
        <Section title="Deleting your data">
          <p>
            Data is kept until it’s deleted.{' '}
            {contact ? (
              <>
                To have your data deleted, or for any question, email <a href={`mailto:${contact}`}>{contact}</a>.
              </>
            ) : (
              'To have your data deleted, contact the person who runs this Split Rupya site.'
            )}
          </p>
        </Section>
      </Prose>
    </Screen>
  )
}

export function Terms() {
  return (
    <Screen title="Terms of use">
      <Prose>
        <p className="text-muted">Last updated {UPDATED}.</p>
        <Section title="Using Split Rupya">
          <p>
            Split Rupya helps a group work out who owes whom. It reads bills with AI, which can make mistakes, so check the
            items and amounts before anyone pays.
          </p>
        </Section>
        <Section title="Money">
          <p>
            Split Rupya doesn’t handle payments. Payments happen in your UPI app between the people involved, and any
            disagreement about money is between them.
          </p>
        </Section>
        <Section title="Fair use">
          <p>
            Use it for real bills. Don’t upload anything you don’t have the right to share, and don’t try to overload or
            break the service.
          </p>
        </Section>
        <Section title="No guarantees">
          <p>
            Split Rupya is provided as it is, without guarantees that it will always be available or correct. These terms
            may change; the date above shows the latest version.
          </p>
        </Section>
      </Prose>
    </Screen>
  )
}

function useContactEmail(): string {
  const [contact, setContact] = useState('')
  useEffect(() => {
    getSite()
      .then((site) => setContact(site.contact_email))
      .catch(() => setContact(''))
  }, [])
  return contact
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mt-6">
      <h2 className="mb-1 font-display text-xl font-semibold">{title}</h2>
      {children}
    </section>
  )
}

function Prose({ children }: { children: ReactNode }) {
  return (
    <div className="max-w-prose leading-relaxed [&_a]:font-semibold [&_a]:underline [&_li]:ml-5 [&_li]:list-disc">
      {children}
    </div>
  )
}
