// Small helpers shared by the group screens.

import type { GroupKind } from './api'
import { formatRupees } from './money'

export const KIND_NAMES: Record<GroupKind, string> = { friends: 'Friends', trip: 'Trip', flat: 'Flatmates' }

const memberKey = (groupId: string) => `split-rupya:group:${groupId}:me`

/** Which member you are in a group, remembered on this phone. Storage can be blocked (private
 * mode), so failures just mean "ask again". */
export function rememberedMember(groupId: string): string | null {
  try {
    return localStorage.getItem(memberKey(groupId))
  } catch {
    return null
  }
}

export function rememberMember(groupId: string, member: string): void {
  try {
    localStorage.setItem(memberKey(groupId), member)
  } catch {
    // Not saved: they'll be asked again next time, which is fine.
  }
}

/** A balance in words: positive means you get money back. */
export function balanceWords(paise: number, you = true): string {
  const subject = you ? 'You' : ''
  if (paise > 0) return `${subject} get back ${formatRupees(paise)}`.trim()
  if (paise < 0) return `${subject} owe ${formatRupees(-paise)}`.trim()
  return you ? 'You’re all square' : 'All square'
}

/** "2026-12-12", "2026-12-15" -> "12 to 15 Dec"; across months -> "30 Dec to 2 Jan". */
export function dateRange(start: string | null, end: string | null): string {
  if (!start || !end) return ''
  const format = (iso: string, withMonth: boolean) =>
    new Date(`${iso}T00:00:00`).toLocaleDateString('en-IN', withMonth ? { day: 'numeric', month: 'short' } : { day: 'numeric' })
  const sameMonth = start.slice(0, 7) === end.slice(0, 7)
  return `${format(start, !sameMonth)} to ${format(end, true)}`
}
