import { create } from 'zustand'
import type { Edition } from '../world/palettes'

export type QualityTier = 'low' | 'high'

type JourneyState = {
  menuIndex: number
  edition: Edition
  quality: QualityTier
  setMenuIndex: (menuIndex: number) => void
  setEdition: (edition: Edition) => void
  setQuality: (quality: QualityTier) => void
}

export const useJourneyStore = create<JourneyState>((set) => ({
  menuIndex: 0,
  edition: 'red',
  quality: 'high',
  setMenuIndex: (menuIndex) => set({ menuIndex }),
  setEdition: (edition) => set({ edition }),
  setQuality: (quality) => set({ quality }),
}))
