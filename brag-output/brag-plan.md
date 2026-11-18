# Split Rupya — launch video plan

**What it is:** A LangGraph agent reads a photo of a group receipt plus a plain-English note,
assigns every item to the right people on its own, and hands the money math to tested,
deterministic Python so the shares always add up exactly.

**Who it's for:** Anyone who's been stuck doing the "wait, who had the biryani" math after a
group meal, trip or flat.

**What sets it apart:** The default — an even split — is quietly unfair to whoever ordered
light. You don't tap through every item to fix that. You type one sentence like a human would
("Ravi doesn't drink") and the agent reads that note against the receipt and gets it right —
you only confirm.

**Visual hook:** A real itemised receipt where the person who had just a juice would still pay
a full even share — the unfairness the app exists to fix — then the actual brand reveal, the
real "Snap the bill" tile, the real receipt-print loading animation, and the real "Who had
what?" screen where chips fill in by themselves instead of needing to be tapped one by one.

**Real UI shown:** The home screen's "Snap the bill" tile, the printing-receipt loader (its
own CSS keyframes, untouched), the item cards with the agent's own "reason" text and its chips
animating to the suggested split, the total-matches checkmark, and a quick glimpse of the
settle-up view as the secondary beat.

**Tone:** `default` — punchy, playful, clean. Matches the app's own voice (dry, specific copy:
"Ravi doesn't drink", not "streamline your expenses").

**Voiceover:** ElevenLabs "Kaanha — Confident Commercial Voiceover" (Indian English, built for
product launches). One line per scene, narrating the problem → fix → proof arc; see the script
below. Ducked under the music bed so it always reads clearly.

**One-line share caption:** see `share-copy.txt`.

**Format:** landscape, 1920×1080, 30fps. **Tempo:** 120 BPM (beat = 0.5s) — every cut lands on
a beat. **Duration:** 38.0s (76 beats) — each scene's length is driven by its voiceover line
(narration + 0.3s lead-in + 0.3s tail, rounded up to the nearest beat), which runs longer than
the skill's usual 18–22s sweet spot.

## Storyboard

| Time | Scene | What's on screen | Voiceover |
|---|---|---|---|
| 0.0–4.5s | **Hook** | Real itemised receipt (Biryani/Beer/Dosa/Juice/Total), the Juice line highlighted, then a flashed "₹1,460 ÷ 4 = ₹365 each". | "Ravi had a juice. Why's he paying for everyone's biryani?" |
| 4.5–13.0s | **Reveal** | Brand mark assembles (the ₹ splits), cuts to the real "Snap the bill" tile pressed with a shutter flash, the real receipt-print loader, then a note bubble types the app's own placeholder text: "Ravi doesn't drink. Meena left before dessert." | "This is Split Rupya. Snap the bill, add a note — like you'd text a friend — and the AI takes care of the right split." |
| 13.0–25.0s | **Highlight 1 — the centerpiece** | Three real item cards: Beer (chips fill for Arjun & Divya, Ravi stays empty), Gulab Jamun (fills for Arjun, Divya & Ravi; Meena stays empty), and Juice (fills for Ravi alone) — closing the loop on the hook. | "It reads the receipt and the note together. Beer — split only between the two who drank. Dessert — skipped for Meena. And Ravi's juice? Just Ravi's." |
| 25.0–31.0s | **Highlight 2** | Real total block ticking to the exact total, checkmark "✓ Matches the total printed on the bill." settling in. | "Every rupee accounted for — shares that always add up, to the paisa." |
| 31.0–34.0s | **Highlight 3 (secondary)** | Real Settle Up box + bottom tab bar. | "Then settle it, in one tap." |
| 34.0–38.0s | **Outro** | Real brand mark + wordmark assemble, tagline and share caption land on the paper-on-ink background. | "Split Rupya. Pay for what you actually had." |

## Sound

Synthesized from scratch (no bundled assets): a soft plucked-synth riff in C major over a light
four-on-the-floor kick/hat pattern, 120 BPM. A short filtered "whoosh" sits under every scene
cut, in the same reverb space as the pad so it reads as one mix instead of a sound effect
stapled on top. One extra kick "bump" lands right on the outro's downbeat (34.0s) for the logo
reveal. The music bed ducks under each of the six voiceover lines (fading to ~32% under the
narration, full level in between) so the narration is never competing with the mix.
