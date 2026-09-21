import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { RtaEmptyState } from './FoundationPage'

describe('unconnected RTA surface', () => {
  it('explains the missing evidence without inventing operational measures', () => {
    const markup = renderToStaticMarkup(<RtaEmptyState />)

    expect(markup).toContain('RTA Command Center is not connected yet')
    expect(markup).toContain('No operational metrics to display')
    expect(markup).toContain('Missing evidence will remain')
    expect(markup).toContain('not connected to a governed RTA data API yet')
    expect(markup).not.toContain('Service level:')
    expect(markup).not.toContain('Staffing gap:')
  })
})
