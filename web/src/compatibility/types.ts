export type ProbeName =
  | 'host_sqlite'
  | 'wasm_worker'
  | 'duckdb_opfs'
  | 'pyodide_forecasting'
  | 'highs_mip'

export type ProbeStatus = 'pending' | 'running' | 'pass' | 'fail'

export type ProbeResult = {
  name: ProbeName
  status: 'pass' | 'fail'
  durationMs: number
  details?: Record<string, unknown>
  error?: {
    type: string
    message: string
  }
}

export type CompatibilityReport = {
  schemaVersion: 1
  profile: 'phase0.4-hybrid-compatibility-spike'
  startedAt: string
  completedAt: string
  overallStatus: 'pass' | 'fail'
  environment: {
    userAgent: string
    language: string
    online: boolean
    secureContext: boolean
    crossOriginIsolated: boolean
    hardwareConcurrency: number | null
    deviceMemoryGiB: number | null
  }
  probes: ProbeResult[]
}

export type WorkerSuccess = {
  ok: true
  details: Record<string, unknown>
}

export type WorkerFailure = {
  ok: false
  error: {
    type: string
    message: string
  }
}

export type WorkerResponse = WorkerSuccess | WorkerFailure
