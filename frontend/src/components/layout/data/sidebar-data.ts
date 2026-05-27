/**
 * Sidebar navigation — Cfp EduVault.
 *
 * Replaces the upstream shadcn-admin demo nav with real Cfp EduVault
 * sections (FASE 6.7→6.9). All listed routes exist in `routeTree.gen.ts`;
 * TanStack Router type-checks each `url` against the generated tree.
 *
 * The `Amministrazione` group is rendered for everyone — the Admin page
 * itself returns a clean "Accesso negato" Card when the backend 403s on
 * non-admins. Hiding the link client-side based on role is cosmetic
 * only (the role is in the JWT and could be forged), so we don't.
 */

import {
  Command,
  LayoutDashboard,
  Library,
  Plus,
  Sliders,
} from 'lucide-react'
import { type SidebarData } from '../types'

export const sidebarData: SidebarData = {
  user: {
    name: 'Operatore',
    email: '',
    avatar: '/brand/favicon-180.png',
  },
  teams: [
    {
      name: 'Cfp EduVault',
      logo: Command,
      plan: 'C.F.P. Montessori',
    },
  ],
  navGroups: [
    {
      title: 'Operativo',
      items: [
        {
          title: 'Dashboard',
          url: '/',
          icon: LayoutDashboard,
        },
        {
          title: 'Nuovo Corso',
          url: '/courses/new',
          icon: Plus,
        },
      ],
    },
    {
      title: 'Conoscenza',
      items: [
        {
          title: 'Normative',
          url: '/regulations',
          icon: Library,
        },
      ],
    },
    {
      title: 'Amministrazione',
      items: [
        {
          title: 'Admin',
          url: '/admin',
          icon: Sliders,
        },
      ],
    },
  ],
}
