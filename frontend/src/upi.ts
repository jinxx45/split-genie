// UPI: checking IDs and making pay links.

import { toRupeesText } from './money'

/** A UPI ID looks like name@bank, e.g. priya@okaxis. Same rule as the backend. */
export const UPI_ID = /^[A-Za-z0-9._-]{2,256}@[A-Za-z]{2,64}$/

/** Opens any UPI app (GPay, PhonePe, Paytm…) with the payee and amount filled in. */
export function upiLink(upiId: string, name: string, paise: number, note = 'Split Rupya'): string {
  // encodeURIComponent, not URLSearchParams: some UPI apps show a "+" for a space literally.
  const params = { pa: upiId, pn: name, am: toRupeesText(paise), cu: 'INR', tn: note }
  const query = Object.entries(params)
    .map(([key, value]) => `${key}=${encodeURIComponent(value)}`)
    .join('&')
  return `upi://pay?${query}`
}

/** The same payment as links that open one named app. UPI works across apps, so each takes the
 * same details; only the start of the link differs. On Android the plain link already offers a
 * list of UPI apps, but an iPhone has no such list, so these let the person choose. */
export function upiAppLinks(upiId: string, name: string, paise: number, note?: string): { app: string; href: string }[] {
  const plain = upiLink(upiId, name, paise, note)
  const opening = (start: string) => plain.replace('upi://pay', start)
  return [
    { app: 'Google Pay', href: opening('tez://upi/pay') },
    { app: 'PhonePe', href: opening('phonepe://pay') },
    { app: 'Paytm', href: opening('paytmmp://pay') },
    { app: 'Other UPI app', href: plain },
  ]
}
