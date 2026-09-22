// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { RtaSourceHealth } from '../lib/api'
import { RtaSourcePanel } from './FoundationPage'

afterEach(cleanup)

const readyHealth: RtaSourceHealth = {
  status: 'ready',
  ready: true,
  sourceRoot: { mode: 'configured', displayName: 'Configured local folder' },
  configuredSources: {
    fte: 'FTE',
    publishedSchedules: 'Verint/Schedules & Activities',
    agentStatus: 'Storm/Agent Status',
    lilo: 'Storm/LILO',
    callByCall: 'Storm/Call by Call',
  },
  activeGenerationId: 7,
  activeGeneration: {
    generationId: 7,
    status: 'succeeded',
    startedAt: '2026-09-21T09:00:00Z',
    finishedAt: '2026-09-21T09:00:01Z',
    counts: {
      rosterAgents: 12,
      timeOffRecords: 2,
      scheduleAssignments: 33,
      agentStatusRows: 80,
      liloRows: 12,
      rawCallLegs: 105,
      canonicalCallLegs: 100,
      serviceIntervals: 8,
      attendanceAgentDays: 24,
      attendanceGapFragments: 3,
      statusPrimaryDays: 20,
      attendanceUnknownDays: 1,
      sourceFiles: 6,
      scheduleFiles: 1,
      agentStatusFiles: 1,
      liloFiles: 1,
      callFiles: 2,
    },
    dateRange: { from: '2026-09-20', to: '2026-09-21' },
    actualDateRanges: {
      agentStatus: { from: '2026-09-20', to: '2026-09-21' },
      lilo: { from: '2026-09-20', to: '2026-09-21' },
      callByCall: { from: '2026-09-20', to: '2026-09-21' },
      attendance: { from: '2026-09-20', to: '2026-09-21' },
    },
    qualityCounts: { error: 0, warning: 1, info: 0 },
  },
  latestRefresh: null,
  quality: { error: 0, warning: 1, info: 0 },
  sources: {
    roster: { ready: true, agentCount: 12, timeOffCount: 2, fileCount: 1 },
    schedule: {
      ready: true,
      shiftCount: 33,
      fileCount: 1,
      minDate: '2026-09-20',
      maxDate: '2026-09-21',
    },
    agentStatus: {
      ready: true,
      rowCount: 80,
      fileCount: 1,
      minDate: '2026-09-20',
      maxDate: '2026-09-21',
    },
    lilo: {
      ready: true,
      rowCount: 12,
      fileCount: 1,
      minDate: '2026-09-20',
      maxDate: '2026-09-21',
    },
    callByCall: {
      ready: true,
      rawLegCount: 105,
      canonicalLegCount: 100,
      serviceIntervalCount: 8,
      fileCount: 2,
      minDate: '2026-09-20',
      maxDate: '2026-09-21',
    },
    attendance: {
      ready: true,
      agentDayCount: 24,
      gapFragmentCount: 3,
      statusPrimaryCount: 20,
      unknownCount: 1,
      minDate: '2026-09-20',
      maxDate: '2026-09-21',
    },
  },
}

describe('RTA source readiness', () => {
  it('shows only validated source evidence and triggers a local refresh', () => {
    const onRefresh = vi.fn()
    render(
      <RtaSourcePanel
        health={readyHealth}
        loading={false}
        error={null}
        refreshing={false}
        canRefresh
        onRefresh={onRefresh}
      />,
    )

    expect(screen.getByText('12 agents')).toBeTruthy()
    expect(screen.getByText('33 assignments')).toBeTruthy()
    expect(screen.getByText('80 intervals')).toBeTruthy()
    expect(screen.getByText('12 daily records')).toBeTruthy()
    expect(screen.getByText('100 governed legs · 8 intervals')).toBeTruthy()
    expect(screen.getByText('24 agent-days · 3 exact gaps · 1 unknown')).toBeTruthy()
    expect(screen.getByText('Generation 7')).toBeTruthy()
    expect(screen.getByText('No operational metrics to display')).toBeTruthy()
    expect(screen.queryByText('Service level:')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Refresh local sources' }))
    expect(onRefresh).toHaveBeenCalledOnce()
  })

  it('does not show stale counts as current and preserves failure context', () => {
    const active = readyHealth.activeGeneration
    if (!active) throw new Error('test fixture has no active generation')
    const failed: RtaSourceHealth = {
      ...readyHealth,
      status: 'source_changed',
      ready: false,
      latestRefresh: { ...active, status: 'failed', failureCode: 'BLOCKING_SOURCE_QUALITY' },
    }
    render(
      <RtaSourcePanel
        health={failed}
        loading={false}
        error={null}
        refreshing={false}
        canRefresh
        onRefresh={() => {}}
      />,
    )

    expect(screen.getByText('Source folder changed')).toBeTruthy()
    expect(screen.getAllByText('Not validated')).toHaveLength(2)
    expect(screen.queryByText('12 agents')).toBeNull()
    expect(screen.getByText(/previous validated cut remains stored/)).toBeTruthy()
  })
})
