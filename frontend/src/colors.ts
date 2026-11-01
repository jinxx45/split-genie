// Each person's colour, used for their avatar and share chips.

const PERSON_COLORS = ['#1e6b45', '#b4541a', '#3b5ba9', '#8e3b8c', '#1f7f86', '#9a6b00', '#b03a57', '#4f5d2f']

/** Each person keeps the same colour everywhere, based on their place in the split. */
export function personColor(people: string[], person: string): string {
  return PERSON_COLORS[Math.max(people.indexOf(person), 0) % PERSON_COLORS.length]
}
