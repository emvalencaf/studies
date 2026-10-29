import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, post, type Certification, type ExamRow, type Running } from '../api'
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

  const start = useMutation({
    mutationFn: () => post<{ attempt_id: number }>('/attempts', { kind: 'exam', exam_id: examId ?? exams.data?.[0]?.id, mode, shuffle }),
    onSuccess: (r) => nav(`/attempts/${r.attempt_id}`),
  })
  const abandon = useMutation({
    mutationFn: (id: number) => post(`/attempts/${id}/abandon`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['running'] }),
  })

  if (certs.error) return <ErrorBox error={certs.error} retry={() => certs.refetch()} />
  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 lg:p-8">
      <h1 className="font-sans text-xl font-bold text-zinc-100">Estudar</h1>

      <Panel title="Attempts em andamento">
        {running.isPending ? <Skeleton className="h-10" /> : running.data?.length ? (
          <ul className="divide-y divide-zinc-800">
            {running.data.map((a) => (
              <li key={a.id} className="flex flex-wrap items-center gap-3 py-2">
                <span className="flex-1">
                  <b className="text-zinc-100">{a.exam_title ? `${a.course_slug} / ${a.exam_title}` : KIND[a.kind]}</b>
                  <span className="ml-2 text-zinc-500">{a.answered}/{a.total} · {a.started_at.slice(0, 16).replace('T', ' ')}</span>
                </span>
                <button onClick={() => nav(`/attempts/${a.id}`)} className="rounded border border-violet-600 px-3 py-2 text-violet-300 lg:py-1 hover:bg-violet-950">Retomar</button>
                <button onClick={() => abandon.mutate(a.id)} className="rounded border border-zinc-700 px-3 py-2 text-zinc-400 hover:bg-zinc-800 lg:py-1">Abandonar</button>
              </li>
            ))}
          </ul>
        ) : <span className="text-zinc-500">Nenhum.</span>}
      </Panel>

      <Panel title="Novo Exam">
        {certs.isPending || exams.isPending ? <Skeleton className="h-28" /> : (
          <div className="space-y-3">
            {certs.data!.length > 1 && (
              <select value={cert ?? ''} onChange={(e) => { setCertId(Number(e.target.value)); setExamId(null) }} className="w-full rounded border border-zinc-700 bg-zinc-900 p-2.5">
                {certs.data!.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            )}
            <select value={examId ?? exams.data![0]?.id ?? ''} onChange={(e) => setExamId(Number(e.target.value))} className="w-full rounded border border-zinc-700 bg-zinc-900 p-2.5">
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
            {start.error && <div className="text-rose-400">{start.error.message}</div>}
          </div>
        )}
      </Panel>
    </div>
  )
}
