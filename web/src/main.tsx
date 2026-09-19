import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from '@tanstack/react-router'
import React from 'react'
import { createRoot } from 'react-dom/client'
import { router } from './router'
import './styles.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

const rootElement = document.getElementById('root')
if (!rootElement) {
  throw new Error('WFMHub root element is missing')
}

createRoot(rootElement).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </React.StrictMode>,
)
