/**
 * F4 D9 — QualityBadge + QualityIssuesPanel (analista sign-off 2026-05-31)
 *
 * ─── Design intent ──────────────────────────────────────────────────────
 * QualityBadge: pallino piccolo (8x8) inline accanto al titolo slide in
 *   sidebar Course Studio. Colore: rosso (error) > arancione (warning) >
 *   blu (info) > nessuno (slide pulita).
 * QualityIssuesPanel: card collapsible nel right rail Course Studio, mostra
 *   lista issue per slide selezionata con tipo + severity + context.
 * Tone: shadcn-admin coerente, brand CFP Montessori (verde/rosa).
 * Constraint REI-1: riusa Badge + Card + ScrollArea shadcn esistenti.
 * Constraint VAA-c (D9): NON blocca download, solo segnala (decisione
 *   analista). Bottone "Rigenera questa slide" (F4b H8) integrato qui per
 *   sinergia visiva con issue catturati.
 */

import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { AlertCircle, AlertTriangle, Info, RefreshCw, Loader2 } from 'lucide-react'
import { toast } from 'sonner'

import { api, ApiError, type QualityIssue } from '@/lib/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
import { getSlideIssues, getSlideMaxSeverity } from '@/hooks/use-quality-checks'
import type { QualityIssuesResponse } from '@/lib/api'

const ISSUE_TYPE_LABELS: Record<string, string> = {
  image_placeholder: 'Immagine mancante',
  diagram_branded_fallback: 'Diagramma fallback brand',
  quiz_no_options: 'Quiz senza opzioni',
  notes_too_short: 'Note speaker troppo brevi',
  module_underpopulated: 'Modulo sotto-popolato',
  module_corpus_thin: 'Corpus normativo insufficiente',
  image_overused_in_module: 'Immagine ripetuta nel modulo',
  title_near_duplicate_in_module: 'Titolo simile ad altra slide',
  bullet_citation_warning: 'Citazione decreto fuori scope',
  bullet_citation_warning_as_object: 'Citazione decreto storico (oggetto)',
  title_citation_warning: 'Decreto fuori scope nel titolo',
}

const SEVERITY_STYLES: Record<
  'error' | 'warning' | 'info',
  { dot: string; badge: string; icon: typeof AlertCircle }
> = {
  error: {
    dot: 'bg-destructive ring-destructive/30',
    badge: 'bg-destructive/15 text-destructive border-destructive/40',
    icon: AlertCircle,
  },
  warning: {
    dot: 'bg-amber-500 ring-amber-300/40',
    badge: 'bg-amber-500/15 text-amber-700 border-amber-500/40 dark:text-amber-300',
    icon: AlertTriangle,
  },
  info: {
    dot: 'bg-sky-500 ring-sky-300/40',
    badge: 'bg-sky-500/15 text-sky-700 border-sky-500/40 dark:text-sky-300',
    icon: Info,
  },
}

/**
 * Pallino inline (8x8) accanto al titolo slide in sidebar.
 * Mostra il max severity issue per la slide. Tooltip con conta + tipi.
 */
export function QualityBadge({
  data,
  slideIndex,
}: {
  data: QualityIssuesResponse | undefined
  slideIndex: number
}) {
  const issues = getSlideIssues(data, slideIndex)
  const severity = getSlideMaxSeverity(data, slideIndex)
  if (!severity || issues.length === 0) return null
  const style = SEVERITY_STYLES[severity]
  const summary = issues
    .map((i) => ISSUE_TYPE_LABELS[i.issue_type] ?? i.issue_type)
    .join(' • ')
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          className={cn(
            'inline-block h-2 w-2 shrink-0 rounded-full ring-2',
            style.dot,
          )}
          aria-label={`${issues.length} issue (${severity})`}
        />
      </TooltipTrigger>
      <TooltipContent side="right" className="max-w-xs">
        <p className="text-xs font-medium">
          {issues.length} issue {severity === 'error' ? '(errore)' : severity === 'warning' ? '(warning)' : '(info)'}
        </p>
        <p className="text-muted-foreground text-xs">{summary}</p>
      </TooltipContent>
    </Tooltip>
  )
}

/**
 * Card right-rail Course Studio: lista issue dettagliati per slide selezionata
 * + bottone F4b "Rigenera questa slide" (H8 voce-aware backend).
 *
 * Non si auto-mostra se zero issue per la slide (resta nascosta, niente
 * ingombro UI).
 */
export function QualityIssuesPanel({
  courseId,
  slideIndex,
  data,
  slideType,
}: {
  courseId: string
  slideIndex: number
  data: QualityIssuesResponse | undefined
  slideType: string
}) {
  const queryClient = useQueryClient()
  const issues = getSlideIssues(data, slideIndex)
  const [showRegenConfirm, setShowRegenConfirm] = useState(false)

  const regenMutation = useMutation({
    mutationFn: () => api.regenerateSlideH8(courseId, slideIndex),
    onSuccess: (result) => {
      toast.success('Slide rigenerata', {
        description: result.new_title
          ? `Nuovo titolo: "${result.new_title.slice(0, 80)}"`
          : 'Slide aggiornata. Esegui Rebuild per ricostruire PPTX.',
      })
      // Invalida cache slide + quality issues
      queryClient.invalidateQueries({ queryKey: ['course-slides', courseId] })
      queryClient.invalidateQueries({ queryKey: ['quality-issues', courseId] })
      queryClient.invalidateQueries({ queryKey: ['course-detail', courseId] })
      setShowRegenConfirm(false)
    },
    onError: (err) => {
      const msg =
        err instanceof ApiError
          ? `${err.status}: ${err.message}`
          : (err as Error).message
      toast.error('Rigenerazione fallita', { description: msg.slice(0, 200) })
      setShowRegenConfirm(false)
    },
  })

  // Bookend slide types non rigenerabili via H8
  const isBookend = ['MODULE_OPEN', 'MODULE_CLOSE', 'TITLE', 'CLOSING'].includes(
    slideType,
  )

  if (issues.length === 0 && !isBookend) {
    return (
      <Card className="border-emerald-500/30 bg-emerald-500/5">
        <CardContent className="pt-6 pb-4 text-center">
          <p className="text-sm text-emerald-700 dark:text-emerald-400">
            ✓ Slide pulita (nessuna issue rilevata)
          </p>
        </CardContent>
      </Card>
    )
  }
  if (issues.length === 0) return null

  // Group by severity (error first)
  const byOrder: Array<'error' | 'warning' | 'info'> = ['error', 'warning', 'info']
  const grouped: Record<string, QualityIssue[]> = {}
  for (const sev of byOrder) {
    const sevIssues = issues.filter((i) => i.severity === sev)
    if (sevIssues.length > 0) grouped[sev] = sevIssues
  }

  return (
    <Card className="border-amber-500/30">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-sm">
          <AlertTriangle className="size-4 text-amber-500" />
          Qualità slide
          <Badge variant="secondary" className="ml-auto">
            {issues.length}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 pt-0">
        <ScrollArea className="max-h-48 pr-2">
          <ul className="space-y-2">
            {byOrder.flatMap((sev) =>
              (grouped[sev] ?? []).map((iss, idx) => {
                const style = SEVERITY_STYLES[sev]
                const Icon = style.icon
                return (
                  <li
                    key={`${sev}-${idx}-${iss.issue_type}`}
                    className={cn(
                      'flex items-start gap-2 rounded-md border p-2 text-xs',
                      style.badge,
                    )}
                  >
                    <Icon className="mt-0.5 size-3.5 shrink-0" />
                    <span className="leading-tight">
                      {ISSUE_TYPE_LABELS[iss.issue_type] ?? iss.issue_type}
                    </span>
                  </li>
                )
              }),
            )}
          </ul>
        </ScrollArea>

        {!isBookend && (
          <div className="border-border border-t pt-3">
            {!showRegenConfirm ? (
              <Button
                variant="outline"
                size="sm"
                className="w-full"
                onClick={() => setShowRegenConfirm(true)}
                disabled={regenMutation.isPending}
              >
                <RefreshCw className="mr-2 size-4" />
                Rigenera questa slide
              </Button>
            ) : (
              <div className="space-y-2">
                <p className="text-muted-foreground text-xs">
                  Rigenera via H8 voce-aware. Operazione 15-30s, sostituisce il
                  contenuto della slide attuale. Esegui poi Rebuild per
                  ricostruire il PPTX.
                </p>
                <div className="flex gap-2">
                  <Button
                    variant="default"
                    size="sm"
                    className="flex-1"
                    onClick={() => regenMutation.mutate()}
                    disabled={regenMutation.isPending}
                  >
                    {regenMutation.isPending ? (
                      <>
                        <Loader2 className="mr-2 size-4 animate-spin" />
                        Rigenerando...
                      </>
                    ) : (
                      'Conferma'
                    )}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setShowRegenConfirm(false)}
                    disabled={regenMutation.isPending}
                  >
                    Annulla
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

/**
 * Summary header (top of Course Studio): conteggio totale + filter toggle.
 */
export function QualityIssuesSummary({
  data,
  onFilterToggle,
  filterActive,
}: {
  data: QualityIssuesResponse | undefined
  onFilterToggle: () => void
  filterActive: boolean
}) {
  if (!data || data.total_issues === 0) return null
  const errors = data.by_severity.error ?? 0
  const warnings = data.by_severity.warning ?? 0
  const infos = data.by_severity.info ?? 0
  return (
    <div className="border-border bg-muted/30 mb-3 flex items-center justify-between gap-2 rounded-md border px-3 py-2 text-xs">
      <div className="flex items-center gap-3">
        <span className="font-medium">
          {data.total_issues} slide richiedono attenzione
        </span>
        {errors > 0 && (
          <Badge variant="destructive" className="text-[10px]">
            {errors} errori
          </Badge>
        )}
        {warnings > 0 && (
          <Badge
            variant="secondary"
            className="bg-amber-500/20 text-amber-700 text-[10px] dark:text-amber-300"
          >
            {warnings} warning
          </Badge>
        )}
        {infos > 0 && (
          <Badge variant="outline" className="text-[10px]">
            {infos} info
          </Badge>
        )}
      </div>
      <Button
        variant={filterActive ? 'default' : 'outline'}
        size="sm"
        className="h-7 text-xs"
        onClick={onFilterToggle}
      >
        {filterActive ? 'Mostra tutte' : 'Filtra problematiche'}
      </Button>
    </div>
  )
}
