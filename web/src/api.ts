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
  consistency_by_section: { group: string; level: string; questions: number; share: number }[]
  insights: Insights
  cert_id?: number
  window: { start: string; end: string } | null
  trend: { current: number | null; previous: number | null; delta: number | null }
  accuracy_new: number | null; accuracy_repeat: number | null
  progression: { bucket: string; segment: 'Inéditas' | 'Repetições'; n: number; accuracy: number | null; rolling: number | null }[]
  by: Partial<Record<'course' | 'exam' | 'section' | 'topic' | 'question', Grouped[]>>
  best_window: { bucket: string; accuracy: number; n: number } | null
  pace: { days: { day: string; questions: number }[]; median_seconds: number | null; mean_seconds: number | null }
  topics: { nodes: { topic: string; primary: number; total: number; answers: number; accuracy: number | null; share?: number; impact?: number | null }[]; edges: { a: string; b: string; questions: number; answers?: number; accuracy?: number | null }[] }
  most_wrong: { question_id: number; answers: number; wrong: number; section: string; course: string; error_rate: number }[]
  lucky_guesses: { question_id: number; times: number; section: string; course: string }[]
}
export type Insights = {
  review_queue: { question_id: number; level: string; score: number; answers: number; wrong: number; lucky: number; confident_wrong: number; section: string; course: string }[]
  weak_neighbors: Record<string, string[]>
  calibration_by_section: { section: string; level: string; n: number; accuracy: number }[]
  calibration_trend: { bucket: string; confident_n: number; confident_accuracy: number | null; guess_n: number; guess_accuracy: number | null; overconfident: number | null }[]
  time: { bins: { label: string; n: number; accuracy: number | null }[]; median_all?: number; median_correct: number | null; median_wrong: number | null
    slow: { question_id: number; answers: number; median_seconds: number; accuracy: number; section: string }[] }
  projection: { n: number; mean_recent: number; predicted: number; low: number; high: number; slope_per_week: number; eta_days: number | null; target: number } | null
  mode_effect: { mode: string; n: number; accuracy: number | null; new_n: number; new_accuracy: number | null; median_seconds: number | null }[]
  retention: { label: string; n: number; kept: number | null; kept_n: number; recovered: number | null; recovered_n: number }[]
  heatmap: { section: string; bucket: string; n: number; accuracy: number }[]
  reasoning: { with_n: number; with_accuracy: number | null; without_n: number; without_accuracy: number | null
    wrong_with_reasoning: { question_id: number; section: string; confidence: string | null; reasoning: string }[] } | null
}
export type Grouped = { group: string; n: number; correct: number; accuracy: number }
export type DashParams = { window: '7d' | '30d' | 'all'; kinds: string[]; freq: 'D' | 'W'; roll: number; stable_after: number }
