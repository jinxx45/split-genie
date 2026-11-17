// The Pay button: tap it to choose how to pay. A UPI app (Google Pay, PhonePe, Paytm or any
// other), a QR code to scan, or the UPI ID to copy. The app only opens the payment; it never
// learns whether it went through, which is why "I've paid" sits next to this button.

import { QRCodeSVG } from 'qrcode.react'
import { useState } from 'react'
import { formatRupees } from './money'
import { upiAppLinks, upiLink } from './upi'

// Defined once, outside the component: React runs a ref function again whenever it's a new
// function, so one written inline would scroll on every tap inside the panel.
const scrollToMiddle = (box: HTMLElement | null) => box?.scrollIntoView({ block: 'center', behavior: 'smooth' })

/** `className` styles the button itself. The choices open on a full-width row below it, so put
 * this inside a `flex flex-wrap` row; other buttons in the row stay beside the Pay button. */
export function PayButton(props: { upiId: string; name: string; paise: number; note?: string; label: string; className: string }) {
  const { upiId, name, paise, note } = props
  const [open, setOpen] = useState(false)
  const [showQr, setShowQr] = useState(false)
  const [copied, setCopied] = useState(false)

  async function copy() {
    try {
      await navigator.clipboard.writeText(upiId)
      setCopied(true)
    } catch {
      // Copying can be blocked (an old browser, or no permission): the ID is on screen to type.
    }
  }

  return (
    <>
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open} className={props.className}>
        {props.label}
      </button>
      {open && (
        <div className="tile order-last basis-full p-3 text-left text-base font-normal text-ink">
          <p className="text-sm text-muted">
            Pay {name} {formatRupees(paise)} with
          </p>
          <div className="mt-2 grid grid-cols-2 gap-2">
            {upiAppLinks(upiId, name, paise, note).map((link) => (
              <a key={link.app} href={link.href} className="rounded-xl bg-steel py-2.5 text-center font-display font-semibold">
                {link.app}
              </a>
            ))}
          </div>

          <div className="mt-3 flex items-center gap-2 border-t border-steel pt-3 text-sm">
            <span className="min-w-0 flex-1">
              <span className="block text-muted">Or pay this UPI ID yourself</span>
              <span className="block truncate font-semibold">{upiId}</span>
            </span>
            <button type="button" onClick={copy} className="rounded-lg bg-steel px-3 py-2 font-semibold">
              {copied ? 'Copied' : 'Copy'}
            </button>
            <button type="button" onClick={() => setShowQr(!showQr)} aria-expanded={showQr} className="rounded-lg bg-steel px-3 py-2 font-semibold">
              QR
            </button>
          </div>
          {showQr && (
            // Always black on white, whatever the theme, so every scanner can read it.
            // Opened low on the page it would sit behind the pinned button, so it scrolls to the middle.
            <div className="mt-3 flex justify-center" ref={scrollToMiddle}>
              <span className="rounded-xl bg-[#ffffff] p-3">
                <QRCodeSVG value={upiLink(upiId, name, paise, note)} size={176} title={`QR code to pay ${name}`} />
              </span>
            </div>
          )}
          <p className="mt-3 text-xs text-muted">
            If an app doesn’t open, it isn’t on this phone or it doesn’t accept payment links. Scan the QR code or copy the
            UPI ID instead.
          </p>
        </div>
      )}
    </>
  )
}
