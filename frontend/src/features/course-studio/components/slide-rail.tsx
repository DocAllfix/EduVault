/**
 * SlideRail — F-STUDIO-UX Step 6 (2026-06-02).
 *
 * ─── Design intent (frontend-design) ──────────────────────────────────────
 * Rail verticale sulla sinistra del Course Studio, organizzato in ACCORDION:
 *   1 modulo aperto alla volta. Click su un modulo → si apre con le sue slide,
 *   gli altri si chiudono. Auto-open del modulo della slide corrente.
 *
 * Pattern Tome/Notion/Gamma: navigation per sezione, riduce cognitive load,
 * niente infinite scroll su corsi 4h+ (80-100+ slide).
 *
 * Per ogni slide (dentro accordion content):
 *  - dot quality severity (verde / arancione / rosso) o vuoto
 *  - numero slide tabular-nums (posizionale globale)
 *  - icon Lucide del tipo (FileText, Image, ListChecks, ecc.)
 *  - title line-clamp-1 (ora c'e` spazio dentro l'accordion content)
 *
 * Filter problematic (lato genitore) gia` applicato a `slides[]`: l'accordion
 * mostrera` solo i moduli con slide problematiche residue.
 */

import { useEffect, useState } from 'react'
import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core'
import {
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import {
  FileText,
  GripVertical,
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
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
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
  /**
   * F-NEXT Fase 1 (2026-06-02): callback per riordinare slide intra-modulo
   * via drag&drop. Riceve global pos `from` e `to` (entrambi 0-based su
   * `slides[]`). Il genitore traduce in chiamate sequenziali
   * `api.moveSlide(courseId, idx, 'up'|'down')`. Se from/to attraversano
   * moduli diversi, il genitore mostra warning e ignora.
   */
  onReorder?: (fromPos: number, toPos: number) => void
}

// F-NEXT Fase 1 (2026-06-02): identificatore univoco per @dnd-kit Sortable
// che resiste al riordinamento del DB (NON usare slide.index perche` cambia
// dopo move). Combinazione module_index + slide-position-locale + slide.index
// fa da chiave stabile durante il drag.
function getSortableId(s: StudioSlide, posInModule: number): string {
  return `slide-${s.module_index ?? 0}-${posInModule}-${s.index}`
}

export function SlideRail({
  slides,
  selectedIdx,
  onSelect,
  qualityData,
  onReorder,
}: SlideRailProps) {
  // Trova la slide selezionata + il suo modulo, per auto-open accordion.
  const selectedSlide = slides.find((s) => s.index === selectedIdx)
  const currentModuleId =
    selectedSlide != null ? `m-${selectedSlide.module_index ?? 0}` : 'm-0'
  const [openModuleId, setOpenModuleId] = useState<string>(currentModuleId)

  // Auto-open: quando l'utente cambia slide (frecce, click TopBar prev/next)
  // e attraversa un modulo, l'accordion segue.
  useEffect(() => {
    setOpenModuleId(currentModuleId)
  }, [currentModuleId])

  // Raggruppa le slide per modulo (preserva l'ordine).
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
    <aside className="border-border bg-card flex h-[calc(100vh-7rem)] w-56 flex-col overflow-y-auto rounded-lg border p-1">
      <Accordion
        type="single"
        collapsible
        value={openModuleId}
        onValueChange={(v) => setOpenModuleId(v || '')}
        className="w-full"
      >
        {groups.map((g) => {
          const moduleSlideCount = g.items.length
          const moduleHasIssue = qualityData?.issues.some(
            (i: { slide_index: number }) => {
              const slideInGroup = g.items.find((s) => s.index === i.slide_index)
              return slideInGroup != null
            },
          )
          return (
            <AccordionItem
              key={`mod-${g.moduleIndex}`}
              value={`m-${g.moduleIndex}`}
              className="border-b-0"
            >
              <AccordionTrigger className="rounded-md px-2 py-2 text-xs font-semibold tracking-wide uppercase hover:bg-muted hover:no-underline data-[state=open]:bg-muted/60">
                <span className="flex items-center gap-2">
                  {moduleHasIssue && (
                    <span
                      className="bg-amber-500 inline-block size-1.5 rounded-full"
                      aria-label="Modulo con slide problematiche"
                    />
                  )}
                  <span className="tabular-nums">M{g.moduleIndex + 1}</span>
                  <span className="text-muted-foreground font-normal normal-case">
                    · {moduleSlideCount} slide
                  </span>
                </span>
              </AccordionTrigger>
              <AccordionContent className="pb-2 pt-1">
                <SortableModuleContent
                  groupItems={g.items}
                  allSlides={slides}
                  moduleIndex={g.moduleIndex}
                  selectedIdx={selectedIdx}
                  onSelect={onSelect}
                  onReorder={onReorder}
                  qualityData={qualityData}
                />
              </AccordionContent>
            </AccordionItem>
          )
        })}
      </Accordion>
    </aside>
  )
}

// ─── F-NEXT Fase 1 (2026-06-02): SortableContext per modulo (intra-modulo
// only). Cross-modulo bloccato lato genitore via warning toast. ───
function SortableModuleContent({
  groupItems,
  allSlides,
  moduleIndex,
  selectedIdx,
  onSelect,
  onReorder,
  qualityData,
}: {
  groupItems: StudioSlide[]
  allSlides: StudioSlide[]
  moduleIndex: number
  selectedIdx: number
  onSelect: (idx: number) => void
  onReorder?: (fromPos: number, toPos: number) => void
  qualityData: QualityIssuesResponse | undefined
}) {
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 5 },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  )

  // Posizioni globali di queste slide (per onReorder traduzione)
  const groupPositionsGlobal = groupItems.map((s) =>
    allSlides.findIndex((x) => x.index === s.index),
  )
  // Ids stable per @dnd-kit. Indice = posizione locale dentro il modulo.
  const sortableIds = groupItems.map((s, posInModule) =>
    getSortableId(s, posInModule),
  )

  const handleDragEnd = (e: DragEndEvent) => {
    const { active, over } = e
    if (!over || active.id === over.id || !onReorder) return
    const fromLocal = sortableIds.indexOf(String(active.id))
    const toLocal = sortableIds.indexOf(String(over.id))
    if (fromLocal < 0 || toLocal < 0) return
    const fromGlobal = groupPositionsGlobal[fromLocal]
    const toGlobal = groupPositionsGlobal[toLocal]
    onReorder(fromGlobal, toGlobal)
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragEnd={handleDragEnd}
    >
      <SortableContext
        items={sortableIds}
        strategy={verticalListSortingStrategy}
      >
        <ul className="space-y-0.5">
          {groupItems.map((s, posInModule) => {
            const meta = getMeta(s.slide_type)
            const posGlobal = allSlides.findIndex((x) => x.index === s.index)
            return (
              <SortableSlideItem
                key={sortableIds[posInModule]}
                id={sortableIds[posInModule]}
                slide={s}
                meta={meta}
                posGlobal={posGlobal}
                moduleIndex={moduleIndex}
                isSelected={s.index === selectedIdx}
                onSelect={onSelect}
                qualityData={qualityData}
              />
            )
          })}
        </ul>
      </SortableContext>
    </DndContext>
  )
}

function SortableSlideItem({
  id,
  slide,
  meta,
  posGlobal,
  isSelected,
  onSelect,
  qualityData,
}: {
  id: string
  slide: StudioSlide
  meta: { label: string; icon: LucideIcon }
  posGlobal: number
  moduleIndex: number
  isSelected: boolean
  onSelect: (idx: number) => void
  qualityData: QualityIssuesResponse | undefined
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  } as React.CSSProperties

  const Icon = meta.icon
  const label = `Slide ${posGlobal + 1} — ${meta.label}${
    slide.title ? ` — ${slide.title}` : ''
  }`

  return (
    <li
      ref={setNodeRef}
      style={style}
      className={cn(
        'group flex items-center gap-1 rounded-md transition-colors',
        isSelected
          ? 'bg-primary/15 text-primary ring-primary/40 ring-1'
          : 'hover:bg-muted text-muted-foreground hover:text-foreground',
      )}
    >
      {/* Grip handle drag — visibile on-hover, attivo solo per drag */}
      <button
        type="button"
        {...attributes}
        {...listeners}
        className="cursor-grab active:cursor-grabbing shrink-0 px-0.5 py-1 opacity-0 transition-opacity group-hover:opacity-60 focus:opacity-100"
        aria-label={`Riordina slide ${posGlobal + 1}`}
        title="Trascina per riordinare"
      >
        <GripVertical className="size-3" />
      </button>
      <button
        type="button"
        onClick={() => onSelect(slide.index)}
        className="flex flex-1 items-center gap-2 px-1 py-1.5 text-left text-xs"
        aria-label={label}
        aria-current={isSelected ? 'true' : undefined}
      >
        <QualityBadge data={qualityData} slideIndex={slide.index} />
        <span className="tabular-nums text-[10px] font-semibold opacity-70 w-5 shrink-0">
          {posGlobal + 1}
        </span>
        <Icon className="size-3.5 shrink-0" aria-hidden="true" />
        <span className="line-clamp-1 flex-1">
          {slide.title || meta.label}
        </span>
      </button>
    </li>
  )
}
