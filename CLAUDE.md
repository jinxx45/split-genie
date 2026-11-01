# CLAUDE.md

## Project: Split Genie

Split Genie turns a photo of a group bill into exact, itemised shares and one-tap UPI payments. A LangGraph agent reads the receipt, assigns items from the splitter's note, asks about unclear items, and hands the maths to plain Python.

PRD (V1 one-pager): https://docs.google.com/document/d/1CdCntVAUfaobB7IhQBtZN8-hMSBmnXqHkBic-is18ws/edit
(Version with the agent graph diagram: https://claude.ai/artifact/92ycqqQeN89Y1D1MkE5QAw)

### Layout

- `backend/` — Python: FastAPI, LangGraph, Pydantic
- `frontend/` — React + Vite + TypeScript, Tailwind, shadcn/ui, mobile-first

### Rules for this codebase

- **The LLM never does money maths.** It extracts and assigns; shares, tax split and settlement are deterministic Python functions with tests.
- **Money is integer paise**, never floats. Shares must always sum exactly to the bill total.
- **Mobile first.** Every screen must work one-handed at 375 px wide.
- **V1 scope only.** Splitting modes (friend review or claiming) and phone OTP are V2. Check the PRD before adding features.
- **Readability over cleverness.** Code should be easy for a newcomer to Python to read. A comprehension is fine for a simple one-step transform; use a plain `for` loop when it would need more than one `for`/`if`, a lambda, or a complex expression. Give intermediate values descriptive names instead of packing logic into one line.

### Teaching mode

The owner is an experienced TypeScript/Angular developer who is new to Python.

- When code introduces new Python syntax or idioms, explain them briefly, compared with the TypeScript equivalent.
- For the parts the PRD marks as the owner's to write (settlement function, one graph node, the Pydantic receipt model), don't write the solution: leave a stub with a clear `TODO`, the tests it must pass, and hints.

---

## Coding guidelines

Adapted from [andrej-karpathy-skills](https://github.com/forrestchang/andrej-karpathy-skills) by forrestchang (MIT License), derived from Andrej Karpathy's observations on LLM coding mistakes.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
