# Split Genie

Snap a photo of a group bill, and Split Genie works out exactly who owes what, then settles it with one-tap UPI payments.

A LangGraph agent reads the receipt, assigns items from a plain-English note ("Ravi doesn't drink"), asks only about the unclear items, and hands the money maths to tested, deterministic Python.

> Status: early development (Milestone 1 of 6 — project scaffold).

## Stack

| Part | Tech |
| --- | --- |
| Frontend | React, Vite, TypeScript, Tailwind CSS |
| Backend | Python, FastAPI |
| Agent | LangGraph (coming in Milestone 3) |

## Run it locally

You need [uv](https://docs.astral.sh/uv/) for Python and Node.js 20+.

**Backend** (http://localhost:8000, API docs at `/docs`):

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

**Frontend** (http://localhost:5173), in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

The frontend forwards `/api` requests to the backend, so open http://localhost:5173 and the page should show **API: connected**.

**Tests:**

```bash
cd backend
uv run pytest
```
