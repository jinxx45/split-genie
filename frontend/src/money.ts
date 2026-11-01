// Money is integer paise everywhere. These only convert for display and typing.

const rupees = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  minimumFractionDigits: 2,
})

/** 123250 -> "₹1,232.50" (Indian digit grouping). */
export function formatRupees(paise: number): string {
  return rupees.format(paise / 100)
}

/** "1,232.5" -> 123250. Returns null if it isn't an amount. Uses string maths, not floats. */
export function parseRupees(text: string): number | null {
  const match = text.replace(/[₹,\s]/g, '').match(/^(\d+)(?:\.(\d{0,2}))?$/)
  if (!match) return null
  const [, whole, fraction = ''] = match
  return Number(whole) * 100 + Number(fraction.padEnd(2, '0'))
}

/** Rupees as the user would type them: 123250 -> "1232.50". */
export function toRupeesText(paise: number): string {
  return `${Math.floor(paise / 100)}.${String(paise % 100).padStart(2, '0')}`
}
