import { invoke, isTauri } from '@tauri-apps/api/core'

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
    ducklake_extension: string
    ducklake_catalog_path: string
    ducklake_data_path: string
  }
  checks: ProbeCheck[]
}

type InvokeConnection = () => Promise<EngineConnection>

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
  if (url.protocol !== 'http:' || !['127.0.0.1', 'localhost'].includes(url.hostname)) {
    throw new Error('Engine URL must use HTTP on loopback')
  }
  return url.toString().replace(/\/$/, '')
}

export async function resolveEngineConnection(
  tauriRuntime: boolean,
  development: boolean,
  environment: Record<string, string | boolean | undefined>,
  invokeConnection: InvokeConnection,
): Promise<EngineConnection> {
  if (tauriRuntime) {
    const connection = await invokeConnection()
    if (connection.phase === 'ready' && connection.baseUrl) {
      return { ...connection, baseUrl: validateLoopbackBaseUrl(connection.baseUrl) }
    }
    return connection
  }

  if (!development) {
    return unavailable('The production web client must run inside the WFMHub desktop shell.')
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

export function getEngineConnection(): Promise<EngineConnection> {
  return resolveEngineConnection(isTauri(), import.meta.env.DEV, import.meta.env, () =>
    invoke<EngineConnection>('get_engine_connection'),
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
