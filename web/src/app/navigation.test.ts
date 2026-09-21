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

  it('shows only the product foundation and the working compatibility doctor', () => {
    expect(
      visibleWorkspaces().map((workspace) => [
        workspace.id,
        workspace.pages.map((page) => page.to),
      ]),
    ).toEqual([
      ['command', ['/']],
      ['govern', ['/compatibility']],
    ])
  })

  it('never exposes an enabled capability until it has an implemented route', () => {
    const availability = { ...capabilityAvailability, 'rta-command': true }
    expect(visibleWorkspaces(availability).some((workspace) => workspace.id === 'operate')).toBe(
      false,
    )
  })
})
