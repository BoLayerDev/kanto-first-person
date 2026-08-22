import { useFrame, useThree } from '@react-three/fiber'
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import { useJourneyStore } from '../state/journey'

const BALL_SEED = 0x151
const HIGH_QUALITY_BALLS = 11
const LOW_QUALITY_BALLS = 6
const BALL_SCALE_TIERS = [0.62, 0.86, 1.12, 1.42] as const
const POKEBALL_RED = '#e43b3f'
const POKEBALL_WHITE = '#f5f1df'
const POKEBALL_BLACK = '#141719'

type BallTransform = {
  position: [number, number, number]
  rotation: [number, number, number]
  scale: number
  phase: number
  speed: number
  direction: number
}

function mulberry32(seed: number) {
  return () => {
    let value = (seed += 0x6d2b79f5)
    value = Math.imul(value ^ (value >>> 15), value | 1)
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61)
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296
  }
}

function createBallLayout(count: number, aspect: number): BallTransform[] {
  const random = mulberry32(BALL_SEED)
  const halfFov = THREE.MathUtils.degToRad(25)

  return Array.from({ length: count }, (_, index) => {
    const side = index % 2 === 0 ? -1 : 1
    const distance = 13 + random() * 25
    const halfHeight = Math.tan(halfFov) * distance
    const scaleTier = BALL_SCALE_TIERS[(index * 3 + 1) % BALL_SCALE_TIERS.length]
    return {
      position: [
        side * halfHeight * aspect * (0.86 + random() * 0.1),
        (random() - 0.5) * halfHeight * 1.65,
        11 - distance,
      ],
      rotation: [
        (random() - 0.5) * 0.65,
        (random() - 0.5) * 0.9,
        (random() - 0.5) * 0.48,
      ],
      scale: halfHeight * 0.105 * scaleTier * (0.94 + random() * 0.12),
      phase: random() * Math.PI * 2,
      speed: 0.045 + random() * 0.075,
      direction: random() > 0.5 ? 1 : -1,
    }
  })
}

function usePrefersReducedMotion() {
  const [reducedMotion, setReducedMotion] = useState(false)

  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)')
    const update = () => setReducedMotion(query.matches)
    update()
    query.addEventListener('change', update)
    return () => query.removeEventListener('change', update)
  }, [])

  return reducedMotion
}

function StaticCamera() {
  const { camera } = useThree()

  useLayoutEffect(() => {
    camera.position.set(0, 0.4, 11)
    camera.lookAt(0, 0, -10)
    const perspective = camera as THREE.PerspectiveCamera
    perspective.fov = 50
    perspective.updateProjectionMatrix()
  }, [camera])

  return null
}

function Atmosphere() {
  const { scene } = useThree()

  useLayoutEffect(() => {
    scene.background = new THREE.Color('#050a12')
    scene.fog = new THREE.Fog('#050a12', 12, 44)
    return () => {
      scene.background = null
      scene.fog = null
    }
  }, [scene])

  return (
    <mesh frustumCulled={false} scale={80}>
      <sphereGeometry args={[1, 24, 14]} />
      <shaderMaterial
        side={THREE.BackSide}
        depthWrite={false}
        toneMapped={false}
        uniforms={{
          uTop: { value: new THREE.Color('#050a12') },
          uHorizon: { value: new THREE.Color('#26364a') },
        }}
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
          void main() {
            float heightMix = pow(clamp(vDirection.y * 0.5 + 0.5, 0.0, 1.0), 0.7);
            gl_FragColor = vec4(mix(uHorizon, uTop, heightMix), 1.0);
          }
        `}
      />
    </mesh>
  )
}

const RING_LOCAL = new THREE.Matrix4().makeRotationX(Math.PI / 2)
const BUTTON_OUTER_LOCAL = new THREE.Matrix4().compose(
  new THREE.Vector3(0, 0, 1.035),
  new THREE.Quaternion().setFromEuler(new THREE.Euler(Math.PI / 2, 0, 0)),
  new THREE.Vector3(1, 1, 1),
)
const BUTTON_INNER_LOCAL = new THREE.Matrix4().compose(
  new THREE.Vector3(0, 0, 1.13),
  new THREE.Quaternion().setFromEuler(new THREE.Euler(Math.PI / 2, 0, 0)),
  new THREE.Vector3(1, 1, 1),
)

function PokeballField() {
  const quality = useJourneyStore((state) => state.quality)
  const reducedMotion = usePrefersReducedMotion()
  const { gl, size } = useThree()
  const count = quality === 'high' ? HIGH_QUALITY_BALLS : LOW_QUALITY_BALLS
  const aspect = size.width / Math.max(size.height, 1)
  const layout = useMemo(() => createBallLayout(count, aspect), [aspect, count])
  const top = useRef<THREE.InstancedMesh>(null)
  const bottom = useRef<THREE.InstancedMesh>(null)
  const band = useRef<THREE.InstancedMesh>(null)
  const buttonOuter = useRef<THREE.InstancedMesh>(null)
  const buttonInner = useRef<THREE.InstancedMesh>(null)
  const scratch = useMemo(
    () => ({
      position: new THREE.Vector3(),
      rotation: new THREE.Euler(),
      quaternion: new THREE.Quaternion(),
      scale: new THREE.Vector3(),
      root: new THREE.Matrix4(),
      world: new THREE.Matrix4(),
    }),
    [],
  )

  const writeMatrices = (time: number) => {
    const meshes = [top.current, bottom.current, band.current, buttonOuter.current, buttonInner.current]
    if (meshes.some((mesh) => !mesh)) return

    layout.forEach((ball, index) => {
      const drift = quality === 'high' && !reducedMotion ? Math.sin(time * 0.42 + ball.phase) * 0.18 : 0
      const spin = quality === 'high' && !reducedMotion ? time * ball.speed * ball.direction : 0
      scratch.position.set(ball.position[0], ball.position[1] + drift, ball.position[2])
      scratch.rotation.set(
        ball.rotation[0] + spin * 0.34,
        ball.rotation[1] + spin,
        ball.rotation[2] + spin * 0.18,
      )
      scratch.quaternion.setFromEuler(scratch.rotation)
      scratch.scale.setScalar(ball.scale)
      scratch.root.compose(scratch.position, scratch.quaternion, scratch.scale)

      top.current?.setMatrixAt(index, scratch.root)
      bottom.current?.setMatrixAt(index, scratch.root)
      scratch.world.multiplyMatrices(scratch.root, RING_LOCAL)
      band.current?.setMatrixAt(index, scratch.world)
      scratch.world.multiplyMatrices(scratch.root, BUTTON_OUTER_LOCAL)
      buttonOuter.current?.setMatrixAt(index, scratch.world)
      scratch.world.multiplyMatrices(scratch.root, BUTTON_INNER_LOCAL)
      buttonInner.current?.setMatrixAt(index, scratch.world)
    })

    meshes.forEach((mesh) => {
      if (mesh) mesh.instanceMatrix.needsUpdate = true
    })
  }

  useLayoutEffect(() => {
    writeMatrices(0)
    ;[top.current, bottom.current, band.current, buttonOuter.current, buttonInner.current].forEach(
      (mesh) => mesh?.computeBoundingSphere(),
    )
    const host = gl.domElement.closest<HTMLElement>('.world-canvas')
    if (host) {
      host.dataset.ballCount = String(count)
      host.dataset.ballSizeVariants = String(BALL_SCALE_TIERS.length)
    }
  }, [count, gl, layout, quality, reducedMotion])

  useFrame(({ clock }) => {
    if (quality === 'high' && !reducedMotion) writeMatrices(clock.elapsedTime)
  })

  return (
    <group name="pokeball-field">
      <instancedMesh ref={top} args={[undefined, undefined, count]}>
        <sphereGeometry args={[1, quality === 'high' ? 28 : 18, quality === 'high' ? 16 : 10, 0, Math.PI * 2, 0, Math.PI / 2]} />
        <meshStandardMaterial color={POKEBALL_RED} roughness={0.31} metalness={0.03} />
      </instancedMesh>
      <instancedMesh ref={bottom} args={[undefined, undefined, count]}>
        <sphereGeometry args={[1, quality === 'high' ? 28 : 18, quality === 'high' ? 16 : 10, 0, Math.PI * 2, Math.PI / 2, Math.PI / 2]} />
        <meshStandardMaterial color={POKEBALL_WHITE} roughness={0.38} metalness={0.02} />
      </instancedMesh>
      <instancedMesh ref={band} args={[undefined, undefined, count]}>
        <torusGeometry args={[1.005, 0.075, 8, quality === 'high' ? 28 : 18]} />
        <meshStandardMaterial color={POKEBALL_BLACK} roughness={0.5} />
      </instancedMesh>
      <instancedMesh ref={buttonOuter} args={[undefined, undefined, count]}>
        <cylinderGeometry args={[0.29, 0.29, 0.16, quality === 'high' ? 24 : 16]} />
        <meshStandardMaterial color={POKEBALL_BLACK} roughness={0.45} />
      </instancedMesh>
      <instancedMesh ref={buttonInner} args={[undefined, undefined, count]}>
        <cylinderGeometry args={[0.18, 0.18, 0.17, quality === 'high' ? 24 : 16]} />
        <meshStandardMaterial color={POKEBALL_WHITE} roughness={0.24} />
      </instancedMesh>
    </group>
  )
}

function RenderDiagnostics() {
  const { gl, scene } = useThree()
  const frame = useRef(0)

  useFrame(() => {
    frame.current += 1
    if (frame.current % 30 !== 0) return
    const host = gl.domElement.closest<HTMLElement>('.world-canvas')
    if (!host) return
    const materials = new Set<THREE.Material>()
    scene.traverse((object) => {
      if (!(object instanceof THREE.Mesh)) return
      const objectMaterials = Array.isArray(object.material) ? object.material : [object.material]
      objectMaterials.forEach((material) => materials.add(material))
    })
    host.dataset.drawCalls = String(gl.info.render.calls)
    host.dataset.triangles = String(gl.info.render.triangles)
    host.dataset.geometries = String(gl.info.memory.geometries)
    host.dataset.textures = String(gl.info.memory.textures)
    host.dataset.materials = String(materials.size)
  })

  return null
}

function LightingRig() {
  return (
    <>
      <hemisphereLight args={['#fff7e6', '#05070b', 2.1]} />
      <directionalLight position={[-7, 10, 8]} color="#fff4dc" intensity={4.2} />
      <directionalLight position={[8, -2, 6]} color="#d9e8ff" intensity={1.15} />
    </>
  )
}

export function KantoWorld() {
  return (
    <>
      <Atmosphere />
      <StaticCamera />
      <LightingRig />
      <PokeballField />
      <RenderDiagnostics />
    </>
  )
}
