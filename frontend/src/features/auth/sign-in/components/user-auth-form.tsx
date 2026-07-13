/**
 * Sign-in form — Nexus EduVault.
 *
 * ─── Design intent (frontend-design skill, point 1) ──────────────────────
 * Purpose: single-shot authentication for EduVault staff (admin,
 *   reviewer, operator). 1× per day, low ceremony.
 * Tone: refined minimalism istituzionale (refused: AI-workflow slop,
 *   glassmorphism, gradients, hero copy).
 * Constraints: REI-1 adapt template, REI-4 NO social/Clerk, REI-11
 *   pixel-perfect with existing shadcn primitives.
 * Differentiation: one brand-pink CTA on a quiet neutral surface
 *   (90/10 enterprise pattern). Italian native copy. No "forgot password"
 *   (BP §08 v1.0: admin-only password reset out of band).
 *
 * ─── Impeccable self-audit (point 4) — see end-of-file SELF-AUDIT block.
 */

import { useState } from 'react'
import { z } from 'zod'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useNavigate } from '@tanstack/react-router'
import { Loader2, LogIn } from 'lucide-react'
import { toast } from 'sonner'

import { api, ApiError } from '@/lib/api'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { PasswordInput } from '@/components/password-input'

// Validation: minimal (UX); the backend is the source of truth.
// We rely on `api.login` → 401 for wrong credentials, surfaced as toast.
const formSchema = z.object({
  email: z.email({
    error: (iss) =>
      iss.input === ''
        ? 'Inserisci la tua email.'
        : 'Email non valida.',
  }),
  password: z
    .string()
    .min(1, 'Inserisci la password.'),
})

type FormValues = z.infer<typeof formSchema>

interface UserAuthFormProps extends React.HTMLAttributes<HTMLFormElement> {
  redirectTo?: string
}

export function UserAuthForm({
  className,
  redirectTo,
  ...props
}: UserAuthFormProps) {
  const [isLoading, setIsLoading] = useState(false)
  const navigate = useNavigate()

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: { email: '', password: '' },
  })

  async function onSubmit(data: FormValues) {
    setIsLoading(true)
    try {
      // api.login() persists access + refresh tokens in localStorage
      // (FASE 6.5). On 401 it throws ApiError; the global 401-refresh
      // interceptor in api.ts skips login (noAuth: true) so this throw
      // reaches us cleanly without retry loops.
      await api.login(data.email, data.password)

      // BP §10: dashboard is the post-login landing. `redirectTo` lets the
      // router restore the URL the user was trying to reach when bounced
      // here by the auth guard (FASE 6.10).
      const target = redirectTo || '/dashboard'
      toast.success('Accesso effettuato.')
      // The `to` is typed against routeTree.gen.ts — redirectTo is an
      // arbitrary string from `?redirect=`, so we cast through unknown.
      navigate({ to: target as unknown as '/dashboard', replace: true })
    } catch (err) {
      // Backend message is intentionally generic ("Credenziali non
      // valide") to prevent user-enumeration (BP §08.5). We surface it
      // verbatim — no client-side rewording that would leak more info.
      const msg =
        err instanceof ApiError
          ? err.message || 'Credenziali non valide.'
          : 'Impossibile contattare il server. Riprova.'
      toast.error(msg)
      // Focus password to let the user retry without re-typing email.
      form.setFocus('password')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Form {...form}>
      <form
        onSubmit={form.handleSubmit(onSubmit)}
        className={cn('grid gap-4', className)}
        noValidate
        {...props}
      >
        <FormField
          control={form.control}
          name='email'
          render={({ field }) => (
            <FormItem>
              <FormLabel>Email</FormLabel>
              <FormControl>
                <Input
                  type='email'
                  autoComplete='username'
                  autoFocus
                  placeholder='nome@eduvault.it'
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name='password'
          render={({ field }) => (
            <FormItem>
              <FormLabel>Password</FormLabel>
              <FormControl>
                <PasswordInput
                  autoComplete='current-password'
                  placeholder='********'
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <Button
          type='submit'
          className='mt-1 w-full'
          disabled={isLoading}
          aria-busy={isLoading}
        >
          {isLoading ? (
            <Loader2 className='animate-spin' aria-hidden='true' />
          ) : (
            <LogIn aria-hidden='true' />
          )}
          {isLoading ? 'Accesso in corso…' : 'Accedi'}
        </Button>
      </form>
    </Form>
  )
}

/*
 * ─── SELF-AUDIT (impeccable skill, point 4) ──────────────────────────────
 *
 * Hierarchy:
 *   ✓ Single H1 ("Accedi al portale") lives in the page (not here). Form
 *     has no headings — labels carry their weight via FormLabel.
 *   ✓ Primary CTA dominant: w-full, brand-primary (rosa #C82E6E via theme).
 *     No competing CTAs (social signin removed per REI-4).
 *
 * Spacing:
 *   ✓ Form gap-4 (16px). Vertical rhythm matches the page Card gap-4.
 *   ✓ Button mt-1 separates it slightly from the last field without
 *     creating a visual gap that suggests another section.
 *
 * Alignment:
 *   ✓ All FormItems left-aligned, full width. No floating "Forgot
 *     password" link (template had one absolutely-positioned at top-right
 *     of the password field — removed: BP §08 v1.0 has no reset flow).
 *
 * A11y:
 *   ✓ `autoFocus` on email lets keyboard users start typing immediately.
 *   ✓ `autoComplete=username | current-password` enables password
 *     managers (1Password, browser native).
 *   ✓ `aria-busy` on the submit button announces async state.
 *   ✓ `noValidate` on <form> disables the browser's English validation
 *     bubbles in favor of our localized Zod messages.
 *   ✓ Loader/LogIn icons marked `aria-hidden` since the visible text
 *     already conveys state to AT users.
 *
 * Italian copy:
 *   ✓ All user-facing strings in IT. Backend already returns Italian
 *     errors ("Credenziali non valide"). No translation layer.
 *
 * Bans applied (impeccable):
 *   ✓ No em dashes in copy. ✓ No gradient text. ✓ No side-stripe.
 *   ✓ No glassmorphism. ✓ No modal. ✓ No hero-metric template.
 *
 * Deferred to 6.5 follow-up (Clerk removal cleanup):
 *   - The `useAuthStore` Zustand placeholder in `stores/auth-store.ts`
 *     still exists with the template's mock-user shape. This form no
 *     longer writes to it (api.ts owns token storage). The store will be
 *     deleted or rewritten when we add the auth guard in 6.10.
 */
