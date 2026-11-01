// Shown while Gemini reads the bill: a receipt printing out of a slot.

export function Reading({ message = 'Reading your bill…' }: { message?: string }) {
  return (
    <div className="mx-auto flex min-h-dvh max-w-md flex-col items-center justify-center px-4" role="status">
      <div className="h-3 w-48 rounded-full bg-ink/80" aria-hidden />
      <div className="h-40 w-40 overflow-hidden" aria-hidden>
        <div className="printing">
          <div className="receipt mx-auto w-36 px-3 pt-3">
            {[70, 90, 55, 80, 65, 85].map((width, line) => (
              <div key={line} className="mb-2.5 flex justify-between gap-2">
                <span className="h-2 rounded bg-steel-dark" style={{ width: `${width - 25}%` }} />
                <span className="h-2 w-6 rounded bg-steel-dark" />
              </div>
            ))}
          </div>
        </div>
      </div>
      <p className="mt-6 font-display text-xl font-semibold">{message}</p>
    </div>
  )
}
