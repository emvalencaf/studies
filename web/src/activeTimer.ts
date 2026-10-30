import { useCallback, useEffect, useRef, useState } from 'react'

export const IDLE_MS = 90_000 // sem toque ou tecla por tanto tempo, o cronômetro pausa
const ACTIVITY = ['pointerdown', 'pointermove', 'keydown', 'scroll', 'touchstart', 'wheel']
const storeKey = (key: string) => `studies_timer_${key}`

function load(key: string): number {
  try { const v = Number(localStorage.getItem(storeKey(key))); return v > 0 ? v : 0 } catch { return 0 }
}
function save(key: string, ms: number) {
  try { localStorage.setItem(storeKey(key), String(Math.round(ms))) } catch { /* sem armazenamento */ }
}

// Tempo ativo na questão: só corre com a aba visível e com interação recente. O acumulado é gravado a cada tick,
// então fechar o app e voltar retoma de onde parou sem contar o tempo fora (e um app morto pelo sistema perde no máximo 1 s).
export function useActiveTimer(key: string | null) {
  const ms = useRef(0)
  const [seconds, setSeconds] = useState(0)
  const [paused, setPaused] = useState(false)

  useEffect(() => {
    if (!key) { ms.current = 0; setSeconds(0); return }
    ms.current = load(key)
    setSeconds(Math.floor(ms.current / 1000))
    let lastActive = Date.now()
    let last = Date.now()
    const bump = () => { lastActive = Date.now() }
    const onVisible = () => { if (document.visibilityState === 'visible') { bump(); last = Date.now() } }
    ACTIVITY.forEach((e) => window.addEventListener(e, bump, { passive: true }))
    document.addEventListener('visibilitychange', onVisible)
    const id = setInterval(() => {
      const now = Date.now()
      const dt = Math.min(now - last, 2000) // aba em segundo plano estrangula o intervalo: não credita o buraco
      last = now
      const active = document.visibilityState === 'visible' && now - lastActive < IDLE_MS
      setPaused(!active)
      if (!active) return
      ms.current += dt
      save(key, ms.current)
      setSeconds(Math.floor(ms.current / 1000))
    }, 1000)
    return () => {
      clearInterval(id)
      ACTIVITY.forEach((e) => window.removeEventListener(e, bump))
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [key])

  const read = useCallback(() => ms.current / 1000, [])
  const clear = useCallback(() => {
    ms.current = 0
    setSeconds(0)
    if (key) { try { localStorage.removeItem(storeKey(key)) } catch { /* sem armazenamento */ } }
  }, [key])
  return { seconds, paused, read, clear }
}

export function mmss(sec: number) {
  return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, '0')}`
}
