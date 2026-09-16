import { useQuery } from '@tanstack/react-query'
import { getHealth } from '../lib/api'

const capabilities = [
  {
    title: 'RTA Command Center',
    text: 'Current service, staffing, attendance evidence and the next 2–4 hours of operational risk.',
    tag: 'Observe',
  },
  {
    title: 'Gap Decomposition',
    text: 'Separate demand, schedule shape, absence, lateness, shrinkage and execution loss.',
    tag: 'Explain',
  },
  {
    title: 'Intervention Engine',
    text: 'Rank eligible actions by expected recovery, confidence, constraints and operational cost.',
    tag: 'Recommend',
  },
  {
    title: 'Decision Learning',
    text: 'Record actions and outcomes so the product learns which interventions work by context.',
    tag: 'Learn',
  },
]

const horizons = [
  ['Intraday', 'Now → hours', 'RTA, service recovery, attendance, risk and interventions'],
  ['Tactical', 'Tomorrow → 12 weeks', 'Forecast, staffing, scheduling, shrinkage and scenarios'],
  ['Strategic', 'Months → 18+ months', 'Capacity, hiring, attrition, budget and workforce strategy'],
]

const stack = [
  'Tauri 2',
  'React 19.3',
  'Python 3.14',
  'DuckDB + DuckLake',
  'Polars',
  'OR-Tools',
  'StatsForecast / XGBoost',
]

export function HomePage() {
  const health = useQuery({
    queryKey: ['engine-health'],
    queryFn: getHealth,
    refetchInterval: 15_000,
  })

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto max-w-[1480px] px-6 py-7 lg:px-10">
        <header className="mb-10 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="grid size-12 place-items-center rounded-2xl bg-blue-400 font-black text-slate-950 shadow-lg shadow-blue-500/20">
              W2
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-blue-300">Workforce Intelligence</p>
              <h1 className="text-2xl font-semibold tracking-tight">WFMHub 2.0</h1>
            </div>
          </div>
          <div className="rounded-full border border-slate-700 bg-slate-900/70 px-4 py-2 text-sm text-slate-300">
            Engine: {health.isSuccess ? `${health.data.status} · ${health.data.version}` : health.isError ? 'offline' : 'connecting'}
          </div>
        </header>

        <section className="grid gap-5 xl:grid-cols-[1.45fr_.55fr]">
          <article className="rounded-3xl border border-slate-800 bg-slate-900/70 p-8 shadow-2xl shadow-black/20">
            <p className="mb-4 text-xs font-semibold uppercase tracking-[0.24em] text-blue-300">Product vision</p>
            <h2 className="max-w-4xl text-4xl font-semibold leading-tight tracking-[-0.04em] md:text-6xl">
              From real-time control to workforce strategy.
            </h2>
            <p className="mt-6 max-w-4xl text-lg leading-8 text-slate-300">
              Tell the WFM user what is happening, why it is happening, what is likely to happen next, which action has the best expected impact, and whether that action worked.
            </p>
            <p className="mt-5 max-w-4xl leading-7 text-slate-400">
              WFMHub is a vendor-neutral decision layer above schedules, forecasts, telephony, attendance and operational evidence. The WFM model is the product; the stack exists to make that product fast, portable and auditable.
            </p>
          </article>

          <aside className="rounded-3xl border border-slate-800 bg-slate-900/70 p-7">
            <p className="mb-5 text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">Decision loop</p>
            <div className="grid gap-2">
              {['Observe', 'Explain', 'Predict', 'Recommend', 'Decide', 'Measure', 'Learn'].map((step, index) => (
                <div key={step} className="flex items-center gap-3 rounded-xl border border-slate-800 bg-slate-950/70 px-4 py-3">
                  <span className="grid size-7 place-items-center rounded-lg bg-blue-400/10 text-xs font-bold text-blue-300">{index + 1}</span>
                  <span className="font-medium text-slate-200">{step}</span>
                </div>
              ))}
            </div>
          </aside>
        </section>

        <section className="mt-10">
          <div className="mb-4 flex items-end justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">Intelligence products</p>
              <h3 className="mt-1 text-xl font-semibold">The operational core</h3>
            </div>
          </div>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {capabilities.map((item) => (
              <article key={item.title} className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
                <span className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-300">{item.tag}</span>
                <h4 className="mt-3 font-semibold text-slate-100">{item.title}</h4>
                <p className="mt-2 text-sm leading-6 text-slate-400">{item.text}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="mt-10 grid gap-4 lg:grid-cols-3">
          {horizons.map(([title, period, description]) => (
            <article key={title} className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">{period}</p>
              <div className="mt-2 text-3xl font-semibold tracking-tight">{title}</div>
              <p className="mt-3 text-sm leading-6 text-slate-400">{description}</p>
            </article>
          ))}
        </section>

        <section className="mt-10 rounded-2xl border border-slate-800 bg-slate-900/50 p-6">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">2026 greenfield baseline</p>
          <div className="mt-4 flex flex-wrap gap-2">
            {stack.map((item) => (
              <span key={item} className="rounded-full border border-slate-700 bg-slate-950 px-3 py-1.5 text-sm text-slate-300">
                {item}
              </span>
            ))}
          </div>
        </section>
      </div>
    </main>
  )
}
