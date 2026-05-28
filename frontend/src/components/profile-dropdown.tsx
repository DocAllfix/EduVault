/**
 * ProfileDropdown — header avatar menu.
 *
 * Wired to the real logged-in user (JWT role + /api/users/me email), same as
 * NavUser. Replaces the upstream template mock (SN / satnaing) and drops the
 * fake Billing / New Team / Profile items that have no routes in v1.0 (REI-5).
 */

import { useEffect, useState } from 'react'
import { Link } from '@tanstack/react-router'
import { LogOut, Palette } from 'lucide-react'
import useDialogState from '@/hooks/use-dialog-state'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { SignOutDialog } from '@/components/sign-out-dialog'
import { api } from '@/lib/api'
import { decodeAccessToken } from '@/lib/auth'

const ROLE_INITIALS: Record<string, string> = {
  admin: 'AD',
  operator: 'OP',
  reviewer: 'RV',
}

export function ProfileDropdown() {
  const [open, setOpen] = useDialogState()
  const [me, setMe] = useState<{ email: string; role: string } | null>(null)

  useEffect(() => {
    const payload = decodeAccessToken()
    if (payload?.role)
      setMe((prev) => ({ email: prev?.email ?? '', role: payload.role! }))
    api
      .getMe()
      .then((u) => setMe({ email: u.email, role: u.role }))
      .catch(() => {
        /* keep JWT-only shape */
      })
  }, [])

  const email = me?.email || ''
  const role = me?.role
  const name = email.split('@')[0]?.replace(/\./g, ' ') || 'Utente'
  const initials =
    (role && ROLE_INITIALS[role]) || (email || 'UT').slice(0, 2).toUpperCase()

  return (
    <>
      <DropdownMenu modal={false}>
        <DropdownMenuTrigger asChild>
          <Button variant='ghost' className='relative h-8 w-8 rounded-full'>
            <Avatar className='h-8 w-8'>
              <AvatarFallback className='bg-primary/10 text-primary font-semibold'>
                {initials}
              </AvatarFallback>
            </Avatar>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent className='w-56' align='end' forceMount>
          <DropdownMenuLabel className='font-normal'>
            <div className='flex flex-col gap-1.5'>
              <p className='text-sm leading-none font-medium capitalize'>
                {name}
              </p>
              <p className='text-muted-foreground text-xs leading-none'>
                {email || role}
              </p>
            </div>
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuGroup>
            <DropdownMenuItem asChild>
              <Link to='/settings/appearance'>
                <Palette />
                Tema
              </Link>
            </DropdownMenuItem>
          </DropdownMenuGroup>
          <DropdownMenuSeparator />
          <DropdownMenuItem variant='destructive' onClick={() => setOpen(true)}>
            <LogOut />
            Esci
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <SignOutDialog open={!!open} onOpenChange={setOpen} />
    </>
  )
}
