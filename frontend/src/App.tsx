import { useEffect, useState } from 'react'

type ApiStatus = 'checking' | 'connected' | 'unreachable'

function App() {
  const [status, setStatus] = useState<ApiStatus>('checking')

  useEffect(() => {
    fetch('/api/health')
      .then((res) => setStatus(res.ok ? 'connected' : 'unreachable'))
      .catch(() => setStatus('unreachable'))
  }, [])

  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col justify-center gap-4 px-4">
      <h1 className="text-3xl font-semibold">Split Genie</h1>
      <p className="text-neutral-600">Snap the bill. Split it fairly. Settle on UPI.</p>
      <p className="text-sm">
        API:{' '}
        <span
          className={
            status === 'connected'
              ? 'text-green-700'
              : status === 'unreachable'
                ? 'text-red-700'
                : 'text-neutral-500'
          }
        >
          {status}
        </span>
      </p>
    </main>
  )
}

export default App
