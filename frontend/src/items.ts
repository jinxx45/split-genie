import type { Item } from './api'

/** How an item is shown: "Cold Coffee ×3", or just "Biryani" for one. Same as item_label in the backend. */
export function itemLabel(item: Item): string {
  return item.quantity > 1 ? `${item.name} ×${item.quantity}` : item.name
}
