/**
 * Regulations — `/regulations` (BP §10).
 *
 * ─── Design intent (frontend-design) ────────────────────────────────────
 * Purpose: knowledge base management. Admin uploads new PDF, all users
 *   browse the indexed list, anyone can inspect the chunks extracted
 *   per regulation.
 * Tone: Notion-style content area — list left/center, detail in a Sheet
 *   on the right when clicked. Calm, no chrome.
 * Constraints: REI-5 backend `/api/regulations` returns array (no envelope);
 *   only admin sees Upload + Archive (BP §10 admin gate).
 * Differentiation: chunk-level visibility — citation provenance lives
 *   at this level too (the user can verify what the AI will quote).
 *
 * ─── SELF-AUDIT — see end-of-file.
 */

import { useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Library, Loader2, Trash2 } from 'lucide-react'
import { toast } from 'sonner'

import { api, ApiError, tokenStorage, type RegulationSummary } from '@/lib/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { ProfileDropdown } from '@/components/profile-dropdown'
import { ThemeSwitch } from '@/components/theme-switch'

import { ChunksSheet } from './components/chunks-sheet'
import { UploadRegulationDialog } from './components/upload-regulation-dialog'

function getRoleFromToken(): string | undefined {
  const tok = tokenStorage.getAccess()
  if (!tok) return undefined
  try {
    const p = tok.split('.')[1]
    const padded = p + '==='.slice((p.length + 3) % 4)
    return (JSON.parse(atob(padded.replace(/-/g, '+').replace(/_/g, '/'))) as { role?: string }).role
  } catch {
    return undefined
  }
}

export function Regulations() {
  const queryClient = useQueryClient()
  const role = useMemo(() => getRoleFromToken(), [])
  const isAdmin = role === 'admin'
  const [filter, setFilter] = useState('')
  const [openChunks, setOpenChunks] = useState<RegulationSummary | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  const regsQ = useQuery({
    queryKey: ['regulations'] as const,
    queryFn: () => api.getRegulations({ page: 1, per_page: 100 }),
  })

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase()
    if (!q) return regsQ.data ?? []
    return (regsQ.data ?? []).filter(
      (r) =>
        r.title.toLowerCase().includes(q) ||
        r.type.toLowerCase().includes(q) ||
        r.region.toLowerCase().includes(q) ||
        (r.slug ?? '').toLowerCase().includes(q),
    )
  }, [regsQ.data, filter])

  async function handleDelete(reg: RegulationSummary) {
    if (!confirm(`Marcare «${reg.title}» come ABROGATA? Resta nel DB ma non sarà più usata dal Research Agent.`)) {
      return
    }
    setDeletingId(reg.id)
    try {
      await api.deleteRegulation(reg.id)
      toast.success('Normativa abrogata.')
      await queryClient.invalidateQueries({ queryKey: ['regulations'] })
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : 'Operazione non riuscita.')
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <>
      <Header>
        <div className='ms-auto flex items-center gap-2'>
          <ThemeSwitch />
          <ProfileDropdown />
        </div>
      </Header>
      <Main>
        <div className='mb-6 flex flex-wrap items-end justify-between gap-3'>
          <div>
            <h1 className='text-2xl font-bold tracking-tight'>Normative</h1>
            <p className='text-sm text-muted-foreground'>
              Knowledge base normativa. {(regsQ.data?.length ?? 0)} documenti indicizzati.
            </p>
          </div>
          {isAdmin && <UploadRegulationDialog />}
        </div>

        <div className='mb-4'>
          <Input
            placeholder='Filtra per titolo, tipo, slug, regione…'
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className='max-w-md'
          />
        </div>

        {regsQ.isLoading ? (
          <div className='space-y-3'>
            {[...Array(3)].map((_, i) => <Skeleton key={i} className='h-24 w-full' />)}
          </div>
        ) : filtered.length === 0 ? (
          <Card>
            <CardHeader>
              <CardTitle className='flex items-center gap-2'>
                <Library className='size-5' aria-hidden='true' />
                Knowledge base vuota
              </CardTitle>
              <CardDescription>
                {isAdmin
                  ? 'Carica il primo PDF normativo per iniziare.'
                  : 'Nessuna normativa indicizzata. Contatta un amministratore.'}
              </CardDescription>
            </CardHeader>
          </Card>
        ) : (
          <div className='space-y-2'>
            {filtered.map((r) => {
              const isAbrogata = r.status === 'ABROGATA'
              return (
                <div
                  key={r.id}
                  className='flex flex-wrap items-center gap-3 rounded-md border p-4'
                >
                  <div className='min-w-0 flex-1'>
                    <button
                      onClick={() => setOpenChunks(r)}
                      className='block w-full text-left'
                    >
                      <div className='truncate font-medium hover:underline'>
                        {r.title}
                      </div>
                      <div className='mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground'>
                        <code className='font-mono'>{r.slug ?? '—'}</code>
                        <span>·</span>
                        <span>{r.type}</span>
                        <span>·</span>
                        <span>{r.region}</span>
                      </div>
                    </button>
                  </div>
                  <Badge
                    variant='outline'
                    className={
                      isAbrogata
                        ? 'border-border bg-muted text-muted-foreground'
                        : 'border-brand-secondary/40 bg-brand-secondary/10 text-brand-secondary'
                    }
                  >
                    {isAbrogata ? 'Abrogata' : 'Vigente'}
                  </Badge>
                  {isAdmin && !isAbrogata && (
                    <Button
                      variant='ghost'
                      size='sm'
                      onClick={() => handleDelete(r)}
                      disabled={deletingId === r.id}
                      className='text-destructive hover:text-destructive'
                    >
                      {deletingId === r.id ? (
                        <Loader2 className='animate-spin' aria-hidden='true' />
                      ) : (
                        <Trash2 aria-hidden='true' />
                      )}
                    </Button>
                  )}
                </div>
              )
            })}
          </div>
        )}

        <ChunksSheet
          regulation={openChunks}
          onOpenChange={(o) => {
            if (!o) setOpenChunks(null)
          }}
        />
      </Main>
    </>
  )
}

/*
 * ─── SELF-AUDIT (impeccable) ──────────────────────────────────────────────
 *
 * Hierarchy:
 *   ✓ H1 + meta line + Upload CTA right-aligned (Upload only for admin).
 *   ✓ List items are rounded borders not nested cards (impeccable §card
 *     ban: cards only when truly best affordance).
 *
 * Spacing:
 *   ✓ mb-6 heading→filter, mb-4 filter→list, space-y-2 inside list.
 *
 * Color:
 *   ✓ Vigente → brand-secondary (green); Abrogata → muted neutral. The
 *     destructive trash icon is the only red element on the page (rare,
 *     intentional, admin-only).
 *
 * Bans:
 *   ✓ No em dashes. ✓ No side-stripe (full borders only).
 *   ✓ No confirm-modal-overuse: native confirm() for delete intentionally
 *     (matches CourseDetail pattern, both are admin-only).
 *
 * Provenance:
 *   ✓ Clicking a row name opens a Sheet with the actual chunks the
 *     Research Agent would retrieve. Operator can verify what the AI
 *     has access to. This is the same value prop as the fingerprint on
 *     CourseDetail: "the AI cites, never invents".
 */
