/**
 * SlideRail — F-STUDIO-UX Step 2 (2026-06-02).
 *
 * ─── Design intent (frontend-design) ──────────────────────────────────────
 * Rail verticale slim 56px sulla sinistra del Course Studio. Sostituisce la
 * sidebar testuale 220px (numero + tipo + titolo line-clamp-2). Pattern di
 * riferimento: Tome, Pitch, Gamma — sidebar visual minimale, info ricca
 * on-hover via Tooltip.
 *
 * Per ogni slide:
 *  - dot quality severity (verde / arancione / rosso) o vuoto
 *  - numero slide tabular-nums (1-based, posizionale)
 *  - icon Lucide del tipo (FileText, Image, ListChecks, ecc.)
 * On-hover Tooltip: "Slide N — TYPE_LABEL — Titolo intero" + eventuali issue.
 *
 * Group divider tra moduli: sticky header "M1", "M2"... a 10px font-mono.
 * Filter problematic resta lato genitore (filterProblematic gia` applicato a
 * slides[] prima del rendering).
 *
 * Recupera ~165px larghezza per il canvas slide preview.
 */

import {
  FileText,
  Image as ImageIcon,
  LayoutPanelTop,
  ListChecks,
  ListTree,
  Presentation,
  RefreshCcw,
  Sparkles,
  XCircle,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
import type { QualityIssuesResponse, StudioSlide } from '@/lib/api'

import { QualityBadge } from './quality-badge'

const SLIDE_TYPE_META: Record<string, { label: string; icon: LucideIcon }> = {
  TITLE: { label: 'Titolo', icon: Presentation },
  MODULE_OPEN: { label: 'Apri modulo', icon: Sparkles },
  MODULE_CLOSE: { label: 'Chiudi modulo', icon: XCircle },
  CONTENT_TEXT: { label: 'Contenuto', icon: FileText },
  CONTENT_IMAGE: { label: 'Immagine', icon: ImageIcon },
  DIAGRAM: { label: 'Diagramma', icon: LayoutPanelTop },
  QUIZ: { label: 'Quiz', icon: ListChecks },
  CASE_STUDY: { label: 'Caso', icon: ListTree },
  RECAP: { label: 'Riepilogo', icon: RefreshCcw },
  CLOSING: { label: 'Chiusura', icon: XCircle },
}

function getMeta(t: string): { label: string; icon: LucideIcon } {
  return SLIDE_TYPE_META[t] ?? { label: t, icon: FileText }
}

export interface SlideRailProps {
  slides: StudioSlide[]
  selectedIdx: number
  onSelect: (idx: number) => void
  qualityData: QualityIssuesResponse | undefined
}

export function SlideRail({
  slides,
  selectedIdx,
  onSelect,
  qualityData,
}: SlideRailProps) {
  // Costruzione gruppi per modulo: array di { moduleIndex, slides[] }
  const groups: Array<{ moduleIndex: number; items: StudioSlide[] }> = []
  let currentGroup: { moduleIndex: number; items: StudioSlide[] } | null = null
  for (const s of slides) {
    const mi = s.module_index ?? 0
    if (!currentGroup || currentGroup.moduleIndex !== mi) {
      currentGroup = { moduleIndex: mi, items: [] }
      groups.push(currentGroup)
    }
    currentGroup.items.push(s)
  }

  return (
    <TooltipProvider delayDuration={150}>
      <aside className="border-border bg-card flex h-[calc(100vh-7rem)] w-14 flex-col items-stretch overflow-y-auto rounded-lg border">
        {groups.map((g) => (
          <div key={`mod-${g.moduleIndex}`} className="flex flex-col">
            <div className="bg-muted/40 text-muted-foreground sticky top-0 z-10 mx-1 mt-1 rounded px-1.5 py-0.5 text-center font-mono text-[10px] font-semibold tabular-nums tracking-tight">
              M{g.moduleIndex + 1}
            </div>
            <ul className="space-y-0.5 py-1">
              {g.items.map((s, posLocal) => {
                const isSelected = s.index === selectedIdx
                const meta = getMeta(s.slide_type)
                const Icon = meta.icon
                // pos globale all'interno di `slides` per il numero
                const posGlobal = slides.findIndex((x) => x.index === s.index)
                const label = `Slide ${posGlobal + 1} — ${meta.label}${
                  s.title ? ` — ${s.title}` : ''
                }`
                return (
                  <li key={`${g.moduleIndex}-${s.index}-${posLocal}`}>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <button
                          type="button"
                          onClick={() => onSelect(s.index)}
                          className={cn(
                            'group relative mx-auto flex size-11 flex-col items-center justify-center gap-0.5 rounded-md transition-colors',
                            isSelected
                              ? 'bg-primary/15 text-primary ring-primary/40 ring-1'
                              : 'hover:bg-muted text-muted-foreground hover:text-foreground',
                          )}
                          aria-label={label}
                          aria-current={isSelected ? 'true' : undefined}
                        >
                          <span className="absolute top-0.5 left-0.5">
                            <QualityBadge
                              data={qualityData}
                              slideIndex={s.index}
                            />
                          </span>
                          <span className="tabular-nums text-[10px] font-semibold leading-none">
                            {posGlobal + 1}
                          </span>
                          <Icon className="size-3.5" aria-hidden="true" />
                        </button>
                      </TooltipTrigger>
                      <TooltipContent side="right" className="max-w-xs">
                        <div className="text-xs font-medium">
                          {meta.label} · Slide {posGlobal + 1}
                        </div>
                        {s.title && (
                          <div className="text-muted-foreground mt-0.5 line-clamp-3 text-xs">
                            {s.title}
                          </div>
                        )}
                      </TooltipContent>
                    </Tooltip>
                  </li>
                )
              })}
            </ul>
          </div>
        ))}
      </aside>
    </TooltipProvider>
  )
}
