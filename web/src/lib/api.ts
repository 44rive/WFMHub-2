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

export type RefreshProgress = {
  status: 'running'
  stage: string
  message: string
  completedFiles: number
  totalFiles: number
  startedAt: string
  elapsedSeconds: number
}

export type SourceRefreshSummary = {
  generationId: number
  status: 'running' | 'succeeded' | 'failed'
  startedAt: string
  finishedAt: string | null
  counts: {
    rosterAgents: number
    timeOffRecords: number
    scheduleAssignments: number
    agentStatusRows: number
    liloRows: number
    rawCallLegs: number
    canonicalCallLegs: number
    serviceIntervals: number
    attendanceAgentDays: number
    attendanceGapFragments: number
    statusPrimaryDays: number
    attendanceUnknownDays: number
    sourceFiles: number
    scheduleFiles: number
    agentStatusFiles: number
    liloFiles: number
    callFiles: number
  }
  dateRange: { from: string | null; to: string | null }
  actualDateRanges: {
    agentStatus: { from: string | null; to: string | null }
    lilo: { from: string | null; to: string | null }
    callByCall: { from: string | null; to: string | null }
    attendance: { from: string | null; to: string | null }
  }
  qualityCounts: SourceQuality
  failureCode?: string
}

export type RtaSourceHealth = {
  status: string
  sourceRoot: SourceRoot
  activeGenerationId: number | null
  activeGeneration: SourceRefreshSummary | null
  latestRefresh: SourceRefreshSummary | null
  refreshProgress: RefreshProgress | null
  configuredSources: {
    fte: string
    publishedSchedules: string
    agentStatus: string
    lilo: string
    callByCall: string
  }
  sources: {
    roster: { ready: boolean; agentCount: number; timeOffCount: number; fileCount: number }
    schedule: {
      ready: boolean
      shiftCount: number
      fileCount: number
      minDate: string | null
      maxDate: string | null
    }
    agentStatus: {
      ready: boolean
      rowCount: number
      fileCount: number
      minDate: string | null
      maxDate: string | null
    }
    lilo: {
      ready: boolean
      rowCount: number
      fileCount: number
      minDate: string | null
      maxDate: string | null
    }
    callByCall: {
      ready: boolean
      rawLegCount: number
      canonicalLegCount: number
      serviceIntervalCount: number
      fileCount: number
      minDate: string | null
      maxDate: string | null
    }
    attendance: {
      ready: boolean
      agentDayCount: number
      gapFragmentCount: number
      statusPrimaryCount: number
      unknownCount: number
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
  unchanged: boolean
  durationMs: number
  sourceHealth: RtaSourceHealth
}

export type ServiceScope = { serviceScope: string; comparisonScope: string }

export type ServiceInterval = {
  intervalStart: string
  intervalEnd: string
  offered: number
  answered: number
  abandoned: number
  shortAbandoned: number
  abandonedWithinTarget: number
  answeredWithinTarget: number
  talkSeconds: number
  holdSeconds: number
  wrapSeconds: number
  handledSeconds: number
  callLegs: number
  transferredLegs: number
}

export type RtaOperateEvidence = {
  status: 'ready' | 'not_ready'
  reason: null | 'NO_ACTIVE_GENERATION' | 'SOURCE_ROOT_UNAVAILABLE' | 'SOURCE_ROOT_CHANGED'
  businessDate: string
  generationId: number | null
  serviceScopes: ServiceScope[]
  selectedScope: ServiceScope | null
  serviceIntervals: ServiceInterval[]
  attendance: {
    scope: 'date-wide'
    evidenceStates: { state: string; agentDays: number }[]
    gapTypes: { type: string; fragments: number; minutes: number }[]
  }
}

export type FlashProfileOption = { id: string; label: string }
export type ServiceComponents = Omit<ServiceInterval, 'intervalStart' | 'intervalEnd'>
export type FlashServiceHour = ServiceComponents & { hourStart: string }
export type FlashParityEvidence = {
  status: 'ready' | 'not_ready'
  reason: RtaOperateEvidence['reason']
  businessDate: string
  generationId: number | null
  catalogSha256: string | null
  profiles: FlashProfileOption[]
  selectedProfile: FlashProfileOption | null
  serviceHours: FlashServiceHour[]
  totals: ServiceComponents | null
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
    getRtaOperateEvidence: async (date: string, scope?: ServiceScope) => {
      if (!isBusinessDate(date)) throw new Error('Select a valid business date')
      const parameters = new URLSearchParams({ date })
      if (scope) {
        if (!scope.serviceScope || !scope.comparisonScope) {
          throw new Error('Select both parts of a service scope')
        }
        parameters.set('serviceScope', scope.serviceScope)
        parameters.set('comparisonScope', scope.comparisonScope)
      }
      const evidence = decodeRtaOperateEvidence(
        await request<unknown>(`/rta/operate-evidence?${parameters.toString()}`),
      )
      if (
        evidence.businessDate !== date ||
        (scope &&
          evidence.status === 'ready' &&
          (evidence.selectedScope?.serviceScope !== scope.serviceScope ||
            evidence.selectedScope?.comparisonScope !== scope.comparisonScope))
      ) {
        throw new Error('Local Operate evidence did not match the selected date and scope')
      }
      return evidence
    },
    getFlashParityEvidence: async (date: string, profile?: string) => {
      if (!isBusinessDate(date)) throw new Error('Select a valid business date')
      if (profile && !/^[a-z0-9_]{1,40}$/.test(profile)) {
        throw new Error('Select a valid Flash profile')
      }
      const parameters = new URLSearchParams({ date })
      if (profile) parameters.set('profile', profile)
      const result = decodeFlashParityEvidence(
        await request<unknown>(`/rta/flash-parity?${parameters.toString()}`),
      )
      if (
        result.businessDate !== date ||
        (profile && result.status === 'ready' && result.selectedProfile?.id !== profile)
      ) {
        throw new Error('Local Flash evidence did not match the selected date and profile')
      }
      return result
    },
  }
}

export function isBusinessDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  const date = new Date(`${value}T00:00:00Z`)
  return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value
}

function isCount(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0
}

function isSeconds(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0
}

function isServiceScope(value: unknown): value is ServiceScope {
  return (
    isRecord(value) &&
    typeof value.serviceScope === 'string' &&
    value.serviceScope.length > 0 &&
    typeof value.comparisonScope === 'string' &&
    value.comparisonScope.length > 0
  )
}

function isServiceComponents(value: unknown): value is ServiceComponents {
  return (
    isRecord(value) &&
    isCount(value.offered) &&
    isCount(value.answered) &&
    isCount(value.abandoned) &&
    isCount(value.shortAbandoned) &&
    isCount(value.abandonedWithinTarget) &&
    isCount(value.answeredWithinTarget) &&
    isSeconds(value.talkSeconds) &&
    isSeconds(value.holdSeconds) &&
    isSeconds(value.wrapSeconds) &&
    isSeconds(value.handledSeconds) &&
    isCount(value.callLegs) &&
    isCount(value.transferredLegs)
  )
}

function isServiceInterval(value: unknown): value is ServiceInterval {
  return (
    isRecord(value) &&
    typeof value.intervalStart === 'string' &&
    typeof value.intervalEnd === 'string' &&
    isServiceComponents(value)
  )
}

function isFlashProfileOption(value: unknown): value is FlashProfileOption {
  return (
    isRecord(value) &&
    typeof value.id === 'string' &&
    /^[a-z0-9_]{1,40}$/.test(value.id) &&
    typeof value.label === 'string' &&
    value.label.length > 0
  )
}

export function decodeFlashParityEvidence(value: unknown): FlashParityEvidence {
  if (
    !isRecord(value) ||
    !['ready', 'not_ready'].includes(String(value.status)) ||
    ![null, 'NO_ACTIVE_GENERATION', 'SOURCE_ROOT_UNAVAILABLE', 'SOURCE_ROOT_CHANGED'].includes(
      value.reason as string | null,
    ) ||
    !isBusinessDate(String(value.businessDate)) ||
    !(value.generationId === null || isCount(value.generationId)) ||
    !(
      value.catalogSha256 === null ||
      (typeof value.catalogSha256 === 'string' && /^[0-9a-f]{64}$/.test(value.catalogSha256))
    ) ||
    !Array.isArray(value.profiles) ||
    !value.profiles.every(isFlashProfileOption) ||
    !(value.selectedProfile === null || isFlashProfileOption(value.selectedProfile)) ||
    !Array.isArray(value.serviceHours) ||
    !value.serviceHours.every(
      (hour: unknown) =>
        isRecord(hour) && typeof hour.hourStart === 'string' && isServiceComponents(hour),
    ) ||
    !(value.totals === null || isServiceComponents(value.totals)) ||
    (value.status === 'ready' &&
      (value.reason !== null ||
        value.generationId === null ||
        value.catalogSha256 === null ||
        value.selectedProfile === null)) ||
    (value.status === 'not_ready' && value.reason === null)
  ) {
    throw new Error('Local Flash parity response did not match the supported contract')
  }
  return value as FlashParityEvidence
}

export function decodeRtaOperateEvidence(value: unknown): RtaOperateEvidence {
  if (
    !isRecord(value) ||
    !['ready', 'not_ready'].includes(String(value.status)) ||
    ![null, 'NO_ACTIVE_GENERATION', 'SOURCE_ROOT_UNAVAILABLE', 'SOURCE_ROOT_CHANGED'].includes(
      value.reason as string | null,
    ) ||
    !isBusinessDate(String(value.businessDate)) ||
    !(value.generationId === null || isCount(value.generationId)) ||
    !Array.isArray(value.serviceScopes) ||
    !value.serviceScopes.every(isServiceScope) ||
    !(value.selectedScope === null || isServiceScope(value.selectedScope)) ||
    !Array.isArray(value.serviceIntervals) ||
    !value.serviceIntervals.every(isServiceInterval) ||
    !isRecord(value.attendance) ||
    value.attendance.scope !== 'date-wide' ||
    !Array.isArray(value.attendance.evidenceStates) ||
    !value.attendance.evidenceStates.every(
      (item: unknown) =>
        isRecord(item) && typeof item.state === 'string' && isCount(item.agentDays),
    ) ||
    !Array.isArray(value.attendance.gapTypes) ||
    !value.attendance.gapTypes.every(
      (item: unknown) =>
        isRecord(item) &&
        typeof item.type === 'string' &&
        isCount(item.fragments) &&
        isSeconds(item.minutes),
    ) ||
    (value.status === 'ready' && (value.reason !== null || value.generationId === null)) ||
    (value.status === 'not_ready' && value.reason === null)
  ) {
    throw new Error('Local Operate evidence response did not match the supported contract')
  }
  return value as RtaOperateEvidence
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

function isDateRange(value: unknown): value is { from: string | null; to: string | null } {
  return (
    isRecord(value) &&
    (value.from === null || typeof value.from === 'string') &&
    (value.to === null || typeof value.to === 'string')
  )
}

function isActualSource(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.ready === 'boolean' &&
    typeof value.rowCount === 'number' &&
    typeof value.fileCount === 'number' &&
    (value.minDate === null || typeof value.minDate === 'string') &&
    (value.maxDate === null || typeof value.maxDate === 'string')
  )
}

function isAttendanceSource(value: unknown): boolean {
  return (
    isRecord(value) &&
    typeof value.ready === 'boolean' &&
    typeof value.agentDayCount === 'number' &&
    typeof value.gapFragmentCount === 'number' &&
    typeof value.statusPrimaryCount === 'number' &&
    typeof value.unknownCount === 'number' &&
    (value.minDate === null || typeof value.minDate === 'string') &&
    (value.maxDate === null || typeof value.maxDate === 'string')
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
    typeof value.counts.agentStatusRows === 'number' &&
    typeof value.counts.liloRows === 'number' &&
    typeof value.counts.rawCallLegs === 'number' &&
    typeof value.counts.canonicalCallLegs === 'number' &&
    typeof value.counts.serviceIntervals === 'number' &&
    typeof value.counts.attendanceAgentDays === 'number' &&
    typeof value.counts.attendanceGapFragments === 'number' &&
    typeof value.counts.statusPrimaryDays === 'number' &&
    typeof value.counts.attendanceUnknownDays === 'number' &&
    typeof value.counts.sourceFiles === 'number' &&
    typeof value.counts.scheduleFiles === 'number' &&
    typeof value.counts.agentStatusFiles === 'number' &&
    typeof value.counts.liloFiles === 'number' &&
    typeof value.counts.callFiles === 'number' &&
    isDateRange(value.dateRange) &&
    isRecord(value.actualDateRanges) &&
    isDateRange(value.actualDateRanges.agentStatus) &&
    isDateRange(value.actualDateRanges.lilo) &&
    isDateRange(value.actualDateRanges.callByCall) &&
    isDateRange(value.actualDateRanges.attendance) &&
    isQuality(value.qualityCounts)
  )
}

function isRefreshProgress(value: unknown): value is RefreshProgress {
  return (
    isRecord(value) &&
    value.status === 'running' &&
    typeof value.stage === 'string' &&
    typeof value.message === 'string' &&
    typeof value.completedFiles === 'number' &&
    typeof value.totalFiles === 'number' &&
    typeof value.startedAt === 'string' &&
    typeof value.elapsedSeconds === 'number'
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
    !(value.refreshProgress === null || isRefreshProgress(value.refreshProgress)) ||
    !isRecord(value.configuredSources) ||
    typeof value.configuredSources.fte !== 'string' ||
    typeof value.configuredSources.publishedSchedules !== 'string' ||
    typeof value.configuredSources.agentStatus !== 'string' ||
    typeof value.configuredSources.lilo !== 'string' ||
    typeof value.configuredSources.callByCall !== 'string' ||
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
    !isActualSource(value.sources.agentStatus) ||
    !isActualSource(value.sources.lilo) ||
    !isRecord(value.sources.callByCall) ||
    typeof value.sources.callByCall.ready !== 'boolean' ||
    typeof value.sources.callByCall.rawLegCount !== 'number' ||
    typeof value.sources.callByCall.canonicalLegCount !== 'number' ||
    typeof value.sources.callByCall.serviceIntervalCount !== 'number' ||
    typeof value.sources.callByCall.fileCount !== 'number' ||
    !(
      value.sources.callByCall.minDate === null ||
      typeof value.sources.callByCall.minDate === 'string'
    ) ||
    !(
      value.sources.callByCall.maxDate === null ||
      typeof value.sources.callByCall.maxDate === 'string'
    ) ||
    !isAttendanceSource(value.sources.attendance) ||
    !isQuality(value.quality) ||
    typeof value.ready !== 'boolean'
  ) {
    throw new Error('Local source-health response did not match the supported contract')
  }
  return value as RtaSourceHealth
}

export function decodeRtaRefreshResult(value: unknown): RtaRefreshResult {
  if (
    !isRecord(value) ||
    value.status !== 'succeeded' ||
    typeof value.generationId !== 'number' ||
    typeof value.unchanged !== 'boolean' ||
    typeof value.durationMs !== 'number'
  ) {
    throw new Error('Local refresh response did not match the supported contract')
  }
  return {
    status: 'succeeded',
    generationId: value.generationId,
    unchanged: value.unchanged,
    durationMs: value.durationMs,
    sourceHealth: decodeRtaSourceHealth(value.sourceHealth),
  }
}
