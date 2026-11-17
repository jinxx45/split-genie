// Small helpers shared by the group screens.

import type { ActivityEntry, Debt, Group, GroupKind } from './api'
import { formatRupees } from './money'

/** What every part of a group's page gets: the group, which member you are, and `act` to run a
 * change and show the group the server sends back. */
export type GroupCtx = { group: Group; you: string; busy: boolean; act: (call: () => Promise<Group>) => void }

export const capitalise = (text: string) => text.charAt(0).toUpperCase() + text.slice(1)

/** "You" for yourself, otherwise the name. */
export const nameOrYou = (person: string, you: string) => (person === you ? 'you' : person)

/** The link that opens the group; whoever opens it picks their name first. */
export const groupLink = (group: Group) => `${window.location.origin}/groups/${group.id}?who`

/** Every pair that still owes, for a WhatsApp message: "Ravi pays Priya ₹636.00". */
export function whoPaysWhom(debts: Debt[]): string[] {
  return debts.map((debt) => `${debt.sender} pays ${debt.receiver} ${formatRupees(debt.amount_paise)}`)
}

/** The activity entry a debt entry points at (an expense or a repayment), if it's still there. */
export function findEntry(group: Group, ref: string): ActivityEntry | undefined {
  return group.activity.find((entry) => entry.id === ref)
}

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
