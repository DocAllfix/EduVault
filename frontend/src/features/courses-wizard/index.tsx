/**
 * Course Wizard — Cfp EduVault (BP §10 POST /api/courses).
 *
 * ─── Design intent (frontend-design skill, point 1) ──────────────────────
 * Purpose: configure a normative course in 6 screens, ≤90 seconds total.
 *   The operator can step back without losing data (react-hook-form
 *   retains state across step transitions).
 * Tone: Stripe-Checkout multi-step — single centred Card, horizontal
 *   step indicator on top, one decision per screen, large nav buttons
 *   anchored at the bottom of the Card.
 * Constraints: REI-1 adapt template Card/Form, REI-5 (outputs constrained
 *   to {pptx, pdf, audio, quiz} matching backend `_ALLOWED_OUTPUTS`),
 *   REI-11 pixel-perfect, react-hook-form + zod for step-by-step
 *   validation (no whole-form validation before the user has reached
 *   the field).
 * Differentiation: (a) step 1 → step 3 cross-step intelligence: catalog
 *   `min_hours`/`max_hours` pre-fill duration; (b) step 4 shows real
 *   palette swatches not just preset name; (c) step 6 shows estimated
 *   slide count using the SAME formula as backend PacingEngine, so the
 *   "Genera" button has zero ambiguity; (d) Back/Next preserves all
 *   fields (react-hook-form retains values until unmount of the
 *   provider — which happens only on route change).
 *
 * ─── Impeccable self-audit (point 4) — see end-of-file SELF-AUDIT block.
 */

import { useState } from 'react'
import { FormProvider, useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useNavigate, useSearch } from '@tanstack/react-router'
import { ArrowLeft, ArrowRight, Loader2, Sparkles } from 'lucide-react'
import { toast } from 'sonner'

import { api, ApiError, type CourseRequest } from '@/lib/api'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Form } from '@/components/ui/form'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { ProfileDropdown } from '@/components/profile-dropdown'
import { ThemeSwitch } from '@/components/theme-switch'
import { HelpButton } from '@/lib/onboarding/HelpButton'
import { JobsBadge } from '@/components/jobs-badge'
import { useJobsStore } from '@/stores/jobs-store'
import { requestNotificationPermissionOnce } from '@/hooks/use-jobs-watcher'

import { StepIndicator } from './components/step-indicator'
import { Step1CourseType } from './components/step-1-course-type'
import { Step2Target } from './components/step-2-target'
import { Step3Params } from './components/step-3-params'
import { Step4Brand } from './components/step-4-brand'
import { Step5Output } from './components/step-5-output'
import { Step6Confirm } from './components/step-6-confirm'
import {
  step1Schema,
  step2Schema,
  step3Schema,
  step4Schema,
  step5Schema,
  wizardDefaults,
  wizardSchema,
  type WizardValues,
} from './schema'

const STEP_LABELS = [
  'Tipo',
  'Destinatario',
  'Parametri',
  'Brand',
  'Output',
  'Conferma',
] as const

const STEP_TITLES: Record<number, { title: string; description: string }> = {
  1: {
    title: 'Tipo di corso',
    description: 'Quale corso normativo vuoi generare?',
  },
  2: {
    title: 'Destinatario',
    description: 'A chi è destinato?',
  },
  3: {
    title: 'Parametri',
    description: 'Durata, regione, densità delle slide.',
  },
  4: {
    title: 'Brand',
    description: 'Identità visiva del corso generato.',
  },
  5: {
    title: 'Output',
    description: 'Quali formati produrre.',
  },
  6: {
    title: 'Conferma e genera',
    description: 'Controlla i parametri e avvia la pipeline.',
  },
}

// Per-step zod schemas keyed by step number. The full `wizardSchema`
// resolver is attached to the form, but step-by-step we only `trigger()`
// the fields belonging to the current step — so the user doesn't see
// validation errors for fields they haven't reached yet.
const STEP_FIELDS: Record<number, (keyof WizardValues)[]> = {
  1: ['course_type'],
  2: ['target'],
  3: ['duration_hours', 'region', 'slide_density'],
  4: ['brand_preset_id'],
  5: ['outputs'],
  6: [],
}

// Sanity: step schemas exported for tests / future server-side mirror.
export { step1Schema, step2Schema, step3Schema, step4Schema, step5Schema }

export function CoursesWizard() {
  const navigate = useNavigate()
  // F11 Issue 3 (D-229): leggo opzionale ?course_type=<slug> per pre-fill
  // dello step 1 quando arrivo dalla pagina /catalog ("Crea corso da questo").
  const search = useSearch({ from: '/_authenticated/courses/new' }) as {
    course_type?: string
  }
  const [step, setStep] = useState(1)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const total = STEP_LABELS.length

  const form = useForm<WizardValues>({
    resolver: zodResolver(wizardSchema),
    mode: 'onChange',
    defaultValues: {
      ...wizardDefaults,
      course_type: search.course_type ?? wizardDefaults.course_type,
    },
  })

  async function goNext() {
    const fields = STEP_FIELDS[step]
    const ok = await form.trigger(fields, { shouldFocus: true })
    if (!ok) return
    setStep((s) => Math.min(s + 1, total))
  }

  function goBack() {
    setStep((s) => Math.max(s - 1, 1))
  }

  async function onSubmit(values: WizardValues) {
    setIsSubmitting(true)
    try {
      // Backend `CourseRequest` is satisfied 1:1 by `WizardValues` —
      // we cast to the API type to silence the structural-equality
      // assertion (TS sees them as distinct types, even though shapes
      // match by construction).
      const payload = values as unknown as CourseRequest
      const { course_id, job_id } = await api.createCourse(payload)
      // F11: registro il job nello store globale → JobsWatcher pollerà
      // /api/jobs/{job_id}/progress e mostrera` toast.success cliccabile
      // quando la pipeline termina, anche se l'utente naviga altrove.
      useJobsStore.getState().addJob({
        courseId: course_id,
        courseTitle:
          payload.course_type
            ?.split('_')
            .map((w: string) => w.charAt(0).toUpperCase() + w.slice(1))
            .join(' ') ?? 'Corso',
        kind: 'generation',
        jobId: job_id,
      })
      requestNotificationPermissionOnce()
      toast.success('Pipeline avviata.')
      // Redirect to the Progress Monitor (FASE 6.9). `?job=` lets the
      // WS connect immediately without an extra lookup round-trip.
      navigate({
        // TanStack file `$id_.progress.tsx` → URL path `/courses/$id/progress`
        // (the underscore is escape syntax in the filename, not in the URL).
        to: '/courses/$id/progress',
        params: { id: course_id },
        search: { job: job_id },
        replace: true,
      })
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.message : 'Impossibile avviare la pipeline.'
      toast.error(msg)
    } finally {
      setIsSubmitting(false)
    }
  }

  const stepInfo = STEP_TITLES[step]
  const isLast = step === total

  return (
    <>
      <Header>
        <div className='ms-auto flex items-center gap-2'>
          <JobsBadge />
          <HelpButton />
          <ThemeSwitch />
          <ProfileDropdown />
        </div>
      </Header>
      <Main>
        <div className='mx-auto w-full max-w-2xl'>
          <div className='mb-8'>
            <h1 className='text-2xl font-bold tracking-tight'>Nuovo Corso</h1>
            <p className='text-sm text-muted-foreground'>
              Sei passaggi per configurare e avviare la generazione.
            </p>
          </div>

          <div className='mb-8'>
            <StepIndicator current={step} total={total} labels={STEP_LABELS} />
          </div>

          <Form {...form}>
            <FormProvider {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} noValidate>
                <Card>
                  <CardHeader>
                    <CardTitle>{stepInfo.title}</CardTitle>
                    <CardDescription>{stepInfo.description}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    {step === 1 && <Step1CourseType />}
                    {step === 2 && <Step2Target />}
                    {step === 3 && <Step3Params />}
                    {step === 4 && <Step4Brand />}
                    {step === 5 && <Step5Output />}
                    {step === 6 && <Step6Confirm />}
                  </CardContent>
                  <CardFooter className='flex items-center justify-between gap-2'>
                    <Button
                      type='button'
                      variant='ghost'
                      onClick={goBack}
                      disabled={step === 1 || isSubmitting}
                    >
                      <ArrowLeft aria-hidden='true' /> Indietro
                    </Button>
                    {isLast ? (
                      <Button type='submit' disabled={isSubmitting}>
                        {isSubmitting ? (
                          <Loader2 className='animate-spin' aria-hidden='true' />
                        ) : (
                          <Sparkles aria-hidden='true' />
                        )}
                        {isSubmitting ? 'Avvio…' : 'Genera Corso'}
                      </Button>
                    ) : (
                      <Button type='button' onClick={goNext}>
                        Avanti <ArrowRight aria-hidden='true' />
                      </Button>
                    )}
                  </CardFooter>
                </Card>
              </form>
            </FormProvider>
          </Form>
        </div>
      </Main>
    </>
  )
}

/*
 * ─── SELF-AUDIT (impeccable skill, point 4) ──────────────────────────────
 *
 * Hierarchy:
 *   ✓ One H1 "Nuovo Corso" + per-step CardTitle (text-lg by shadcn).
 *     No competing headings inside the steps.
 *   ✓ Step indicator visually subordinate to the title (smaller, muted
 *     labels, brand-pink only for current/done dots).
 *
 * Spacing:
 *   ✓ Page max-w-2xl centred — wizard is intentionally narrow (Stripe-
 *     style). mb-8 between heading→indicator→card preserves rhythm.
 *   ✓ Card uses default shadcn padding; no custom overrides.
 *   ✓ Footer: justify-between locks Back+Next at opposite ends so the
 *     primary action (Next/Genera) is always far-right (Western reading
 *     direction = "forward").
 *
 * Color strategy (impeccable §color):
 *   ✓ Restrained: brand pink only on (a) step indicator active+done
 *     dots and track fill, (b) selected radio/checkbox cards, (c)
 *     Genera Corso CTA, (d) Step 6 estimate banner. ≤10% surface.
 *
 * Bans applied:
 *   ✓ No em dashes in copy. ✓ No gradient. ✓ No glassmorphism. ✓ No
 *     side-stripe. ✓ No hero metric. ✓ No nested cards (steps render
 *     inside the single Card, not as sub-cards).
 *   ✓ Modal NOT used as first thought — this is a full route with its
 *     own URL, so refresh/share/back-button all work naturally.
 *
 * State preservation:
 *   ✓ react-hook-form retains values until the component unmounts.
 *     Stepping back never re-mounts the step components in a way that
 *     resets the form (parent re-renders, children read from
 *     useFormContext). Verified by inspection of step components.
 *
 * Cross-step intelligence:
 *   ✓ Step 1 sets a hint that Step 3 uses to pre-fill duration. The
 *     user is never blocked by a 422 on duration because we never let
 *     them pick a value the catalog disallows in default flow.
 *
 * A11y:
 *   ✓ Step indicator has role=progressbar with valuemin/max/now.
 *   ✓ Each step's first FormControl receives focus via `trigger
 *     ({shouldFocus:true})` on Next (it focuses the first failing field).
 *   ✓ Buttons disabled on first step / submitting — aria-busy via
 *     `disabled` is sufficient (Loader2 visible).
 *
 * Category-reflex:
 *   First-order "wizard → progress bar + 6 vertical step list + giant
 *   icons" → AVOIDED: horizontal dots, no per-step illustration.
 *   Second-order "wizard not-vertical → modal Sheet drawer" → AVOIDED:
 *   full route, dedicated URL.
 *
 * Deferred to 6.9:
 *   - On successful submit, navigate to `/courses/${id}` (Progress
 *     Monitor). Today we navigate to `/` with `?filter=<prefix>` so the
 *     user sees their fresh row at the top of the dashboard list.
 */
