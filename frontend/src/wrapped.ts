// Draws the "Wrapped" card: one tall picture of a group's highlights, made to be shared.
// It's drawn on a canvas (not built from page elements) so the picture people share is exactly
// the picture on screen, in the app's own fonts. The card is always black and saffron, whatever
// theme is on: it leaves the app, so it carries the brand.

import type { Wrapped } from './api'
import { dateRange } from './groups'
import { formatRupees } from './money'

export const CARD = { width: 1080, height: 1920 } // a phone story's shape, 9:16

const INK = '#0a0a0a'
const PAPER = '#f6f4ee'
const SAFFRON = '#f2a93b'
const MUTED = '#a1a5a9'
const TILE = '#17171a'
const LINE = '#2e2e33'
const GOOD = '#7fd4a0'

const DISPLAY = '"Bricolage Grotesque Variable", system-ui, sans-serif'
const BODY = '"DM Sans Variable", system-ui, sans-serif'
const BRAND = 'Sora, system-ui, sans-serif'

const EDGE = 80 // the margin on every side
const INNER = CARD.width - 2 * EDGE

/** The fonts the card uses. A font file is only fetched once something needs it, and a canvas
 * doesn't wait for that, so they're asked for before drawing ("₹" pulls in the file with it). */
export async function loadCardFonts(): Promise<void> {
  const fonts = [`800 100px ${DISPLAY}`, `500 40px ${BODY}`, `700 40px ${BODY}`, `700 40px ${BRAND}`, `300 40px ${BRAND}`]
  await Promise.all(fonts.map((font) => document.fonts.load(font, '₹Aa0')))
}

/** The logo mark, ready to draw. Null if it can't be loaded: the card then goes without it. */
export function loadMark(): Promise<HTMLImageElement | null> {
  return new Promise((resolve) => {
    const image = new Image()
    image.onload = () => resolve(image)
    image.onerror = () => resolve(null)
    image.src = '/mark.svg'
  })
}

/** "₹2,366.00" -> "₹2,366": the card has room for big numbers, not paise that are zero. */
const short = (paise: number) => formatRupees(paise).replace(/\.00$/, '')

/** Set the font as big as `size` allows while `text` still fits in `width`, down to `smallest`.
 * Returns the text, cut short with "…" if it doesn't fit even then. */
function fit(ctx: CanvasRenderingContext2D, text: string, width: number, size: number, smallest: number, font: string): string {
  for (let px = size; px >= smallest; px -= 4) {
    ctx.font = font.replace('SIZE', `${px}px`)
    if (ctx.measureText(text).width <= width) return text
  }
  let cut = text
  while (cut.length > 1 && ctx.measureText(`${cut}…`).width > width) cut = cut.slice(0, -1)
  return `${cut.trimEnd()}…`
}

function box(ctx: CanvasRenderingContext2D, x: number, y: number, width: number, height: number, fill: string, stroke?: string) {
  ctx.beginPath()
  ctx.roundRect(x, y, width, height, 40)
  ctx.fillStyle = fill
  ctx.fill()
  if (stroke) {
    ctx.lineWidth = 3
    ctx.strokeStyle = stroke
    ctx.stroke()
  }
}

/** One small tile: a label, a big value and a note under it. */
function tile(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  parts: { label: string; value: string; note: string; accent?: boolean },
) {
  const width = (INNER - 24) / 2
  const inside = width - 72
  box(ctx, x, y, width, 290, TILE, LINE)
  ctx.fillStyle = MUTED
  ctx.fillText(fit(ctx, parts.label, inside, 34, 26, `500 SIZE ${BODY}`), x + 36, y + 70)
  ctx.fillStyle = parts.accent ? SAFFRON : PAPER
  ctx.fillText(fit(ctx, parts.value, inside, 84, 44, `800 SIZE ${DISPLAY}`), x + 36, y + 172)
  ctx.fillStyle = MUTED
  ctx.fillText(fit(ctx, parts.note, inside, 34, 26, `500 SIZE ${BODY}`), x + 36, y + 238)
}

const dayMonth = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })

export function drawWrapped(canvas: HTMLCanvasElement, wrapped: Wrapped, mark: HTMLImageElement | null, site: string): void {
  canvas.width = CARD.width
  canvas.height = CARD.height
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  ctx.textBaseline = 'alphabetic'
  ctx.fillStyle = INK
  ctx.fillRect(0, 0, CARD.width, CARD.height)

  // The logo and wordmark.
  let x = EDGE
  if (mark) {
    ctx.drawImage(mark, EDGE - 10, 70, 84, 84)
    x += 86
  }
  ctx.fillStyle = PAPER
  ctx.font = `700 44px ${BRAND}`
  ctx.fillText('Split', x, 128)
  x += ctx.measureText('Split ').width
  ctx.font = `300 44px ${BRAND}`
  ctx.fillText('Rupya', x, 128)

  // What it is, its name and when.
  ctx.fillStyle = SAFFRON
  ctx.font = `700 40px ${BODY}`
  ctx.fillText(wrapped.kind === 'trip' ? 'Trip wrapped' : 'Wrapped', EDGE, 300)
  ctx.fillStyle = PAPER
  ctx.fillText(fit(ctx, wrapped.name, INNER, 132, 64, `800 SIZE ${DISPLAY}`), EDGE, 430)
  const when = wrapped.start_date === wrapped.end_date ? dayMonth(wrapped.start_date) : dateRange(wrapped.start_date, wrapped.end_date)
  ctx.fillStyle = MUTED
  ctx.font = `500 40px ${BODY}`
  ctx.fillText(`${when}, ${wrapped.people} people`, EDGE, 500)

  // The headline: the total.
  box(ctx, EDGE, 570, INNER, 370, SAFFRON)
  ctx.fillStyle = INK
  ctx.font = `700 40px ${BODY}`
  ctx.fillText('Together you spent', EDGE + 48, 660)
  ctx.fillText(fit(ctx, short(wrapped.total_paise), INNER - 96, 176, 80, `800 SIZE ${DISPLAY}`), EDGE + 48, 820)
  ctx.font = `500 36px ${BODY}`
  ctx.fillText(`across ${wrapped.expenses} ${wrapped.expenses === 1 ? 'expense' : 'expenses'}`, EDGE + 48, 890)

  // Four facts.
  const right = EDGE + (INNER - 24) / 2 + 24
  tile(ctx, EDGE, 970, { label: 'Each, about', value: short(wrapped.per_person_paise), note: 'per person' })
  tile(ctx, right, 970, {
    label: 'Per day',
    value: short(wrapped.per_day_paise),
    note: `over ${wrapped.days} ${wrapped.days === 1 ? 'day' : 'days'}`,
  })
  tile(ctx, EDGE, 1284, { label: 'Biggest spend', value: short(wrapped.biggest.total_paise), note: wrapped.biggest.title })
  tile(ctx, right, 1284, {
    label: 'Paid the most up front',
    value: wrapped.banker.person,
    note: short(wrapped.banker.paid_paise),
    accent: true,
  })

  // Up to two more lines, only when they say something (ties are left out by the server).
  const extras = [
    wrapped.top_spender && `Spent the most: ${wrapped.top_spender.person}, ${short(wrapped.top_spender.spent_paise)}`,
    wrapped.busiest_day && `Busiest day: ${dayMonth(wrapped.busiest_day.date)}, ${short(wrapped.busiest_day.total_paise)}`,
  ].filter((line): line is string => Boolean(line))
  ctx.fillStyle = PAPER
  extras.forEach((line, index) => {
    ctx.fillText(fit(ctx, line, INNER, 40, 28, `500 SIZE ${BODY}`), EDGE, 1660 + index * 62)
  })

  // The footer: where things stand, and where to find the app.
  const settled = wrapped.payments_left === 0
  ctx.fillStyle = settled ? GOOD : SAFFRON
  ctx.font = `700 38px ${BODY}`
  ctx.fillText(settled ? 'All settled' : `${wrapped.payments_left} ${wrapped.payments_left === 1 ? 'payment' : 'payments'} to go`, EDGE, 1840)
  ctx.fillStyle = MUTED
  ctx.font = `500 34px ${BODY}`
  ctx.textAlign = 'right'
  ctx.fillText(site, CARD.width - EDGE, 1840)
  ctx.textAlign = 'left'
}
