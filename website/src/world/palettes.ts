export type Edition = 'red' | 'blue' | 'yellow'

export type WorldPalette = {
  name: string
  fieldNote: string
  accent: string
  accentBright: string
  accentSoft: string
  ink: string
  panel: string
  panelDark: string
  mid: string
  pale: string
  banner: string
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
    accent: '#d52f3a',
    accentBright: '#ff8474',
    accentSoft: '#ffc0ae',
    ink: '#260c14',
    panel: '#fff0e3',
    panelDark: '#e8aba4',
    mid: '#713642',
    pale: '#d99b9d',
    banner: '#ff8a73',
    skyTop: '#541522',
    skyHorizon: '#ed5e4b',
    fog: '#bd6b57',
    ground: '#9b6341',
    grass: '#55733b',
    stone: '#4c4054',
    signal: '#ffcf67',
  },
  blue: {
    name: 'BLUE / STORM WATCH',
    fieldNote: 'Cold rain, deep fog, and charged clouds over the route.',
    accent: '#2357c7',
    accentBright: '#72c8ff',
    accentSoft: '#addcff',
    ink: '#071c36',
    panel: '#e6f4ff',
    panelDark: '#9fc9e8',
    mid: '#315b7d',
    pale: '#8dbbda',
    banner: '#66b8f2',
    skyTop: '#071e52',
    skyHorizon: '#2b78b8',
    fog: '#1f4a68',
    ground: '#3d5860',
    grass: '#315c58',
    stone: '#25364b',
    signal: '#63e5ff',
  },
  yellow: {
    name: 'YELLOW / ELECTRIC DAWN',
    fieldNote: 'Bright haze, electric sparks, and a fast-rising sun.',
    accent: '#d48b00',
    accentBright: '#ffe054',
    accentSoft: '#ffe991',
    ink: '#2b2305',
    panel: '#fff7b8',
    panelDark: '#e1c54a',
    mid: '#685719',
    pale: '#cfb94d',
    banner: '#ffdc3f',
    skyTop: '#594300',
    skyHorizon: '#ffcc2e',
    fog: '#91a56e',
    ground: '#9c7941',
    grass: '#608447',
    stone: '#555145',
    signal: '#fff27a',
  },
}
