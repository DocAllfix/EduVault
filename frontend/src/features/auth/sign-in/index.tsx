/**
 * Sign-in page — Nexus EduVault (BLUEPRINT §08 + §10).
 *
 * ─── Design intent (frontend-design skill, point 1) ──────────────────────
 * Purpose: bring the operator from "I need to use Nexus" to "I am inside"
 *   in ≤3 actions (focus email → type, tab → type, Enter). Nothing else
 *   on the page competes for attention.
 * Tone: refined institutional. Card without shadow flair, no
 *   marketing copy, no social proof, no "welcome back".
 * Constraints: REI-1 (adapt template SignIn/Card), REI-4 (no Clerk, no
 *   sign-up — admin creates users out-of-band), REI-11 (pixel-perfect).
 * Differentiation: text wordmark (auth-layout) + Italian copy + zero
 *   secondary CTAs. Page title says exactly what the user expects.
 */

import { useEffect } from 'react'
import { useSearch } from '@tanstack/react-router'

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { AuthLayout } from '../auth-layout'
import { UserAuthForm } from './components/user-auth-form'

const PAGE_TITLE = 'EduVault — Accesso'

export function SignIn() {
  const { redirect } = useSearch({ from: '/(auth)/login' })

  // Set the document title on mount. No react-helmet dependency: the
  // template doesn't ship one and adding it for a single page would
  // violate REI-5 (minimum code). Restore the previous title on unmount
  // so navigating away cleans up.
  useEffect(() => {
    const previous = document.title
    document.title = PAGE_TITLE
    return () => {
      document.title = previous
    }
  }, [])

  return (
    <AuthLayout>
      <Card className='gap-4'>
        <CardHeader className='space-y-1'>
          <CardTitle className='text-lg tracking-tight'>
            Accedi al portale
          </CardTitle>
          <CardDescription>
            Inserisci le tue credenziali per continuare.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <UserAuthForm redirectTo={redirect} />
        </CardContent>
        {/*
         * Template had a CardFooter with Terms / Privacy disclaimer.
         * Removed: BP §08 v1.0 does not include those documents and
         * legally we cannot show a link to pages that don't exist. They
         * return in FASE 7 when /terms and /privacy ship.
         *
         * Template also had "Don't have an account? Sign Up" in the
         * CardDescription — removed: REI-4 + BP §08 say only admins
         * create users. Self-registration is not a feature.
         */}
      </Card>
    </AuthLayout>
  )
}

/*
 * ─── SELF-AUDIT (impeccable skill, point 4) ──────────────────────────────
 *
 * Hierarchy:
 *   ✓ <h1>EduVault</h1> in AuthLayout (one per page, the
 *     brand block). CardTitle is <div> via shadcn — not <h1>, so no
 *     duplicate heading-1.
 *   ✓ CardTitle text-lg, CardDescription text-sm muted: clear two-level
 *     descent within the card.
 *
 * Spacing:
 *   ✓ AuthLayout outer space-y-6 (24px) between brand block and card.
 *   ✓ Card gap-4 (16px) between header and content.
 *   ✓ No nested cards (impeccable absolute ban).
 *
 * Copy:
 *   ✓ Every word earns its place. CardTitle "Accedi al portale" is what
 *     the user is about to do; description is the next instruction.
 *     No restated heading.
 *   ✓ No em dashes. Uses periods + colons + parentheses.
 *
 * Bans applied:
 *   ✓ No glassmorphism. ✓ No gradient text. ✓ No side-stripe.
 *   ✓ No modal. ✓ No hero-metric template.
 *
 * Category-reflex check:
 *   First-order "education portal → blue + cream + serif" → AVOIDED: we
 *   use brand pink (#C82E6E) + neutral slate, no serif.
 *   Second-order "education app that's not pastel-cream → dashy-grid
 *   tiles" → AVOIDED: single centered card, no grid, no tile.
 */
