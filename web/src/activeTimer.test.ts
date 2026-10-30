// @vitest-environment jsdom
import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { clearAttemptTimers, IDLE_MS, mmss, useActiveTimer } from './activeTimer'

const setVisibility = (v: 'visible' | 'hidden') => {
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => v })
  document.dispatchEvent(new Event('visibilitychange'))
}
const tick = (s: number) => { for (let i = 0; i < s; i++) act(() => { vi.advanceTimersByTime(1000) }) }
const touch = () => act(() => { window.dispatchEvent(new Event('pointerdown')) })

describe('cronômetro de tempo ativo', () => {
  beforeEach(() => { vi.useFakeTimers(); localStorage.clear(); setVisibility('visible') })
  afterEach(() => vi.useRealTimers())

  it('conta enquanto a aba está visível e com interação', () => {
    const { result } = renderHook(() => useActiveTimer('1:1'))
    tick(5)
    expect(result.current.read()).toBe(5)
  })

  it('não conta com a aba escondida e retoma ao voltar', () => {
    const { result } = renderHook(() => useActiveTimer('1:1'))
    tick(3)
    setVisibility('hidden'); tick(600)
    setVisibility('visible'); tick(2)
    expect(result.current.read()).toBe(5)
  })

  it('pausa após inatividade e volta com uma interação', () => {
    const { result } = renderHook(() => useActiveTimer('1:1'))
    tick(IDLE_MS / 1000 + 30)
    const parado = result.current.read()
    expect(parado).toBeLessThanOrEqual(IDLE_MS / 1000)
    expect(result.current.paused).toBe(true)
    touch(); tick(4)
    expect(result.current.read()).toBe(parado + 4)
  })

  it('fechar e reabrir retoma do acumulado, sem contar o tempo fora', () => {
    const first = renderHook(() => useActiveTimer('1:1'))
    tick(7)
    first.unmount()
    vi.advanceTimersByTime(3_600_000)
    const again = renderHook(() => useActiveTimer('1:1'))
    expect(again.result.current.read()).toBe(7)
  })

  it('clear zera e apaga o que estava guardado', () => {
    const { result, unmount } = renderHook(() => useActiveTimer('1:1'))
    tick(4)
    act(() => result.current.clear())
    unmount()
    expect(renderHook(() => useActiveTimer('1:1')).result.current.read()).toBe(0)
  })

  it('cada questão tem o seu próprio tempo', () => {
    const a = renderHook(() => useActiveTimer('1:1'))
    tick(4); a.unmount()
    expect(renderHook(() => useActiveTimer('1:2')).result.current.read()).toBe(0)
  })

  it('finalizar ou abandonar apaga os tempos parciais só daquele Attempt', () => {
    for (const k of ['7:1', '7:2', '70:1']) { const h = renderHook(() => useActiveTimer(k)); tick(2); h.unmount() }
    clearAttemptTimers(7)
    expect(renderHook(() => useActiveTimer('7:1')).result.current.read()).toBe(0)
    expect(renderHook(() => useActiveTimer('7:2')).result.current.read()).toBe(0)
    expect(renderHook(() => useActiveTimer('70:1')).result.current.read()).toBe(2)
  })

  it('formata mm:ss', () => { expect(mmss(65)).toBe('1:05'); expect(mmss(0)).toBe('0:00') })
})
