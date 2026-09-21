import { Link, Outlet, useRouterState } from '@tanstack/react-router'
import { useEffect, useRef } from 'react'
import { visibleWorkspaces } from './navigation'

const navigation = visibleWorkspaces()

export function AppShell() {
  const pathname = useRouterState({ select: (state) => state.location.pathname })
  const activeWorkspace = navigation.find((workspace) =>
    workspace.pages.some((page) => page.to === pathname),
  )
  const previousPathname = useRef(pathname)

  useEffect(() => {
    if (previousPathname.current !== pathname) {
      document.querySelector<HTMLElement>('#main-content h1')?.focus()
      previousPathname.current = pathname
    }
  }, [pathname])

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <header className="app-header">
        <div className="app-header-inner">
          <Link to="/" className="app-brand" aria-label="WFMHub 2 home">
            <span className="app-brand-mark" aria-hidden="true">
              W2
            </span>
            <span className="app-brand-name">
              WFMHub <strong>2</strong>
            </span>
          </Link>
          <nav className="primary-nav" aria-label="Workspaces">
            {navigation.map((workspace) => {
              const firstPage = workspace.pages[0]
              const active = activeWorkspace?.id === workspace.id
              return (
                <Link
                  key={workspace.id}
                  to={firstPage.to}
                  className={`primary-nav-link${active ? ' is-active' : ''}`}
                  aria-current={active ? 'location' : undefined}
                >
                  {workspace.label}
                </Link>
              )
            })}
          </nav>
          <span className="app-header-context">Local workbench</span>
        </div>
      </header>
      <div className="app-subbar">
        <div className="app-subbar-inner">
          <span className="app-subbar-label">{activeWorkspace?.label ?? 'WFMHub'}</span>
          <span className="app-subbar-separator" aria-hidden="true" />
          <span className="app-subbar-description">
            {activeWorkspace?.purpose ?? 'Portable workforce intelligence'}
          </span>
          <span className="app-subbar-credit">by Anass ASSRI</span>
        </div>
      </div>
      <Outlet />
    </div>
  )
}
