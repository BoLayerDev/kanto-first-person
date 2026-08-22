import { Canvas } from '@react-three/fiber'
import * as THREE from 'three'
import { useJourneyStore } from '../state/journey'
import { KantoWorld } from './KantoWorld'

export default function WorldCanvas() {
  const quality = useJourneyStore((state) => state.quality)
  const setSelectedHotspot = useJourneyStore((state) => state.setSelectedHotspot)

  return (
    <div className="world-canvas" aria-hidden="true">
      <Canvas
        dpr={quality === 'high' ? [1, 1.5] : 1}
        shadows={quality === 'high'}
        camera={{ position: [0, 2.45, 7.5], fov: 54, near: 0.08, far: 120 }}
        gl={{ antialias: false, powerPreference: 'high-performance' }}
        onCreated={({ gl }) => {
          gl.outputColorSpace = THREE.SRGBColorSpace
          gl.toneMapping = THREE.ACESFilmicToneMapping
          gl.toneMappingExposure = 1.05
        }}
        onPointerMissed={() => setSelectedHotspot(null)}
        fallback={<div className="webgl-fallback">3D view unavailable. The field guide is still below.</div>}
      >
        <KantoWorld />
      </Canvas>
    </div>
  )
}
