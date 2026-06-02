import { type QueryClient } from '@tanstack/react-query'
import { createRootRouteWithContext, Outlet } from '@tanstack/react-router'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { TanStackRouterDevtools } from '@tanstack/react-router-devtools'
import { Toaster } from '@/components/ui/sonner'
import { NavigationProgress } from '@/components/navigation-progress'
import { GeneralError } from '@/features/errors/general-error'
import { NotFoundError } from '@/features/errors/not-found-error'
import { useJobsWatcher } from '@/hooks/use-jobs-watcher'

// F11: watcher globale dei job (generation/rebuild/audio_rebuild).
// Polling background ogni 4s; lancia toast.success cliccabile quando
// un job finisce. Idempotente: zero impatto se store vuoto.
function JobsWatcherMount() {
  useJobsWatcher()
  return null
}

export const Route = createRootRouteWithContext<{
  queryClient: QueryClient
}>()({
  component: () => {
    return (
      <>
        <NavigationProgress />
        <JobsWatcherMount />
        <Outlet />
        <Toaster duration={5000} />
        {import.meta.env.MODE === 'development' && (
          <>
            <ReactQueryDevtools buttonPosition='bottom-left' />
            <TanStackRouterDevtools position='bottom-right' />
          </>
        )}
      </>
    )
  },
  notFoundComponent: NotFoundError,
  errorComponent: GeneralError,
})
