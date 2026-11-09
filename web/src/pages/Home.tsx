import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { clearAttemptTimers } from '../activeTimer'
import { api, post, type Certification, type ExamRow, type Running, type Section } from '../api'
import { ErrorBox, Panel, Skeleton } from '../ui'

const KIND = { exam: 'Exam', review: 'Review', drill: 'Drill' } as Record<string, string>

export default function Home() {
  const nav = useNavigate()
  const qc = useQueryClient()
  const certs = useQuery({ queryKey: ['certs'], queryFn: () => api<Certification[]>('/certifications') })
  const [certId, setCertId] = useState<number | null>(null)
  const cert = certId ?? certs.data?.[0]?.id ?? null
  const exams = useQuery({ queryKey: ['exams', cert], queryFn: () => api<ExamRow[]>(`/certifications/${cert}/exams`), enabled: cert !== null })
  const running = useQuery({ queryKey: ['running'], queryFn: () => api<Running[]>('/attempts'), staleTime: 0 })
  const [examId, setExamId] = useState<number | null>(null)
  const [mode, setMode] = useState<'practice' | 'exam'>('exam')
  const [shuffle, setShuffle] = useState(false)
  const sections = useQuery({ queryKey: ['sections', cert], queryFn: () => api<Section[]>(`/certifications/${cert}/sections`), enabled: cert !== null })
  const topics = useQuery({ queryKey: ['topics', cert], queryFn: () => api<string[]>(`/certifications/${cert}/topics`), enabled: cert !== null })
  const [sectionIds, setSectionIds] = useState<number[]>([])
  const [topicNames, setTopicNames] = useState<string[]>([])
  const [drillN, setDrillN] = useState(20)

  const start = useMutation({
    mutationFn: () => post<{ attempt_id: number }>('/attempts', { kind: 'exam', exam_id: examId ?? exams.data?.[0]?.id, mode, shuffle }),
    onSuccess: (r) => nav(`/attempts/${r.attempt_id}`),
  })
  const startDrill = useMutation({
    mutationFn: () => post<{ attempt_id: number }>('/attempts', {
      kind: 'drill', mode: 'practice', certification_id: cert, section_ids: sectionIds, topics: topicNames, n: drillN,
    }),
    onSuccess: (r) => nav(`/attempts/${r.attempt_id}`),
  })
  const toggleSection = (id: number) => setSectionIds((s) => s.includes(id) ? s.filter((x) => x !== id) : [...s, id])
  const abandon = useMutation({
    mutationFn: (id: number) => post(`/attempts/${id}/abandon`),
    onSuccess: (_, id) => { clearAttemptTimers(id); qc.invalidateQueries({ queryKey: ['running'] }) },
  })

  if (certs.error) return <ErrorBox error={certs.error} retry={() => certs.refetch()} />
  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 lg:p-8">
      <h1 className="font-sans text-xl font-bold text-zinc-800 dark:text-zinc-100">Estudar</h1>

      <Panel title="Attempts em andamento">
        {running.isPending ? <Skeleton className="h-10" /> : running.data?.length ? (
          <ul className="divide-y divide-zinc-200 dark:divide-zinc-800">
            {running.data.map((a) => (
              <li key={a.id} className="flex flex-wrap items-center gap-3 py-2">
                <span className="flex-1">
                  <b className="text-zinc-800 dark:text-zinc-100">{a.exam_title ? `${a.course_slug} / ${a.exam_title}` : KIND[a.kind]}</b>
                  <span className="ml-2 text-zinc-500">{a.answered}/{a.total} · {a.started_at.slice(0, 16).replace('T', ' ')}</span>
                </span>
                <button onClick={() => nav(`/attempts/${a.id}`)} className="rounded border border-violet-600 px-3 py-2 text-violet-700 lg:py-1 hover:bg-violet-50 dark:text-violet-300 dark:hover:bg-violet-950">Retomar</button>
                <button onClick={() => abandon.mutate(a.id)} className="rounded border border-zinc-300 px-3 py-2 text-zinc-500 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-800 lg:py-1">Abandonar</button>
              </li>
            ))}
          </ul>
        ) : <span className="text-zinc-500">Nenhum.</span>}
      </Panel>

      <Panel title="Novo Exam">
        {certs.isPending || exams.isPending ? <Skeleton className="h-28" /> : (
          <div className="space-y-3">
            {certs.data!.length > 1 && (
              <select value={cert ?? ''} onChange={(e) => { setCertId(Number(e.target.value)); setExamId(null) }} className="w-full rounded border border-zinc-300 bg-white p-2.5 dark:border-zinc-700 dark:bg-zinc-900">
                {certs.data!.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            )}
            <select value={examId ?? exams.data![0]?.id ?? ''} onChange={(e) => setExamId(Number(e.target.value))} className="w-full rounded border border-zinc-300 bg-white p-2.5 dark:border-zinc-700 dark:bg-zinc-900">
              {exams.data!.map((e) => <option key={e.id} value={e.id}>{e.course} / {e.title}</option>)}
            </select>
            <div className="flex flex-wrap gap-4">
              {(['exam', 'practice'] as const).map((m) => (
                <label key={m} className="flex items-center gap-2 py-1">
                  <input type="radio" checked={mode === m} onChange={() => setMode(m)} />
                  {m === 'exam' ? 'Exam (gabarito só ao finalizar)' : 'Practice (gabarito após cada resposta)'}
                </label>
              ))}
              <label className="flex items-center gap-2 py-1"><input type="checkbox" checked={shuffle} onChange={(e) => setShuffle(e.target.checked)} />Embaralhar opções</label>
            </div>
            <button onClick={() => start.mutate()} disabled={start.isPending} className="w-full rounded-md bg-violet-600 px-4 py-2.5 font-semibold text-white disabled:opacity-40 sm:w-auto">
              {start.isPending ? <><i className="fa-solid fa-circle-notch fa-spin mr-2" />Criando…</> : 'Iniciar Exam'}
            </button>
            {start.error && <div className="text-rose-600 dark:text-rose-400">{start.error.message}</div>}
          </div>
        )}
      </Panel>

      <Panel title="Nova sessão de prática">
        {sections.isPending || topics.isPending ? <Skeleton className="h-28" /> : (
          <div className="space-y-3">
            <div>
              <div className="mb-1 text-sm font-semibold text-zinc-600 dark:text-zinc-400">Domínios</div>
              <div className="flex flex-wrap gap-3">
                {sections.data!.map((s) => (
                  <label key={s.id} className="flex items-center gap-2 py-1">
                    <input type="checkbox" checked={sectionIds.includes(s.id)} onChange={() => toggleSection(s.id)} />
                    {s.name}
                  </label>
                ))}
              </div>
            </div>
            <div>
              <div className="mb-1 text-sm font-semibold text-zinc-600 dark:text-zinc-400">Temas</div>
              <select multiple value={topicNames} onChange={(e) => setTopicNames(Array.from(e.target.selectedOptions, (o) => o.value))}
                className="h-40 w-full rounded border border-zinc-300 bg-white p-2 dark:border-zinc-700 dark:bg-zinc-900">
                {topics.data!.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <label className="flex items-center gap-2 py-1">
              Quantidade de questões
              <input type="number" min={1} value={drillN} onChange={(e) => setDrillN(Number(e.target.value))}
                className="w-20 rounded border border-zinc-300 bg-white p-1.5 dark:border-zinc-700 dark:bg-zinc-900" />
            </label>
            <button onClick={() => startDrill.mutate()} disabled={startDrill.isPending || (sectionIds.length === 0 && topicNames.length === 0)}
              className="w-full rounded-md bg-violet-600 px-4 py-2.5 font-semibold text-white disabled:opacity-40 sm:w-auto">
              {startDrill.isPending ? <><i className="fa-solid fa-circle-notch fa-spin mr-2" />Criando…</> : 'Iniciar sessão'}
            </button>
            {startDrill.error && <div className="text-rose-600 dark:text-rose-400">{startDrill.error.message}</div>}
          </div>
        )}
      </Panel>
    </div>
  )
}
