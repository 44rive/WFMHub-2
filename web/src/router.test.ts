import { describe, expect, it } from 'vitest'
import { router } from './router'

describe('product routes', () => {
  it('retains a working home route and a dedicated compatibility route', () => {
    expect(router.routesByPath['/']).toBeDefined()
    expect(router.routesByPath['/compatibility']).toBeDefined()
  })
})
