// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import type { RtaOperateEvidence, RtaSourceHealth } from '../lib/api'
import {
  AttendanceEvidence,
  isCurrentOperateCut,
  latestActualDate,
  ServiceEvidence,
} from './OperateEvidencePage'

afterEach(cleanup)

const evidence: RtaOperateEvidence = {
  status: 'ready',
  reason: null,
  businessDate: '2026-09-20',
  generationId: 7,
  serviceScopes: [{ serviceScope: 'RSA', comparisonScope: 'Belgium' }],
  selectedScope: { serviceScope: 'RSA', comparisonScope: 'Belgium' },
  serviceIntervals: [
    {
      intervalStart: '2026-09-20T09:00:00',
      intervalEnd: '2026-09-20T09:15:00',
      offered: 20,
      answered: 18,
      abandoned: 2,
      shortAbandoned: 1,
      abandonedWithinTarget: 1,
      answeredWithinTarget: 16,
      talkSeconds: 2200,
      holdSeconds: 100,
      wrapSeconds: 150,
      handledSeconds: 2450,
      callLegs: 21,
      transferredLegs: 1,
    },
  ],
  attendance: {
    scope: 'date-wide',
    evidenceStates: [{ state: 'unknown', agentDays: 2 }],
    gapTypes: [{ type: 'late', fragments: 3, minutes: 45 }],
  },
}

describe('read-only Operate evidence', () => {
  it('defaults to the latest available actual-source date, not a schedule date', () => {
    const health = {
      sources: {
        agentStatus: { maxDate: '2026-09-19' },
        lilo: { maxDate: '2026-09-20' },
        callByCall: { maxDate: '2026-09-18' },
        attendance: { maxDate: '2026-09-20' },
        schedule: { maxDate: '2026-10-31' },
      },
    } as RtaSourceHealth
    expect(latestActualDate(health)).toBe('2026-09-20')
  })

  it('does not promote a stale or mismatched generation to current evidence', () => {
    const current = { ready: true, activeGenerationId: 7 } as RtaSourceHealth
    expect(isCurrentOperateCut(current, evidence)).toBe(true)
    expect(isCurrentOperateCut({ ...current, ready: false }, evidence)).toBe(false)
    expect(isCurrentOperateCut({ ...current, activeGenerationId: 8 }, evidence)).toBe(false)
    expect(isCurrentOperateCut(undefined, evidence)).toBe(false)
    expect(isCurrentOperateCut(current, { ...evidence, status: 'not_ready' })).toBe(false)
  })

  it('renders only additive service components with accessible interval headings', () => {
    render(<ServiceEvidence evidence={evidence} />)
    expect(screen.getByRole('table', { name: /Additive Call-by-Call evidence/ })).toBeTruthy()
    expect(screen.getByRole('columnheader', { name: 'Offered' })).toBeTruthy()
    expect(screen.getByRole('rowheader', { name: '09:00–09:15' })).toBeTruthy()
    expect(screen.getByText('2,200')).toBeTruthy()
    expect(screen.queryByText(/SLA/)).toBeNull()
    expect(screen.queryByText(/AHT/)).toBeNull()
  })

  it('keeps attendance explicitly date-wide and distinguishes missing service from zero', () => {
    render(
      <>
        <ServiceEvidence evidence={{ ...evidence, serviceIntervals: [] }} />
        <AttendanceEvidence evidence={evidence} />
      </>,
    )
    expect(screen.getByText(/not a zero-service claim/)).toBeTruthy()
    expect(screen.getByText(/not filtered by service scope/)).toBeTruthy()
    expect(screen.getByRole('rowheader', { name: 'unknown' })).toBeTruthy()
    expect(screen.getByRole('rowheader', { name: 'late' })).toBeTruthy()
    expect(screen.getByText('45')).toBeTruthy()
  })
})
