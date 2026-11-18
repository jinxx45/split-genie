# Split Rupya — launch video plan

**What it is:** A LangGraph agent reads a photo of a group receipt plus a plain-English note,
assigns every item to the right people on its own, and hands the money math to tested,
deterministic Python so the shares always add up exactly.

**Who it's for:** Anyone who's been stuck doing the "wait, who had the biryani" math after a
group meal, trip or flat.

**What sets it apart:** You don't tap through every item. You type one sentence like a human
would ("Ravi doesn't drink, Meena had the biryani") and the agent reads that note against the
receipt and gets it right — you only confirm.

**Visual hook:** The real "Snap the bill" tile on the home screen, then the actual receipt-print
loading animation, then the real "Who had what?" screen where chips fill in by themselves instead
of needing to be tapped one by one.

**Real UI shown:** Home.tsx's "Snap the bill" tile, Reading.tsx's printing-receipt loader (its own
CSS keyframes, untouched), ReviewItems.tsx's item cards with the agent's own "reason" text and
ShareChips animating to the suggested split, ConfirmItems.tsx's total-matches checkmark, and a
quick glimpse of GroupSettle's settle-up view as the secondary beat.

**Tone:** `default` — punchy, playful, clean. Matches the app's own voice (dry, specific copy:
"Ravi doesn't drink", not "streamline your expenses").

**One-line share caption:** "Type a note. Split Rupya reads the bill and figures out who had
what — so you don't have to." (see share-copy.txt for the final wording)

**Format:** landscape, 1920×1080, 30fps. **Tempo:** 120 BPM (beat = 0.5s) — every cut below lands
on a beat. **Duration:** 22.0s (44 beats, 11 bars of 4/4).

## Storyboard

| Time | Scene | Beat | What's on screen |
|---|---|---|---|
| 0.0–2.5s | **Hook** | 0–5 | Headline "WHO HAD THE BIRYANI?" punches in over a blurred receipt texture; cuts to the real "Snap the bill" tile (camera icon, sky-blue, hard shadow) pressed with a shutter flash. |
| 2.5–6.5s | **Reveal** | 5–13 | The real printing-receipt loader. Beside it, a note bubble types itself out: "Ravi doesn't drink. Meena had the biryani." — the app's own placeholder copy. Headline: "Type a note. That's it." |
| 6.5–12.0s | **Highlight 1 — the centerpiece** | 13–24 | The real "Who had what?" item card for Biryani, with the agent's reason text appearing, then its ShareChips filling in one by one (full share) without being tapped. Headline: "Split Rupya reads the bill — and the note." |
| 12.0–15.5s | **Highlight 2** | 24–31 | Real total block from Confirm Items: amount ticks up to the exact total, checkmark "✓ Matches the total printed on the bill." settles in. Headline: "Shares that always add up. To the paisa." |
| 15.5–18.0s | **Highlight 3 (secondary)** | 31–36 | Quick glimpse of the real Settle Up box ("They pay ₹600.00") and the bottom tab bar. Headline: "Then settle it in one tap." |
| 18.0–22.0s | **Outro** | 36–44 | Real brand mark + wordmark assemble (the ₹ splits, per the brand kit's own splash animation), on the paper background. Share caption land as the final card. |

## Sound

Synthesized from scratch (no bundled assets): a soft plucked-synth riff in C major over a light
four-on-the-floor kick/hat pattern, 120 BPM. A short filtered "whoosh" sits under each scene cut
(all six, at the beat times above), in the same reverb space as the pad so it reads as one mix
instead of a sound effect stapled on top. The kick stays soft under the voice-less scenes and
gets one extra hit (a small "bump") right on the outro's downbeat (18.0s) for the logo reveal.
