// Types and calls for the Split Genie API. Shapes match backend/app/api/splits.py.

export type Weight = 1 | 2 // 1 = half share, 2 = full share

/** Who had one item. Shared: FULL/HALF weights. By count: how many each had, adding up to the
 * item's quantity. Empty weights: not decided yet. */
export type Assignment = { weights: Record<string, number>; by_count: boolean }
export type Category = 'food' | 'drink' | 'alcohol' | 'dessert'

export type Item = { name: string; amount_paise: number; category: Category; quantity: number }

export type Receipt = {
  place: string // the restaurant or shop name; '' if the bill doesn't show one
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
  | { step: 'review_assignments'; people: string[]; items: ReviewItem[]; light_eaters: string[] }
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
  status: 'waiting' | 'failed' | 'done'
  people: string[]
  can_answer: boolean // false: started by someone else while signed in; only they can answer
  question: Question | null
  result: {
    title: string // the place names of every receipt, e.g. 'Hotel Saravana'; '' if none
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
  created_at: string // UTC, "2026-11-02 09:14:05"
  status: Split['status']
  people: string[]
  title: string
  total_paise: number | null // null until the split is done
  payments: number
  paid: number
}

export type Friend = { name: string; upi_id: string }
export type Me = { user: { name: string; email: string; upi_id: string } | null; friends: Friend[] }

export class ApiError extends Error {}

async function request<T = Split>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init)
  const body = await response.json().catch(() => ({}))
  if (!response.ok) {
    // Our own errors carry a sentence in `detail`; framework validation errors carry a list.
    const message =
      typeof body.detail === 'string' ? body.detail : 'Please check the details and try again.'
    throw new ApiError(message)
  }
  return body as T
}

const json = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export function createSplit(people: string[], note: string, photos: File[]): Promise<Split> {
  const form = new FormData()
  people.forEach((person) => form.append('people', person))
  form.append('note', note)
  photos.forEach((photo) => form.append('photos', photo))
  return request('/api/splits', { method: 'POST', body: form })
}

export const getSplit = (id: string) => request(`/api/splits/${id}`)
export const answerSplit = (id: string, answer: unknown) =>
  request(`/api/splits/${id}/answer`, json(answer))
export const retrySplit = (id: string) => request(`/api/splits/${id}/retry`, { method: 'POST' })
export const markPayment = (id: string, mark: PaymentMark) => request(`/api/splits/${id}/payments`, json(mark))

// --- Signing in, and the signed-in user's details ---

export const getAuthConfig = () => request<{ google_client_id: string }>('/api/auth/config')
export const getMe = () => request<Me>('/api/me')
export const signInWithGoogle = (credential: string) => request<Me>('/api/auth/google', json({ credential }))
export const signOut = () => request<Me>('/api/auth/sign-out', { method: 'POST' })
export const getMySplits = () => request<{ splits: SplitSummary[] }>('/api/splits')
export const saveMyUpiId = (upi_id: string) => request<Me>('/api/me', { ...json({ upi_id }), method: 'PATCH' })
export const saveFriendUpiId = (name: string, upi_id: string) =>
  request<Me>('/api/me/friends', { ...json({ name, upi_id }), method: 'PUT' })
