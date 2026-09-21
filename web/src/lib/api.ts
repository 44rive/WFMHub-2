export type EnginePhase = 'starting' | 'ready' | 'failed' | 'unavailable'

export type EngineConnection = {
  phase: EnginePhase
  baseUrl: string | null
  sessionToken: string | null
  message: string | null
}

export type Health = {
  status: string
  version: string
  architecture: string
  thirdPartyHostNativeFiles?: number
}

export type SavedCompatibilityReport = {
  status: 'saved'
  relativePath: string
}

export type ProbeCheck = {
  name: string
  status: 'pass' | 'fail'
  details?: Record<string, unknown>
  error?: {
    type: string
    message: string
  }
}

export type StackProbe = {
  status: 'ok' | 'failed'
  mode: 'offline' | 'development'
  settings: {
    home: string
    control_db_path: string
    ducklake_extension: string | null
    ducklake_catalog_path: string
    ducklake_data_path: string
  }
  checks: ProbeCheck[]
}

export type SourceRoot = {
  mode: 'default' | 'configured' | 'invalid'
  displayName?: string
  pointerPath?: string
  errorCode?: string
}

export type SourceQuality = { error: number; warning: number; info: number }

export type SourceRefreshSummary = {
  generationId: number
  status: 'running' | 'succeeded' | 'failed'
  startedAt: string
  finishedAt: string | null
  counts: {
    rosterAgents: number
    timeOffRecords: number
    scheduleAssignments: number
    sourceFiles: number
  }
  dateRange: { from: string | null; to: string | null }
  qualityCounts: SourceQuality
  failureCode?: string
}

export type RtaSourceHealth = {
  status: string
  sourceRoot: SourceRoot
  activeGenerationId: number | null
  activeGeneration: SourceRefreshSummary | null
  latestRefresh: SourceRefreshSummary | null
  configuredSources: { fte: string; publishedSchedules: string }
  sources: {
    roster: { ready: boolean; agentCount: number; timeOffCount: number; fileCount: number }
    schedule: {
      ready: boolean
      shiftCount: number
      fileCount: number
      minDate: string | null
      maxDate: string | null
    }
  }
  quality: SourceQuality
  ready: boolean
}

export type RtaRefreshResult = {
  status: 'succeeded'
  generationId: number
  sourceHealth: RtaSourceHealth
}

const sessionTokenFragmentKey = 'wfmhub_token'
const sessionTokenStorageKey = 'wfmhub2.session-token'

function unavailable(message: string): EngineConnection {
  return {
    phase: 'unavailable',
    baseUrl: null,
    sessionToken: null,
    message,
  }
}

export function validateLoopbackBaseUrl(rawUrl: string): string {
  const url = new URL(rawUrl)
  if (
    url.protocol !== 'http:' ||
    !['127.0.0.1', 'localhost'].includes(url.hostname) ||
    url.username !== '' ||
    url.password !== ''
  ) {
    throw new Error('Engine URL must use HTTP on loopback')
  }
  return url.toString().replace(/\/$/, '')
}

export function sessionTokenFromFragment(fragment: string): string | null {
  const parameters = new URLSearchParams(fragment.startsWith('#') ? fragment.slice(1) : fragment)
  const token = parameters.get(sessionTokenFragmentKey)
  return token && token.trim() !== '' ? token : null
}

export function resolveEngineConnection(
  development: boolean,
  environment: Record<string, string | boolean | undefined>,
  browserOrigin: string,
  browserSessionToken: string | null,
): EngineConnection {
  if (browserSessionToken) {
    try {
      return {
        phase: 'ready',
        baseUrl: validateLoopbackBaseUrl(`${browserOrigin}/api`),
        sessionToken: browserSessionToken,
        message: 'Connected to the local portable engine.',
      }
    } catch (error) {
      return unavailable(error instanceof Error ? error.message : 'Invalid portable engine URL')
    }
  }

  if (!development) {
    return unavailable('Start WFMHub with WFMHub.cmd to create a secure browser session.')
  }

  const baseUrl = environment.VITE_ENGINE_BASE_URL
  const sessionToken = environment.VITE_ENGINE_SESSION_TOKEN
  if (typeof baseUrl !== 'string' || typeof sessionToken !== 'string') {
    return unavailable(
      'Browser development requires explicit VITE_ENGINE_BASE_URL and VITE_ENGINE_SESSION_TOKEN values.',
    )
  }

  try {
    return {
      phase: 'ready',
      baseUrl: validateLoopbackBaseUrl(baseUrl),
      sessionToken,
      message: 'Connected through the explicit browser-development override.',
    }
  } catch (error) {
    return unavailable(error instanceof Error ? error.message : 'Invalid development engine URL')
  }
}

function browserSessionToken(): string | null {
  const launchToken = sessionTokenFromFragment(window.location.hash)
  if (launchToken) {
    try {
      window.sessionStorage.setItem(sessionTokenStorageKey, launchToken)
    } catch {
      // The current page can still use the in-memory token when storage is disabled.
    }

    const parameters = new URLSearchParams(window.location.hash.slice(1))
    parameters.delete(sessionTokenFragmentKey)
    const remainingFragment = parameters.toString()
    window.history.replaceState(
      window.history.state,
      '',
      `${window.location.pathname}${window.location.search}${remainingFragment ? `#${remainingFragment}` : ''}`,
    )
    return launchToken
  }

  try {
    return window.sessionStorage.getItem(sessionTokenStorageKey)
  } catch {
    return null
  }
}

export function getEngineConnection(): Promise<EngineConnection> {
  return Promise.resolve(
    resolveEngineConnection(
      import.meta.env.DEV,
      import.meta.env,
      window.location.origin,
      browserSessionToken(),
    ),
  )
}

export function createEngineClient(connection: EngineConnection) {
  if (connection.phase !== 'ready' || !connection.baseUrl || !connection.sessionToken) {
    throw new Error('Engine connection is not ready')
  }

  const baseUrl = validateLoopbackBaseUrl(connection.baseUrl)
  const sessionToken = connection.sessionToken

  const errorFromResponse = async (response: Response): Promise<Error> => {
    let message: string | null = null
    try {
      const payload: unknown = await response.json()
      if (isRecord(payload)) {
        if (typeof payload.message === 'string') {
          message = payload.message
        } else if (typeof payload.detail === 'string') {
          message = payload.detail
        } else if (isRecord(payload.error) && typeof payload.error.message === 'string') {
          message = payload.error.message
        }
      }
    } catch {
      // A non-JSON response still receives the stable status-only fallback below.
    }

    if (message) {
      const safeMessage = Array.from(message.replaceAll(sessionToken, '[redacted]'))
        .map((character) => {
          const code = character.charCodeAt(0)
          return code < 32 || code === 127 ? ' ' : character
        })
        .join('')
        .trim()
        .slice(0, 300)
      if (safeMessage) {
        return new Error(`Engine request failed (${response.status}): ${safeMessage}`)
      }
    }
    return new Error(`Engine request failed: ${response.status}`)
  }

  const request = async <T>(path: string): Promise<T> => {
    const response = await fetch(`${baseUrl}${path}`, {
      headers: {
        'X-WFMHub-Token': sessionToken,
      },
    })
    if (!response.ok) {
      throw await errorFromResponse(response)
    }
    return response.json() as Promise<T>
  }

  const post = async <T>(path: string, body: unknown): Promise<T> => {
    const response = await fetch(`${baseUrl}${path}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-WFMHub-Token': sessionToken,
      },
      body: JSON.stringify(body),
    })
    if (!response.ok) {
      throw await errorFromResponse(response)
    }
    return response.json() as Promise<T>
  }

  return {
    getHealth: () => request<Health>('/health'),
    getCompatibilityHealth: () => request<Health>('/compat/health'),
    getStackProbe: () => request<StackProbe>('/stack/probe'),
    saveCompatibilityReport: (report: unknown) =>
      post<SavedCompatibilityReport>('/compat/report', report),
    getRtaSourceHealth: async () =>
      decodeRtaSourceHealth(await request<unknown>('/rta/source-health')),
    refreshRtaSources: async () => decodeRtaRefreshResult(await post<unknown>('/rta/refresh', {})),
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isQuality(value: unknown): value is SourceQuality {
  return (
    isRecord(value) &&
    typeof value.error === 'number' &&
    typeof value.warning === 'number' &&
    typeof value.info === 'number'
  )
}

function isSummary(value: unknown): value is SourceRefreshSummary {
  return (
    isRecord(value) &&
    typeof value.generationId === 'number' &&
    ['running', 'succeeded', 'failed'].includes(String(value.status)) &&
    typeof value.startedAt === 'string' &&
    (value.finishedAt === null || typeof value.finishedAt === 'string') &&
    isRecord(value.counts) &&
    typeof value.counts.rosterAgents === 'number' &&
    typeof value.counts.timeOffRecords === 'number' &&
    typeof value.counts.scheduleAssignments === 'number' &&
    typeof value.counts.sourceFiles === 'number' &&
    isRecord(value.dateRange) &&
    (value.dateRange.from === null || typeof value.dateRange.from === 'string') &&
    (value.dateRange.to === null || typeof value.dateRange.to === 'string') &&
    isQuality(value.qualityCounts)
  )
}

export function decodeRtaSourceHealth(value: unknown): RtaSourceHealth {
  if (
    !isRecord(value) ||
    typeof value.status !== 'string' ||
    !isRecord(value.sourceRoot) ||
    !['default', 'configured', 'invalid'].includes(String(value.sourceRoot.mode)) ||
    !(value.activeGenerationId === null || typeof value.activeGenerationId === 'number') ||
    !(value.activeGeneration === null || isSummary(value.activeGeneration)) ||
    !(value.latestRefresh === null || isSummary(value.latestRefresh)) ||
    !isRecord(value.configuredSources) ||
    typeof value.configuredSources.fte !== 'string' ||
    typeof value.configuredSources.publishedSchedules !== 'string' ||
    !isRecord(value.sources) ||
    !isRecord(value.sources.roster) ||
    typeof value.sources.roster.ready !== 'boolean' ||
    typeof value.sources.roster.agentCount !== 'number' ||
    typeof value.sources.roster.timeOffCount !== 'number' ||
    typeof value.sources.roster.fileCount !== 'number' ||
    !isRecord(value.sources.schedule) ||
    typeof value.sources.schedule.ready !== 'boolean' ||
    typeof value.sources.schedule.shiftCount !== 'number' ||
    typeof value.sources.schedule.fileCount !== 'number' ||
    !(
      value.sources.schedule.minDate === null || typeof value.sources.schedule.minDate === 'string'
    ) ||
    !(
      value.sources.schedule.maxDate === null || typeof value.sources.schedule.maxDate === 'string'
    ) ||
    !isQuality(value.quality) ||
    typeof value.ready !== 'boolean'
  ) {
    throw new Error('Local source-health response did not match the supported contract')
  }
  return value as RtaSourceHealth
}

export function decodeRtaRefreshResult(value: unknown): RtaRefreshResult {
  if (!isRecord(value) || value.status !== 'succeeded' || typeof value.generationId !== 'number') {
    throw new Error('Local refresh response did not match the supported contract')
  }
  return {
    status: 'succeeded',
    generationId: value.generationId,
    sourceHealth: decodeRtaSourceHealth(value.sourceHealth),
  }
}
