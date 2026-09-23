import { createRootRoute, createRoute, createRouter } from '@tanstack/react-router'
import { AppShell } from './app/AppShell'
import { FoundationPage } from './pages/FoundationPage'
import { HomePage } from './pages/HomePage'
import { OperateEvidencePage } from './pages/OperateEvidencePage'

const rootRoute = createRootRoute({
  component: AppShell,
})

const homeRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  component: FoundationPage,
})

const compatibilityRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/compatibility',
  component: HomePage,
})

const operateEvidenceRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/operate/evidence',
  component: OperateEvidencePage,
})

const routeTree = rootRoute.addChildren([homeRoute, compatibilityRoute, operateEvidenceRoute])

export const router = createRouter({ routeTree })

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
