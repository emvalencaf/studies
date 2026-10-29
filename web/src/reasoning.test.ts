import { describe, expect, it } from 'vitest'
import { joinReasoning, splitReasoning } from './reasoning'

describe('raciocínio com alternativas descartadas', () => {
  it('compõe e separa de volta sem perder nada', () => {
    const text = joinReasoning('achei que era managed', { b: 'não escala', d: '' })!
    expect(text).toBe('achei que era managed\nDescartei b) — não escala\nDescartei d)')
    expect(splitReasoning(text)).toEqual({ why: 'achei que era managed', elim: { b: 'não escala', d: '' } })
  })
  it('sem raciocínio nem descartes vira null; só descartes também funciona', () => {
    expect(joinReasoning('  ', {})).toBeNull()
    expect(splitReasoning(joinReasoning('', { a: 'caro' }))).toEqual({ why: '', elim: { a: 'caro' } })
  })
  it('raciocínio antigo, sem descartes, passa intacto; quebra de linha no comentário não corrompe', () => {
    expect(splitReasoning('texto livre\nem duas linhas')).toEqual({ why: 'texto livre\nem duas linhas', elim: {} })
    expect(splitReasoning(joinReasoning('', { c: 'a\nb' })).elim).toEqual({ c: 'a b' })
    expect(splitReasoning(null)).toEqual({ why: '', elim: {} })
  })
})
