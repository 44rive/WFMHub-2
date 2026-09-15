const capabilities = [
  ['RTA Command Center', 'Current service, staffing, attendance evidence and the next 2–4 hours of operational risk.', 'Intraday'],
  ['Gap Decomposition', 'Explain shortages through demand, schedule shape, absence, lateness, offline time and uncertainty.', 'Explain'],
  ['Intervention Engine', 'Rank deterministic actions by expected recovery, confidence, constraints and operational cost.', 'Recommend'],
  ['Decision Learning', 'Record actions and outcomes so WFMHub can measure which interventions work in which conditions.', 'Learn'],
]

const horizons = [
  ['Intraday', 'Now → hours', 'RTA, service recovery, attendance, risk and interventions'],
  ['Tactical', 'Tomorrow → 12 weeks', 'Forecast, staffing, scheduling, shrinkage and scenarios'],
  ['Strategic', 'Months → 18+ months', 'Capacity, hiring, attrition, budget and workforce strategy'],
]

export function App() {
  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <div className="logo">W2</div>
          <div><p className="eyebrow">Workforce Intelligence</p><h1>WFMHub 2.0</h1></div>
        </div>
        <div className="status">Architecture / bootstrap</div>
      </header>

      <main className="content">
        <section className="hero">
          <div className="panel">
            <p className="eyebrow">Product vision</p>
            <h2>From real-time control to workforce strategy.</h2>
            <p className="northstar">Tell the WFM user what is happening, why it is happening, what is likely to happen next, and which action has the best expected impact.</p>
            <p>WFMHub 2.0 is a vendor-neutral decision layer above schedules, forecasts, telephony, attendance and operational extracts. The product is the WFM operating model; the technology stack exists to make that model fast, portable and auditable.</p>
          </div>
          <aside className="panel loop">
            <p className="eyebrow">Decision loop</p>
            {['Observe', 'Explain', 'Predict', 'Recommend', 'Decide', 'Measure', 'Learn'].map(step => <span key={step}>{step}</span>)}
          </aside>
        </section>

        <h3 className="section-title">Core intelligence products</h3>
        <section className="grid">
          {capabilities.map(([title, description, tag]) => (
            <article className="card" key={title}><strong>{title}</strong><p>{description}</p><span className="tag">{tag}</span></article>
          ))}
        </section>

        <h3 className="section-title">One platform, three planning horizons</h3>
        <section className="grid horizons">
          {horizons.map(([title, period, description]) => (
            <article className="card" key={title}><span className="eyebrow">{period}</span><div className="metric">{title}</div><p>{description}</p></article>
          ))}
        </section>

        <p className="footer-note">Initial UI shell — live service, coverage, risk, forecast, scenario and intervention views will replace these product cards as domain modules land.</p>
      </main>
    </div>
  )
}
