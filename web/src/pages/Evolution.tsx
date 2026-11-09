import type { Dashboard as Data } from '../api'
import { pct } from '../ui'
import { Delta } from './StudyPulse'

const READY_RATIO = 0.8

function Kpi({ icon, tone, label, value, hint }: { icon: string; tone: string; label: string; value: React.ReactNode; hint?: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-950/60 p-3">
      <div className="mb-1 flex items-center gap-2 text-[11px] uppercase tracking-wider text-zinc-500"><i className={`fa-solid ${icon} ${tone}`} />{label}</div>
      <div className="text-2xl font-bold text-zinc-800 dark:text-zinc-100">{value}</div>
      {hint && <div className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">{hint}</div>}
    </div>
  )
}

export function EvolutionKPIs({ d }: { d: Data }) {
  const r = d.readiness, st = d.streaks, p = d.insights.projection
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <Kpi icon="fa-flag-checkered" tone={r.ready ? 'text-emerald-600 dark:text-emerald-400' : 'text-amber-600 dark:text-amber-400'} label="Prontidão"
        value={r.ready ? 'PRONTO' : 'AINDA NÃO'}
        hint={r.attempts < r.needed ? `${r.attempts}/${r.needed} Exams necessários` : `${r.streak}/${r.needed} Exams ≥ ${pct(READY_RATIO)}`} />
      <Kpi icon="fa-bullseye" tone="text-violet-500" label="Acerto"
        value={pct(d.trend.current)}
        hint={d.trend.delta == null ? 'sem janela anterior' : <Delta now={d.trend.current ?? 0} before={(d.trend.current ?? 0) - d.trend.delta} fmt={(n) => `${Math.round(n * 100)}pp`} />} />
      <Kpi icon="fa-chart-line" tone="text-sky-600 dark:text-sky-400" label="Nota projetada"
        value={p ? pct(p.predicted) : '–'}
        hint={p ? `faixa ${pct(p.low)}–${pct(p.high)}` : 'precisa de 3+ Exams'} />
      <Kpi icon={st.current_kind === 'wrong' ? 'fa-fire-flame-curved' : 'fa-bolt'} tone={st.current_kind === 'wrong' ? 'text-rose-600 dark:text-rose-400' : 'text-orange-600 dark:text-orange-400'} label="Sequência atual"
        value={`${st.current} ${st.current_kind === 'correct' ? '✓' : st.current_kind === 'wrong' ? '✗' : ''}`}
        hint={`recorde ✓ ${st.longest_correct} · recorde ✗ ${st.longest_wrong}`} />
    </div>
  )
}

const PER_LEVEL = 50

export function LevelBar({ answers }: { answers: number }) {
  const level = Math.floor(answers / PER_LEVEL) + 1
  const into = answers % PER_LEVEL
  return (
    <div className="rounded-lg border border-zinc-200 bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-950/60 p-3">
      <div className="flex items-center justify-between text-sm">
        <span className="font-semibold text-zinc-800 dark:text-zinc-100"><i className="fa-solid fa-star mr-1 text-amber-500" />Nível {level}</span>
        <span className="text-xs text-zinc-500">{into}/{PER_LEVEL} para o nível {level + 1}</span>
      </div>
      <div className="mt-2 h-2 rounded bg-zinc-200 dark:bg-zinc-800"><div className="h-2 rounded bg-amber-500" style={{ width: `${(into / PER_LEVEL) * 100}%` }} /></div>
    </div>
  )
}

type Badge = { icon: string; label: string; done: boolean }

function badges(d: Data): Badge[] {
  const conf = d.calibration.find((c) => c.level === 'confident')
  const guess = d.calibration.find((c) => c.level === 'guess')
  const calibrated = conf && guess && conf.n >= 5 && guess.n >= 5 && conf.accuracy - guess.accuracy >= 0.3
  const mastered = (d.by.section ?? []).find((s) => s.n >= 20 && s.accuracy >= 0.85)
  return [
    { icon: 'fa-shoe-prints', label: '100 questões', done: d.answers >= 100 },
    { icon: 'fa-person-running', label: '250 questões', done: d.answers >= 250 },
    { icon: 'fa-medal', label: 'Exam ≥ 80%', done: d.best_per_exam.some((b) => b.score >= READY_RATIO) },
    { icon: 'fa-crown', label: mastered ? `Domina ${mastered.group.split(' (')[0].split(',')[0]}` : 'Domínio dominado', done: !!mastered },
    { icon: 'fa-scale-balanced', label: 'Bem calibrado', done: !!calibrated },
    { icon: 'fa-flag-checkered', label: 'Pronto pra prova', done: d.readiness.ready },
  ]
}

export function BadgesStrip({ d }: { d: Data }) {
  return (
    <div className="flex gap-2 overflow-x-auto pb-1">
      {badges(d).map((b) => (
        <div key={b.label} title={b.label}
          className={`flex shrink-0 items-center gap-2 rounded-full border px-3 py-1.5 text-xs whitespace-nowrap ${b.done
            ? 'border-violet-500 bg-violet-500/15 text-violet-700 dark:text-violet-200'
            : 'border-zinc-300 text-zinc-400 dark:border-zinc-700 dark:text-zinc-600'}`}>
          <i className={`fa-solid ${b.icon}`} />{b.label}
        </div>
      ))}
    </div>
  )
}
