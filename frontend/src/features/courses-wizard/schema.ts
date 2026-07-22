/**
 * Wizard form schema — aligned to `CourseRequest` (BP §10 / `app/models/requests.py`).
 *
 * Each step has its own schema slice so we can validate progressively
 * (only validate fields seen so far). The merged `wizardSchema` matches
 * the Pydantic contract verbatim — re-deriving the TS type via z.infer
 * keeps the two in lockstep without a second declaration.
 *
 * Bounds match Pydantic Field constraints:
 *   duration_hours: gt=0, le=16  (CourseRequest)
 *   outputs: non-empty, subset of {pptx, pdf, audio, quiz}
 *   slide_density: enum SlideDensity (leggera|standard|intensiva)
 *   target: enum TargetType (discente|formatore)
 *
 * `brand_preset_id` is a UUID string — we don't enforce UUID format here
 * because the user picks from a Select populated by the backend.
 */

import { z } from 'zod'

export const TARGETS = ['discente', 'formatore'] as const
export const DENSITIES = ['leggera', 'standard', 'intensiva'] as const
export const OUTPUTS = ['pptx', 'pdf', 'audio', 'quiz'] as const
export type OutputValue = (typeof OUTPUTS)[number]

// Per-step schemas (used to validate just-this-step on Next click).
export const step1Schema = z.object({
  course_type: z
    .string()
    .min(1, 'Seleziona un tipo di corso.'),
})

export const step2Schema = z.object({
  target: z.enum(TARGETS, {
    error: () => 'Seleziona un destinatario.',
  }),
})

export const step3Schema = z.object({
  duration_hours: z
    .number({ error: 'Durata non valida.' })
    .gt(0, 'La durata deve essere maggiore di 0.')
    .max(16, 'La durata non può superare 16 ore.'),
  region: z.string().min(1, 'Seleziona una regione.'),
  slide_density: z.enum(DENSITIES),
  // FASE 2 pacing dinamico: durata-slide scelta dall'utente. Range guidato
  // 40-240s (sotto i 40 si riaprono i problemi di budget output dell'LLM).
  seconds_per_slide: z
    .number({ error: 'Durata slide non valida.' })
    .min(40, 'Minimo 40 secondi per slide.')
    .max(240, 'Massimo 240 secondi (4 minuti) per slide.'),
})

export const step4Schema = z.object({
  brand_preset_id: z.string().min(1, 'Seleziona un brand preset.'),
})

export const step5Schema = z.object({
  outputs: z
    .array(z.enum(OUTPUTS))
    .min(1, 'Seleziona almeno un formato di output.'),
})

// Composite schema (final submit shape).
export const wizardSchema = step1Schema
  .merge(step2Schema)
  .merge(step3Schema)
  .merge(step4Schema)
  .merge(step5Schema)

export type WizardValues = z.infer<typeof wizardSchema>

/**
 * Default state. `region` defaults to NAZIONALE per BP §10.
 * `outputs` defaults to ["pptx","pdf"] to match the Pydantic default and
 * tick the two boxes for the user (sensible majority case).
 */
export const wizardDefaults: WizardValues = {
  course_type: '',
  target: 'discente',
  duration_hours: 4,
  region: 'NAZIONALE',
  slide_density: 'standard',
  seconds_per_slide: 45,
  brand_preset_id: '',
  outputs: ['pptx', 'pdf'],
}

/**
 * Italian regions (ISO 3166-2:IT codes) plus NAZIONALE. Hardcoded list
 * is acceptable here (REI-5): the set is constitutionally fixed and the
 * backend's regional filter (research_agent BP §05.4) expects exactly
 * these tokens. If a region gets renamed by the State, we update once.
 */
export const REGIONS = [
  { value: 'NAZIONALE', label: 'Nazionale' },
  { value: 'ABRUZZO', label: 'Abruzzo' },
  { value: 'BASILICATA', label: 'Basilicata' },
  { value: 'CALABRIA', label: 'Calabria' },
  { value: 'CAMPANIA', label: 'Campania' },
  { value: 'EMILIA_ROMAGNA', label: 'Emilia-Romagna' },
  { value: 'FRIULI_VENEZIA_GIULIA', label: 'Friuli-Venezia Giulia' },
  { value: 'LAZIO', label: 'Lazio' },
  { value: 'LIGURIA', label: 'Liguria' },
  { value: 'LOMBARDIA', label: 'Lombardia' },
  { value: 'MARCHE', label: 'Marche' },
  { value: 'MOLISE', label: 'Molise' },
  { value: 'PIEMONTE', label: 'Piemonte' },
  { value: 'PUGLIA', label: 'Puglia' },
  { value: 'SARDEGNA', label: 'Sardegna' },
  { value: 'SICILIA', label: 'Sicilia' },
  { value: 'TOSCANA', label: 'Toscana' },
  { value: 'TRENTINO_ALTO_ADIGE', label: 'Trentino-Alto Adige' },
  { value: 'UMBRIA', label: 'Umbria' },
  { value: 'VALLE_AOSTA', label: "Valle d'Aosta" },
  { value: 'VENETO', label: 'Veneto' },
] as const

export const DENSITY_OPTIONS = [
  { value: 'leggera', label: 'Leggera', desc: 'Meno slide, più approfondimento per slide.' },
  { value: 'standard', label: 'Standard', desc: 'Bilanciamento default.' },
  { value: 'intensiva', label: 'Intensiva', desc: 'Più slide, contenuti più frazionati.' },
] as const

export const OUTPUT_OPTIONS: { value: OutputValue; label: string; desc: string }[] = [
  { value: 'pptx', label: 'PPTX', desc: 'Presentazione PowerPoint con branding e immagini.' },
  { value: 'pdf', label: 'PDF', desc: 'Dispensa cartacea con TOC e citazioni normative.' },
  { value: 'audio', label: 'Audio', desc: 'Narrazione MP3 per ogni slide (edge-tts).' },
  { value: 'quiz', label: 'Quiz', desc: 'Verifiche interattive a fine modulo.' },
]
