/**
 * Auth layout — Nexus EduVault.
 *
 * Shared shell for all routes under `(auth)/*` (sign-in only in v1.0;
 * forgot-password and otp template scaffolds are unused — REI-4, BP §08).
 *
 * Composition (impeccable skill, refined-minimalism register):
 *  - centered vertical stack on a calm neutral surface (no gradient/glass)
 *  - text-only "EduVault" wordmark above the form (rebrand 2026-07-11:
 *    legacy client branding fully removed, no image asset needed)
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
    <div className='grid min-h-svh place-items-center bg-gradient-to-b from-background to-muted/40 px-4 py-8'>
      <div className='w-full max-w-sm space-y-7'>
        {/* Brand block — wordmark testuale, nessun asset immagine. */}
        <div className='flex flex-col items-center gap-3 text-center'>
          <h1 className='text-3xl font-bold tracking-tight'>
            Edu<span className='text-primary'>Vault</span>
          </h1>
          <p className='text-sm text-muted-foreground'>
            Generazione corsi normativi
          </p>
        </div>
        {children}
      </div>
    </div>
  )
}
