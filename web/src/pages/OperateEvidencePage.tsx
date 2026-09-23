import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useState } from 'react'
import {
  createEngineClient,
  getEngineConnection,
  isBusinessDate,
  type RtaOperateEvidence,
  type RtaSourceHealth,
  type ServiceScope,
} from '../lib/api'

const numberFormat = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 })

export function latestActualDate(health: RtaSourceHealth): string | null {
  const dates = [
    health.sources.agentStatus.maxDate,
    health.sources.lilo.maxDate,
    health.sources.callByCall.maxDate,
    health.sources.attendance.maxDate,
  ].filter((date): date is string => date !== null && isBusinessDate(date))
  return dates.sort().at(-1) ?? null
}

export function isCurrentOperateCut(
  health: RtaSourceHealth | undefined,
  evidence: RtaOperateEvidence | undefined,
): boolean {
  return (
    evidence?.status === 'ready' &&
    health?.ready === true &&
    health.activeGenerationId === evidence.generationId
  )
}

export function hasFailedLatestRefresh(health: RtaSourceHealth | undefined): boolean {
  return health?.latestRefresh?.status === 'failed'
}

function reasonMessage(reason: RtaOperateEvidence['reason']): string {
  switch (reason) {
    case 'NO_ACTIVE_GENERATION':
      return 'No validated source generation is active. Refresh local sources in Command first.'
    case 'SOURCE_ROOT_UNAVAILABLE':
      return 'The configured local source folder is unavailable. Check the folder and SETUP.cmd.'
    case 'SOURCE_ROOT_CHANGED':
      return 'The local source folder changed since this generation was validated. Refresh before using this view.'
    default:
      return 'The selected evidence is not ready.'
  }
}

function formatIntervalTime(value: string): string {
  const match = /(?:T|\s)(\d{2}:\d{2})(?::\d{2})?/.exec(value)
  return match?.[1] ?? value
}

export function OperateEvidencePage() {
  const [chosenDate, setChosenDate] = useState<string | null>(null)
  const [chosenScope, setChosenScope] = useState<ServiceScope | null>(null)
  const connection = useQuery({
    queryKey: ['engine-connection'],
    queryFn: getEngineConnection,
    retry: false,
  })
  const sourceHealth = useQuery({
    queryKey: ['rta-source-health', connection.data?.baseUrl],
    queryFn: () => {
      if (!connection.data) throw new Error('Local host connection is unavailable')
      return createEngineClient(connection.data).getRtaSourceHealth()
    },
    enabled: connection.data?.phase === 'ready',
    retry: false,
  })
  const date = chosenDate ?? (sourceHealth.data ? latestActualDate(sourceHealth.data) : null)
  const evidence = useQuery({
    queryKey: [
      'rta-operate-evidence',
      connection.data?.baseUrl,
      date,
      chosenScope?.serviceScope,
      chosenScope?.comparisonScope,
    ],
    queryFn: () => {
      if (!connection.data || !date) throw new Error('Business evidence is unavailable')
      return createEngineClient(connection.data).getRtaOperateEvidence(
        date,
        chosenScope ?? undefined,
      )
    },
    enabled: connection.data?.phase === 'ready' && Boolean(date) && isBusinessDate(date ?? ''),
    retry: false,
  })
  const result = evidence.data
  const selectedIndex = result?.serviceScopes.findIndex(
    (scope) =>
      scope.serviceScope === result.selectedScope?.serviceScope &&
      scope.comparisonScope === result.selectedScope?.comparisonScope,
  )
  const sourceChanged = sourceHealth.data?.status === 'source_changed'
  const notReady = result?.status === 'not_ready'
  const validatingCut = connection.isFetching || sourceHealth.isFetching || evidence.isFetching
  const cutCurrent =
    !validatingCut &&
    !connection.error &&
    !sourceHealth.error &&
    !evidence.error &&
    isCurrentOperateCut(sourceHealth.data, result)
  const cutMismatch = !validatingCut && result?.status === 'ready' && !cutCurrent

  return (
    <main id="main-content" className="product-main">
      <div className="product-container">
        <div className="page-intro">
          <div>
            <p className="eyebrow">Operate / read-only evidence</p>
            <h1 tabIndex={-1}>Service &amp; attendance evidence</h1>
            <p className="page-lede">
              Inspect additive 15-minute service components and date-wide attendance evidence from
              one validated local generation. This is not the RTA Command Center.
            </p>
          </div>
          <Link to="/" className="button button-secondary">
            Source readiness
          </Link>
        </div>

        <section className="evidence-strip" aria-label="Operate evidence provenance">
          <div className="evidence-strip-item">
            <span className="evidence-label">Business date</span>
            <span className="evidence-value">{date ?? 'No actual date available'}</span>
          </div>
          <div className="evidence-strip-item">
            <span className="evidence-label">Validated generation</span>
            <span className="evidence-value">
              {cutCurrent && result ? `Generation ${result.generationId}` : 'Not current'}
            </span>
          </div>
          <div className="evidence-strip-item">
            <span className="evidence-label">Evidence scope</span>
            <span className="evidence-value">Service: selected pair · attendance: date-wide</span>
          </div>
        </section>

        <section className="panel operate-controls" aria-labelledby="operate-controls-title">
          <div className="panel-heading">
            <p className="eyebrow">Inspect a validated cut</p>
            <h2 id="operate-controls-title">Date and service scope</h2>
          </div>
          <div className="operate-control-grid">
            <label className="operate-field">
              <span>Business date</span>
              <input
                type="date"
                value={date ?? ''}
                onChange={(event) => {
                  setChosenDate(event.target.value)
                  setChosenScope(null)
                }}
                disabled={connection.data?.phase !== 'ready'}
              />
            </label>
            <label className="operate-field">
              <span>Service / comparison scope</span>
              <select
                value={
                  selectedIndex !== undefined && selectedIndex >= 0 ? String(selectedIndex) : ''
                }
                onChange={(event) => {
                  const scope = result?.serviceScopes[Number(event.target.value)]
                  setChosenScope(scope ?? null)
                }}
                disabled={result?.status !== 'ready' || result.serviceScopes.length === 0}
              >
                <option value="">No service scope available</option>
                {result?.serviceScopes.map((scope, index) => (
                  <option
                    key={`${scope.serviceScope}\u0000${scope.comparisonScope}`}
                    value={String(index)}
                  >
                    {scope.serviceScope} / {scope.comparisonScope}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <p className="operate-help">
            Service rows belong only to the selected service/comparison pair. Attendance totals
            cover the whole date and are not allocated to that pair.
          </p>
        </section>

        {validatingCut ||
        connection.isPending ||
        (connection.data?.phase === 'ready' && sourceHealth.isPending) ||
        (date && evidence.isPending) ? (
          <p className="operate-notice" role="status">
            Loading local evidence…
          </p>
        ) : null}
        {connection.data?.phase === 'unavailable' ? (
          <p className="operate-notice operate-warning" role="alert">
            {connection.data.message}
          </p>
        ) : null}
        {sourceHealth.error || evidence.error ? (
          <p className="operate-notice operate-error" role="alert">
            {sourceHealth.error instanceof Error
              ? sourceHealth.error.message
              : evidence.error instanceof Error
                ? evidence.error.message
                : 'Local evidence could not be loaded.'}
          </p>
        ) : null}
        {!date && !sourceHealth.isPending && !sourceHealth.error ? (
          <p className="operate-notice" role="status">
            No actual-source date is available. Refresh local sources, or select a business date to
            inspect an existing cut.
          </p>
        ) : null}
        {sourceChanged || notReady ? (
          <p className="operate-notice operate-warning" role="alert">
            {notReady
              ? reasonMessage(result.reason)
              : 'The source folder changed; refresh local sources before relying on this cut.'}
          </p>
        ) : null}
        {cutMismatch && !sourceChanged ? (
          <p className="operate-notice operate-warning" role="alert">
            Source readiness and the returned evidence do not identify the same active validated
            generation. Refresh source readiness before relying on this view.
          </p>
        ) : null}
        {cutCurrent && hasFailedLatestRefresh(sourceHealth.data) ? (
          <p className="operate-notice operate-warning" role="status">
            The last refresh failed. This view still uses the previous validated generation; it does
            not include the attempted new sources.
          </p>
        ) : null}

        {cutCurrent && !sourceChanged && result ? (
          <>
            <ServiceEvidence evidence={result} />
            <AttendanceEvidence evidence={result} />
          </>
        ) : null}

        <p className="operate-boundary">
          Read-only source components only. No SLA, AHT, staffing gap, absence decision, or
          agent-level action is calculated here. Unknown evidence remains unknown.
        </p>
      </div>
    </main>
  )
}

export function ServiceEvidence({ evidence }: { evidence: RtaOperateEvidence }) {
  const selected = evidence.selectedScope
  return (
    <section className="panel operate-section" aria-labelledby="service-evidence-title">
      <div className="panel-heading">
        <p className="eyebrow">Call-by-Call / additive components</p>
        <h2 id="service-evidence-title">15-minute service intervals</h2>
      </div>
      <p className="operate-section-copy">
        {selected
          ? `${selected.serviceScope} / ${selected.comparisonScope} · generation ${evidence.generationId}`
          : 'No service scope is selected for this date.'}
      </p>
      {evidence.serviceIntervals.length === 0 ? (
        <p className="operate-empty" role="status">
          No governed service intervals for this date and scope. This is not a zero-service claim.
        </p>
      ) : (
        <section className="operate-table-scroll" aria-label="Service interval table">
          <table className="operate-table">
            <caption>
              Additive Call-by-Call evidence for {evidence.businessDate}; counts and seconds only
            </caption>
            <thead>
              <tr>
                <th scope="col">Interval</th>
                <th scope="col">Offered</th>
                <th scope="col">Answered</th>
                <th scope="col">Abandoned</th>
                <th scope="col">Short abandoned</th>
                <th scope="col">Abandoned within target</th>
                <th scope="col">Answered within target</th>
                <th scope="col">Talk sec</th>
                <th scope="col">Hold sec</th>
                <th scope="col">Wrap sec</th>
                <th scope="col">Handled sec</th>
                <th scope="col">Call legs</th>
                <th scope="col">Transferred legs</th>
              </tr>
            </thead>
            <tbody>
              {evidence.serviceIntervals.map((row) => (
                <tr key={`${row.intervalStart}-${row.intervalEnd}`}>
                  <th scope="row">
                    {formatIntervalTime(row.intervalStart)}–{formatIntervalTime(row.intervalEnd)}
                  </th>
                  <td>{numberFormat.format(row.offered)}</td>
                  <td>{numberFormat.format(row.answered)}</td>
                  <td>{numberFormat.format(row.abandoned)}</td>
                  <td>{numberFormat.format(row.shortAbandoned)}</td>
                  <td>{numberFormat.format(row.abandonedWithinTarget)}</td>
                  <td>{numberFormat.format(row.answeredWithinTarget)}</td>
                  <td>{numberFormat.format(row.talkSeconds)}</td>
                  <td>{numberFormat.format(row.holdSeconds)}</td>
                  <td>{numberFormat.format(row.wrapSeconds)}</td>
                  <td>{numberFormat.format(row.handledSeconds)}</td>
                  <td>{numberFormat.format(row.callLegs)}</td>
                  <td>{numberFormat.format(row.transferredLegs)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </section>
  )
}

export function AttendanceEvidence({ evidence }: { evidence: RtaOperateEvidence }) {
  return (
    <section className="panel operate-section" aria-labelledby="attendance-evidence-title">
      <div className="panel-heading">
        <p className="eyebrow">Agent Status / LILO / schedule</p>
        <h2 id="attendance-evidence-title">Attendance evidence and gaps</h2>
      </div>
      <p className="operate-section-copy">
        Date-wide totals for {evidence.businessDate}; not filtered by service scope. These are
        evidence classifications, not employee-level findings or confirmed absence.
      </p>
      <div className="operate-summary-grid">
        <div>
          <h3>Evidence states</h3>
          {evidence.attendance.evidenceStates.length === 0 ? (
            <p className="operate-empty">No attendance evidence states for this date.</p>
          ) : (
            <table className="operate-summary-table">
              <thead>
                <tr>
                  <th scope="col">State</th>
                  <th scope="col">Agent-days</th>
                </tr>
              </thead>
              <tbody>
                {evidence.attendance.evidenceStates.map((item) => (
                  <tr key={item.state}>
                    <th scope="row">{item.state.replaceAll('_', ' ')}</th>
                    <td>{numberFormat.format(item.agentDays)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        <div>
          <h3>Gap fragments</h3>
          {evidence.attendance.gapTypes.length === 0 ? (
            <p className="operate-empty">No classified gap fragments for this date.</p>
          ) : (
            <table className="operate-summary-table">
              <thead>
                <tr>
                  <th scope="col">Type</th>
                  <th scope="col">Fragments</th>
                  <th scope="col">Minutes</th>
                </tr>
              </thead>
              <tbody>
                {evidence.attendance.gapTypes.map((item) => (
                  <tr key={item.type}>
                    <th scope="row">{item.type.replaceAll('_', ' ')}</th>
                    <td>{numberFormat.format(item.fragments)}</td>
                    <td>{numberFormat.format(item.minutes)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </section>
  )
}
