import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  createEngineClient,
  decodeRtaSourceHealth,
  type EngineConnection,
  resolveEngineConnection,
  sessionTokenFromFragment,
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

describe('browser engine discovery', () => {
  it('uses the same-origin portable endpoint and fragment token', () => {
    const token = sessionTokenFromFragment('#wfmhub_token=launch-secret')
    const connection = resolveEngineConnection(false, {}, 'http://127.0.0.1:43127', token)

    expect(connection).toMatchObject({
      phase: 'ready',
      baseUrl: 'http://127.0.0.1:43127/api',
      sessionToken: 'launch-secret',
    })
    expect(connection.baseUrl).not.toContain('launch-secret')
  })

  it('does not permit a production browser without a launcher token', () => {
    const connection = resolveEngineConnection(false, {}, 'http://127.0.0.1:43127', null)

    expect(connection.phase).toBe('unavailable')
    expect(connection.baseUrl).toBeNull()
    expect(connection.sessionToken).toBeNull()
  })

  it('rejects non-loopback production origins', () => {
    const connection = resolveEngineConnection(false, {}, 'https://example.com', 'secret')

    expect(connection.phase).toBe('unavailable')
    expect(() => validateLoopbackBaseUrl('http://127.0.0.1:40100/api')).not.toThrow()
  })

  it('preserves explicit loopback browser-development endpoints', () => {
    const connection = resolveEngineConnection(
      true,
      {
        VITE_ENGINE_BASE_URL: 'http://127.0.0.1:40100/api',
        VITE_ENGINE_SESSION_TOKEN: 'development-secret',
      },
      'http://127.0.0.1:5173',
      null,
    )

    expect(connection).toMatchObject({
      phase: 'ready',
      baseUrl: 'http://127.0.0.1:40100/api',
      sessionToken: 'development-secret',
    })
  })
})

describe('engine API client', () => {
  it('decodes the governed source-health contract and rejects drift', () => {
    const health = {
      status: 'not_ready',
      ready: false,
      sourceRoot: { mode: 'default', displayName: 'extracts' },
      configuredSources: {
        fte: 'FTE',
        publishedSchedules: 'Verint/Schedules & Activities',
        agentStatus: 'Storm/Agent Status',
        lilo: 'Storm/LILO',
        callByCall: 'Storm/Call by Call',
      },
      activeGenerationId: null,
      activeGeneration: null,
      latestRefresh: null,
      refreshProgress: null,
      quality: { error: 0, warning: 0, info: 0 },
      sources: {
        roster: { ready: false, agentCount: 0, timeOffCount: 0, fileCount: 0 },
        schedule: { ready: false, shiftCount: 0, fileCount: 0, minDate: null, maxDate: null },
        agentStatus: { ready: false, rowCount: 0, fileCount: 0, minDate: null, maxDate: null },
        lilo: { ready: false, rowCount: 0, fileCount: 0, minDate: null, maxDate: null },
        callByCall: {
          ready: false,
          rawLegCount: 0,
          canonicalLegCount: 0,
          serviceIntervalCount: 0,
          fileCount: 0,
          minDate: null,
          maxDate: null,
        },
        attendance: {
          ready: false,
          agentDayCount: 0,
          gapFragmentCount: 0,
          statusPrimaryCount: 0,
          unknownCount: 0,
          minDate: null,
          maxDate: null,
        },
      },
    }
    expect(decodeRtaSourceHealth(health).ready).toBe(false)
    expect(() => decodeRtaSourceHealth({ ...health, quality: { errors: 0 } })).toThrow()
  })

  it('refreshes only the fixed local source contract', async () => {
    const health = {
      status: 'not_ready',
      ready: false,
      sourceRoot: { mode: 'default', displayName: 'extracts' },
      configuredSources: {
        fte: 'FTE',
        publishedSchedules: 'Verint/Schedules & Activities',
        agentStatus: 'Storm/Agent Status',
        lilo: 'Storm/LILO',
        callByCall: 'Storm/Call by Call',
      },
      activeGenerationId: null,
      activeGeneration: null,
      latestRefresh: null,
      refreshProgress: null,
      quality: { error: 0, warning: 0, info: 0 },
      sources: {
        roster: { ready: false, agentCount: 0, timeOffCount: 0, fileCount: 0 },
        schedule: { ready: false, shiftCount: 0, fileCount: 0, minDate: null, maxDate: null },
        agentStatus: { ready: false, rowCount: 0, fileCount: 0, minDate: null, maxDate: null },
        lilo: { ready: false, rowCount: 0, fileCount: 0, minDate: null, maxDate: null },
        callByCall: {
          ready: false,
          rawLegCount: 0,
          canonicalLegCount: 0,
          serviceIntervalCount: 0,
          fileCount: 0,
          minDate: null,
          maxDate: null,
        },
        attendance: {
          ready: false,
          agentDayCount: 0,
          gapFragmentCount: 0,
          statusPrimaryCount: 0,
          unknownCount: 0,
          minDate: null,
          maxDate: null,
        },
      },
    }
    const fetchMock = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            status: 'succeeded',
            generationId: 1,
            unchanged: false,
            durationMs: 12,
            sourceHealth: health,
          }),
          { status: 200 },
        ),
    )
    vi.stubGlobal('fetch', fetchMock)

    await expect(createEngineClient(readyConnection).refreshRtaSources()).resolves.toMatchObject({
      generationId: 1,
    })
    expect(fetchMock).toHaveBeenCalledWith('http://127.0.0.1:43127/api/rta/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-WFMHub-Token': 'launch-secret' },
      body: '{}',
    })
  })

  it('reads the Phase 0.4 host health endpoint from the product shell', async () => {
    const fetchMock = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            status: 'ok',
            version: '0.2.0-phase0.4',
            architecture: 'stdlib-sqlite-browser-wasm-spike',
            thirdPartyHostNativeFiles: 0,
          }),
          { status: 200 },
        ),
    )
    vi.stubGlobal('fetch', fetchMock)

    await expect(
      createEngineClient(readyConnection).getCompatibilityHealth(),
    ).resolves.toMatchObject({
      status: 'ok',
      thirdPartyHostNativeFiles: 0,
    })
    expect(fetchMock).toHaveBeenCalledWith('http://127.0.0.1:43127/api/compat/health', {
      headers: { 'X-WFMHub-Token': 'launch-secret' },
    })
  })

  it('uses the dynamic port and authenticates the health request', async () => {
    const fetchMock = vi.fn(
      async () =>
        new Response(
          JSON.stringify({ status: 'ok', version: '0.2.0', architecture: 'portable-browser' }),
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

  it('saves a compatibility report through the protected local boundary', async () => {
    const fetchMock = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            status: 'saved',
            relativePath: 'data/compatibility/last-browser-report.json',
          }),
          { status: 200 },
        ),
    )
    vi.stubGlobal('fetch', fetchMock)
    const report = { schemaVersion: 1, probes: [] }

    await expect(
      createEngineClient(readyConnection).saveCompatibilityReport(report),
    ).resolves.toMatchObject({ status: 'saved' })
    expect(fetchMock).toHaveBeenCalledWith('http://127.0.0.1:43127/api/compat/report', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-WFMHub-Token': 'launch-secret',
      },
      body: JSON.stringify(report),
    })
  })
})
