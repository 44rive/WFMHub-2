import type { EngineConnection } from '../lib/api'
import type { CompatibilityReport, ProbeName, ProbeResult, WorkerResponse } from './types'

export const probeOrder: ProbeName[] = [
  'host_sqlite',
  'wasm_worker',
  'duckdb_opfs',
  'pyodide_forecasting',
  'highs_mip',
]

export const probeLabels: Record<ProbeName, { title: string; description: string }> = {
  host_sqlite: {
    title: 'Portable Python + SQLite host',
    description: 'Confirms the stdlib-only loopback host started without native third-party DLLs.',
  },
  wasm_worker: {
    title: 'WebAssembly inside a Worker',
    description: 'Proves Edge policy permits application WebAssembly outside the UI thread.',
  },
  duckdb_opfs: {
    title: 'DuckDB-Wasm + OPFS reopen',
    description: 'Writes, checkpoints, closes, reopens and reads a browser-private analytical DB.',
  },
  pyodide_forecasting: {
    title: 'Pyodide forecasting stack',
    description: 'Loads offline NumPy, scikit-learn and statsmodels and fits two small models.',
  },
  highs_mip: {
    title: 'HiGHS-Wasm integer optimization',
    description: 'Solves a small constrained staffing allocation as a browser MIP.',
  },
}

type ProgressCallback = (name: ProbeName) => void

function normalizeError(error: unknown): ProbeResult['error'] {
  if (error instanceof Error) {
    return { type: error.name || 'Error', message: error.message.slice(0, 2000) }
  }
  return { type: 'Error', message: String(error).slice(0, 2000) }
}

async function timedProbe(
  name: ProbeName,
  operation: () => Promise<Record<string, unknown>>,
): Promise<ProbeResult> {
  const started = performance.now()
  try {
    const details = await operation()
    return {
      name,
      status: 'pass',
      durationMs: Math.round(performance.now() - started),
      details,
    }
  } catch (error) {
    return {
      name,
      status: 'fail',
      durationMs: Math.round(performance.now() - started),
      error: normalizeError(error),
    }
  }
}

function runWorker(worker: Worker, timeoutMs: number): Promise<Record<string, unknown>> {
  return new Promise((resolve, reject) => {
    const timeout = window.setTimeout(() => {
      worker.terminate()
      reject(new Error(`Probe exceeded ${Math.round(timeoutMs / 1000)} seconds`))
    }, timeoutMs)

    worker.addEventListener(
      'message',
      (event: MessageEvent<WorkerResponse>) => {
        window.clearTimeout(timeout)
        worker.terminate()
        if (event.data.ok) {
          resolve(event.data.details)
        } else {
          const error = new Error(event.data.error.message)
          error.name = event.data.error.type
          reject(error)
        }
      },
      { once: true },
    )
    worker.addEventListener(
      'error',
      (event) => {
        window.clearTimeout(timeout)
        worker.terminate()
        reject(new Error(event.message || 'Worker failed before returning a result'))
      },
      { once: true },
    )
    worker.postMessage({ run: true })
  })
}

function hostProbe(connection: EngineConnection): Promise<Record<string, unknown>> {
  if (connection.phase !== 'ready' || !connection.baseUrl || !connection.sessionToken) {
    return Promise.reject(new Error('Portable host session is unavailable'))
  }
  return fetch(`${connection.baseUrl}/compat/health`, {
    headers: { 'X-WFMHub-Token': connection.sessionToken },
  }).then(async (response) => {
    if (!response.ok) {
      throw new Error(`Host health returned HTTP ${response.status}`)
    }
    const health = (await response.json()) as Record<string, unknown>
    if (health.thirdPartyHostNativeFiles !== 0) {
      throw new Error('Compatibility host unexpectedly reports native third-party dependencies')
    }
    return health
  })
}

function operation(name: ProbeName, connection: EngineConnection) {
  switch (name) {
    case 'host_sqlite':
      return () => hostProbe(connection)
    case 'wasm_worker':
      return () =>
        runWorker(
          new Worker(new URL('../workers/basicWasm.worker.ts', import.meta.url), {
            type: 'module',
          }),
          30_000,
        )
    case 'duckdb_opfs':
      return () =>
        runWorker(
          new Worker(new URL('../workers/duckdbOpfs.worker.ts', import.meta.url), {
            type: 'module',
          }),
          180_000,
        )
    case 'pyodide_forecasting':
      return () =>
        runWorker(
          new Worker(new URL('../workers/pyodideForecast.worker.ts', import.meta.url), {
            type: 'module',
          }),
          360_000,
        )
    case 'highs_mip':
      return () =>
        runWorker(
          new Worker(new URL('../workers/highsMip.worker.ts', import.meta.url), {
            type: 'module',
          }),
          180_000,
        )
  }
}

function environment(): CompatibilityReport['environment'] {
  const extendedNavigator = navigator as Navigator & { deviceMemory?: number }
  return {
    userAgent: navigator.userAgent,
    language: navigator.language,
    online: navigator.onLine,
    secureContext: window.isSecureContext,
    crossOriginIsolated: window.crossOriginIsolated,
    hardwareConcurrency: navigator.hardwareConcurrency || null,
    deviceMemoryGiB: extendedNavigator.deviceMemory ?? null,
  }
}

export async function runCompatibilityReport(
  connection: EngineConnection,
  onProgress: ProgressCallback,
): Promise<CompatibilityReport> {
  const startedAt = new Date().toISOString()
  const results: ProbeResult[] = []
  for (const name of probeOrder) {
    onProgress(name)
    results.push(await timedProbe(name, operation(name, connection)))
  }
  return {
    schemaVersion: 1,
    profile: 'phase0.4-hybrid-compatibility-spike',
    startedAt,
    completedAt: new Date().toISOString(),
    overallStatus: results.every((result) => result.status === 'pass') ? 'pass' : 'fail',
    environment: environment(),
    probes: results,
  }
}
