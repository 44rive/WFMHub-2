import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { createEngineClient, getEngineConnection } from '../lib/api'

export function FoundationPage() {
  const connection = useQuery({
    queryKey: ['engine-connection'],
    queryFn: getEngineConnection,
    retry: false,
  })
  const host = useQuery({
    queryKey: ['compatibility-health', connection.data?.baseUrl],
    queryFn: () => {
      if (!connection.data) throw new Error('Local host connection is unavailable')
      return createEngineClient(connection.data).getCompatibilityHealth()
    },
    enabled: connection.data?.phase === 'ready',
    retry: false,
  })

  const hostReady = host.data?.status === 'ok'
  const checking = connection.isPending || (connection.data?.phase === 'ready' && host.isPending)
  const status = hostReady ? 'Host connected' : checking ? 'Checking host' : 'Host unavailable'
  const statusTone = hostReady ? 'ready' : checking ? 'checking' : 'unavailable'
  const detail = hostReady
    ? `Portable host ${host.data?.version ?? 'version unknown'} is responding on this device.`
    : host.error instanceof Error
      ? host.error.message
      : host.data
        ? `Portable host returned status ${host.data.status}; it is not ready for this session.`
        : (connection.data?.message ?? 'Open WFMHub through its local launcher.')

  return (
    <main id="main-content" className="product-main">
      <div className="product-container">
        <div className="page-intro">
          <div>
            <p className="eyebrow">Command / product foundation</p>
            <h1 tabIndex={-1}>Workforce decision workbench</h1>
            <p className="page-lede">
              One local place for evidence, planning, decisions, and outcomes. The Phase 1 RTA
              workflow is being built; this screen reports platform readiness only.
            </p>
          </div>
          <Link to="/compatibility" className="button button-secondary">
            Open compatibility doctor
          </Link>
        </div>

        <section className="evidence-strip" aria-label="Current evidence status">
          <div className="evidence-strip-item">
            <span className="evidence-label">Local platform</span>
            <span className={`state-pill state-${statusTone}`} role="status">
              {status}
            </span>
          </div>
          <div className="evidence-strip-item">
            <span className="evidence-label">RTA business evidence</span>
            <span className="evidence-value">Not connected</span>
          </div>
          <div className="evidence-strip-item">
            <span className="evidence-label">Operational data cut</span>
            <span className="evidence-value">Not connected</span>
          </div>
        </section>

        <div className="product-grid">
          <RtaEmptyState />

          <aside className="panel" aria-labelledby="platform-heading">
            <div className="panel-heading">
              <p className="eyebrow">Platform status</p>
              <h2 id="platform-heading">Local runtime</h2>
            </div>
            <p className="status-detail">{detail}</p>
            <dl className="fact-list">
              <div>
                <dt>Host</dt>
                <dd>{hostReady ? 'Portable host responded' : 'Not verified in this session'}</dd>
              </div>
              <div>
                <dt>Business data</dt>
                <dd>Not connected</dd>
              </div>
              <div>
                <dt>Browser analytics</dt>
                <dd>Optional; inspect in doctor</dd>
              </div>
            </dl>
            <Link to="/compatibility" className="text-link">
              Run the five capability probes <span aria-hidden="true">→</span>
            </Link>
          </aside>
        </div>

        <section className="panel next-slice" aria-labelledby="next-slice-heading">
          <div className="panel-heading">
            <p className="eyebrow">Delivery path</p>
            <h2 id="next-slice-heading">What becomes usable next</h2>
          </div>
          <ol className="delivery-steps">
            <li>
              <strong>Read-only source refresh</strong>
              <span>Map old-product source contracts into canonical SQLite evidence.</span>
            </li>
            <li>
              <strong>Governed RTA position</strong>
              <span>Validate service, attendance, and staffing gaps at their natural grains.</span>
            </li>
            <li>
              <strong>Decision workflow</strong>
              <span>
                Expose inspection, human action records, outcomes, and local Excel delivery.
              </span>
            </li>
          </ol>
        </section>
      </div>
    </main>
  )
}

export function RtaEmptyState() {
  return (
    <section className="panel panel-feature" aria-labelledby="first-slice-heading">
      <div className="panel-heading">
        <p className="eyebrow">Phase 1 / first governed slice</p>
        <h2 id="first-slice-heading">RTA Command Center is not connected yet</h2>
      </div>
      <p>
        This screen cannot show service level, staffing gap, attendance position, or an action queue
        until a governed RTA data API is connected. Missing evidence will remain unknown—not zero,
        absent, or compliant.
      </p>
      <div className="empty-state">
        <span className="empty-state-icon" aria-hidden="true">
          —
        </span>
        <div>
          <strong>No operational metrics to display</strong>
          <span>This screen is not connected to a governed RTA data API yet.</span>
        </div>
      </div>
    </section>
  )
}
