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
