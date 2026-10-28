const BASE = ((import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000').replace(/\/$/, '')
export const API_BASE = BASE
const KEY = 'studies_token'

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
  }
}

// localStorage pode lançar (janela privada, dados bloqueados): o app funciona sem ele, só pede o token de novo.
export function getToken(): string | null {
  try { return localStorage.getItem(KEY) } catch { return null }
}
export function setToken(t: string | null) {
  try { t ? localStorage.setItem(KEY, t) : localStorage.removeItem(KEY) } catch { /* sem armazenamento */ }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken()
  const res = await fetch(BASE + path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...init.headers },
  })
  if (!res.ok) {
    if (res.status === 401 && typeof window !== 'undefined') window.dispatchEvent(new Event('studies:unauthorized'))
    let detail = res.statusText
    try { detail = String((await res.json()).detail ?? detail) } catch { /* corpo sem JSON */ }
    throw new ApiError(res.status, detail)
  }
  return res.json() as Promise<T>
}

export const post = <T>(path: string, body?: unknown) =>
  api<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })

export type Pass = { needed: number; remaining: number; accuracy: number | null; still_needed: number; passed: boolean; failed: boolean }
export type Score = { total: number; correct: number; wrong: number; skipped: number; answered: number; pass: Pass | null }
export type Certification = { id: number; name: string }
export type ExamRow = { id: number; course: string; title: string }
export type Running = { id: number; kind: string; mode: string; started_at: string; answered: number; total: number; course_slug: string | null; exam_title: string | null }
export type AttemptInfo = {
  id: number; kind: string; mode: 'practice' | 'exam'; state: 'in_progress' | 'finished' | 'abandoned'
  score: Score; map: { position: number; answered: boolean; is_correct: boolean | null }[]
}
export type Question = {
  position: number; total: number; state: string; mode: 'practice' | 'exam'; section: string; prompt_html: string
  multi: boolean; choose?: number; options: { letter: string; html: string }[]; answered: boolean; selected: string[]
  confidence: string | null; reveal: boolean
  correct?: string[]; is_correct?: boolean | null; reasoning?: string | null; explanation_html?: string
  ai_reasoning?: string | null; topics?: { topic: string; is_primary: number }[]
}
export type Dashboard = {
  answers: number; accuracy: number | null; elapsed_ms: number
  readiness: { ready: boolean; streak: number; needed: number; attempts: number; recent_mean: number | null }
  streaks: { current: number; current_kind: 'correct' | 'wrong' | null; longest_correct: number; longest_wrong: number }
  scores: { attempt_id: number; exam_title: string; mode: string; score: number | null; answered: number; skipped: number; finished_at: string }[]
  best_per_exam: { exam_title: string; score: number; mode: string; finished_at: string }[]
  calibration: { level: string; n: number; correct: number; accuracy: number; in_calibration: boolean }[]
  consistency: { group: string; level: string; questions: number; share: number }[]
}
