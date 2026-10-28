import { useQuery } from '@tanstack/react-query'
import { api, type Dashboard as Data } from '../api'
import { ErrorBox, Panel, pct, Skeleton } from '../ui'

const READY_RATIO = 0.8 // espelha metrics.READY_RATIO; a API entrega só quantos Exams seguidos estão na meta
const LEVELS: [string, string, string][] = [
  ['stable', 'Estável', 'bg-violet-500'], ['learned', 'Aprendida', 'bg-orange-500'], ['unstable', 'Instável', 'bg-emerald-500'],
  ['failing', 'Errando', 'bg-amber-500'], ['few_data', 'Poucos dados', 'bg-zinc-600'],
]
const CONF = { confident: 'Confiante', educated_guess: 'Educated guess', guess: 'Chute', unmarked: 'Sem marcação' } as Record<string, string>

function ScoreLine({ scores }: { scores: Data['scores'] }) {
  const pts = scores.filter((s) => s.score != null)
  if (pts.length < 2) return <div className="text-zinc-500">São necessários pelo menos 2 Exams finalizados.</div>
  const W = 300, H = 90, y = (v: number) => H - 10 - v * (H - 20)
  const xy = pts.map((s, i) => [10 + (i * (W - 20)) / (pts.length - 1), y(s.score!)] as const)
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Nota por Exam ao longo do tempo">
      <line x1="0" x2={W} y1={y(READY_RATIO)} y2={y(READY_RATIO)} stroke="#52525b" strokeDasharray="3 3" />
      <polyline fill="none" stroke="#a78bfa" strokeWidth="2" points={xy.map((p) => p.join(',')).join(' ')} />
      {xy.map(([x, yy], i) => <circle key={i} cx={x} cy={yy} r="3" fill="#a78bfa"><title>{pts[i].exam_title}: {pct(pts[i].score)}</title></circle>)}
    </svg>
  )
}

export default function Dashboard() {
  const { data: d, error, refetch } = useQuery({
    queryKey: ['dashboard'],
    queryFn: async () => {
      const certs = await api<{ id: number }[]>('/certifications')
      if (!certs.length) throw new Error('Banco vazio.')
      return api<Data>(`/dashboard/${certs[0].id}`)
    },
  })
  if (error) return <ErrorBox error={error} retry={() => refetch()} />
  if (!d) return (
    <div className="grid gap-4 p-4 lg:grid-cols-6 lg:p-6" aria-busy="true">
      <Skeleton className="h-32 lg:col-span-2" /><Skeleton className="h-32 lg:col-span-2" /><Skeleton className="h-32 lg:col-span-2" />
      <Skeleton className="h-40 lg:col-span-3" /><Skeleton className="h-40 lg:col-span-3" />
    </div>
  )
  const { readiness: r, streaks: st } = d
  const total = d.consistency
  return (
    <div className="grid gap-4 p-4 lg:grid-cols-6 lg:p-6">
      <Panel title="Prontidão" className="lg:col-span-2">
        <div className={`text-4xl font-bold ${r.ready ? 'text-emerald-400' : 'text-amber-400'}`}>{r.ready ? 'PRONTO' : 'AINDA NÃO'}</div>
        <div className="mt-2 flex gap-1">
          {Array.from({ length: r.needed }, (_, i) => <div key={i} className={`h-2 flex-1 rounded ${i < r.streak ? 'bg-emerald-500' : 'bg-zinc-700'}`} />)}
        </div>
        <div className="mt-2 text-zinc-400">
          {r.attempts < r.needed ? `${r.attempts}/${r.needed} Exams finalizados necessários` : `${r.streak}/${r.needed} Exams ≥ ${pct(READY_RATIO)}`} · média {pct(r.recent_mean)}
        </div>
      </Panel>
      <Panel title="Sequências" className="lg:col-span-2">
        <div className="grid grid-cols-3 gap-2 text-center">
          <div><div className="text-2xl font-bold text-orange-400">{st.current}</div><div className="text-zinc-500">atual ({st.current_kind === 'correct' ? '✓' : st.current_kind === 'wrong' ? '✗' : '–'})</div></div>
          <div><div className="text-2xl font-bold text-emerald-400">{st.longest_correct}</div><div className="text-zinc-500">máx ✓</div></div>
          <div><div className="text-2xl font-bold text-rose-400">{st.longest_wrong}</div><div className="text-zinc-500">máx ✗</div></div>
        </div>
      </Panel>
      <Panel title="Geral" className="lg:col-span-2">
        <div className="text-4xl font-bold text-zinc-100">{pct(d.accuracy)}</div>
        <div className="mt-2 text-zinc-500">{d.answers} Answers · API respondeu em {d.elapsed_ms} ms</div>
      </Panel>
      <Panel title="Nota por Exam (linha tracejada = 80%)" className="lg:col-span-3"><ScoreLine scores={d.scores} /></Panel>
      <Panel title="Calibração" className="lg:col-span-3">
        {d.calibration.length ? d.calibration.map((c) => (
          <div key={c.level} className="mb-2">
            <div className="flex justify-between"><span>{CONF[c.level] ?? c.level}</span><b>{pct(c.accuracy)} <span className="font-normal text-zinc-500">n={c.n}</span></b></div>
            <div className="h-1.5 rounded bg-zinc-800"><div className={`h-1.5 rounded ${c.in_calibration ? 'bg-violet-500' : 'bg-zinc-500'}`} style={{ width: `${c.accuracy * 100}%` }} /></div>
          </div>
        )) : <span className="text-zinc-500">Sem Answers.</span>}
      </Panel>
      <Panel title="Consistência das Questions" className="lg:col-span-3">
        {total.length ? (
          <>
            <div className="flex h-3 overflow-hidden rounded">
              {LEVELS.map(([k, label, color]) => {
                const row = total.find((t) => t.level === k)
                return row ? <div key={k} className={color} style={{ width: `${row.share * 100}%` }} title={`${label}: ${row.questions}`} /> : null
              })}
            </div>
            <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-zinc-400">
              {LEVELS.map(([k, label, color]) => <span key={k}><span className={`mr-1 inline-block h-2 w-2 ${color}`} />{label} {total.find((t) => t.level === k)?.questions ?? 0}</span>)}
            </div>
          </>
        ) : <span className="text-zinc-500">Sem dados.</span>}
      </Panel>
      <Panel title="Melhor Attempt por Exam" className="lg:col-span-3">
        {d.best_per_exam.length ? (
          <table className="w-full"><tbody>
            {d.best_per_exam.map((b) => (
              <tr key={b.exam_title} className="border-t border-zinc-800">
                <td className="max-w-[16rem] truncate py-1.5 pr-2">{b.exam_title}</td>
                <td className="w-24"><div className="h-1.5 rounded bg-zinc-800"><div className={`h-1.5 rounded ${b.score >= READY_RATIO ? 'bg-emerald-500' : 'bg-amber-500'}`} style={{ width: `${b.score * 100}%` }} /></div></td>
                <td className="w-12 text-right">{pct(b.score)}</td>
              </tr>
            ))}
          </tbody></table>
        ) : <span className="text-zinc-500">Nenhum Exam finalizado.</span>}
      </Panel>
    </div>
  )
}
