/**
 * NavUser — sidebar footer profile + sign-out (FASE 6.10).
 *
 * Simplified from the upstream template:
 *  - Real email/role from the JWT (no mock "satnaing")
 *  - Removed Upgrade-to-Pro / Account / Billing / Notifications menu
 *    items (none of those routes ship in v1.0 — REI-5)
 *  - Two actions remain: Tema (appearance settings — already in
 *    template), and Esci (SignOutDialog)
 *  - Localised IT
 */

import { useEffect, useState } from 'react'
import { Link } from '@tanstack/react-router'
import { ChevronsUpDown, LogOut, Palette } from 'lucide-react'
import useDialogState from '@/hooks/use-dialog-state'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from '@/components/ui/sidebar'
import { SignOutDialog } from '@/components/sign-out-dialog'
import { api } from '@/lib/api'
import { decodeAccessToken } from '@/lib/auth'

type NavUserProps = {
  user: {
    name: string
    email: string
    avatar: string
  }
}

export function NavUser({ user: fallbackUser }: NavUserProps) {
  const { isMobile } = useSidebar()
  const [open, setOpen] = useDialogState()
  const [me, setMe] = useState<{ email: string; role: string } | null>(null)

  // Optimistic: read role from JWT immediately (instant render), then
  // fetch /api/users/me for the email. If /me fails, keep the JWT-only
  // shape — better than blocking the sidebar on a network call.
  useEffect(() => {
    const payload = decodeAccessToken()
    if (payload?.role) setMe((prev) => ({ email: prev?.email ?? '', role: payload.role! }))
    api
      .getMe()
      .then((u) => setMe({ email: u.email, role: u.role }))
      .catch(() => {
        /* keep fallback */
      })
  }, [])

  const displayEmail = me?.email || fallbackUser.email || ''
  const displayRole = me?.role
  const displayName =
    displayEmail.split('@')[0]?.replace(/\./g, ' ') || fallbackUser.name
  const initials = (displayEmail || fallbackUser.name)
    .slice(0, 2)
    .toUpperCase()

  return (
    <>
      <SidebarMenu>
        <SidebarMenuItem>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <SidebarMenuButton
                size='lg'
                className='data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground'
              >
                <Avatar className='h-8 w-8 rounded-lg'>
                  <AvatarImage src={fallbackUser.avatar} alt={displayName} />
                  <AvatarFallback className='rounded-lg'>
                    {initials}
                  </AvatarFallback>
                </Avatar>
                <div className='grid flex-1 text-start text-sm leading-tight'>
                  <span className='truncate font-semibold capitalize'>
                    {displayName}
                  </span>
                  <span className='truncate text-xs text-muted-foreground'>
                    {displayRole ? displayRole : displayEmail}
                  </span>
                </div>
                <ChevronsUpDown className='ms-auto size-4' />
              </SidebarMenuButton>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              className='w-(--radix-dropdown-menu-trigger-width) min-w-56 rounded-lg'
              side={isMobile ? 'bottom' : 'right'}
              align='end'
              sideOffset={4}
            >
              <DropdownMenuLabel className='p-0 font-normal'>
                <div className='flex items-center gap-2 px-1 py-1.5 text-start text-sm'>
                  <Avatar className='h-8 w-8 rounded-lg'>
                    <AvatarImage src={fallbackUser.avatar} alt={displayName} />
                    <AvatarFallback className='rounded-lg'>
                      {initials}
                    </AvatarFallback>
                  </Avatar>
                  <div className='grid flex-1 text-start text-sm leading-tight'>
                    <span className='truncate font-semibold capitalize'>
                      {displayName}
                    </span>
                    <span className='truncate text-xs text-muted-foreground'>
                      {displayEmail}
                    </span>
                  </div>
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
              <DropdownMenuItem
                variant='destructive'
                onClick={() => setOpen(true)}
              >
                <LogOut />
                Esci
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </SidebarMenuItem>
      </SidebarMenu>

      <SignOutDialog open={!!open} onOpenChange={setOpen} />
    </>
  )
}
