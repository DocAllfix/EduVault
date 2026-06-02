/**
 * SlideEditor — form di modifica della slide selezionata (FASE 9).
 *
 * Design: pannello laterale con campi title/body/speaker_notes/normative_ref
 * (+ quiz options se QUIZ). Salva → PATCH backend → invalida query. Gli errori
 * 422 del validator strict (FASE 1) vengono mostrati inline come toast.
 * REI-1: riusa Input/Textarea/Button/Label shadcn.
 */

import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2, Save } from 'lucide-react'
import { toast } from 'sonner'

import { api, ApiError, type StudioSlide, type SlidePatchBody } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { LabelWithHelp } from '@/lib/onboarding/LabelWithHelp'

export function SlideEditor({
  courseId,
  slide,
}: {
  courseId: string
  slide: StudioSlide
}) {
  const qc = useQueryClient()
  // Backend may emit null for any of these (strict SlideContent ships
  // `body=None` + structured `bullets[]`). Textareas need string values,
  // so coerce here once.
  const [title, setTitle] = useState(slide.title ?? '')
  const [body, setBody] = useState(slide.body ?? '')
  const [notes, setNotes] = useState(slide.speaker_notes ?? '')
  const [ref, setRef] = useState(slide.normative_ref ?? '')
  const [quizOptions, setQuizOptions] = useState<string[]>(slide.quiz_options ?? [])
  const [quizCorrect, setQuizCorrect] = useState<number>(slide.quiz_correct ?? 0)

  // Re-sync quando cambia la slide selezionata
  useEffect(() => {
    setTitle(slide.title ?? '')
    setBody(slide.body ?? '')
    setNotes(slide.speaker_notes ?? '')
    setRef(slide.normative_ref ?? '')
    setQuizOptions(slide.quiz_options ?? [])
    setQuizCorrect(slide.quiz_correct ?? 0)
  }, [slide])

  const isQuiz = slide.slide_type === 'QUIZ'

  const mutation = useMutation({
    mutationFn: (patch: SlidePatchBody) =>
      api.patchCourseSlide(courseId, slide.index, patch),
    onSuccess: () => {
      toast.success('Slide aggiornata')
      qc.invalidateQueries({ queryKey: ['course-slides', courseId] })
    },
    onError: (err) => {
      if (err instanceof ApiError && err.status === 422) {
        toast.error(`Modifica rifiutata: ${err.message}`)
      } else {
        toast.error('Errore salvataggio slide')
      }
    },
  })

  const onSave = () => {
    const patch: SlidePatchBody = {
      title,
      speaker_notes: notes,
      normative_ref: ref,
    }
    if (isQuiz) {
      patch.quiz_options = quizOptions
      patch.quiz_correct = quizCorrect
    } else {
      patch.body = body
    }
    mutation.mutate(patch)
  }

  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <Label htmlFor="slide-title">Titolo</Label>
        <Input
          id="slide-title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
      </div>

      {isQuiz ? (
        <div className="space-y-2">
          <LabelWithHelp
            help={
              <>
                Le 4 opzioni del quiz. Seleziona il radio button accanto alla
                lettera (A/B/C/D) per indicare la risposta corretta. Il marker
                non appare nel PPTX scaricabile per non distrarre lo studente,
                ma l’informazione è salvata nel database per tracking.
              </>
            }
          >
            Opzioni quiz (la corretta è selezionata)
          </LabelWithHelp>
          {quizOptions.map((opt, i) => (
            <div key={i} className="flex items-center gap-2">
              <input
                type="radio"
                name="quiz-correct"
                checked={quizCorrect === i}
                onChange={() => setQuizCorrect(i)}
                className="accent-[var(--brand-secondary)]"
              />
              <span className="text-muted-foreground w-4 text-sm font-bold">
                {String.fromCharCode(65 + i)}
              </span>
              <Input
                value={opt}
                onChange={(e) => {
                  const next = [...quizOptions]
                  next[i] = e.target.value
                  setQuizOptions(next)
                }}
              />
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-1.5">
          <Label htmlFor="slide-body">Corpo (un bullet per riga)</Label>
          <Textarea
            id="slide-body"
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={6}
          />
        </div>
      )}

      <div className="space-y-1.5">
        <LabelWithHelp
          htmlFor="slide-notes"
          help={
            <>
              Testo che diventerà la narrazione audio (Azure Neural TTS, voce
              Elsa). Target ~75-90 parole per circa 30 secondi di parlato.
              Puoi inserire <code>(PAUSE 2s)</code> per pause SSML naturali.
            </>
          }
        >
          Note relatore (narrazione audio)
        </LabelWithHelp>
        <Textarea
          id="slide-notes"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={4}
        />
        <p className="text-muted-foreground text-xs">
          {notes.trim().split(/\s+/).filter(Boolean).length} parole (target 75-90
          per ~30s di voce)
        </p>
      </div>

      <div className="space-y-1.5">
        <LabelWithHelp
          htmlFor="slide-ref"
          help={
            <>
              Citazione normativa visibile in basso a sinistra nella slide
              (es. “D.Lgs 81/08 — art. 15”). Lasciare vuoto se la slide non
              ha un riferimento normativo diretto.
            </>
          }
        >
          Riferimento normativo
        </LabelWithHelp>
        <Input id="slide-ref" value={ref} onChange={(e) => setRef(e.target.value)} />
      </div>

      <Button onClick={onSave} disabled={mutation.isPending} className="w-full">
        {mutation.isPending ? (
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        ) : (
          <Save className="mr-2 h-4 w-4" />
        )}
        Salva modifiche
      </Button>
    </div>
  )
}
