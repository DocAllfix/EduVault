/**
 * EnrichedStats — 4 dati aggiuntivi dashboard (FASE 13 vast-hopping-sketch):
 * 1. breakdown corsi per status, 2. ultimi 5 corsi, 3. corsi con modifiche
 * non rigenerate (dirty), 4. ore totali di formazione prodotte.
 *
 * Design: riga di 3 mini-card (status / dirty / ore) + lista compatta degli
 * ultimi 5 corsi. REI-1 riusa Card shadcn, niente grafici (coerente con la
 * dashboard esistente).
 */

import { useNavigate } from '@tanstack/react-router'
import { Clock, FileWarning, Layers } from 'lucide-react'

import type { components } from '@/lib/api'
import { cn } from '@/lib/utils'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { CourseStatusBadge } from './course-status-badge'

type DashboardStats = components['schemas']['DashboardStats']

const STATUS_ORDER = [
  'generating',
  'completed',
  'reviewed',
  'certified',
  'failed',
  'archived',
] as const

export function EnrichedStats({ stats }: { stats?: DashboardStats }) {
  const navigate = useNavigate()
  if (!stats) return null

  const breakdown = stats.status_breakdown ?? {}
  const recent = stats.recent_courses ?? []

  return (
    <div className="mb-8 grid grid-cols-1 gap-4 lg:grid-cols-3">
      {/* Status breakdown */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm">
            <Layers className="h-4 w-4" /> Corsi per stato
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          {STATUS_ORDER.filter((s) => breakdown[s]).map((s) => (
            <div key={s} className="flex items-center gap-1.5">
              <CourseStatusBadge status={s} />
              <span className="text-foreground text-sm font-semibold">
                {breakdown[s]}
              </span>
            </div>
          ))}
          {Object.keys(breakdown).length === 0 && (
            <span className="text-muted-foreground text-sm">Nessun corso</span>
          )}
        </CardContent>
      </Card>

      {/* Dirty + ore totali (due mini stat impilate) */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm">
            <FileWarning className="h-4 w-4" /> Da rigenerare
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div
            className={cn(
              'font-semibold',
              stats.dirty_count === 0
                ? 'text-muted-foreground text-lg'
                : 'text-destructive text-2xl font-bold'
            )}
          >
            {stats.dirty_count}
          </div>
          <p className="text-muted-foreground text-xs">
            corsi con modifiche non ancora rigenerate
          </p>
          <div className="mt-3 flex items-center gap-2 border-t pt-3">
            <Clock className="text-muted-foreground h-4 w-4" />
            <span className="text-foreground text-lg font-semibold">
              {stats.total_training_hours}h
            </span>
            <span className="text-muted-foreground text-xs">
              formazione prodotta
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Ultimi 5 corsi */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">Ultimi corsi generati</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1.5">
          {recent.length === 0 && (
            <span className="text-muted-foreground text-sm">Nessun corso recente</span>
          )}
          {recent.map((c) => (
            <button
              key={c.id}
              onClick={() => navigate({ to: '/courses/$id', params: { id: c.id } })}
              className="hover:bg-muted flex w-full items-center justify-between gap-2 rounded px-2 py-1 text-left"
            >
              <span className="text-foreground truncate text-sm">{c.title}</span>
              <CourseStatusBadge status={c.status} />
            </button>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}
