import { useFrame, useThree } from '@react-three/fiber'
import { useLayoutEffect, useMemo, useRef } from 'react'
import * as THREE from 'three'
import { useJourneyStore } from '../state/journey'
import { PALETTES } from '../world/palettes'

const CAMERA_VIEWS = [
  { position: new THREE.Vector3(3.8, 3.15, 8.2), target: new THREE.Vector3(0, 1.35, -1.5) },
  { position: new THREE.Vector3(4.4, 3.3, -5), target: new THREE.Vector3(0, 1.5, -15) },
  { position: new THREE.Vector3(5.2, 4.4, -17), target: new THREE.Vector3(0, 1.3, -27) },
  { position: new THREE.Vector3(-3.5, 3.1, -11), target: new THREE.Vector3(0, 1.6, -22) },
  { position: new THREE.Vector3(3.2, 2.7, -27), target: new THREE.Vector3(0, 1.5, -36) },
  { position: new THREE.Vector3(-5.4, 4.8, -15), target: new THREE.Vector3(0, 1.6, -25) },
  { position: new THREE.Vector3(0, 5.6, -22), target: new THREE.Vector3(0, 1.1, -34) },
]

function damp(current: number, target: number, lambda: number, delta: number) {
  return THREE.MathUtils.lerp(current, target, 1 - Math.exp(-lambda * delta))
}

function mulberry32(seed: number) {
  return () => {
    let value = (seed += 0x6d2b79f5)
    value = Math.imul(value ^ (value >>> 15), value | 1)
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61)
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296
  }
}

function MenuCamera() {
  const menuIndex = useJourneyStore((state) => state.menuIndex)
  const quality = useJourneyStore((state) => state.quality)
  const cameraTarget = useMemo(() => CAMERA_VIEWS[0].position.clone(), [])
  const lookTarget = useMemo(() => CAMERA_VIEWS[0].target.clone(), [])

  useFrame(({ camera, pointer }, delta) => {
    const view = CAMERA_VIEWS[menuIndex] ?? CAMERA_VIEWS[0]
    cameraTarget.copy(view.position)
    const pointerAmount = quality === 'high' ? 0.22 : 0.04
    cameraTarget.x += pointer.x * pointerAmount
    cameraTarget.y += pointer.y * pointerAmount * 0.4

    camera.position.lerp(cameraTarget, 1 - Math.exp(-3.8 * delta))
    lookTarget.lerp(view.target, 1 - Math.exp(-4.2 * delta))
    camera.lookAt(lookTarget)

    const perspective = camera as THREE.PerspectiveCamera
    perspective.fov = damp(perspective.fov, menuIndex === 6 ? 58 : 52, 4, delta)
    perspective.updateProjectionMatrix()
  })

  return null
}

function AtmosphereRig() {
  const edition = useJourneyStore((state) => state.edition)
  const palette = PALETTES[edition]
  const { scene } = useThree()
  const targetBackground = useMemo(() => new THREE.Color(), [])
  const targetFog = useMemo(() => new THREE.Color(), [])

  useLayoutEffect(() => {
    scene.background = new THREE.Color(palette.skyTop)
    scene.fog = new THREE.Fog(palette.fog, 8, 48)
    return () => {
      scene.background = null
      scene.fog = null
    }
  }, [scene])

  useFrame((_, delta) => {
    targetBackground.set(palette.skyTop)
    targetFog.set(palette.fog)
    if (scene.background instanceof THREE.Color) {
      scene.background.lerp(targetBackground, 1 - Math.exp(-1.7 * delta))
    }
    if (scene.fog instanceof THREE.Fog) {
      scene.fog.color.lerp(targetFog, 1 - Math.exp(-1.7 * delta))
      scene.fog.near = damp(scene.fog.near, edition === 'blue' ? 6 : 9, 2, delta)
      scene.fog.far = damp(scene.fog.far, edition === 'blue' ? 38 : 52, 2, delta)
    }
  })

  return null
}

function GradientSky() {
  const edition = useJourneyStore((state) => state.edition)
  const material = useRef<THREE.ShaderMaterial>(null)
  const uniforms = useMemo(
    () => ({
      uTop: { value: new THREE.Color(PALETTES.red.skyTop) },
      uHorizon: { value: new THREE.Color(PALETTES.red.skyHorizon) },
      uSignal: { value: new THREE.Color(PALETTES.red.signal) },
    }),
    [],
  )
  const targets = useMemo(
    () => ({ top: new THREE.Color(), horizon: new THREE.Color(), signal: new THREE.Color() }),
    [],
  )

  useFrame((_, delta) => {
    const palette = PALETTES[edition]
    targets.top.set(palette.skyTop)
    targets.horizon.set(palette.skyHorizon)
    targets.signal.set(palette.signal)
    const rate = 1 - Math.exp(-1.8 * delta)
    uniforms.uTop.value.lerp(targets.top, rate)
    uniforms.uHorizon.value.lerp(targets.horizon, rate)
    uniforms.uSignal.value.lerp(targets.signal, rate)
  })

  return (
    <mesh frustumCulled={false} scale={80}>
      <sphereGeometry args={[1, 32, 18]} />
      <shaderMaterial
        ref={material}
        side={THREE.BackSide}
        depthWrite={false}
        toneMapped={false}
        uniforms={uniforms}
        vertexShader={`
          varying vec3 vDirection;
          void main() {
            vDirection = normalize(position);
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
          }
        `}
        fragmentShader={`
          varying vec3 vDirection;
          uniform vec3 uTop;
          uniform vec3 uHorizon;
          uniform vec3 uSignal;
          void main() {
            float heightMix = pow(clamp(vDirection.y * 0.5 + 0.5, 0.0, 1.0), 0.62);
            vec3 color = mix(uHorizon, uTop, heightMix);
            vec3 sunDirection = normalize(vec3(-0.22, 0.10, -0.97));
            float sun = max(dot(normalize(vDirection), sunDirection), 0.0);
            color += uSignal * (pow(sun, 420.0) + pow(sun, 8.0) * 0.18);
            gl_FragColor = vec4(color, 1.0);
          }
        `}
      />
    </mesh>
  )
}

type BlockFieldProps = {
  positions: Array<[number, number, number]>
  size: [number, number, number]
  color: string
  roughness?: number
  emissive?: string
  emissiveIntensity?: number
}

function BlockField({
  positions,
  size,
  color,
  roughness = 0.82,
  emissive = '#000000',
  emissiveIntensity = 0,
}: BlockFieldProps) {
  const mesh = useRef<THREE.InstancedMesh>(null)

  useLayoutEffect(() => {
    const matrix = new THREE.Matrix4()
    positions.forEach(([x, y, z], index) => {
      matrix.makeTranslation(x, y, z)
      mesh.current?.setMatrixAt(index, matrix)
    })
    if (mesh.current) {
      mesh.current.instanceMatrix.needsUpdate = true
      mesh.current.computeBoundingSphere()
    }
  }, [positions])

  return (
    <instancedMesh ref={mesh} args={[undefined, undefined, positions.length]} castShadow receiveShadow>
      <boxGeometry args={size} />
      <meshStandardMaterial
        color={color}
        roughness={roughness}
        emissive={emissive}
        emissiveIntensity={emissiveIntensity}
      />
    </instancedMesh>
  )
}

const ROOM_FLOOR = Array.from({ length: 80 }, (_, index) => {
  const x = (index % 8) - 3.5
  const z = 8 - Math.floor(index / 8)
  return [x, -0.05, z] as [number, number, number]
})

const ROUTE_TILES = Array.from({ length: 34 }, (_, index) => [0, 0, -3.4 - index * 0.92] as [
  number,
  number,
  number,
])

const TREE_POSITIONS = Array.from({ length: 28 }, (_, index) => {
  const random = mulberry32(180 + index)
  const side = index % 2 === 0 ? -1 : 1
  return [side * (2.4 + random() * 2.9), 1.05, -5.5 - index * 0.82] as [
    number,
    number,
    number,
  ]
})

const TREE_CROWNS = TREE_POSITIONS.map(([x, , z], index) => [
  x,
  2.65 + (index % 3) * 0.12,
  z,
] as [number, number, number])

const CAVE_COLUMNS = Array.from({ length: 26 }, (_, index) => {
  const side = index % 2 === 0 ? -1 : 1
  const row = Math.floor(index / 2)
  return [side * (3.25 + (row % 3) * 0.23), 1.65, -29 - row * 1.2] as [
    number,
    number,
    number,
  ]
})

function StartingRoom() {
  const palette = PALETTES[useJourneyStore((state) => state.edition)]

  return (
    <group>
      <BlockField positions={ROOM_FLOOR} size={[0.98, 0.1, 0.98]} color={palette.ground} />
      <mesh position={[-4.3, 2.35, 3.5]} receiveShadow>
        <boxGeometry args={[0.25, 4.8, 9]} />
        <meshStandardMaterial color={palette.panel} roughness={0.75} />
      </mesh>
      <mesh position={[4.3, 2.35, 3.5]} receiveShadow>
        <boxGeometry args={[0.25, 4.8, 9]} />
        <meshStandardMaterial color={palette.panel} roughness={0.75} />
      </mesh>
      <mesh position={[0, 4.72, 3.5]} receiveShadow>
        <boxGeometry args={[8.8, 0.18, 9]} />
        <meshStandardMaterial color={palette.ink} roughness={0.9} />
      </mesh>
      <mesh position={[2.7, 1.05, 1.1]} castShadow>
        <boxGeometry args={[1.75, 2.1, 0.35]} />
        <meshStandardMaterial color={palette.accent} roughness={0.55} />
      </mesh>
      <mesh position={[2.7, 1.2, 0.9]}>
        <circleGeometry args={[0.42, 32]} />
        <meshStandardMaterial color={palette.signal} emissive={palette.signal} emissiveIntensity={1.4} />
      </mesh>
      <pointLight position={[0, 3.7, 3]} color={palette.signal} intensity={13} distance={11} />
    </group>
  )
}

function ForestRoute() {
  const palette = PALETTES[useJourneyStore((state) => state.edition)]

  return (
    <group>
      <BlockField positions={ROUTE_TILES} size={[1.8, 0.18, 0.86]} color={palette.ground} />
      <BlockField positions={TREE_POSITIONS} size={[0.48, 2.1, 0.48]} color="#59422d" />
      <BlockField positions={TREE_CROWNS} size={[1.72, 1.7, 1.72]} color={palette.grass} />
      <mesh position={[-7.5, 2.1, -22]} rotation={[0, 0.2, -0.12]}>
        <coneGeometry args={[6.2, 6.8, 5]} />
        <meshStandardMaterial color={palette.stone} roughness={1} />
      </mesh>
      <mesh position={[7.8, 2.5, -25]} rotation={[0, -0.3, 0.1]}>
        <coneGeometry args={[7, 7.5, 5]} />
        <meshStandardMaterial color={palette.stone} roughness={1} />
      </mesh>
    </group>
  )
}

function CrystalCave() {
  const palette = PALETTES[useJourneyStore((state) => state.edition)]
  const ceiling = CAVE_COLUMNS.map(([x, , z]) => [x * 0.45, 5.2, z] as [number, number, number])
  const crystals: Array<[number, number, number]> = [
    [-2.55, 0.75, -32],
    [2.4, 0.8, -35.8],
    [-2.2, 0.65, -39.5],
    [1.7, 0.9, -42],
  ]

  return (
    <group>
      <BlockField positions={CAVE_COLUMNS} size={[1.6, 3.3, 1.1]} color={palette.stone} />
      <BlockField positions={ceiling} size={[4.4, 1.0, 1.15]} color={palette.stone} />
      {crystals.map((position, index) => (
        <group key={position.join('-')} position={position} rotation={[0, index * 0.65, 0.16]}>
          <mesh castShadow>
            <octahedronGeometry args={[0.62 + index * 0.05, 0]} />
            <meshStandardMaterial
              color={palette.accentSoft}
              emissive={palette.signal}
              emissiveIntensity={2.8}
              roughness={0.22}
            />
          </mesh>
          <pointLight color={palette.signal} intensity={8} distance={6} />
        </group>
      ))}
    </group>
  )
}

function WeatherParticles() {
  const edition = useJourneyStore((state) => state.edition)
  const quality = useJourneyStore((state) => state.quality)
  const points = useRef<THREE.Points>(null)
  const count = quality === 'high' ? 420 : 150
  const positions = useMemo(() => {
    const random = mulberry32(151)
    const values = new Float32Array(count * 3)
    for (let index = 0; index < count; index += 1) {
      values[index * 3] = (random() - 0.5) * 24
      values[index * 3 + 1] = random() * 11
      values[index * 3 + 2] = -2 - random() * 43
    }
    return values
  }, [count])

  useFrame(({ clock }, delta) => {
    if (!points.current) return
    const speed = edition === 'blue' ? 0.48 : edition === 'yellow' ? 0.12 : 0.035
    points.current.position.y -= delta * speed
    points.current.rotation.y = Math.sin(clock.elapsedTime * 0.08) * 0.04
    if (points.current.position.y < -1.5) points.current.position.y = 1.5
  })

  const palette = PALETTES[edition]
  return (
    <points ref={points}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        color={palette.signal}
        size={edition === 'blue' ? 0.055 : 0.08}
        transparent
        opacity={edition === 'red' ? 0.46 : 0.72}
        depthWrite={false}
        sizeAttenuation
      />
    </points>
  )
}

function LightingRig() {
  const edition = useJourneyStore((state) => state.edition)
  const quality = useJourneyStore((state) => state.quality)
  const key = useRef<THREE.DirectionalLight>(null)
  const pulse = useRef<THREE.PointLight>(null)
  const palette = PALETTES[edition]

  useFrame(({ clock }, delta) => {
    if (key.current) {
      key.current.color.lerp(new THREE.Color(palette.accentSoft), 1 - Math.exp(-2 * delta))
      key.current.intensity = damp(key.current.intensity, edition === 'blue' ? 2.4 : 3.6, 2, delta)
    }
    if (pulse.current) {
      const lightning = edition === 'blue' && Math.sin(clock.elapsedTime * 0.73) > 0.985
      const electric = edition === 'yellow' ? 3 + Math.sin(clock.elapsedTime * 4) * 1.2 : 0
      pulse.current.intensity = lightning ? 55 : Math.max(0, electric)
      pulse.current.color.set(palette.signal)
    }
  })

  return (
    <>
      <hemisphereLight args={[palette.skyHorizon, '#191824', 2.5]} />
      <directionalLight
        ref={key}
        position={[-7, 11, 5]}
        color={palette.accentSoft}
        intensity={3.6}
        castShadow={quality === 'high'}
        shadow-mapSize={[1024, 1024]}
        shadow-camera-left={-10}
        shadow-camera-right={10}
        shadow-camera-top={10}
        shadow-camera-bottom={-10}
      />
      <pointLight ref={pulse} position={[0, 7, -18]} color={palette.signal} distance={50} />
    </>
  )
}

export function KantoWorld() {
  return (
    <>
      <AtmosphereRig />
      <GradientSky />
      <MenuCamera />
      <LightingRig />
      <StartingRoom />
      <ForestRoute />
      <CrystalCave />
      <WeatherParticles />
    </>
  )
}
