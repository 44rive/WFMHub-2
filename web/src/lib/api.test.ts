import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  createEngineClient,
  type EngineConnection,
  resolveEngineConnection,
  validateLoopbackBaseUrl,
} from './api'

const readyConnection: EngineConnection = {
  phase: 'ready',
  baseUrl: 'http://127.0.0.1:43127/api',
  sessionToken: 'launch-secret',
  message: null,
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('desktop engine discovery', () => {
  it('uses the desktop command instead of a hard-coded port', async () => {
    const invokeConnection = vi.fn(async () => readyConnection)

    await expect(resolveEngineConnection(true, false, {}, invokeConnection)).resolves.toEqual(
      readyConnection,
    )
    expect(invokeConnection).toHaveBeenCalledOnce()
  })

  it('does not permit a production browser fallback', async () => {
    const connection = await resolveEngineConnection(false, false, {}, vi.fn())

    expect(connection.phase).toBe('unavailable')
    expect(connection.baseUrl).toBeNull()
    expect(connection.sessionToken).toBeNull()
  })

  it('only permits explicit loopback browser-development endpoints', async () => {
    const connection = await resolveEngineConnection(
      false,
      true,
      {
        VITE_ENGINE_BASE_URL: 'https://example.com/api',
        VITE_ENGINE_SESSION_TOKEN: 'development-secret',
      },
      vi.fn(),
    )

    expect(connection.phase).toBe('unavailable')
    expect(() => validateLoopbackBaseUrl('http://127.0.0.1:40100/api')).not.toThrow()
  })
})

describe('engine API client', () => {
  it('uses the dynamic port and authenticates the health request', async () => {
    const fetchMock = vi.fn(
      async () =>
        new Response(
          JSON.stringify({ status: 'ok', version: '0.2.0', architecture: 'portable-sidecar' }),
          { status: 200 },
        ),
    )
    vi.stubGlobal('fetch', fetchMock)

    await expect(createEngineClient(readyConnection).getHealth()).resolves.toMatchObject({
      status: 'ok',
    })
    expect(fetchMock).toHaveBeenCalledWith('http://127.0.0.1:43127/api/health', {
      headers: { 'X-WFMHub-Token': 'launch-secret' },
    })
  })

  it('calls the token-protected offline stack probe', async () => {
    const fetchMock = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            status: 'ok',
            mode: 'offline',
            settings: {},
            checks: [{ name: 'ducklake', status: 'pass' }],
          }),
          { status: 200 },
        ),
    )
    vi.stubGlobal('fetch', fetchMock)

    const result = await createEngineClient(readyConnection).getStackProbe()

    expect(result.checks).toEqual([{ name: 'ducklake', status: 'pass' }])
    expect(fetchMock).toHaveBeenCalledWith('http://127.0.0.1:43127/api/stack/probe', {
      headers: { 'X-WFMHub-Token': 'launch-secret' },
    })
  })
})
