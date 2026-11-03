// Types and calls for the Split Rupya API. Shapes match backend/app/api/splits.py.

export type Weight = 1 | 2 // 1 = half share, 2 = full share

/** Who had one item. Shared: FULL/HALF weights. By count: how many each had, adding up to the
 * item's quantity. Empty weights: not decided yet. */
export type Assignment = { weights: Record<string, number>; by_count: boolean }
export type Category = 'food' | 'drink' | 'alcohol' | 'dessert'

export type Item = { name: string; amount_paise: number; category: Category; quantity: number }

export type Receipt = {
  items: Item[]
  tax_paise: number
  service_charge_paise: number
  printed_total_paise: number
}

export type ItemShare = {
  item: string
  amount_paise: number
  shared_by: number
  half: boolean // a half share next to someone with a full one
  count: number | null // how many they had, when the item is split by count
}
export type Breakdown = { items: ItemShare[]; charges_paise: number; total_paise: number }
export type Payment = {
  sender: string
  receiver: string
  amount_paise: number
  marked_paid_by?: string | null // on a finished split: who marked it paid; null = still waiting
}
export type PaymentMark = { sender: string; receiver: string; paid: boolean; by: string }
export type Change = { item: string; before: Assignment; after: Assignment }

export type ReviewItem = {
  index: number
  item: Item
  suggested: Assignment
  reason: string
  needs_answer: boolean
}

export type Question =
  | { step: 'confirm_items'; receipt: Receipt; totals_match: boolean }
  | {
      step: 'review_assignments'
      people: string[]
      items: ReviewItem[]
      light_eaters: string[]
      claims: Record<string, Record<string, number>> // friend -> {item index: weight}, from their links
      claimed: Assignment[] // the suggestions updated with friends' claims, one per item
    }
  | { step: 'payer'; people: string[]; total_paise: number }
  | {
      step: 'approve'
      shares: Record<string, number>
      breakdown: Record<string, Breakdown>
      payments: Payment[]
      changes: Change[]
      error: string | null
    }

export type Split = {
  id: string
  name: string // what the split is for, e.g. 'Saturday lunch'
  group: { id: string; name: string; added_by: string } | null // set when the bill was scanned into a group
  status: 'waiting' | 'failed' | 'done'
  people: string[]
  can_answer: boolean // false: started by someone else while signed in; only they can answer
  question: Question | null
  result: {
    total_paise: number
    paid: Record<string, number>
    shares: Record<string, number>
    breakdown: Record<string, Breakdown>
    payments: Payment[]
  } | null
}

/** One of the signed-in user's splits, for the history list. */
export type SplitSummary = {
  id: string
  created_at: string // UTC, "2026-11-02T09:14:05.123456Z"
  status: Split['status']
  people: string[]
  name: string
  total_paise: number | null // null until the split is done
  payments: number
  paid: number
}

export type Friend = { name: string; upi_id: string }
export type Me = { user: { name: string; email: string; upi_id: string } | null; friends: Friend[] }

export class ApiError extends Error {}

async function request<T = Split>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, init)
  } catch {
    throw new ApiError('Couldn’t reach Split Rupya. Check your internet connection and try again.')
  }
  const body = await response.json().catch(() => null) // null: the reply wasn't JSON
  if (!response.ok) throw new ApiError(errorMessage(response, body))
  return body as T
}

/** A sentence for the user, for any failed reply. The backend always sends one in `detail`;
 * the other cases are replies that never came from it. */
function errorMessage(response: Response, body: { detail?: unknown } | null): string {
  if (typeof body?.detail === 'string') return body.detail
  // Every reply from the backend carries a request id. Without one, the dev server (or a proxy
  // in production) answered because the backend didn't.
  if (!response.headers.has('X-Request-ID')) {
    return 'The Split Rupya server isn’t responding. If you’re running it yourself, check that the backend is started.'
  }
  const ref = response.headers.get('X-Request-ID')
  return `Something went wrong on our side (error ${response.status}, ref ${ref}). Please try again.`
}

const json = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

/** Photos per split; the server allows the same. */
export const MAX_PHOTOS = 5

export function createSplit(
  name: string,
  people: string[],
  note: string,
  photos: File[],
  group?: { id: string; addedBy: string }, // scanning a bill into a group
): Promise<Split> {
  const form = new FormData()
  form.append('name', name)
  if (group) {
    form.append('group_id', group.id)
    form.append('added_by', group.addedBy)
  }
  people.forEach((person) => form.append('people', person))
  form.append('note', note)
  photos.forEach((photo) => form.append('photos', photo))
  return request('/api/splits', { method: 'POST', body: form })
}

/** One amount, no photo: `shares` is how many shares each person sharing it takes (1 each: equal). */
export type InstantSplit = {
  name: string
  amount_paise: number
  people: string[]
  paid_by: string
  shares: Record<string, number>
}
export const createInstantSplit = (split: InstantSplit) => request('/api/splits/instant', json(split))

export const getSplit = (id: string) => request(`/api/splits/${id}`)
export const answerSplit = (id: string, answer: unknown) =>
  request(`/api/splits/${id}/answer`, json(answer))
export const retrySplit = (id: string) => request(`/api/splits/${id}/retry`, { method: 'POST' })
export const claimItems = (id: string, person: string, items: Record<number, number>) =>
  request(`/api/splits/${id}/claims`, json({ person, items }))
export const markPayment = (id: string, mark: PaymentMark) => request(`/api/splits/${id}/payments`, json(mark))

// --- Signing in, and the signed-in user's details ---

export const getSite = () => request<{ contact_email: string }>('/api/site')
export const getAuthConfig = () => request<{ google_client_id: string }>('/api/auth/config')
export const getMe = () => request<Me>('/api/me')
export const signInWithGoogle = (credential: string) => request<Me>('/api/auth/google', json({ credential }))
export const signOut = () => request<Me>('/api/auth/sign-out', { method: 'POST' })
export const getMySplits = () => request<{ splits: SplitSummary[] }>('/api/splits')
export const saveMyUpiId = (upi_id: string) => request<Me>('/api/me', { ...json({ upi_id }), method: 'PATCH' })
export const saveFriendUpiId = (name: string, upi_id: string) =>
  request<Me>('/api/me/friends', { ...json({ name, upi_id }), method: 'PUT' })

// --- Groups: Friends, Trip, Flatmates ---

export type GroupKind = 'friends' | 'trip' | 'flat'

export type ActivityEntry =
  | {
      type: 'expense'
      id: string
      title: string
      source: 'bill' | 'quick' | 'recurring'
      total_paise: number
      paid: Record<string, number>
      owed: Record<string, number>
      added_by: string
      created_at: string
      split_id: string | null
    }
  | {
      type: 'repayment'
      id: string
      sender: string
      receiver: string
      amount_paise: number
      marked_by: string
      created_at: string
    }

export type RecurringBill = {
  id: string
  title: string
  amount_paise: number | null // null: changes each month
  paid_by: string
  weights: Record<string, number>
  day_of_month: number
}

export type Group = {
  id: string
  kind: GroupKind
  name: string
  members: string[]
  upi_ids: Record<string, string>
  start_date: string | null
  end_date: string | null
  closed: boolean
  is_owner: boolean
  balances: Record<string, number> // positive: gets money back; negative: owes
  settle_up: { sender: string; receiver: string; amount_paise: number }[]
  spent: Record<string, number> // each person's own shares
  total_paise: number
  activity: ActivityEntry[] // newest first
  // Flatmates only:
  recurring?: RecurringBill[]
  due?: { recurring_id: string; title: string; paid_by: string; month: string; label: string }[]
  months?: { month: string; label: string; total_paise: number; owed: Record<string, number> }[]
}

export type GroupSummary = {
  id: string
  kind: GroupKind
  name: string
  member: string
  balance_paise: number
  closed: boolean
}

export type NewGroup = {
  kind: GroupKind
  name: string
  members: string[]
  me: string
  start_date?: string
  end_date?: string
}

const put = (body: unknown): RequestInit => ({ ...json(body), method: 'PUT' })
const del: RequestInit = { method: 'DELETE' }
const groupUrl = (id: string, rest = '') => `/api/groups/${id}${rest}`

export const createGroup = (group: NewGroup) => request<Group>('/api/groups', json(group))
export const getMyGroups = () => request<{ groups: GroupSummary[] }>('/api/groups')
export const getGroup = (id: string) => request<Group>(groupUrl(id))
export const joinGroup = (id: string, member: string) => request<Group>(groupUrl(id, '/join'), json({ member }))
export const addQuickExpense = (
  id: string,
  expense: { title: string; amount_paise: number; paid_by: string; weights: Record<string, number>; added_by: string },
) => request<Group>(groupUrl(id, '/expenses'), json(expense))
export const deleteExpense = (id: string, expenseId: string) => request<Group>(groupUrl(id, `/expenses/${expenseId}`), del)
export const addRepayment = (
  id: string,
  repayment: { sender: string; receiver: string; amount_paise: number; by: string },
) => request<Group>(groupUrl(id, '/repayments'), json(repayment))
export const deleteRepayment = (id: string, repaymentId: string) =>
  request<Group>(groupUrl(id, `/repayments/${repaymentId}`), del)
export const setGroupUpiId = (id: string, member: string, upi_id: string) =>
  request<Group>(groupUrl(id, '/upi'), put({ member, upi_id }))
export const setGroupClosed = (id: string, closed: boolean) => request<Group>(groupUrl(id, '/closed'), put({ closed }))
export const addRecurring = (
  id: string,
  bill: { title: string; amount_paise: number | null; paid_by: string; weights: Record<string, number>; day_of_month: number },
) => request<Group>(groupUrl(id, '/recurring'), json(bill))
export const stopRecurring = (id: string, billId: string) => request<Group>(groupUrl(id, `/recurring/${billId}`), del)
export const enterMonthAmount = (id: string, billId: string, month: string, amount_paise: number, by: string) =>
  request<Group>(groupUrl(id, `/recurring/${billId}/months/${month}`), put({ amount_paise, by }))
