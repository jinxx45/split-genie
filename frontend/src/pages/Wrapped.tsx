// A group's "Wrapped", at /groups/:id/wrapped: its highlights as one picture, to share on
// WhatsApp or save. The numbers come from the server; wrapped.ts draws them.

import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router'
import { ApiError, getWrapped } from '../api'
import type { Wrapped } from '../api'
import { formatRupees } from '../money'
import { ErrorText, PrimaryButton, Screen } from '../ui'
import { CARD, drawWrapped, loadCardFonts, loadMark } from '../wrapped'
import { Reading } from './Reading'

export function WrappedPage() {
  const { id = '' } = useParams()
  const canvas = useRef<HTMLCanvasElement>(null)
  const [wrapped, setWrapped] = useState<Wrapped | null>(null)
  const [drawn, setDrawn] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getWrapped(id)
      .then(setWrapped)
      .catch((problem) => setError(problem instanceof ApiError ? problem.message : 'Couldn’t reach Split Rupya. Check your connection.'))
  }, [id])

  // Draw once the numbers, the fonts and the logo are all here.
  useEffect(() => {
    if (!wrapped) return
    let current = true
    Promise.all([loadMark(), loadCardFonts()]).then(([mark]) => {
      if (!current || !canvas.current) return
      drawWrapped(canvas.current, wrapped, mark, window.location.host)
      setDrawn(true)
    })
    return () => {
      current = false // the page was left before the fonts arrived
    }
  }, [wrapped])

  const back = `/groups/${id}`
  if (!wrapped) {
    return error ? (
      <Screen title="Nothing to show yet">
        <p className="text-muted">{error}</p>
        <Link to={back} className="mt-4 inline-block font-semibold underline">
          Back to the group
        </Link>
      </Screen>
    ) : (
      <Reading message="Wrapping it up…" />
    )
  }

  const title = wrapped.kind === 'trip' ? 'Trip Wrapped' : 'Wrapped'
  const fileName = `${wrapped.name.replace(/[^A-Za-z0-9]+/g, '-').toLowerCase()}-wrapped.png`
  /** The card as a PNG. toBlob hands the picture over later, through its callback. */
  const picture = () =>
    new Promise<Blob | null>((resolve) => {
      if (canvas.current) canvas.current.toBlob(resolve, 'image/png')
      else resolve(null)
    })

  /** Share the picture through the phone's share sheet (WhatsApp, status, anywhere). Where the
   * browser can't share files, it's saved instead. */
  async function share() {
    setError(null)
    const blob = await picture()
    if (!blob) return setError('Couldn’t make the picture. Try again.')
    const file = new File([blob], fileName, { type: 'image/png' })
    const text = `${wrapped?.name} wrapped. See it on Split Rupya:\n${window.location.origin}${back}?who`
    if (navigator.canShare?.({ files: [file] })) {
      try {
        await navigator.share({ files: [file], text })
      } catch (problem) {
        // AbortError: they closed the share sheet without sending. Anything else means sharing
        // didn't work on this device, so they get the picture as a file.
        if (!(problem instanceof DOMException && problem.name === 'AbortError')) save(blob)
      }
    } else {
      save(blob)
    }
  }

  function save(blob: Blob) {
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = fileName
    document.body.append(link) // some browsers only download from a link that's on the page
    link.click()
    link.remove()
    // Freed a little later: letting go of it straight away can cancel the download.
    setTimeout(() => URL.revokeObjectURL(link.href), 10_000)
  }

  const summary =
    `${wrapped.name}: together you spent ${formatRupees(wrapped.total_paise)} across ${wrapped.expenses} expenses. ` +
    `Biggest spend: ${wrapped.biggest.title}. ${wrapped.banker.person} paid the most up front.`

  return (
    <Screen
      title={title}
      action={
        <PrimaryButton onClick={share} disabled={!drawn}>
          Share the picture
        </PrimaryButton>
      }
    >
      <canvas
        ref={canvas}
        role="img"
        aria-label={summary}
        className="w-full rounded-[1.25rem] border-2 border-line bg-coal"
        style={{ aspectRatio: `${CARD.width} / ${CARD.height}` }}
      />
      <div className="mt-4 flex items-center justify-between text-sm font-semibold">
        <Link to={back} className="underline">
          Back to {wrapped.name}
        </Link>
        <button type="button" disabled={!drawn} onClick={() => picture().then((blob) => blob && save(blob))} className="underline">
          Save image
        </button>
      </div>
      {error && <ErrorText>{error}</ErrorText>}
    </Screen>
  )
}
