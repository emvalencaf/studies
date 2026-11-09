import { useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { api, type DashParams, type Dashboard as Data, type Grouped } from '../api'
import { usePalette } from '../palette'
import { ErrorBox, Panel, pct, Skeleton } from '../ui'
import StudyPulse from './StudyPulse'
import { BadgesStrip, EvolutionKPIs, LevelBar } from './Evolution'
import { CalibrationDeep, Heatmap, Reasoning, Retention, ReviewQueue, TopicImpact } from './insights'

const READY_RATIO = 0.8 // espelha metrics.READY_RATIO; a API entrega só quantos Exams seguidos estão na meta
const LEVELS: [string, string, string][] = [
  ['stable', 'Estável', 'bg-violet-500'], ['learned', 'Aprendida', 'bg-orange-500'], ['unstable', 'Instável', 'bg-emerald-500'],
  ['failing', 'Errando', 'bg-amber-500'], ['few_data', 'Poucos dados', 'bg-zinc-300 dark:bg-zinc-600'],
]
const CONF = { confident: 'Confiante', educated_guess: 'Educated guess', guess: 'Chute', unmarked: 'Sem marcação' } as Record<string, string>

function ScoreLine({ scores }: { scores: Data['scores'] }) {
  const pal = usePalette()
  const pts = scores.filter((s) => s.score != null)
  if (pts.length < 2) return <div className="text-zinc-500">São necessários pelo menos 2 Exams finalizados.</div>
  const W = 300, H = 90, y = (v: number) => H - 10 - v * (H - 20)
  const xy = pts.map((s, i) => [10 + (i * (W - 20)) / (pts.length - 1), y(s.score!)] as const)
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Nota por Exam ao longo do tempo">
      <line x1="0" x2={W} y1={y(READY_RATIO)} y2={y(READY_RATIO)} stroke={pal.muted} strokeDasharray="3 3" />
      <polyline fill="none" stroke={pal.s1} strokeWidth="2" points={xy.map((p) => p.join(',')).join(' ')} />
      {xy.map(([x, yy], i) => <circle key={i} cx={x} cy={yy} r="3" fill={pal.s1}><title>{pts[i].exam_title}: {pct(pts[i].score)}</title></circle>)}
    </svg>
  )
}


const KINDS: [string, string][] = [['exam', 'Exam'], ['review', 'Review'], ['drill', 'Drill']]
const WINDOWS: [DashParams['window'], string][] = [['7d', '7 dias'], ['30d', '30 dias'], ['all', 'Tudo']]
const TABS = ['Prioridades', 'Progressão', 'Calibração', 'Ritmo', 'Consistência', 'Evolução', 'Temas'] as const
const GRANS: [keyof Data['by'], string][] = [['section', 'Section'], ['course', 'Course'], ['exam', 'Exam'], ['topic', 'Tema'], ['question', 'Question']]
const short = (t: string) => t.split(' (')[0]
const day = (iso: string) => new Date(iso).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })

function Chip({ on, onClick, children }: { on: boolean; onClick: () => void; children: React.ReactNode }) {
  return <button onClick={onClick} aria-pressed={on} className={`rounded-full border px-3 py-1 text-xs ${on ? 'border-violet-500 bg-violet-500/20 text-violet-700 dark:text-violet-200' : 'border-zinc-300 text-zinc-500 dark:border-zinc-700 dark:text-zinc-400'}`}>{children}</button>
}

function Stat({ label, value, hint }: { label: string; value: React.ReactNode; hint?: React.ReactNode }) {
  return <div><div className="text-2xl font-bold text-zinc-800 dark:text-zinc-100">{value}</div><div className="text-zinc-500">{label}</div>{hint && <div className="text-xs text-zinc-600">{hint}</div>}</div>
}

function Bar({ value, color = 'bg-violet-500' }: { value: number | null; color?: string }) {
  return <div className="h-1.5 rounded bg-zinc-200 dark:bg-zinc-800"><div className={`h-1.5 rounded ${color}`} style={{ width: `${(value ?? 0) * 100}%` }} /></div>
}

function AccTable({ rows, label }: { rows: Grouped[]; label: string }) {
  if (!rows.length) return <span className="text-zinc-500">Sem Answers na janela.</span>
  return (
    <table className="w-full"><thead><tr className="text-left text-xs text-zinc-500"><th className="font-normal">{label}</th><th /><th className="text-right font-normal">Acerto</th><th className="w-14 text-right font-normal">n</th></tr></thead><tbody>
      {rows.map((r) => (
        <tr key={r.group} className="border-t border-zinc-200 dark:border-zinc-800">
          <td className="max-w-[20rem] truncate max-lg:max-w-none max-lg:whitespace-normal max-lg:break-words py-1.5 pr-2" title={String(r.group)}>{short(String(r.group))}</td>
          <td className="w-24"><Bar value={r.accuracy} color={r.accuracy >= READY_RATIO ? 'bg-emerald-500' : 'bg-amber-500'} /></td>
          <td className="w-12 text-right">{pct(r.accuracy)}</td><td className="text-right text-zinc-500">{r.n}</td>
        </tr>
      ))}
    </tbody></table>
  )
}

function Progression({ rows }: { rows: Data['progression'] }) {
  const pal = usePalette()
  const pts = rows.filter((r) => r.rolling != null)
  if (!pts.length) return <span className="text-zinc-500">Sem Answers na janela.</span>
  const times = pts.map((r) => +new Date(r.bucket)), t0 = Math.min(...times), t1 = Math.max(...times)
  const W = 600, H = 180, x = (t: number) => 30 + (t1 === t0 ? 0.5 : (t - t0) / (t1 - t0)) * (W - 40), y = (v: number) => H - 20 - v * (H - 35)
  // Ordem fixa: a cor segue a entidade (o segmento), não a posição dos pontos no gráfico.
  const series: [Data['progression'][number]['segment'], string][] = [['Inéditas', pal.s1], ['Repetições', pal.s2]]
  return (
    <>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Acerto ao longo do tempo, inéditas e repetições">
        {[0, 0.5, 1].map((v) => <g key={v}><line x1="30" x2={W - 10} y1={y(v)} y2={y(v)} stroke={pal.grid} /><text x="0" y={y(v) + 3} fontSize="9" fill={pal.muted}>{v * 100}%</text></g>)}
        {series.map(([seg, color]) => {
          const g = pts.filter((r) => r.segment === seg)
          return g.length ? (
            <g key={seg}>
              <polyline fill="none" stroke={color} strokeWidth="2" points={g.map((r) => `${x(+new Date(r.bucket))},${y(r.rolling!)}`).join(' ')} />
              {g.map((r) => <circle key={r.bucket} cx={x(+new Date(r.bucket))} cy={y(r.rolling!)} r="3.5" fill={color}><title>{seg} · {day(r.bucket)}: {pct(r.rolling)} (móvel), bucket {pct(r.accuracy)} em {r.n} Answers</title></circle>)}
            </g>
          ) : null
        })}
        <text x="30" y={H - 4} fontSize="9" fill={pal.muted}>{day(new Date(t0).toISOString())}</text>
        <text x={W - 10} y={H - 4} fontSize="9" fill={pal.muted} textAnchor="end">{day(new Date(t1).toISOString())}</text>
      </svg>
      <div className="mt-1 flex gap-4 text-xs text-zinc-500 dark:text-zinc-400">{series.map(([s, c]) => <span key={s}><span className="mr-1 inline-block h-2 w-2 rounded-full" style={{ background: c }} />{s}</span>)}</div>
      <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-600">Média móvel ponderada pelo número de Answers. Inéditas medem conhecimento; repetições podem refletir memória.</p>
    </>
  )
}

function PaceChart({ days }: { days: Data['pace']['days'] }) {
  if (!days.length) return <span className="text-zinc-500">Sem Answers na janela.</span>
  const max = Math.max(...days.map((d) => d.questions), 1)
  return (
    <div className="flex h-32 items-end gap-px" role="img" aria-label="Questions por dia">
      {days.map((d) => <div key={d.day} className="min-w-[2px] flex-1 rounded-t bg-violet-500" style={{ height: `${(d.questions / max) * 100}%` }} title={`${day(d.day)}: ${d.questions} Questions`} />)}
    </div>
  )
}

function ConsistencyBySection({ rows }: { rows: Data['consistency_by_section'] }) {
  const groups = [...new Set(rows.map((r) => r.group))].sort()
  if (!groups.length) return <span className="text-zinc-500">Sem dados.</span>
  return (
    <div className="space-y-2">
      {groups.map((g) => (
        <div key={g}>
          <div className="truncate text-zinc-500 dark:text-zinc-400" title={g}>{g}</div>
          <div className="flex h-3 overflow-hidden rounded">
            {LEVELS.map(([k, label, color]) => {
              const row = rows.find((r) => r.group === g && r.level === k)
              return row ? <div key={k} className={color} style={{ width: `${row.share * 100}%` }} title={`${label}: ${row.questions}`} /> : null
            })}
          </div>
        </div>
      ))}
      <div className="flex flex-wrap gap-x-4 gap-y-1 pt-1 text-xs text-zinc-500 dark:text-zinc-400">{LEVELS.map(([k, label, color]) => <span key={k}><span className={`mr-1 inline-block h-2 w-2 ${color}`} />{label}</span>)}</div>
    </div>
  )
}

function Topics({ t }: { t: Data['topics'] }) {
  if (!t.nodes.length) return <span className="text-zinc-500">Sem temas. Rode <code>uv run python -m studies.load</code> para calculá-los.</span>
  return (
    <div>
      <div className="mb-1 text-xs text-zinc-500">Tema = assunto da documentação AWS citada na explicação.</div>
      <table className="w-full"><thead><tr className="text-left text-xs text-zinc-500"><th className="font-normal">Tema</th><th className="text-right font-normal">Princ.</th><th className="text-right font-normal">Citam</th><th className="text-right font-normal">Acerto</th></tr></thead><tbody>
        {t.nodes.map((n) => (
          <tr key={n.topic} className="border-t border-zinc-200 dark:border-zinc-800">
            <td className="max-w-[14rem] truncate max-lg:max-w-none max-lg:whitespace-normal max-lg:break-words py-1.5 pr-2" title={n.topic}>{short(n.topic)}</td>
            <td className="text-right">{n.primary}</td><td className="text-right">{n.total}</td><td className="text-right">{pct(n.accuracy)}</td>
          </tr>
        ))}
      </tbody></table>
    </div>
  )
}

export default function Dashboard() {
  const [p, setP] = useState<DashParams>({ window: 'all', kinds: ['exam', 'review', 'drill'], freq: 'D', roll: 3, stable_after: 3 })
  const [tab, setTab] = useState<(typeof TABS)[number]>('Prioridades')
  const [gran, setGran] = useState<keyof Data['by']>('section')
  const { data: d, error, refetch } = useQuery({
    queryKey: ['dashboard', p],
    placeholderData: keepPreviousData,
    queryFn: async () => {
      const certs = await api<{ id: number }[]>('/certifications')
      if (!certs.length) throw new Error('Banco vazio.')
      const q = new URLSearchParams({ window: p.window, freq: p.freq, roll: String(p.roll), stable_after: String(p.stable_after) })
      p.kinds.forEach((k) => q.append('kinds', k))
      return { ...(await api<Data>(`/dashboard/${certs[0].id}?${q}`)), cert_id: certs[0].id }
    },
  })
  const toggleKind = (k: string) => setP((o) => ({ ...o, kinds: o.kinds.includes(k) ? o.kinds.filter((x) => x !== k) : [...o.kinds, k] }))
  if (error) return <ErrorBox error={error} retry={() => refetch()} />
  if (!d) return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-4 p-4 lg:grid-cols-6 lg:p-6" aria-busy="true">
      <Skeleton className="h-32 lg:col-span-2" /><Skeleton className="h-32 lg:col-span-2" /><Skeleton className="h-32 lg:col-span-2" />
      <Skeleton className="h-40 lg:col-span-3" /><Skeleton className="h-40 lg:col-span-3" />
    </div>
  )
  const total = d.consistency
  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-4 p-4 lg:grid-cols-6 lg:p-6">
      <div className="flex flex-wrap items-center gap-2 lg:col-span-6">
        {WINDOWS.map(([k, l]) => <Chip key={k} on={p.window === k} onClick={() => setP((o) => ({ ...o, window: k }))}>{l}</Chip>)}
        <span className="mx-1 text-zinc-300 dark:text-zinc-700">|</span>
        {KINDS.map(([k, l]) => <Chip key={k} on={p.kinds.includes(k)} onClick={() => toggleKind(k)}>{l}</Chip>)}
        <span className="mx-1 text-zinc-300 dark:text-zinc-700">|</span>
        <Chip on={p.freq === 'D'} onClick={() => setP((o) => ({ ...o, freq: 'D' }))}>Dia</Chip>
        <Chip on={p.freq === 'W'} onClick={() => setP((o) => ({ ...o, freq: 'W' }))}>Semana</Chip>
        <label className="ml-1 flex items-center gap-2 text-xs text-zinc-500 dark:text-zinc-400">Média móvel {p.roll}
          <input type="range" min={1} max={14} value={p.roll} onChange={(e) => setP((o) => ({ ...o, roll: +e.target.value }))} />
        </label>
        {d.window && <span className="ml-auto text-xs text-zinc-500">{new Date(d.window.start).toLocaleDateString('pt-BR')} a {new Date(d.window.end).toLocaleDateString('pt-BR')}</span>}
      </div>
      <Panel title="Ritmo de estudo" className="lg:col-span-6"><StudyPulse a={d.activity} /></Panel>
      <div className="lg:col-span-6"><EvolutionKPIs d={d} /></div>
      <div className="lg:col-span-6"><LevelBar answers={d.answers} /></div>
      <div className="lg:col-span-6"><BadgesStrip d={d} /></div>
      <Panel title="Nota por Exam (linha tracejada = 80%)" className="lg:col-span-6"><ScoreLine scores={d.scores} /></Panel>
      <Panel title="Janela" className="lg:col-span-6">
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <Stat label="Answers" value={d.answers} />
          <Stat label="Acerto em inéditas" value={pct(d.accuracy_new)} hint="mede conhecimento" />
          <Stat label="Acerto em repetições" value={pct(d.accuracy_repeat)} hint="pode estar inflado por memória" />
          <Stat label="Consistência estável" value={`${total.find((t) => t.level === 'stable')?.questions ?? 0}/${total.reduce((n, t) => n + t.questions, 0)}`} hint="Questions" />
        </div>
      </Panel>
      <div className="lg:col-span-6">
        <div role="tablist" className="mb-3 flex flex-wrap gap-1 border-b border-zinc-200 dark:border-zinc-800">
          {TABS.map((t) => <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)} className={`px-3 py-2 text-sm ${tab === t ? 'border-b-2 border-violet-500 text-zinc-800 dark:text-zinc-100' : 'text-zinc-500'}`}>{t}</button>)}
        </div>
        {tab === 'Prioridades' && (
          <div className="grid grid-cols-[minmax(0,1fr)] gap-4">
            <Panel title="Fila de revisão"><ReviewQueue rows={d.insights.review_queue} certId={d.cert_id} /></Panel>
            <Panel title="Temas fracos por impacto"><TopicImpact nodes={d.topics.nodes} weak={d.insights.weak_neighbors} /></Panel>
          </div>
        )}
        {tab === 'Progressão' && (
          <div className="grid grid-cols-[minmax(0,1fr)] gap-4 lg:grid-cols-2">
            <Panel title="Acerto ao longo do tempo"><Progression rows={d.progression} /></Panel>
            <Panel title="Acerto por">
              <div className="mb-2 flex flex-wrap gap-1">{GRANS.map(([k, l]) => <Chip key={k} on={gran === k} onClick={() => setGran(k)}>{l}</Chip>)}</div>
              <AccTable rows={d.by[gran] ?? []} label={GRANS.find(([k]) => k === gran)![1]} />
              {gran === 'question' && <p className="mt-2 text-xs text-zinc-600">Só Questions com 2+ Answers; top 30.</p>}
            </Panel>
            <Panel title="Melhor Attempt por Exam">
              {d.best_per_exam.length ? (
                <table className="w-full"><tbody>
                  {d.best_per_exam.map((b) => (
                    <tr key={b.exam_title} className="border-t border-zinc-200 dark:border-zinc-800">
                      <td className="max-w-[16rem] truncate max-lg:max-w-none max-lg:whitespace-normal max-lg:break-words py-1.5 pr-2">{b.exam_title}</td>
                      <td className="w-24 max-lg:w-14"><div className="h-1.5 rounded bg-zinc-200 dark:bg-zinc-800"><div className={`h-1.5 rounded ${b.score >= READY_RATIO ? 'bg-emerald-500' : 'bg-amber-500'}`} style={{ width: `${b.score * 100}%` }} /></div></td>
                      <td className="w-12 text-right">{pct(b.score)}</td>
                    </tr>
                  ))}
                </tbody></table>
              ) : <span className="text-zinc-500">Nenhum Exam finalizado.</span>}
            </Panel>
            <Panel title="Melhor janela">
              {d.best_window ? <Stat label={`Melhor ${p.freq === 'D' ? 'dia' : 'semana'} (≥10 Answers)`} value={pct(d.best_window.accuracy)} hint={`${new Date(d.best_window.bucket).toLocaleDateString('pt-BR')} · ${d.best_window.n} Answers`} />
                : <span className="text-zinc-500">Nenhum {p.freq === 'D' ? 'dia' : 'semana'} com 10 ou mais Answers ainda.</span>}
            </Panel>
          </div>
        )}
        {tab === 'Calibração' && (
          <Panel title="Acerto por confiança">
            {d.calibration.length ? d.calibration.map((c) => (
              <div key={c.level} className="mb-2"><div className="flex justify-between"><span>{CONF[c.level] ?? c.level}</span><b>{pct(c.accuracy)} <span className="font-normal text-zinc-500">n={c.n}</span></b></div><Bar value={c.accuracy} color={c.in_calibration ? 'bg-violet-500' : 'bg-zinc-500'} /></div>
            )) : <span className="text-zinc-500">Sem Answers na janela.</span>}
            <p className="mt-2 text-xs text-zinc-600">Bem calibrado = acerta mais quando confiante do que quando chuta. “Sem marcação” fica fora da calibração. {d.lucky_guesses.length} Questions você só acertou de chute — ainda não é conhecimento sólido.</p>
          </Panel>
        )}
        {tab === 'Calibração' && <div className="mt-4 space-y-4"><CalibrationDeep ins={d.insights} /><Panel title="Raciocínio escrito"><Reasoning r={d.insights.reasoning} /></Panel></div>}
        {tab === 'Ritmo' && (
          <Panel title="Questions por dia">
            <PaceChart days={d.pace.days} />
            <div className="mt-4 grid grid-cols-3 gap-4">
              <Stat label="Questions por dia ativo" value={(() => { const a = d.pace.days.filter((x) => x.questions > 0); return a.length ? Math.round(a.reduce((n, x) => n + x.questions, 0) / a.length) : '–' })()} />
              <Stat label="Tempo mediano" value={d.pace.median_seconds == null ? '–' : `${Math.round(d.pace.median_seconds)} s`} />
              <Stat label="Tempo médio" value={d.pace.mean_seconds == null ? '–' : `${Math.round(d.pace.mean_seconds)} s`} hint="sensível a pausas longas" />
            </div>
          </Panel>
        )}
        {tab === 'Evolução' && (
          <div className="grid grid-cols-[minmax(0,1fr)] gap-4">
            <Panel title="Retenção por intervalo (todo o histórico)"><Retention rows={d.insights.retention} /></Panel>
            <Panel title="Section × semana"><Heatmap rows={d.insights.heatmap} /></Panel>
          </div>
        )}
        {tab === 'Consistência' && (
          <Panel title="Consistência por Section">
            <label className="mb-3 flex items-center gap-2 text-xs text-zinc-500 dark:text-zinc-400">Acertos seguidos para considerar estável: {p.stable_after}
              <input type="range" min={2} max={6} value={p.stable_after} onChange={(e) => setP((o) => ({ ...o, stable_after: +e.target.value }))} />
            </label>
            <ConsistencyBySection rows={d.consistency_by_section} />
            <p className="mt-2 text-xs text-zinc-600">Sobre todo o histórico, independente da janela. Estável: {p.stable_after} acertos seguidos sem erro antes · Aprendida: errou antes e agora acerta {p.stable_after} seguidas · Instável: alterna · Errando: {p.stable_after} erros seguidos · Poucos dados: menos de {p.stable_after} Answers.</p>
          </Panel>
        )}
        {tab === 'Temas' && <Panel title="Temas"><Topics t={d.topics} /></Panel>}
      </div>
    </div>
  )
}
