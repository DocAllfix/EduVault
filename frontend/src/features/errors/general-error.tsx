import { useNavigate, useRouter } from '@tanstack/react-router'
import { RefreshCw, ShieldAlert } from 'lucide-react'

import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'

type GeneralErrorProps = React.HTMLAttributes<HTMLDivElement> & {
  minimal?: boolean
}

export function GeneralError({
  className,
  minimal = false,
}: GeneralErrorProps) {
  const navigate = useNavigate()
  const { history } = useRouter()

  return (
    <div className={cn('h-svh w-full', className)}>
      <div className='m-auto flex h-full w-full flex-col items-center justify-center gap-3 px-6'>
        {!minimal && (
          <div className='mb-2 flex size-20 items-center justify-center rounded-full bg-destructive/10'>
            <ShieldAlert
              className='size-10 text-destructive'
              aria-hidden='true'
            />
          </div>
        )}
        <span className='text-lg font-semibold'>
          Si è verificato un errore imprevisto
        </span>
        <p className='max-w-md text-center text-sm text-muted-foreground'>
          La pagina non si è caricata correttamente. Può capitare se la
          connessione è instabile, il server sta riavviando, o il controllo
          anti-bot di Vercel è scattato. Riprova fra qualche secondo.
        </p>
        {!minimal && (
          <div className='mt-4 flex flex-wrap items-center justify-center gap-3'>
            <Button
              variant='default'
              className='bg-brand-primary hover:bg-brand-primary/90 gap-2'
              onClick={() => window.location.reload()}
            >
              <RefreshCw className='size-4' aria-hidden='true' />
              Riprova
            </Button>
            <Button variant='outline' onClick={() => history.go(-1)}>
              Pagina precedente
            </Button>
            <Button variant='ghost' onClick={() => navigate({ to: '/' })}>
              Dashboard
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
