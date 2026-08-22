export type Edition = 'red' | 'blue' | 'yellow'

export type WorldPalette = {
  name: string
  fieldNote: string
  accent: string
  accentBright: string
  accentSoft: string
  ink: string
  panel: string
  skyTop: string
  skyHorizon: string
  fog: string
  ground: string
  grass: string
  stone: string
  signal: string
}

export const PALETTES: Record<Edition, WorldPalette> = {
  red: {
    name: 'RED / GOLDEN HOUR',
    fieldNote: 'Warm route light, drifting embers, and long mountain shadows.',
    accent: '#d83a3a',
    accentBright: '#ff7465',
    accentSoft: '#ffd0b5',
    ink: '#1b1014',
    panel: '#f7e8cd',
    skyTop: '#4b3f91',
    skyHorizon: '#ff9f55',
    fog: '#bd6b57',
    ground: '#9b6341',
    grass: '#55733b',
    stone: '#4c4054',
    signal: '#ffcf67',
  },
  blue: {
    name: 'BLUE / STORM WATCH',
    fieldNote: 'Cold rain, deep fog, and charged clouds over the route.',
    accent: '#3157a4',
    accentBright: '#68b9ff',
    accentSoft: '#bde9ff',
    ink: '#09131f',
    panel: '#e8f5fa',
    skyTop: '#071b42',
    skyHorizon: '#356e9e',
    fog: '#1f4a68',
    ground: '#3d5860',
    grass: '#315c58',
    stone: '#25364b',
    signal: '#63e5ff',
  },
  yellow: {
    name: 'YELLOW / ELECTRIC DAWN',
    fieldNote: 'Bright haze, electric sparks, and a fast-rising sun.',
    accent: '#d9a900',
    accentBright: '#ffe45b',
    accentSoft: '#fff1a6',
    ink: '#171509',
    panel: '#fff8cf',
    skyTop: '#327b9f',
    skyHorizon: '#ffd96b',
    fog: '#91a56e',
    ground: '#9c7941',
    grass: '#608447',
    stone: '#555145',
    signal: '#fff27a',
  },
}
