import type { HotspotId } from '../state/journey'

export type HotspotRecord = {
  id: HotspotId
  number: string
  label: string
  title: string
  location: string
  summary: string
  facts: string[]
}

export const HOTSPOTS: Record<HotspotId, HotspotRecord> = {
  interiors: {
    id: 'interiors',
    number: '001',
    label: 'INTERIOR DEPTH',
    title: 'Rooms become places.',
    location: 'STARTING ROOM',
    summary:
      'Walls, ceilings, windows, rails, posters, and doorway light give indoor maps a clear shape.',
    facts: ['Ceiling cutaway modes', 'Doorway light cues', 'Host-owned rendering'],
  },
  weather: {
    id: 'weather',
    number: '025',
    label: 'ROUTE ATMOSPHERE',
    title: 'Routes reach the horizon.',
    location: 'FOREST ROUTE',
    summary:
      'World aprons, raised trees, mountains, fog, clouds, rain, and particles extend the view beyond the map edge.',
    facts: ['Deterministic weather', 'Budgeted world detail', 'Red / Blue / Yellow'],
  },
  caves: {
    id: 'caves',
    number: '150',
    label: 'CAVE VOLUME',
    title: 'Darkness gets structure.',
    location: 'CRYSTAL CAVERN',
    summary:
      'Uneven roofs, rock columns, pools, sconces, and depth fog turn flat cave rooms into enclosed spaces.',
    facts: ['Uneven cave roofs', 'Readable depth layers', 'Bounded light effects'],
  },
}
