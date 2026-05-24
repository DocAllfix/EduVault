import { useNavigate, useLocation } from '@tanstack/react-router'
import { api } from '@/lib/api'
import { useAuthStore } from '@/stores/auth-store'
import { ConfirmDialog } from '@/components/confirm-dialog'

interface SignOutDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function SignOutDialog({ open, onOpenChange }: SignOutDialogProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const { auth } = useAuthStore()

  const handleSignOut = () => {
    // Clear JWT (api.ts owns tokenStorage). Also clear the template's
    // legacy Zustand mock store for parity until 6.x/7.x removes it.
    api.logout()
    auth.reset()
    navigate({
      to: '/login',
      search: { redirect: location.href },
      replace: true,
    })
  }

  return (
    <ConfirmDialog
      open={open}
      onOpenChange={onOpenChange}
      title='Esci'
      desc='Sei sicuro di voler uscire? Dovrai effettuare di nuovo l’accesso per rientrare.'
      confirmText='Esci'
      destructive
      handleConfirm={handleSignOut}
      className='sm:max-w-sm'
    />
  )
}
