import { describe, expect, it } from 'vitest'
import { capabilityAvailability, visibleWorkspaces, workspaces } from './navigation'

describe('product navigation', () => {
  it('defines the complete six-workspace product architecture in order', () => {
    expect(workspaces.map((workspace) => workspace.id)).toEqual([
      'command',
      'operate',
      'plan',
      'capacity',
      'review',
      'govern',
    ])
  })

  it('shows the foundation, narrow Operate evidence page, and compatibility doctor', () => {
    expect(
      visibleWorkspaces().map((workspace) => [
        workspace.id,
        workspace.pages.map((page) => page.to),
      ]),
    ).toEqual([
      ['command', ['/']],
      ['operate', ['/operate/evidence']],
      ['govern', ['/compatibility']],
    ])
  })

  it('never exposes an enabled capability until it has an implemented route', () => {
    const availability = { ...capabilityAvailability, 'rta-command': true }
    expect(
      visibleWorkspaces(availability).find((workspace) => workspace.id === 'operate')?.pages,
    ).toHaveLength(1)
    expect(
      visibleWorkspaces(availability)
        .find((workspace) => workspace.id === 'operate')
        ?.pages.some((page) => page.id === 'rta-command'),
    ).toBe(false)
  })
})
