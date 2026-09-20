import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { probeLabels, probeOrder, runCompatibilityReport } from '../compatibility/runner'
import type { CompatibilityReport, ProbeName, ProbeStatus } from '../compatibility/types'
import { createEngineClient, type EngineConnection, getEngineConnection } from '../lib/api'

const initialStatuses = (): Record<ProbeName, ProbeStatus> => ({
  host_sqlite: 'pending',
  wasm_worker: 'pending',
  duckdb_opfs: 'pending',
  pyodide_forecasting: 'pending',
  highs_mip: 'pending',
})

export function HomePage() {
  const connection = useQuery({
    queryKey: ['engine-connection'],
    queryFn: getEngineConnection,
    retry: false,
  })
  const [statuses, setStatuses] = useState(initialStatuses)
  const [running, setRunning] = useState(false)
  const [report, setReport] = useState<CompatibilityReport | null>(null)
  const [saveMessage, setSaveMessage] = useState<string | null>(null)

  const results = useMemo(
    () => new Map(report?.probes.map((probe) => [probe.name, probe]) ?? []),
    [report],
  )

  const runAll = async () => {
    if (connection.data?.phase !== 'ready') return
    setRunning(true)
    setReport(null)
    setSaveMessage(null)
    setStatuses(initialStatuses())
    try {
      const completed = await runCompatibilityReport(connection.data as EngineConnection, (name) =>
        setStatuses((current) => ({ ...current, [name]: 'running' })),
      )
      setReport(completed)
      setStatuses(
        Object.fromEntries(completed.probes.map((probe) => [probe.name, probe.status])) as Record<
          ProbeName,
          ProbeStatus
        >,
      )
      try {
        const saved = await createEngineClient(connection.data).saveCompatibilityReport(completed)
        setSaveMessage(`Saved locally to ${saved.relativePath}`)
      } catch (error) {
        setSaveMessage(
          `Tests completed, but the local report could not be saved: ${error instanceof Error ? error.message : String(error)}`,
        )
      }
    } finally {
      setRunning(false)
    }
  }

  const copyReport = async () => {
    if (!report) return
    await navigator.clipboard.writeText(JSON.stringify(report, null, 2))
    setSaveMessage('Complete report copied to the clipboard.')
  }

  const downloadReport = () => {
    if (!report) return
    const url = URL.createObjectURL(
      new Blob([`${JSON.stringify(report, null, 2)}\n`], { type: 'application/json' }),
    )
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = 'wfmhub2-hybrid-compatibility-report.json'
    anchor.click()
    URL.revokeObjectURL(url)
  }

  const connectionReady = connection.data?.phase === 'ready'
  const overall = report?.overallStatus ?? (running ? 'running' : 'not run')

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto max-w-6xl px-5 py-7 sm:px-8 lg:px-10">
        <header className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-6">
          <div className="flex items-center gap-4">
            <div className="grid size-12 place-items-center rounded-2xl bg-cyan-300 font-black text-slate-950">
              W2
            </div>
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.22em] text-cyan-300">
                Phase 0.4
              </p>
              <h1 className="text-2xl font-semibold tracking-tight">Hybrid compatibility gate</h1>
            </div>
          </div>
          <StatusBadge status={overall} />
        </header>

        <section className="mt-8 rounded-3xl border border-amber-300/25 bg-amber-300/5 p-6">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-amber-200">
            Honest scope
          </p>
          <h2 className="mt-2 text-2xl font-semibold">
            This tests the architecture. It is not the WFM product yet.
          </h2>
          <p className="mt-3 max-w-4xl leading-7 text-slate-300">
            The host uses only the already-proven portable Python, SQLite and pure-Python Excel
            boundary. Edge then tests WebAssembly analytics, forecasting and optimization. A failed
            optional probe must never stop the future RTA core.
          </p>
        </section>

        <section className="mt-6 grid gap-4 md:grid-cols-3">
          <SummaryCard
            label="Local host"
            value={connectionReady ? 'Connected' : (connection.data?.phase ?? 'Checking')}
            detail="127.0.0.1 only · per-launch token"
            good={connectionReady}
          />
          <SummaryCard
            label="Third-party host native files"
            value="Zero"
            detail="Only the official CPython runtime is native"
            good
          />
          <SummaryCard
            label="Runtime network"
            value="Not required"
            detail="All JS, WASM and Python packages are self-hosted"
            good
          />
        </section>

        {connection.data?.message ? (
          <p className="mt-5 rounded-xl border border-slate-700 bg-slate-900 px-4 py-3 text-sm text-slate-300">
            {connection.data.message}
          </p>
        ) : null}

        <section className="mt-8 rounded-3xl border border-slate-800 bg-slate-900/70 p-6 sm:p-8">
          <div className="flex flex-wrap items-end justify-between gap-5">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.2em] text-slate-400">
                Corporate-PC acceptance test
              </p>
              <h2 className="mt-2 text-2xl font-semibold">Run every capability once</h2>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
                Pyodide is the largest test and may take several minutes on first run. Keep this tab
                and the WFMHub console open.
              </p>
            </div>
            <button
              type="button"
              disabled={!connectionReady || running}
              onClick={() => void runAll()}
              className="rounded-xl bg-cyan-300 px-5 py-3 font-bold text-slate-950 transition hover:bg-cyan-200 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {running ? 'Testing…' : 'Run all probes'}
            </button>
          </div>

          <div className="mt-7 grid gap-3">
            {probeOrder.map((name, index) => {
              const result = results.get(name)
              return (
                <article
                  key={name}
                  className="grid gap-3 rounded-2xl border border-slate-800 bg-slate-950/70 p-5 md:grid-cols-[2.25rem_1fr_auto] md:items-center"
                >
                  <span className="grid size-9 place-items-center rounded-xl bg-slate-800 text-sm font-bold text-slate-300">
                    {index + 1}
                  </span>
                  <div>
                    <h3 className="font-semibold">{probeLabels[name].title}</h3>
                    <p className="mt-1 text-sm leading-6 text-slate-400">
                      {result?.error?.message ?? probeLabels[name].description}
                    </p>
                    {result?.details ? (
                      <p className="mt-2 break-words font-mono text-xs text-slate-500">
                        {JSON.stringify(result.details)}
                      </p>
                    ) : null}
                  </div>
                  <div className="flex items-center gap-3 md:justify-end">
                    {result ? (
                      <span className="text-xs text-slate-500">{result.durationMs} ms</span>
                    ) : null}
                    <StatusBadge status={statuses[name]} compact />
                  </div>
                </article>
              )
            })}
          </div>
        </section>

        {report ? (
          <section
            className={`mt-6 rounded-3xl border p-6 ${
              report.overallStatus === 'pass'
                ? 'border-emerald-300/30 bg-emerald-300/5'
                : 'border-rose-300/30 bg-rose-300/5'
            }`}
          >
            <h2 className="text-xl font-semibold">
              {report.overallStatus === 'pass'
                ? 'Hybrid browser stack passed this machine'
                : 'One or more browser capabilities are unavailable'}
            </h2>
            <p className="mt-2 text-sm leading-6 text-slate-300">
              {report.overallStatus === 'pass'
                ? 'This authorizes the next RTA vertical-slice build. It does not yet prove production-scale performance.'
                : 'This is useful evidence, not a dead end. The failed component will be removed or kept optional while Python and SQLite remain the core.'}
            </p>
            {saveMessage ? <p className="mt-3 text-sm text-slate-400">{saveMessage}</p> : null}
            <div className="mt-5 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => void copyReport()}
                className="rounded-xl border border-slate-600 px-4 py-2 text-sm font-semibold hover:border-slate-400"
              >
                Copy complete result
              </button>
              <button
                type="button"
                onClick={downloadReport}
                className="rounded-xl border border-slate-600 px-4 py-2 text-sm font-semibold hover:border-slate-400"
              >
                Download JSON
              </button>
            </div>
          </section>
        ) : null}

        <footer className="mt-8 text-sm leading-6 text-slate-500">
          After the test, close Edge and press Ctrl+C in the WFMHub console. Browser OPFS is a
          rebuildable cache; SQLite and source files remain authoritative.
        </footer>
      </div>
    </main>
  )
}

function SummaryCard({
  label,
  value,
  detail,
  good,
}: {
  label: string
  value: string
  detail: string
  good: boolean
}) {
  return (
    <article className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
      <p className="text-xs font-bold uppercase tracking-[0.18em] text-slate-500">{label}</p>
      <p className={`mt-2 text-xl font-semibold ${good ? 'text-emerald-300' : 'text-amber-200'}`}>
        {value}
      </p>
      <p className="mt-1 text-sm text-slate-400">{detail}</p>
    </article>
  )
}

function StatusBadge({ status, compact = false }: { status: string; compact?: boolean }) {
  const color =
    status === 'pass'
      ? 'border-emerald-300/30 bg-emerald-300/10 text-emerald-200'
      : status === 'fail'
        ? 'border-rose-300/30 bg-rose-300/10 text-rose-200'
        : status === 'running'
          ? 'border-cyan-300/30 bg-cyan-300/10 text-cyan-200'
          : 'border-slate-700 bg-slate-900 text-slate-400'
  return (
    <span
      className={`rounded-full border font-bold uppercase tracking-[0.15em] ${color} ${
        compact ? 'px-3 py-1 text-[0.65rem]' : 'px-4 py-2 text-xs'
      }`}
    >
      {status}
    </span>
  )
}
