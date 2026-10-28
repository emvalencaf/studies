import { useEffect, useState } from 'react'
import { api, API_BASE } from './api'

const TIMEOUT_MS = 120_000 // o Render Free leva ~1 min para acordar

// Espera a API responder /health. No Render Free a primeira abertura do dia é lenta, então a tela mostra o tempo.
export default function Boot({ onReady }: { onReady: () => void }) {
  const [elapsed, setElapsed] = useState(0)
  const [failed, setFailed] = useState(false)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let alive = true
    const t0 = Date.now()
    setFailed(false)
    setElapsed(0)
    const tick = setInterval(() => setElapsed(Math.floor((Date.now() - t0) / 1000)), 500)
    ;(async () => {
      while (alive && Date.now() - t0 < TIMEOUT_MS) {
        try {
          await api('/health', { signal: AbortSignal.timeout(20_000) })
          if (alive) onReady()
          return
        } catch {
          await new Promise((r) => setTimeout(r, 2_000))
        }
      }
      if (alive) setFailed(true)
    })()
    return () => { alive = false; clearInterval(tick) }
  }, [attempt, onReady])

  return (
    <div className="fixed inset-0 grid place-items-center bg-zinc-950 p-6">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center gap-3">
          <i className="fa-solid fa-graduation-cap text-2xl text-violet-400" />
          <span className="font-sans text-lg font-bold text-zinc-100">Studies</span>
        </div>
        <ul className="space-y-3">
          <li className="flex gap-3 pop">
            <i className="fa-solid fa-check mt-0.5 w-5 text-center text-emerald-400" />
            <span className="text-zinc-100">Interface carregada</span>
          </li>
          <li className="flex gap-3 pop">
            {failed ? <i className="fa-solid fa-xmark mt-0.5 w-5 text-center text-rose-400" />
              : <i className="fa-solid fa-circle-notch fa-spin mt-0.5 w-5 text-center text-violet-400" />}
            <span>
              <span className="text-zinc-100">{failed ? 'A API não respondeu' : `Acordando a API · ${elapsed}s`}</span>
              <span className="block text-xs text-zinc-500">
                {failed ? 'Passou de 2 minutos. O serviço do Render pode estar fora do ar, ou o CORS_ORIGINS dele não inclui este endereço.' : 'O plano grátis do Render dorme sem uso; a primeira abertura do dia leva cerca de 1 minuto.'}
              </span>
              {failed && (
                <span className="mt-2 block break-all text-xs text-zinc-600">
                  API: {API_BASE}<br />Origem deste front (precisa estar em CORS_ORIGINS): {window.location.origin}
                </span>
              )}
            </span>
          </li>
        </ul>
        {failed ? (
          <button onClick={() => setAttempt((n) => n + 1)} className="mt-6 rounded-md bg-violet-600 px-4 py-2 font-semibold text-white">
            Tentar de novo
          </button>
        ) : (
          <div className="relative mt-6 h-1 overflow-hidden rounded bg-zinc-800">
            <div className="indet absolute inset-y-0 w-1/3 bg-violet-500" />
          </div>
        )}
      </div>
    </div>
  )
}
