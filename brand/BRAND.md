# Split Rupya — Brand

Logo: "Split Rupee" — the ₹ glyph split vertically; the right half shifts up and right (+5, −7 in a 100-unit box).

## Files
- mark.svg — the symbol for light backgrounds
- mark-white.svg — the symbol for dark backgrounds
- app-icon.svg — 1024×1024 app icon (corner radius 230)
- lockup-light.svg / lockup-dark.svg — symbol plus wordmark

## Colors
- Indigo (primary): #26215C
- Sky (accent): #DCF0FD — the brand colour. Fills only: buttons, the selected tab, the headline
  block on a Wrapped card. Never text, and never a thin line: it is close enough to white to
  disappear on paper and on a dark card alike.
- Sky strong: #8FC0EC — the same blue with enough colour left to hold its own as a shape or as
  small text. Use it for the right half of the ₹, focus rings, and accents on dark.
- Black (dark bg, app icon, splash): #0A0A0A
- Paper (light-on-dark): #F6F4EE

The app carries these as `--color-accent` and `--color-accent-strong` in `frontend/src/index.css`,
with `--color-accent-soft` / `--color-accent-deep` for a tinted pill and its text. Change them
there and the whole app follows, the Wrapped card included — it reads both from the stylesheet.

## Type
- Wordmark: Sora — "Split" in 700, "Rupya" in 300, letter-spacing −0.02em, with a small gap between the words
- ₹ glyph in the mark: Poppins 700

## Rules
- Keep clear space of at least 25% of the mark's height on every side
- Minimum size: 20px for the mark alone, 96px wide for the lockup
- Don't recolor, rotate or re-space the two halves
- The SVGs load their fonts from Google Fonts; outline the text in Figma or Illustrator before print or production use
