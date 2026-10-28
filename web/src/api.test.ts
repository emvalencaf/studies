import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError, post } from './api'

const reply = (status: number, body: unknown) =>
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(body), { status })))

afterEach(() => vi.unstubAllGlobals())

describe('api', () => {
  it('devolve o JSON quando a resposta é ok', async () => {
    reply(200, { ok: true })
    expect(await api('/health')).toEqual({ ok: true })
  })

  it('lança ApiError com o status e o detail do servidor', async () => {
    reply(401, { detail: 'Token inválido' })
    await expect(api('/certifications')).rejects.toMatchObject({ status: 401, message: 'Token inválido' })
    reply(409, { detail: 'Question já respondida neste Attempt' })
    await expect(post('/attempts/1/answers', {})).rejects.toBeInstanceOf(ApiError)
  })

  it('funciona sem localStorage (Node não tem) e sem Authorization', async () => {
    reply(200, {})
    await api('/health')
    const init = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][1] as RequestInit
    expect((init.headers as Record<string, string>).Authorization).toBeUndefined()
  })
})
