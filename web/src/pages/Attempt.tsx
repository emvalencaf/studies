import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import DOMPurify from 'dompurify'
import { useEffect, useRef, useState } from 'react'
import { joinReasoning, splitReasoning } from '../reasoning'
import { useNavigate, useParams } from 'react-router-dom'
import { api, post, type AttemptInfo, type Question, type Score } from '../api'
import { ErrorBox, pct, Skeleton } from '../ui'

const CONF = { confident: 'Confiante', educated_guess: 'Educated guess', guess: 'Chute' } as Record<string, string>
const html = (s: string) => ({ __html: DOMPurify.sanitize(s) })

// Escolha guardada por modo. Sem escolha: visível no Practice, escondido no Exam em andamento (como na prova real).
function useShowScore(mode: 'practice' | 'exam', open: boolean): [boolean, () => void] {
  const key = `studies_show_score_${mode}`
  const fallback = !(mode === 'exam' && open)
  const [show, setShow] = useState<boolean>(() => {
    try { const v = localStorage.getItem(key); return v === null ? fallback : v === '1' } catch { return fallback }
  })
  const toggle = () => setShow((v) => {
    try { localStorage.setItem(key, v ? '0' : '1') } catch { /* sem armazenamento */ }
    return !v
  })
  return [show, toggle]
}

function verdict(s: Score) {
  const p = s.pass
  if (!p) return null
  if (p.passed) return { tone: 'text-emerald-400', text: `Matematicamente aprovado: ${s.correct} certas, a meta era ${p.needed}.` }
  if (p.failed) return { tone: 'text-rose-400', text: `Matematicamente reprovado: nem acertando todas as restantes chega a ${p.needed}.` }
  return { tone: 'text-sky-400', text: `Faltam ${p.still_needed} acertos entre ${p.remaining} Questions restantes (meta ${p.needed}/${s.total}).` }
}

function ScoreBar({ score, open, mode }: { score: Score; open: boolean; mode: 'practice' | 'exam' }) {
  const [show, toggle] = useShowScore(mode, open)
  const p = score.pass
  const v = verdict(score)
  const cell = (label: string, value: string | number, tone = '') => (
    <div className="shrink-0 border-r border-zinc-800 px-3 last:border-0"><span className="text-zinc-500">{label}</span> <b className={tone}>{value}</b></div>
  )
  return (
    <div className="sticky top-0 z-20 flex items-center overflow-x-auto whitespace-nowrap border-b border-zinc-800 bg-zinc-900 py-2">
      {show ? (
        <>
          {cell('✓', score.correct, 'text-emerald-400')}{cell('✗', score.wrong, 'text-rose-400')}
          {cell('restam', open ? score.skipped : 0)}
          {cell('acerto', pct(score.answered ? score.correct / score.answered : null), 'text-violet-300')}
          {p && <>{cell('meta', `${p.needed}/${score.total}`)}{cell('gap', p.still_needed)}{cell('teto', `${score.correct + p.remaining}/${score.total}`)}</>}
          {v && <div className={`px-3 ${v.tone}`}>▸ {v.text}</div>}
        </>
      ) : <div className="px-3 text-zinc-600">placar oculto</div>}
      <button onClick={toggle} title="Mostrar ou esconder o placar" className="ml-auto mr-3 shrink-0 rounded border border-zinc-700 px-2 py-0.5 text-zinc-400 hover:text-white">
        <i className={`fa-solid ${show ? 'fa-eye' : 'fa-eye-slash'}`} /> placar
      </button>
    </div>
  )
}

export default function AttemptPage() {
  const aid = Number(useParams().id)
  const nav = useNavigate()
  const qc = useQueryClient()
  const attempt = useQuery({ queryKey: ['attempt', aid], queryFn: () => api<AttemptInfo>(`/attempts/${aid}`), staleTime: 0 })
  const [pos, setPos] = useState<number | null>(null)
  const [picked, setPicked] = useState<string[]>([])
  const [conf, setConf] = useState('')
  const [why, setWhy] = useState('')
  const [elim, setElim] = useState<Record<string, string>>({}) // letra -> por que descartei
  const [editing, setEditing] = useState<string | null>(null) // balão de comentário aberto
  const shownAt = useRef(Date.now())

  useEffect(() => {
    if (pos === null && attempt.data) setPos(attempt.data.map.find((m) => !m.answered)?.position ?? 1)
  }, [attempt.data, pos])

  useEffect(() => { window.scrollTo(0, 0) }, [pos]) // trocar de questão volta ao topo

  const question = useQuery({ queryKey: ['question', aid, pos], queryFn: () => api<Question>(`/attempts/${aid}/questions/${pos}`), enabled: pos !== null, staleTime: 0 })
  const q = question.data

  useEffect(() => {
    if (!q) return
    const r = splitReasoning(q.reasoning)
    setPicked(q.selected); setConf(q.confidence ?? ''); setWhy(r.why); setElim(r.elim); setEditing(null); shownAt.current = Date.now()
  }, [q])

  const refresh = () => { qc.invalidateQueries({ queryKey: ['attempt', aid] }); qc.invalidateQueries({ queryKey: ['question', aid] }); qc.invalidateQueries({ queryKey: ['running'] }) }
  const answer = useMutation({
    mutationFn: () => post(`/attempts/${aid}/answers`, { position: pos, selected: picked, confidence: conf || null, reasoning: joinReasoning(why, elim), time_seconds: (Date.now() - shownAt.current) / 1000 }),
    onSuccess: () => { refresh(); if (q?.mode === 'exam' && pos! < q.total) setPos(pos! + 1) },
  })
  const finish = useMutation({ mutationFn: () => post(`/attempts/${aid}/finish`), onSuccess: refresh })

  const editable = !!q && q.state === 'in_progress' && (q.mode === 'exam' || !q.answered)
  const toggleElim = (letter: string) => {
    if (!editable) return
    if (letter in elim) { setElim(({ [letter]: _, ...rest }) => rest); setEditing(null); return }
    setElim((cur) => ({ ...cur, [letter]: '' }))
    setPicked((cur) => cur.filter((l) => l !== letter)) // descartada não pode estar marcada
    setEditing(letter)
  }
  const choose = (letter: string) => {
    if (!editable || !q) return
    if (letter in elim) setElim(({ [letter]: _, ...rest }) => rest) // marcar uma descartada desfaz o descarte
    setPicked((cur) => (q.multi ? (cur.includes(letter) ? cur.filter((l) => l !== letter) : [...cur, letter]) : [letter]))
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).closest('input, textarea, select')) return
      if (!q) return
      const digit = /^Digit([1-9])$/.exec(e.code)
      if (e.shiftKey && digit) { e.preventDefault(); const o = q.options[Number(digit[1]) - 1]; if (o) toggleElim(o.letter); return } // Shift+n descarta
      const i = Number(e.key) - 1
      if (i >= 0 && i < q.options.length) choose(q.options[i].letter)
      else if (e.key === 'Enter' && editable && picked.length && !answer.isPending) answer.mutate()
      else if (e.key === 'ArrowRight' && pos! < q.total) setPos(pos! + 1)
      else if (e.key === 'ArrowLeft' && pos! > 1) setPos(pos! - 1)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  if (attempt.error) return <ErrorBox error={attempt.error} retry={() => attempt.refetch()} />
  const a = attempt.data
  return (
    <div>
      {a ? <ScoreBar key={`${a.id}-${a.state}`} score={a.score} open={a.state === 'in_progress'} mode={a.mode} /> : <Skeleton className="m-2 h-8" />}
      {a && a.state !== 'in_progress' && (
        <div className="border-b border-zinc-800 bg-zinc-900/40 px-4 py-2 text-zinc-300">
          Attempt {a.state === 'finished' ? 'finalizado' : 'abandonado'}: {a.score.correct}/{a.score.answered} certas, {a.score.skipped} puladas.
          <button onClick={() => nav('/')} className="ml-3 underline">voltar ao início</button>
        </div>
      )}
      <div className="lg:flex">
        <aside className="border-b border-zinc-800 p-4 lg:sticky lg:top-11 lg:h-[calc(100vh-2.75rem)] lg:w-64 lg:overflow-y-auto lg:border-b-0 lg:border-r">
          <div className="mb-2 text-zinc-500">MAPA · {a?.map.length ?? '…'} questões</div>
          <div className="grid grid-cols-10 gap-1 lg:grid-cols-8">
            {a?.map.map((m) => (
              <button key={m.position} onClick={() => setPos(m.position)}
                className={`grid aspect-square place-items-center rounded-sm text-[10px] ${m.position === pos ? 'outline outline-2 outline-violet-400' : ''} ${
                  m.is_correct === true ? 'bg-emerald-600/70' : m.is_correct === false ? 'bg-rose-600/70' : m.answered ? 'bg-violet-700/60' : 'bg-zinc-800 text-zinc-500'}`}>
                {m.position}
              </button>
            ))}
          </div>
          <div className="mt-3 space-y-1 text-[11px] text-zinc-500">
            <div><span className="mr-1 inline-block h-2 w-2 bg-emerald-600/70" />certa</div>
            <div><span className="mr-1 inline-block h-2 w-2 bg-rose-600/70" />errada</div>
            <div><span className="mr-1 inline-block h-2 w-2 bg-violet-700/60" />respondida (gabarito oculto)</div>
            <div><span className="mr-1 inline-block h-2 w-2 bg-zinc-800" />pendente</div>
          </div>
          {a?.state === 'in_progress' && (
            <button onClick={() => finish.mutate()} disabled={finish.isPending} className="mt-4 w-full rounded border border-zinc-700 py-2 text-zinc-300 hover:bg-zinc-800">
              Finalizar Attempt
            </button>
          )}
        </aside>

        <section className="max-w-3xl flex-1 p-4 pb-24 lg:p-8">
          {question.error ? <ErrorBox error={question.error} retry={() => question.refetch()} /> : !q ? (
            <div className="space-y-3"><Skeleton className="h-4 w-2/3" /><Skeleton className="h-24" /><Skeleton className="h-12" /><Skeleton className="h-12" /></div>
          ) : (
            <>
              <div className="mb-1 text-zinc-500">Q{q.position}/{q.total} · {q.section}
                {q.topics?.[0] && <span className="text-violet-300"> · #{q.topics[0].topic.toLowerCase().replace(/ /g, '-')}</span>}</div>
              <div className="mb-5 font-sans text-[15px] leading-relaxed text-zinc-100" dangerouslySetInnerHTML={html(q.prompt_html)} />
              {q.multi && <div className="mb-2 text-sky-400">Escolha {q.choose} opções.</div>}
              <div className="space-y-1.5 font-sans">
                {q.options.map((o, i) => {
                  const sel = picked.includes(o.letter)
                  const ok = q.reveal && q.correct?.includes(o.letter)
                  const bad = q.reveal && sel && !ok
                  const out = o.letter in elim
                  return (
                    <div key={o.letter} className="relative">
                      <button onClick={() => choose(o.letter)} disabled={!editable && !q.reveal}
                        className={`flex w-full gap-3 rounded-md border px-3 py-2.5 pr-12 text-left transition ${out && !ok ? 'opacity-50' : ''} ${
                          ok ? 'border-emerald-600 bg-emerald-950/40' : bad ? 'border-rose-600 bg-rose-950/40' : sel ? 'border-violet-500 bg-violet-950/60' : 'border-zinc-800 hover:bg-zinc-900'}`}>
                        <kbd className="h-fit rounded bg-zinc-800 px-1.5 text-zinc-300">{i + 1}</kbd>
                        <span className={`text-sm ${out ? 'line-through decoration-zinc-500' : ''}`}><b className="mr-2 text-zinc-400">{o.letter})</b><span dangerouslySetInnerHTML={html(o.html)} />
                          {ok && <i className="fa-solid fa-check ml-2 text-emerald-400" />}{bad && <i className="fa-solid fa-xmark ml-2 text-rose-400" />}</span>
                      </button>
                      {editable && (
                        <button onClick={() => toggleElim(o.letter)} aria-pressed={out} title={out ? 'Desfazer descarte (Shift+' + (i + 1) + ')' : 'Descartar (Shift+' + (i + 1) + ')'} aria-label={`Descartar alternativa ${o.letter}`}
                          className={`absolute right-2 top-2 grid h-7 w-7 place-items-center rounded ${out ? 'bg-zinc-700 text-amber-300' : 'text-zinc-600 hover:bg-zinc-800 hover:text-zinc-300'}`}>
                          <i className="fa-solid fa-ban" />
                        </button>
                      )}
                      {out && editing !== o.letter && (
                        <button onClick={() => editable && setEditing(o.letter)} disabled={!editable}
                          className="ml-10 mt-0.5 block text-left text-xs italic text-amber-300/80">
                          {elim[o.letter] ? `descartei: ${elim[o.letter]}` : editable ? 'descartada · por quê? (clique)' : 'descartada'}
                        </button>
                      )}
                      {editing === o.letter && editable && (
                        <div className="absolute right-2 top-full z-10 mt-1 w-72 max-w-[90%] rounded-lg border border-amber-500/60 bg-zinc-900 p-2 shadow-lg">
                          <span className="absolute -top-1.5 right-3 h-3 w-3 rotate-45 border-l border-t border-amber-500/60 bg-zinc-900" />
                          <input autoFocus value={elim[o.letter] ?? ''} onChange={(e) => setElim((c) => ({ ...c, [o.letter]: e.target.value }))}
                            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === 'Escape') { e.preventDefault(); setEditing(null) } }} onBlur={() => setEditing(null)}
                            placeholder={`Por que descartou ${o.letter})? (Enter fecha)`}
                            className="relative w-full rounded border border-zinc-700 bg-zinc-950 p-1.5 font-sans text-sm outline-none focus:border-amber-400" />
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>

              {editable ? (
                <div className="mt-4 space-y-3">
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(CONF).map(([k, label]) => (
                      <button key={k} onClick={() => setConf(conf === k ? '' : k)} className={`rounded border px-3 py-1 ${conf === k ? 'border-violet-500 bg-violet-950 text-violet-200' : 'border-zinc-700 text-zinc-400'}`}>{label}</button>
                    ))}
                  </div>
                  <textarea value={why} onChange={(e) => setWhy(e.target.value)} rows={2} placeholder="Seu raciocínio (opcional)"
                    className="w-full rounded-md border border-zinc-700 bg-zinc-900 p-2 font-sans outline-none focus:border-violet-500" />
                  <div className="flex items-center gap-2">
                    <button onClick={() => answer.mutate()} disabled={!picked.length || answer.isPending} className="rounded-md bg-violet-600 px-4 py-2 font-semibold text-white disabled:opacity-30">
                      {answer.isPending ? <><i className="fa-solid fa-circle-notch fa-spin mr-2" />Gravando…</> : 'Confirmar ⏎'}
                    </button>
                    <span className="text-zinc-600">teclas 1–9 escolhem · Shift+1–9 descarta · Enter confirma · ←/→ navegam</span>
                  </div>
                  {answer.error && <div className="text-rose-400">{answer.error.message}</div>}
                </div>
              ) : (
                <div className="mt-4 text-zinc-500">
                  {q.state === 'in_progress' && q.answered && 'Resposta registrada. '}
                  {q.reveal && q.answered && (q.is_correct ? <span className="text-emerald-400">Correto</span> : <span className="text-rose-400">Errado</span>)}
                  {q.reveal && !q.answered && <span className="text-amber-400">Sem resposta</span>}
                  {q.confidence && <span> · Confiança: {CONF[q.confidence]}</span>}
                </div>
              )}

              {q.reveal && q.explanation_html && (
                <details open className="mt-5 rounded-lg border border-zinc-800 bg-zinc-900/40 p-4">
                  <summary className="cursor-pointer text-zinc-400">Explicação da Udemy</summary>
                  <div className="mt-2 font-sans text-sm leading-relaxed [&_a]:text-violet-300 [&_a]:underline [&_li]:ml-5 [&_li]:list-disc" dangerouslySetInnerHTML={html(q.explanation_html)} />
                </details>
              )}
              <div className="mt-6 flex gap-2">
                <button onClick={() => setPos(pos! - 1)} disabled={pos! <= 1} className="rounded border border-zinc-700 px-3 py-1.5 disabled:opacity-30"><i className="fa-solid fa-arrow-left mr-1" />Anterior</button>
                <button onClick={() => setPos(pos! + 1)} disabled={pos! >= q.total} className="rounded border border-zinc-700 px-3 py-1.5 disabled:opacity-30">Próxima<i className="fa-solid fa-arrow-right ml-1" /></button>
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  )
}
