/**
 * Audio narration preference store.
 *
 * Persists whether the per-slide voice narration should play in Course Studio.
 * Default ON. The choice survives reloads (localStorage) so an operator who
 * turns narration off once keeps it off across the whole session and beyond.
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface AudioNarrationState {
  enabled: boolean
  toggle: () => void
  setEnabled: (value: boolean) => void
}

export const useAudioNarration = create<AudioNarrationState>()(
  persist(
    (set) => ({
      enabled: true,
      toggle: () => set((s) => ({ enabled: !s.enabled })),
      setEnabled: (value) => set({ enabled: value }),
    }),
    { name: 'eduvault-audio-narration' }
  )
)
