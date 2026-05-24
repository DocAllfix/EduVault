/**
 * Auth layout — Nexus EduVault.
 *
 * Shared shell for all routes under `(auth)/*` (sign-in only in v1.0;
 * forgot-password and otp template scaffolds are unused — REI-4, BP §08).
 *
 * Composition (impeccable skill, refined-minimalism register):
 *  - centered vertical stack on a calm neutral surface (no gradient/glass)
 *  - real C.F.P. Montessori logo above the form (recognizable identity in
 *    0.2s, not a placeholder; satisfies REI-1 brand requirement)
 *  - one-line tagline "Generazione corsi normativi" sets context without
 *    marketing copy
 *  - everything left of vh: container is `max-w-sm` so the form never
 *    stretches absurdly wide on desktop
 *
 * The page <title> is set per-route by the SignIn page (not here), since
 * other (auth) routes will want different titles.
 */

type AuthLayoutProps = {
  children: React.ReactNode
}

export function AuthLayout({ children }: AuthLayoutProps) {
  return (
    <div className='grid min-h-svh place-items-center bg-background px-4 py-8'>
      <div className='w-full max-w-sm space-y-6'>
        {/* Brand block — logo + wordmark + tagline */}
        <div className='flex flex-col items-center gap-3 text-center'>
          <img
            src='/brand/logo.png'
            alt='C.F.P. Montessori'
            className='h-12 w-auto object-contain dark:hidden'
          />
          {/* Transparent variant for dark mode (FASE 6.3 auto-gen) */}
          <img
            src='/brand/logo-transparent.png'
            alt='C.F.P. Montessori'
            className='hidden h-12 w-auto object-contain dark:block'
          />
          <div className='space-y-1'>
            <h1 className='text-xl font-semibold tracking-tight'>
              Cfp EduVault
            </h1>
            <p className='text-sm text-muted-foreground'>
              Generazione corsi normativi
            </p>
          </div>
        </div>
        {children}
      </div>
    </div>
  )
}
