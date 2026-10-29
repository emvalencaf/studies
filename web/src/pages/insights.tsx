import { useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { post, type Insights, type Dashboard as Data } from '../api'
import { Panel, pct } from '../ui'

const READY = 0.8
const CONF = { confident: 'Confiante', educated_guess: 'Educated guess', guess: 'Chute', unmarked: 'Sem marcação' } as Record<string, string>
const LEVEL = { stable: 'Estável', learned: 'Aprendida', unstable: 'Instável', failing: 'Errando', few_data: 'Poucos dados' } as Record<string, string>
const short = (t: string) => t.split(' (')[0]
const dm = (iso: string) => new Date(iso).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })
const secs = (s: number | null | undefined) => (s == null ? '–' : s >= 90 ? `${(s / 60).toFixed(1)} min` : `${Math.round(s)} s`)
const none = (t = 'Sem dados na janela.') => <span className="text-zinc-500">{t}</span>
const tone = (a: number | null) => (a == null ? 'bg-zinc-800' : a >= READY ? 'bg-emerald-500' : a >= 0.6 ? 'bg-amber-500' : 'bg-rose-500')

function Bar({ v, color = 'bg-violet-500' }: { v: number | null; color?: string }) {
  return <div className="h-1.5 rounded bg-zinc-800"><div className={`h-1.5 rounded ${color}`} style={{ width: `${(v ?? 0) * 100}%` }} /></div>
}
function Note({ children }: { children: React.ReactNode }) { return <p className="mt-2 text-xs text-zinc-600">{children}</p> }

// 5. Projeção de nota
export function Projection({ p }: { p: Insights['projection'] }) {
  if (!p) return none('Precisa de 3+ Exams finalizados.')
  const eta = p.predicted >= p.target ? 'já acima da meta' : p.eta_days == null ? 'sem tendência de alta' : `meta em ~${p.eta_days} dias no ritmo atual`
  return (
    <>
      <div className="text-4xl font-bold text-zinc-100">{pct(p.predicted)}</div>
      <div className="text-zinc-500">faixa {pct(p.low)}–{pct(p.high)} · {eta}</div>
      <div className="relative mt-3 h-2 rounded bg-zinc-800" role="img" aria-label="Faixa provável da próxima nota">
        <div className="absolute h-2 rounded bg-violet-500/60" style={{ left: `${p.low * 100}%`, width: `${(p.high - p.low) * 100}%` }} />
        <div className="absolute -top-1 h-4 w-0.5 bg-emerald-400" style={{ left: `${p.target * 100}%` }} title={`Meta ${pct(p.target)}`} />
      </div>
      <Note>Regressão linear nos últimos {p.n} Exams ({p.slope_per_week >= 0 ? '+' : ''}{(p.slope_per_week * 100).toFixed(1)} pp/semana). Faixa de ~90%.</Note>
    </>
  )
}

// 1. Fila de revisão
export function ReviewQueue({ rows, certId }: { rows: Insights['review_queue']; certId?: number }) {
  const nav = useNavigate()
  const go = useMutation({
    mutationFn: (filter: string) => post<{ attempt_id: number }>('/attempts', { kind: 'review', certification_id: certId, filter, n: rows.length }),
    onSuccess: (r) => nav(`/attempts/${r.attempt_id}`),
  })
  return (
    <>
      <div className="mb-3 flex flex-wrap gap-2">
        {([['priority', `Revisar a fila (${rows.length}, por risco)`], ['any_wrong', 'Revisar erradas'], ['lucky_guess', 'Revisar acertos com chute']] as const).map(([f, l]) =>
          <button key={f} disabled={!certId || go.isPending || (f === 'priority' && !rows.length)} onClick={() => go.mutate(f)} className={`rounded border px-3 py-1 text-xs disabled:opacity-40 ${f === 'priority' ? 'border-violet-500 bg-violet-500/20 text-violet-100' : 'border-zinc-600 text-zinc-300'}`}>{l}</button>)}
        {go.error && <span className="text-xs text-rose-400">{(go.error as Error).message}</span>}
      </div>
      {rows.length ? (
        <table className="w-full"><thead><tr className="text-left text-xs text-zinc-500"><th className="font-normal">Question</th><th className="font-normal">Section</th><th className="font-normal">Nível</th><th className="text-right font-normal" title="erros / chutes certos / erros confiantes">E · C · !</th><th className="w-16 text-right font-normal">Risco</th></tr></thead><tbody>
          {rows.map((r) => (
            <tr key={r.question_id} className="border-t border-zinc-800">
              <td className="py-1.5 pr-2 text-zinc-400">{r.question_id}</td>
              <td className="max-w-[14rem] truncate pr-2" title={r.section}>{r.section}</td>
              <td className="pr-2">{LEVEL[r.level] ?? r.level}</td>
              <td className="text-right text-zinc-400">{r.wrong}/{r.answers} · {r.lucky} · {r.confident_wrong}</td>
              <td className="text-right font-bold text-amber-400">{r.score.toFixed(1)}</td>
            </tr>
          ))}
        </tbody></table>
      ) : none('Nada para revisar.')}
      <Note>Risco soma: nível de Consistency (errando e instável pesam mais), taxa de erro, acertos com chute e erros em que estava confiante (“!”). Sobre todo o histórico.</Note>
    </>
  )
}

// 2. Temas fracos por impacto
export function TopicImpact({ nodes, weak }: { nodes: Data['topics']['nodes']; weak: Insights['weak_neighbors'] }) {
  const pts = nodes.filter((n) => n.accuracy != null && n.answers > 0)
  if (!pts.length) return none()
  const W = 560, H = 220, maxS = Math.max(...pts.map((n) => n.primary), 1)
  const x = (a: number) => 36 + (1 - a) * (W - 50), y = (p: number) => H - 24 - (p / maxS) * (H - 40)
  const rank = [...pts].filter((n) => n.impact != null).sort((a, b) => b.impact! - a.impact!).slice(0, 8)
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div>
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Taxa de erro por peso do tema">
          <line x1="36" x2={W - 10} y1={H - 24} y2={H - 24} stroke="#3f3f46" /><line x1="36" x2="36" y1="8" y2={H - 24} stroke="#3f3f46" />
          <text x={W - 10} y={H - 6} fontSize="9" fill="#71717a" textAnchor="end">mais erros →</text>
          <text x="40" y="14" fontSize="9" fill="#71717a">↑ mais Questions (principal)</text>
          {pts.map((n) => <circle key={n.topic} cx={x(n.accuracy!)} cy={y(n.primary)} r={4 + Math.min(n.answers, 40) / 8} fill="#a78bfa" fillOpacity="0.55" stroke="#a78bfa"><title>{short(n.topic)}: acerto {pct(n.accuracy)}, {n.primary} Questions, {n.answers} Answers</title></circle>)}
        </svg>
        <Note>Canto superior direito = tema grande e fraco: onde estudar rende mais. Tamanho = Answers.</Note>
      </div>
      <div>
        <div className="mb-1 text-xs text-zinc-500">Maior impacto (Questions × taxa de erro)</div>
        <table className="w-full"><tbody>
          {rank.map((n) => (
            <tr key={n.topic} className="border-t border-zinc-800 align-top">
              <td className="py-1.5 pr-2"><div className="max-w-[16rem] truncate" title={n.topic}>{short(n.topic)}</div>
                {weak[n.topic] && <div className="text-xs text-zinc-500">vizinhos fracos: {weak[n.topic].slice(0, 3).map(short).join(', ')}{weak[n.topic].length > 3 ? ` +${weak[n.topic].length - 3}` : ''}</div>}</td>
              <td className="w-12 text-right">{pct(n.accuracy)}</td><td className="w-16 text-right text-amber-400">{n.impact!.toFixed(1)}</td>
            </tr>
          ))}
        </tbody></table>
      </div>
    </div>
  )
}

// 3. Calibração por Section e no tempo
export function CalibrationDeep({ ins }: { ins: Insights }) {
  const sections = [...new Set(ins.calibration_by_section.map((r) => r.section))].sort()
  const lv = ['confident', 'educated_guess', 'guess']
  const tr = ins.calibration_trend.filter((t) => t.confident_n > 0)
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Panel title="Calibração por Section">
        {sections.length ? (
          <table className="w-full"><thead><tr className="text-left text-xs text-zinc-500"><th className="font-normal">Section</th>{lv.map((l) => <th key={l} className="text-right font-normal">{CONF[l]}</th>)}</tr></thead><tbody>
            {sections.map((s) => (
              <tr key={s} className="border-t border-zinc-800">
                <td className="max-w-[14rem] truncate py-1.5 pr-2" title={s}>{s}</td>
                {lv.map((l) => { const r = ins.calibration_by_section.find((x) => x.section === s && x.level === l); return <td key={l} className="text-right">{r ? <>{pct(r.accuracy)} <span className="text-xs text-zinc-600">{r.n}</span></> : '–'}</td> })}
              </tr>
            ))}
          </tbody></table>
        ) : none()}
        <Note>Se “Confiante” não for bem maior que “Chute” numa Section, a sua confiança ali não é confiável.</Note>
      </Panel>
      <Panel title="Confiança errada ao longo do tempo">
        {tr.length ? (
          <table className="w-full"><thead><tr className="text-left text-xs text-zinc-500"><th className="font-normal">Período</th><th className="text-right font-normal">Acerto confiante</th><th className="text-right font-normal">Acerto chute</th><th className="text-right font-normal">Erro confiante</th></tr></thead><tbody>
            {tr.map((t) => (
              <tr key={t.bucket} className="border-t border-zinc-800">
                <td className="py-1.5">{dm(t.bucket)}</td><td className="text-right">{pct(t.confident_accuracy)} <span className="text-xs text-zinc-600">{t.confident_n}</span></td>
                <td className="text-right">{pct(t.guess_accuracy)} <span className="text-xs text-zinc-600">{t.guess_n}</span></td>
                <td className={`text-right ${t.overconfident != null && t.overconfident > 0.25 ? 'text-rose-400' : ''}`}>{pct(t.overconfident)}</td>
              </tr>
            ))}
          </tbody></table>
        ) : none('Nenhuma Answer marcada como confiante.')}
        <Note>“Erro confiante” = parte das Answers confiantes que estava errada. É o erro mais perigoso na prova; em vermelho acima de 25%.</Note>
      </Panel>
    </div>
  )
}

// 4 + 6. Tempo × acerto e efeito do modo
export function TimeAndMode({ ins }: { ins: Insights }) {
  const t = ins.time, max = Math.max(...t.bins.map((b) => b.n), 1)
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Panel title="Tempo × acerto">
        {t.bins.some((b) => b.n) ? (
          <>
            {t.bins.map((b) => (
              <div key={b.label} className="mb-2 grid grid-cols-[5rem_1fr_6rem] items-center gap-2">
                <span className="text-zinc-400">{b.label}</span>
                <div className="h-3 rounded bg-zinc-800"><div className={`h-3 rounded ${tone(b.accuracy)}`} style={{ width: `${(b.n / max) * 100}%` }} /></div>
                <span className="text-right">{pct(b.accuracy)} <span className="text-xs text-zinc-600">n={b.n}</span></span>
              </div>
            ))}
            <div className="mt-3 grid grid-cols-3 gap-2 text-center">
              <div><div className="text-xl font-bold">{secs(t.median_correct)}</div><div className="text-xs text-zinc-500">mediana certas</div></div>
              <div><div className="text-xl font-bold">{secs(t.median_wrong)}</div><div className="text-xs text-zinc-500">mediana erradas</div></div>
              <div><div className="text-xl font-bold">{secs(t.median_all)}</div><div className="text-xs text-zinc-500">mediana geral</div></div>
            </div>
            <Note>Largura = quantas Answers na faixa; cor = acerto (verde ≥80%, âmbar ≥60%, vermelho abaixo).</Note>
          </>
        ) : none('Sem tempos registrados.')}
        {t.slow.length > 0 && (
          <>
            <div className="mb-1 mt-3 text-xs text-zinc-500">Questions lentas (mediana &gt; 1,5× a geral)</div>
            <table className="w-full"><tbody>
              {t.slow.map((q) => <tr key={q.question_id} className="border-t border-zinc-800"><td className="py-1.5 pr-2 text-zinc-400">{q.question_id}</td><td className="max-w-[12rem] truncate pr-2" title={q.section}>{q.section}</td><td className="text-right">{secs(q.median_seconds)}</td><td className="w-12 text-right text-zinc-500">{pct(q.accuracy)}</td></tr>)}
            </tbody></table>
          </>
        )}
      </Panel>
      <Panel title="Practice × Exam mode">
        {ins.mode_effect.length ? (
          <table className="w-full"><thead><tr className="text-left text-xs text-zinc-500"><th className="font-normal">Modo</th><th className="text-right font-normal">Answers</th><th className="text-right font-normal">Acerto</th><th className="text-right font-normal">Inéditas</th><th className="text-right font-normal">Tempo</th></tr></thead><tbody>
            {ins.mode_effect.map((m) => (
              <tr key={m.mode} className="border-t border-zinc-800">
                <td className="py-1.5">{m.mode === 'exam' ? 'Exam' : 'Practice'}</td><td className="text-right">{m.n}</td><td className="text-right">{pct(m.accuracy)}</td>
                <td className="text-right">{pct(m.new_accuracy)} <span className="text-xs text-zinc-600">{m.new_n}</span></td><td className="text-right">{secs(m.median_seconds)}</td>
              </tr>
            ))}
          </tbody></table>
        ) : none()}
        <Note>Se o acerto em Practice for bem maior, o gabarito imediato (e as repetições) pode estar inflando a sua percepção. Compare nas inéditas.</Note>
      </Panel>
    </div>
  )
}

// 7 + 8. Retenção e mapa de calor
export function Retention({ rows }: { rows: Insights['retention'] }) {
  if (!rows.some((r) => r.n)) return none('Precisa de Questions respondidas mais de uma vez.')
  return (
    <>
      {rows.map((r) => (
        <div key={r.label} className="mb-3">
          <div className="flex justify-between text-zinc-400"><span>{r.label}</span><span className="text-xs text-zinc-600">{r.n} pares</span></div>
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>Manteve (certa → certa) <b className="text-zinc-100">{pct(r.kept)}</b> <span className="text-zinc-600">n={r.kept_n}</span><Bar v={r.kept} color={tone(r.kept)} /></div>
            <div>Recuperou (errada → certa) <b className="text-zinc-100">{pct(r.recovered)}</b> <span className="text-zinc-600">n={r.recovered_n}</span><Bar v={r.recovered} color={tone(r.recovered)} /></div>
          </div>
        </div>
      ))}
      <Note>Se “Manteve” cai com o intervalo, esse é o prazo em que você começa a esquecer: revise um pouco antes.</Note>
    </>
  )
}

export function Heatmap({ rows }: { rows: Insights['heatmap'] }) {
  if (!rows.length) return none()
  const buckets = [...new Set(rows.map((r) => r.bucket))].sort(), sections = [...new Set(rows.map((r) => r.section))].sort()
  const color = (a: number) => (a >= READY ? 'bg-emerald-500' : a >= 0.6 ? 'bg-amber-500' : 'bg-rose-500')
  return (
    <div className="overflow-x-auto">
      <table className="text-xs"><thead><tr><th />{buckets.map((b) => <th key={b} className="px-1 font-normal text-zinc-500">{dm(b)}</th>)}</tr></thead><tbody>
        {sections.map((s) => (
          <tr key={s}>
            <td className="max-w-[14rem] truncate pr-3 text-zinc-400" title={s}>{s}</td>
            {buckets.map((b) => {
              const r = rows.find((x) => x.section === s && x.bucket === b)
              return <td key={b} className="p-0.5">{r ? <div className={`h-6 w-9 rounded text-center leading-6 text-zinc-950 ${color(r.accuracy)}`} style={{ opacity: 0.4 + Math.min(r.n, 10) / 10 * 0.6 }} title={`${s} · semana de ${dm(b)}: ${pct(r.accuracy)} em ${r.n} Answers`}>{Math.round(r.accuracy * 100)}</div> : <div className="h-6 w-9 rounded bg-zinc-900" />}</td>
            })}
          </tr>
        ))}
      </tbody></table>
      <Note>Células vazias = Section não estudada na semana. Cor = acerto; opacidade = volume de Answers.</Note>
    </div>
  )
}

// 9. Raciocínio
export function Reasoning({ r }: { r: Insights['reasoning'] }) {
  if (!r) return none()
  return (
    <>
      <div className="grid grid-cols-2 gap-4">
        <div><div className="text-2xl font-bold">{pct(r.with_accuracy)}</div><div className="text-zinc-500">com raciocínio escrito <span className="text-xs text-zinc-600">n={r.with_n}</span></div></div>
        <div><div className="text-2xl font-bold">{pct(r.without_accuracy)}</div><div className="text-zinc-500">sem raciocínio <span className="text-xs text-zinc-600">n={r.without_n}</span></div></div>
      </div>
      <div className="mb-1 mt-3 text-xs text-zinc-500">Erros recentes em que você escreveu o raciocínio</div>
      {r.wrong_with_reasoning.length ? r.wrong_with_reasoning.map((w) => (
        <div key={w.question_id + w.reasoning} className="border-t border-zinc-800 py-2">
          <div className="text-xs text-zinc-500">Question {w.question_id} · {w.section}{w.confidence ? ` · ${CONF[w.confidence]}` : ''}</div>
          <div className="text-zinc-300">{w.reasoning}</div>
        </div>
      )) : none('Nenhum.')}
      <Note>Raciocínio que parecia sólido e mesmo assim errou costuma indicar uma armadilha da Question: vale reler a explicação.</Note>
    </>
  )
}
