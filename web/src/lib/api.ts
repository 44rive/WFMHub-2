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
  const request = async <T>(path: string): Promise<T> => {
    const response = await fetch(`${baseUrl}${path}`, {
      headers: {
        'X-WFMHub-Token': connection.sessionToken as string,
      },
    })
    if (!response.ok) {
      throw new Error(`Engine request failed: ${response.status}`)
    }
    return response.json() as Promise<T>
  }

  return {
    getHealth: () => request<Health>('/health'),
    getStackProbe: () => request<StackProbe>('/stack/probe'),
  }
}
