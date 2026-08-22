import { Canvas } from '@react-three/fiber'
import * as THREE from 'three'
import { useJourneyStore } from '../state/journey'
import { KantoWorld } from './KantoWorld'

export default function WorldCanvas() {
  const quality = useJourneyStore((state) => state.quality)

  return (
    <div
      className="world-canvas world-pokeballs"
      data-scene-mode="pokeballs-only"
      data-menu-reactive="false"
      aria-hidden="true"
    >
      <Canvas
        dpr={quality === 'high' ? [1, 1.5] : 1}
        shadows={false}
        camera={{ position: [0, 0.4, 11], fov: 50, near: 0.08, far: 90 }}
        gl={{ antialias: false, powerPreference: 'high-performance' }}
        onCreated={({ gl }) => {
          gl.outputColorSpace = THREE.SRGBColorSpace
          gl.toneMapping = THREE.ACESFilmicToneMapping
          gl.toneMappingExposure = 1.05
        }}
        fallback={<div className="webgl-fallback">3D preview unavailable. All menu options remain available.</div>}
      >
        <KantoWorld />
      </Canvas>
    </div>
  )
}
