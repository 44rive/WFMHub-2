import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { createEngineClient, getEngineConnection, type RtaSourceHealth } from '../lib/api'

export function FoundationPage() {
  const queryClient = useQueryClient()
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

  const refresh = useMutation({
    mutationFn: () => {
      if (!connection.data) throw new Error('Local host connection is unavailable')
      return createEngineClient(connection.data).refreshRtaSources()
    },
    onSuccess: (result) => {
      queryClient.setQueryData(['rta-source-health', connection.data?.baseUrl], result.sourceHealth)
    },
    onError: () => {
      void queryClient.invalidateQueries({ queryKey: ['rta-source-health'] })
    },
  })
  const sourceHealth = useQuery({
    queryKey: ['rta-source-health', connection.data?.baseUrl],
    queryFn: () => {
      if (!connection.data) throw new Error('Local host connection is unavailable')
      return createEngineClient(connection.data).getRtaSourceHealth()
    },
    enabled: host.data?.status === 'ok' && connection.data?.phase === 'ready',
    retry: false,
    refetchInterval: refresh.isPending ? 750 : false,
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
              workflow is being built; this screen shows local source readiness, not operational
              KPIs.
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
            <span className="evidence-value">
              {sourceHealth.data?.ready ? 'Validated local sources' : 'Not ready'}
            </span>
          </div>
          <div className="evidence-strip-item">
            <span className="evidence-label">Operational data cut</span>
            <span className="evidence-value">
              {sourceHealth.data?.ready ? formatDateRange(sourceHealth.data) : 'Unknown'}
            </span>
          </div>
        </section>

        <div className="product-grid">
          <RtaSourcePanel
            health={sourceHealth.data}
            loading={hostReady && sourceHealth.isPending}
            error={refresh.error ?? sourceHealth.error}
            refreshing={refresh.isPending}
            refreshUnchanged={refresh.data?.unchanged ?? false}
            canRefresh={hostReady && connection.data?.phase === 'ready'}
            onRefresh={() => refresh.mutate()}
          />

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
                <dd>{sourceHealth.data?.ready ? 'Local source cut validated' : 'Not ready'}</dd>
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
              <span>FTE and published schedule evidence into generation-scoped SQLite.</span>
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

function formatDateRange(health: RtaSourceHealth): string {
  const from = health.sources.schedule.minDate
  const to = health.sources.schedule.maxDate
  if (!from || !to) return 'Unknown'
  return from === to ? from : `${from} – ${to}`
}

type RtaSourcePanelProps = {
  health?: RtaSourceHealth
  loading: boolean
  error: Error | null
  refreshing: boolean
  refreshUnchanged?: boolean
  canRefresh: boolean
  onRefresh: () => void
}

export function RtaSourcePanel({
  health,
  loading,
  error,
  refreshing,
  refreshUnchanged = false,
  canRefresh,
  onRefresh,
}: RtaSourcePanelProps) {
  const latestFailed = health?.latestRefresh?.status === 'failed' && !refreshUnchanged
  const activeId = health?.activeGenerationId
  const rootLabel =
    health?.sourceRoot.mode === 'configured'
      ? 'Existing local folder set by SETUP.cmd'
      : health?.sourceRoot.mode === 'invalid'
        ? 'Source folder configuration needs repair'
        : 'Portable extracts folder'
  return (
    <section className="panel panel-feature" aria-labelledby="first-slice-heading">
      <div className="panel-heading">
        <p className="eyebrow">Phase 1 / local evidence</p>
        <h2 id="first-slice-heading">RTA source readiness</h2>
      </div>
      <p>
        Read your existing FTE, Verint schedule, Agent Status, LILO, and Call-by-Call exports in
        place. Refresh does not upload, copy, or modify those files. Storm sources are optional; the
        governed attendance read model is connected, while headline service rates and action queues
        are not connected yet.
      </p>
      <div className="source-actions">
        <button
          className="button button-primary"
          type="button"
          disabled={!canRefresh || refreshing}
          onClick={onRefresh}
        >
          {refreshing ? 'Refreshing local sources…' : 'Refresh local sources'}
        </button>
        <span
          className={`state-pill state-${health?.ready ? 'ready' : 'unavailable'}`}
          role="status"
        >
          {loading
            ? 'Checking sources'
            : health?.ready
              ? 'Source cut ready'
              : health?.status === 'source_changed'
                ? 'Source folder changed'
                : 'Sources not ready'}
        </span>
      </div>
      {refreshing && health?.refreshProgress && (
        <p className="source-progress" role="status" aria-live="polite">
          {health.refreshProgress.message} · {health.refreshProgress.elapsedSeconds}s
          {health.refreshProgress.totalFiles > 0
            ? ` · ${health.refreshProgress.completedFiles}/${health.refreshProgress.totalFiles} files`
            : ''}
        </p>
      )}
      {!refreshing && refreshUnchanged && (
        <p className="source-progress" role="status">
          Sources are unchanged; the validated generation was reused.
        </p>
      )}
      {error && (
        <p className="source-error" role="alert">
          {error.message}
        </p>
      )}
      {latestFailed && (
        <p className="source-warning" role="status">
          The last refresh failed ({health.latestRefresh?.failureCode ?? 'unknown reason'}).
          {activeId !== null
            ? ' The previous validated cut remains stored.'
            : ' No cut was published.'}
        </p>
      )}
      <dl className="fact-list source-facts">
        <div>
          <dt>Source folder</dt>
          <dd>{rootLabel}</dd>
        </div>
        <div>
          <dt>FTE roster</dt>
          <dd>{health?.ready ? `${health.sources.roster.agentCount} agents` : 'Not validated'}</dd>
        </div>
        <div>
          <dt>Published schedules</dt>
          <dd>
            {health?.ready ? `${health.sources.schedule.shiftCount} assignments` : 'Not validated'}
          </dd>
        </div>
        <div>
          <dt>Schedule dates</dt>
          <dd>{health?.ready ? formatDateRange(health) : 'Unknown'}</dd>
        </div>
        <div>
          <dt>Agent Status</dt>
          <dd>
            {health?.ready && health.sources.agentStatus.ready
              ? `${health.sources.agentStatus.rowCount} intervals`
              : 'Optional source not loaded'}
          </dd>
        </div>
        <div>
          <dt>LILO</dt>
          <dd>
            {health?.ready && health.sources.lilo.ready
              ? `${health.sources.lilo.rowCount} daily records`
              : 'Optional fallback not loaded'}
          </dd>
        </div>
        <div>
          <dt>Call by Call</dt>
          <dd>
            {health?.ready && health.sources.callByCall.ready
              ? `${health.sources.callByCall.canonicalLegCount} governed legs · ${health.sources.callByCall.serviceIntervalCount} intervals`
              : 'Optional service source not loaded'}
          </dd>
        </div>
        <div>
          <dt>Attendance evidence</dt>
          <dd>
            {health?.ready && health.sources.attendance.ready
              ? `${health.sources.attendance.agentDayCount} agent-days · ${health.sources.attendance.gapFragmentCount} exact gaps · ${health.sources.attendance.unknownCount} unknown`
              : 'Needs Agent Status or LILO evidence'}
          </dd>
        </div>
        <div>
          <dt>Quality findings</dt>
          <dd>
            {health?.ready
              ? `${health.quality.error} errors · ${health.quality.warning} warnings`
              : 'Unknown'}
          </dd>
        </div>
        <div>
          <dt>Active cut</dt>
          <dd>{health?.ready ? `Generation ${activeId}` : 'None current'}</dd>
        </div>
      </dl>
      <Link to="/operate/evidence" className="text-link">
        Inspect service and attendance evidence <span aria-hidden="true">→</span>
      </Link>
      <p className="source-help">
        Run <code>SETUP.cmd</code> once to select your existing WFM Database folder, or place
        extracts under <code>extracts/FTE</code> and{' '}
        <code>extracts/Verint/Schedules &amp; Activities</code>.
      </p>
      <div className="empty-state compact-empty">
        <span className="empty-state-icon" aria-hidden="true">
          —
        </span>
        <div>
          <strong>No operational metrics to display</strong>
          <span>Source readiness is not an RTA performance position.</span>
        </div>
      </div>
    </section>
  )
}
