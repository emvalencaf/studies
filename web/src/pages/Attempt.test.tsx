// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { AttemptInfo, Question } from '../api'
import AttemptPage from './Attempt'

const attempt: AttemptInfo = {
  id: 1, kind: 'review', mode: 'practice', state: 'in_progress',
  score: { total: 2, correct: 0, wrong: 0, skipped: 2, answered: 0, pass: null },
  map: [{ position: 1, answered: false, is_correct: null }, { position: 2, answered: false, is_correct: null }],
}
const question = (over: Partial<Question> = {}): Question => ({
  position: 1, total: 2, state: 'in_progress', mode: 'practice', section: 'S', prompt_html: '<p>Qual?</p>', multi: false,
  options: ['a', 'b', 'c', 'd'].map((l) => ({ letter: l, html: `texto ${l}` })), answered: false, selected: [],
  confidence: null, reveal: false, reasoning: null, ...over,
})

let current: Question
let posted: Record<string, unknown>[]

beforeEach(() => {
  current = question()
  posted = []
  window.scrollTo = vi.fn()
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const json = (b: unknown) => new Response(JSON.stringify(b), { status: 200 })
    if (init?.method === 'POST') { posted.push(JSON.parse(String(init.body))); return json({}) }
    return json(/\/questions\/\d+$/.test(url) ? current : attempt)
  }))
})
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

async function open() {
  const user = userEvent.setup()
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={['/attempts/1']}><Routes><Route path="attempts/:id" element={<AttemptPage />} /></Routes></MemoryRouter>
    </QueryClientProvider>,
  )
  await screen.findByText('texto a')
  return user
}
const optionBtn = (l: string) => screen.getByText(`${l})`).closest('button') as HTMLButtonElement
const banBtn = (l: string) => screen.getByRole('button', { name: `Descartar alternativa ${l}` })
const struck = (l: string) => screen.getByText(`${l})`).parentElement!.className.includes('line-through')
const balloon = () => screen.queryByPlaceholderText(/^Por que descartou/) as HTMLInputElement | null

describe('descartar alternativas (atalhos)', () => {
  it('Shift+2 descarta a alternativa b, risca o texto e abre o balão já focado', async () => {
    const user = await open()
    await user.keyboard('{Shift>}2{/Shift}')
    expect(struck('b')).toBe(true)
    expect(banBtn('b').getAttribute('aria-pressed')).toBe('true')
    expect(balloon()).not.toBeNull()
    expect(document.activeElement).toBe(balloon())
  })

  it('o caractere do atalho não vaza para o campo do balão', async () => {
    const user = await open()
    await user.keyboard('{Shift>}2{/Shift}')
    await user.keyboard('caro')
    expect(balloon()!.value).toBe('caro')
  })

  it('Shift+n de novo desfaz o descarte e some com o comentário', async () => {
    const user = await open()
    await user.keyboard('{Shift>}3{/Shift}')
    await user.keyboard('{Escape}')
    expect(struck('c')).toBe(true)
    await user.keyboard('{Shift>}3{/Shift}')
    expect(struck('c')).toBe(false)
    expect(balloon()).toBeNull()
    expect(screen.queryByText(/descartada/)).toBeNull()
  })

  it('dentro do campo de raciocínio os atalhos ficam desligados: Shift+2 vira texto e não descarta', async () => {
    const user = await open()
    const why = screen.getByPlaceholderText('Seu raciocínio (opcional)') as HTMLTextAreaElement
    await user.click(why)
    await user.keyboard('{Shift>}2{/Shift}')
    expect(why.value).not.toBe('') // a tecla foi para o campo, não para o atalho
    expect(struck('b')).toBe(false)
    expect(balloon()).toBeNull()
  })

  it('Shift com número maior que a quantidade de alternativas não faz nada', async () => {
    const user = await open()
    await user.keyboard('{Shift>}9{/Shift}')
    expect(balloon()).toBeNull()
    expect(screen.queryByText(/descartada/)).toBeNull()
  })

  it('os atalhos de escolha continuam: 3 marca c, e dígitos digitados no balão não escolhem nada', async () => {
    const user = await open()
    await user.keyboard('3')
    expect(optionBtn('c').className).toContain('border-violet-500')
    await user.keyboard('{Shift>}2{/Shift}')
    await user.keyboard('1 e 4')
    expect(balloon()!.value).toBe('1 e 4')
    expect(optionBtn('a').className).not.toContain('border-violet-500')
    expect(optionBtn('d').className).not.toContain('border-violet-500')
  })
})

describe('balão de comentário', () => {
  it('Enter fecha o balão e mostra o motivo abaixo da alternativa', async () => {
    const user = await open()
    await user.keyboard('{Shift>}2{/Shift}')
    await user.keyboard('reranker não resolve{Enter}')
    expect(balloon()).toBeNull()
    expect(screen.getByText('descartei: reranker não resolve')).toBeTruthy()
    expect(struck('b')).toBe(true)
  })

  it('Esc fecha sem apagar o descarte; sem motivo aparece o convite a comentar', async () => {
    const user = await open()
    await user.click(banBtn('d'))
    expect(balloon()).not.toBeNull()
    await user.keyboard('{Escape}')
    expect(balloon()).toBeNull()
    expect(struck('d')).toBe(true)
    expect(screen.getByText(/por quê\?/)).toBeTruthy()
  })

  it('clicar no convite reabre o balão com o motivo já escrito', async () => {
    const user = await open()
    await user.click(banBtn('b'))
    await user.keyboard('motivo{Enter}')
    await user.click(screen.getByText('descartei: motivo'))
    expect(balloon()!.value).toBe('motivo')
  })

  it('clicar fora (blur) fecha o balão', async () => {
    const user = await open()
    await user.click(banBtn('b'))
    await user.click(screen.getByPlaceholderText('Seu raciocínio (opcional)'))
    expect(balloon()).toBeNull()
    expect(struck('b')).toBe(true)
  })
})

describe('interação com a escolha', () => {
  it('descartar uma alternativa marcada a desmarca', async () => {
    const user = await open()
    await user.keyboard('2')
    expect(optionBtn('b').className).toContain('border-violet-500')
    await user.keyboard('{Shift>}2{/Shift}')
    await user.keyboard('{Escape}')
    expect(optionBtn('b').className).not.toContain('border-violet-500')
  })

  it('marcar uma alternativa descartada desfaz o descarte', async () => {
    const user = await open()
    await user.keyboard('{Shift>}4{/Shift}')
    await user.keyboard('{Escape}')
    await user.keyboard('4')
    expect(struck('d')).toBe(false)
    expect(optionBtn('d').className).toContain('border-violet-500')
  })
})

describe('gravação e restauração', () => {
  it('Confirmar envia o raciocínio com uma linha "Descartei" por alternativa', async () => {
    const user = await open()
    await user.type(screen.getByPlaceholderText('Seu raciocínio (opcional)'), 'achei managed')
    await user.click(document.body) // tira o foco do campo para os atalhos voltarem a valer
    await user.keyboard('{Shift>}2{/Shift}')
    await user.keyboard('não escala{Enter}')
    await user.click(banBtn('d'))
    await user.keyboard('{Escape}')
    await user.click(optionBtn('a'))
    await user.click(screen.getByRole('button', { name: /Confirmar/ }))
    await waitFor(() => expect(posted).toHaveLength(1))
    expect(posted[0]).toMatchObject({
      position: 1, selected: ['a'],
      reasoning: 'achei managed\nDescartei b) — não escala\nDescartei d)',
    })
  })

  it('só descartes, sem texto de raciocínio, também são enviados; sem nada vai null', async () => {
    const user = await open()
    await user.click(optionBtn('a'))
    await user.click(screen.getByRole('button', { name: /Confirmar/ }))
    await waitFor(() => expect(posted).toHaveLength(1))
    expect(posted[0].reasoning).toBeNull()
  })

  it('ao carregar, separa as linhas "Descartei" do texto: o campo mostra só o raciocínio', async () => {
    current = question({ reasoning: 'meu texto\nDescartei b) — caro\nDescartei c)' })
    await open()
    await screen.findByText('descartei: caro') // o estado vem de um useEffect depois do primeiro render
    expect((screen.getByPlaceholderText('Seu raciocínio (opcional)') as HTMLTextAreaElement).value).toBe('meu texto')
    expect(struck('b')).toBe(true)
    expect(struck('c')).toBe(true)
    expect(struck('a')).toBe(false)
    expect(screen.getByText('descartei: caro')).toBeTruthy()
  })

  it('questão já respondida (gabarito aberto): mostra os descartes mas não deixa editar', async () => {
    current = question({ answered: true, reveal: true, selected: ['a'], correct: ['a'], is_correct: true, reasoning: 'Descartei b) — caro' })
    await open()
    await screen.findByText('descartei: caro')
    expect(struck('b')).toBe(true)
    expect(screen.queryByRole('button', { name: /Descartar alternativa/ })).toBeNull()
    await userEvent.setup().keyboard('{Shift>}3{/Shift}')
    expect(struck('c')).toBe(false)
    expect(balloon()).toBeNull()
  })
})
