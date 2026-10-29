import type { ReactNode } from 'react'
import type { Activity } from '../api'

export function duration(sec: number) {
  const m = Math.round(sec / 60)
  if (sec < 60) return `${Math.round(sec)}s`
  return m < 60 ? `${m} min` : `${Math.floor(m / 60)}h${String(m % 60).padStart(2, '0')}`
}
const dm = (iso: string) => new Date(iso).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })
const weekday = (iso: string) => new Date(iso).toLocaleDateString('pt-BR', { weekday: 'long' })
// "terça passada", mas "sábado passado" (dias de fim de semana são masculinos)
const lastWeek = (iso: string) => { const w = weekday(iso).split('-')[0]; return `${w} ${w === 'sábado' || w === 'domingo' ? 'passado' : 'passada'}` }

// Seta e cor da variação. Sem base de comparação (0) mostra a diferença absoluta.
function Delta({ now, before, fmt = String }: { now: number; before: number; fmt?: (n: number) => string }) {
  const diff = now - before
  const tone = diff > 0 ? 'text-emerald-400' : diff < 0 ? 'text-rose-400' : 'text-zinc-400'
  const rel = before > 0 ? ` (${diff > 0 ? '+' : ''}${Math.round((diff / before) * 100)}%)` : ''
  return (
    <span className={`inline-flex items-center gap-1 font-semibold ${tone}`}>
      <i className={`fa-solid ${diff > 0 ? 'fa-arrow-trend-up' : diff < 0 ? 'fa-arrow-trend-down' : 'fa-equals'}`} />
      {diff > 0 ? '+' : diff < 0 ? '−' : ''}{fmt(Math.abs(diff))}{rel}
    </span>
  )
}

function Card({ icon, tone, label, children }: { icon: string; tone: string; label: string; children: ReactNode }) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-3">
      <div className="mb-1 flex items-center gap-2 text-[11px] uppercase tracking-wider text-zinc-500"><i className={`fa-solid ${icon} ${tone}`} />{label}</div>
      {children}
    </div>
  )
}

function Duel({ now, before, label }: { now: number; before: number; label: string }) {
  const max = Math.max(now, before, 1)
  return (
    <div className="mt-2 space-y-1" aria-hidden>
      <div className="h-1.5 rounded bg-zinc-800"><div className="h-1.5 rounded bg-violet-400" style={{ width: `${(now / max) * 100}%` }} /></div>
      <div className="h-1.5 rounded bg-zinc-800"><div className="h-1.5 rounded bg-zinc-500" style={{ width: `${(before / max) * 100}%` }} /></div>
      <div className="text-[10px] text-zinc-600"><span className="text-violet-400">▬</span> hoje · <span className="text-zinc-500">▬</span> {label}</div>
    </div>
  )
}

function DaysChart({ a }: { a: Activity }) {
  const max = Math.max(...a.days.map((d) => d.questions), a.avg_per_day ?? 0, 1)
  const lw = a.last_week?.day.slice(0, 10)
  const last = a.days.length - 1
  return (
    <div className="relative mt-3">
      <div className="flex h-24 items-end gap-1" role="img" aria-label="Questions por dia nos últimos 14 dias">
        {a.days.map((d, i) => (
          <div key={d.day} className="flex h-full flex-1 flex-col justify-end" title={`${weekday(d.day)} ${dm(d.day)}: ${d.questions} Questions · ${duration(d.seconds)}`}>
            <div className={`rounded-t ${i === last ? 'bg-violet-400' : d.questions ? 'bg-violet-700/70' : 'bg-zinc-800'} ${d.day.slice(0, 10) === lw ? 'ring-1 ring-amber-400' : ''}`}
              style={{ height: `${Math.max((d.questions / max) * 100, d.questions ? 4 : 2)}%` }} />
          </div>
        ))}
      </div>
      {a.avg_per_day != null && <div className="pointer-events-none absolute inset-x-0 border-t border-dashed border-zinc-500/70" style={{ bottom: `${(a.avg_per_day / max) * 96}px` }}><span className="absolute -top-4 left-0 bg-zinc-900 pr-1 text-[10px] text-zinc-400">média {a.avg_per_day.toFixed(1)}</span></div>}
      <div className="mt-1 flex justify-between text-[10px] text-zinc-600"><span>{dm(a.days[0].day)}</span><span>hoje</span></div>
    </div>
  )
}

export default function StudyPulse({ a }: { a: Activity }) {
  const lw = a.last_week
  const s = a.streak
  const wk = a.week
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <Card icon="fa-pen-to-square" tone="text-violet-400" label="Hoje">
        <div className="text-3xl font-bold text-zinc-100">{a.today.questions}<span className="ml-1 text-sm font-normal text-zinc-500">questões</span></div>
        {lw ? (
          <>
            <div className="text-xs"><Delta now={a.today.questions} before={lw.questions} /></div>
            <div className="text-[11px] text-zinc-500">{lastWeek(lw.day)} ({dm(lw.day)}): {lw.questions}</div>
            <Duel now={a.today.questions} before={lw.questions} label={lastWeek(lw.day)} />
          </>
        ) : <div className="mt-1 text-[11px] text-zinc-500">Sem dia equivalente na semana passada.</div>}
      </Card>
      <Card icon="fa-hourglass-half" tone="text-sky-400" label="Tempo hoje">
        <div className="text-3xl font-bold text-zinc-100">{duration(a.today.seconds)}</div>
        {lw ? (
          <>
            <div className="text-xs"><Delta now={a.today.seconds} before={lw.seconds} fmt={duration} /></div>
            <div className="text-[11px] text-zinc-500">{lastWeek(lw.day)}: {duration(lw.seconds)}</div>
            <Duel now={a.today.seconds} before={lw.seconds} label={lastWeek(lw.day)} />
          </>
        ) : <div className="mt-1 text-[11px] text-zinc-500">Soma do tempo das questões respondidas.</div>}
      </Card>
      <Card icon="fa-fire" tone={s.current ? 'text-orange-400' : 'text-zinc-600'} label="Dias seguidos">
        <div className={`text-3xl font-bold ${s.current ? 'text-orange-400' : 'text-zinc-500'}`}>{s.current}<span className="ml-1 text-sm font-normal text-zinc-500">{s.current === 1 ? 'dia' : 'dias'}</span></div>
        <div className="text-xs text-zinc-400">{s.today_done ? 'hoje já conta' : s.current ? 'estude hoje para manter' : 'comece hoje'}</div>
        <div className="text-[11px] text-zinc-500">recorde: {s.longest} · {a.active_days} dias ativos</div>
        <div className="mt-2 flex gap-0.5" aria-hidden>{Array.from({ length: Math.min(Math.max(s.longest, 7), 14) }, (_, i) => <div key={i} className={`h-2 flex-1 rounded-sm ${i < s.current ? 'bg-orange-400' : 'bg-zinc-800'}`} />)}</div>
      </Card>
      <Card icon="fa-gauge-high" tone="text-emerald-400" label="Média por dia">
        <div className="text-3xl font-bold text-zinc-100">{a.avg_per_day == null ? '–' : a.avg_per_day.toFixed(1)}<span className="ml-1 text-sm font-normal text-zinc-500">q/dia</span></div>
        {a.avg_per_active_day != null && <div className="text-[11px] text-zinc-500">{a.avg_per_active_day.toFixed(1)} nos dias em que estuda</div>}
        <div className="mt-1 text-xs text-zinc-400">7 dias: <b className="text-zinc-200">{wk.current}</b>
          {wk.previous != null && <> · <Delta now={wk.current} before={wk.previous} /></>}</div>
        {wk.previous != null && <div className="text-[11px] text-zinc-500">semana anterior: {wk.previous}</div>}
      </Card>
      <div className="col-span-2 rounded-lg border border-zinc-800 bg-zinc-950/60 p-3 lg:col-span-4">
        <div className="flex items-center justify-between text-[11px] uppercase tracking-wider text-zinc-500">
          <span>Últimos 14 dias</span>
          <span className="normal-case tracking-normal text-zinc-600">{lw && <><span className="mr-1 inline-block h-2 w-2 rounded-sm ring-1 ring-amber-400" />{lastWeek(lw.day)}</>}</span>
        </div>
        <DaysChart a={a} />
      </div>
    </div>
  )
}
