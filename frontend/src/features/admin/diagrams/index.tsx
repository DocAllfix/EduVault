/**
 * Diagrams Catalog Admin — `/admin/diagrams` (Step C 2026-05-31).
 *
 * ─── Design intent (frontend-design) ──────────────────────────────────────
 * Purpose: gallery view dei template SVG diagram disponibili (15 totali post
 *   Step D: 7 originali + 8 nuovi timeline/fishbone/cycle_pdca/etc). Per
 *   ogni template mostra preview SVG renderizzato + descrizione semantica +
 *   slot list (name + max_chars) + usage count nei corsi.
 * Tone: gallery wall 3-col grid, calm hover for detail expand, brand
 *   C.F.P. Montessori. Read-only catalog viewer.
 * Constraints: REI-1 shadcn (Card/Badge). SVG inline rendering via iframe
 *   o fetch statico. Pagina admin/reviewer accessible.
 */

import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Layers } from 'lucide-react'
import { Link } from '@tanstack/react-router'

import { api, type DiagramTemplateInfo } from '@/lib/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { ProfileDropdown } from '@/components/profile-dropdown'
import { ThemeSwitch } from '@/components/theme-switch'

export function DiagramsCatalogAdmin() {
  const q = useQuery({
    queryKey: ['admin', 'diagrams-catalog'] as const,
    queryFn: () => api.adminDiagramsCatalog(),
  })

  return (
    <>
      <Header>
        <div className='ms-auto flex items-center gap-2'>
          <ThemeSwitch />
          <ProfileDropdown />
        </div>
      </Header>
      <Main>
        <div className='mb-4 flex items-center gap-2'>
          <Button variant='ghost' size='sm' asChild>
            <Link to='/admin' className='gap-1'>
              <ArrowLeft className='size-4' /> Admin
            </Link>
          </Button>
        </div>

        <div className='mb-6'>
          <h1 className='text-2xl font-bold tracking-tight'>Diagrammi catalog</h1>
          <p className='text-sm text-muted-foreground'>
            {q.data
              ? `${q.data.length} template disponibili, ${q.data.reduce(
                  (acc, t) => acc + t.usage_count,
                  0,
                )} usi totali nei corsi.`
              : 'Catalogo template SVG con preview, slot e usage count.'}
          </p>
        </div>

        {q.isLoading ? (
          <div className='grid gap-4 sm:grid-cols-2 lg:grid-cols-3'>
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className='h-72' />
            ))}
          </div>
        ) : !q.data?.length ? (
          <Card>
            <CardHeader className='items-center text-center'>
              <Layers className='size-12 text-muted-foreground' />
              <CardTitle>Nessun template</CardTitle>
              <CardDescription>
                Il catalogo DIAGRAM_CATALOG è vuoto.
              </CardDescription>
            </CardHeader>
          </Card>
        ) : (
          <div className='grid gap-4 sm:grid-cols-2 lg:grid-cols-3'>
            {q.data.map((tpl) => (
              <DiagramCard key={tpl.name} template={tpl} />
            ))}
          </div>
        )}
      </Main>
    </>
  )
}

function DiagramCard({ template }: { template: DiagramTemplateInfo & { svg_content?: string | null } }) {
  // SVG inline via dangerouslySetInnerHTML: contenuto controllato dal backend
  // (template SVG che SCRIVIAMO NOI in assets/svg_templates), zero user input
  // -> nessun rischio XSS.
  return (
    <Card>
      <CardHeader>
        <div className='flex items-center justify-between'>
          <CardTitle className='font-mono text-base'>{template.name}</CardTitle>
          <Badge variant='secondary'>{template.usage_count} usi</Badge>
        </div>
        <CardDescription className='text-xs'>{template.description}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className='mb-3 aspect-video overflow-hidden rounded-md border bg-muted/30 p-2'>
          {template.svg_content ? (
            <div
              className='size-full [&_svg]:size-full [&_svg]:max-h-full'
              dangerouslySetInnerHTML={{ __html: template.svg_content }}
            />
          ) : (
            <div className='flex size-full items-center justify-center text-xs text-muted-foreground'>
              SVG non disponibile
            </div>
          )}
        </div>
        <div>
          <p className='mb-1 text-[10px] uppercase tracking-wide text-muted-foreground'>
            Slot ({template.slots.length})
          </p>
          <div className='flex flex-wrap gap-1'>
            {template.slots.map((s) => (
              <Badge key={s.name} variant='outline' className='font-mono text-[10px]'>
                {s.name} ≤{s.max_chars}
              </Badge>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
