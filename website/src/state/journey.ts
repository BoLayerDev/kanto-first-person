import { create } from 'zustand'
import type { Edition } from '../world/palettes'

export type HotspotId = 'interiors' | 'weather' | 'caves'
export type QualityTier = 'low' | 'high'

type JourneyState = {
  booted: boolean
  progress: number
  edition: Edition
  scannerEnabled: boolean
  hoveredHotspot: HotspotId | null
  selectedHotspot: HotspotId | null
  quality: QualityTier
  setBooted: (booted: boolean) => void
  setProgress: (progress: number) => void
  setEdition: (edition: Edition) => void
  setScannerEnabled: (enabled: boolean) => void
  setHoveredHotspot: (id: HotspotId | null) => void
  setSelectedHotspot: (id: HotspotId | null) => void
  setQuality: (quality: QualityTier) => void
}

export const useJourneyStore = create<JourneyState>((set) => ({
  booted: false,
  progress: 0,
  edition: 'red',
  scannerEnabled: false,
  hoveredHotspot: null,
  selectedHotspot: null,
  quality: 'high',
  setBooted: (booted) => set({ booted }),
  setProgress: (progress) => set({ progress: Math.min(1, Math.max(0, progress)) }),
  setEdition: (edition) => set({ edition }),
  setScannerEnabled: (scannerEnabled) =>
    set({ scannerEnabled, hoveredHotspot: null }),
  setHoveredHotspot: (hoveredHotspot) => set({ hoveredHotspot }),
  setSelectedHotspot: (selectedHotspot) => set({ selectedHotspot }),
  setQuality: (quality) => set({ quality }),
}))
