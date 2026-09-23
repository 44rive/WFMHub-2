export type WorkspaceId = 'command' | 'operate' | 'plan' | 'capacity' | 'review' | 'govern'

export type CapabilityId =
  | 'foundation'
  | 'compatibility-doctor'
  | 'decision-register'
  | 'rta-command'
  | 'operate-evidence'
  | 'forecast-demand'
  | 'capacity-plan'
  | 'outcome-review'
  | 'data-readiness'

export type ImplementedPath = '/' | '/compatibility' | '/operate/evidence'

export type PageDefinition = {
  id: string
  label: string
  capability: CapabilityId
  to?: ImplementedPath
}

export type WorkspaceDefinition = {
  id: WorkspaceId
  label: string
  purpose: string
  pages: readonly PageDefinition[]
}

// A page needs both a working route and an enabled capability before it can appear.
// Future workspaces remain typed here without presenting dead links to the user.
export const capabilityAvailability: Readonly<Record<CapabilityId, boolean>> = {
  foundation: true,
  'compatibility-doctor': true,
  'decision-register': false,
  'rta-command': false,
  'operate-evidence': true,
  'forecast-demand': false,
  'capacity-plan': false,
  'outcome-review': false,
  'data-readiness': false,
}

export const workspaces: readonly WorkspaceDefinition[] = [
  {
    id: 'command',
    label: 'Command',
    purpose: 'Cross-horizon work and decisions',
    pages: [
      { id: 'foundation', label: 'Product foundation', capability: 'foundation', to: '/' },
      { id: 'decision-register', label: 'Decision register', capability: 'decision-register' },
    ],
  },
  {
    id: 'operate',
    label: 'Operate',
    purpose: 'Service and people evidence for today',
    pages: [
      {
        id: 'operate-evidence',
        label: 'Service & attendance evidence',
        capability: 'operate-evidence',
        to: '/operate/evidence',
      },
      { id: 'rta-command', label: 'RTA Command Center', capability: 'rta-command' },
    ],
  },
  {
    id: 'plan',
    label: 'Plan',
    purpose: 'Forecasting, requirements, and scenarios',
    pages: [{ id: 'forecast-demand', label: 'Forecast & Demand', capability: 'forecast-demand' }],
  },
  {
    id: 'capacity',
    label: 'Capacity',
    purpose: 'Tactical and strategic workforce supply',
    pages: [{ id: 'capacity-plan', label: 'Workforce Plan', capability: 'capacity-plan' }],
  },
  {
    id: 'review',
    label: 'Review',
    purpose: 'Actuals, integrity, and measured outcomes',
    pages: [{ id: 'outcome-review', label: 'Decision Outcomes', capability: 'outcome-review' }],
  },
  {
    id: 'govern',
    label: 'Govern',
    purpose: 'Data trust, refreshes, and delivery',
    pages: [
      { id: 'data-readiness', label: 'Data Readiness', capability: 'data-readiness' },
      {
        id: 'compatibility-doctor',
        label: 'Compatibility Doctor',
        capability: 'compatibility-doctor',
        to: '/compatibility',
      },
    ],
  },
]

export type VisiblePage = PageDefinition & { to: ImplementedPath }
export type VisibleWorkspace = Omit<WorkspaceDefinition, 'pages'> & { pages: VisiblePage[] }

export function visibleWorkspaces(
  availability: Readonly<Record<CapabilityId, boolean>> = capabilityAvailability,
): VisibleWorkspace[] {
  return workspaces.flatMap((workspace) => {
    const pages = workspace.pages.filter((page): page is VisiblePage =>
      Boolean(page.to && availability[page.capability]),
    )
    return pages.length ? [{ ...workspace, pages }] : []
  })
}
