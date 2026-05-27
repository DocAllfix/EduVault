import { useMemo } from 'react'
import { useLayout } from '@/context/layout-provider'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarRail,
} from '@/components/ui/sidebar'
import { getRole } from '@/lib/auth'
import { AppTitle } from './app-title'
import { sidebarData } from './data/sidebar-data'
import { NavGroup } from './nav-group'
import { NavUser } from './nav-user'

// Section titles that are admin-only — filtered out of the sidebar for
// operator/reviewer roles. The corresponding routes still exist and the
// pages themselves render a clean "Accesso negato" Card when the backend
// 403s, but hiding the nav reduces visual noise for non-admins.
const ADMIN_ONLY_GROUPS = new Set(['Amministrazione', 'Conoscenza'])

export function AppSidebar() {
  const { collapsible, variant } = useLayout()
  const role = getRole()
  const visibleGroups = useMemo(() => {
    if (role === 'admin') return sidebarData.navGroups
    return sidebarData.navGroups.filter(
      (g) => !ADMIN_ONLY_GROUPS.has(g.title),
    )
  }, [role])

  return (
    <Sidebar collapsible={collapsible} variant={variant}>
      <SidebarHeader>
        <AppTitle />
      </SidebarHeader>
      <SidebarContent>
        {visibleGroups.map((props) => (
          <NavGroup key={props.title} {...props} />
        ))}
      </SidebarContent>
      <SidebarFooter>
        <NavUser user={sidebarData.user} />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
