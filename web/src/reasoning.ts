// Alternativas descartadas viajam dentro do raciocínio, uma linha cada ("Descartei b) — porque ..."), então não há
// mudança de schema e o texto continua legível em qualquer lugar. As letras são as exibidas na tela.
const ELIM_LINE = /^Descartei ([a-z])\)(?: — (.*))?$/
export function splitReasoning(text: string | null | undefined): { why: string; elim: Record<string, string> } {
  const elim: Record<string, string> = {}, rest: string[] = []
  for (const line of (text ?? '').split('\n')) {
    const m = ELIM_LINE.exec(line.trim())
    if (m) elim[m[1]] = m[2] ?? ''
    else rest.push(line)
  }
  return { why: rest.join('\n').trim(), elim }
}
export function joinReasoning(why: string, elim: Record<string, string>): string | null {
  const lines = Object.keys(elim).sort().map((l) => `Descartei ${l})${elim[l].trim() ? ` — ${elim[l].trim().replace(/\s*\n\s*/g, ' ')}` : ''}`)
  const out = [why.trim(), ...lines].filter(Boolean).join('\n')
  return out || null
}
