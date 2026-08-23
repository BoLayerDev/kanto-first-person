import {
  BackSide,
  Color,
  CylinderGeometry,
  DirectionalLight,
  DynamicDrawUsage,
  Euler,
  Fog,
  Group,
  HemisphereLight,
  InstancedMesh,
  MathUtils,
  Matrix4,
  Mesh,
  MeshStandardMaterial,
  PerspectiveCamera,
  Quaternion,
  Scene,
  ShaderMaterial,
  SphereGeometry,
  TorusGeometry,
  Vector3,
  WebGLRenderer,
} from 'three'
import type { QualityTier } from '../state/journey'

const BALL_SEED = 0x151
const HIGH_QUALITY_BALLS = 11
const LOW_QUALITY_BALLS = 6
const BALL_SCALE_TIERS = [0.62, 0.86, 1.12, 1.42] as const
const BALL_SCALE_PATTERN = [0.62, 0.86, 1.12, 0.62, 0.86, 1.42, 0.62, 1.12, 1.42, 0.86, 0.86] as const
const LEFT_VERTICAL_SLOTS = [-0.84, -0.5, -0.17, 0.17, 0.5, 0.84] as const
const RIGHT_VERTICAL_SLOTS = [-0.78, -0.39, 0, 0.39, 0.78] as const
const LEFT_EDGE_SLOTS = [0.88, 0.96, 0.84, 0.94, 0.86, 0.97] as const
const RIGHT_EDGE_SLOTS = [0.9, 0.97, 0.84, 0.95, 0.88] as const
const POKEBALL_RED = '#e43b3f'
const POKEBALL_WHITE = '#f5f1df'
const POKEBALL_BLACK = '#141719'

type BallTransform = {
  side: -1 | 1
  screenY: number
  position: [number, number, number]
  rotation: [number, number, number]
  scale: number
  phase: number
  speed: number
  direction: number
}

export type KantoWorldRuntime = {
  update: (time: number) => void
  resize: (aspect: number) => void
  updateDiagnostics: () => void
  dispose: () => void
}

type KantoWorldOptions = {
  scene: Scene
  camera: PerspectiveCamera
  renderer: WebGLRenderer
  host: HTMLElement
  quality: QualityTier
  reducedMotion: boolean
  aspect: number
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
  const halfFov = MathUtils.degToRad(25)

  return Array.from({ length: count }, (_, index) => {
    const side = index % 2 === 0 ? -1 : 1
    const sideIndex = Math.floor(index / 2)
    const verticalSlots = side === -1 ? LEFT_VERTICAL_SLOTS : RIGHT_VERTICAL_SLOTS
    const edgeSlots = side === -1 ? LEFT_EDGE_SLOTS : RIGHT_EDGE_SLOTS
    const screenY = verticalSlots[sideIndex % verticalSlots.length]
    const distance = 13 + random() * 25
    const halfHeight = Math.tan(halfFov) * distance
    const scaleTier = BALL_SCALE_PATTERN[index % BALL_SCALE_PATTERN.length]
    return {
      side,
      screenY,
      position: [
        side * halfHeight * aspect * edgeSlots[sideIndex % edgeSlots.length],
        screenY * halfHeight,
        11 - distance,
      ],
      rotation: [
        (random() - 0.5) * 0.65,
        (random() - 0.5) * 0.9,
        (random() - 0.5) * 0.48,
      ],
      scale: halfHeight * 0.105 * scaleTier,
      phase: random() * Math.PI * 2,
      speed: 0.045 + random() * 0.075,
      direction: random() > 0.5 ? 1 : -1,
    }
  })
}

const RING_LOCAL = new Matrix4().makeRotationX(Math.PI / 2)
const BUTTON_OUTER_LOCAL = new Matrix4().compose(
  new Vector3(0, 0, 1.035),
  new Quaternion().setFromEuler(new Euler(Math.PI / 2, 0, 0)),
  new Vector3(1, 1, 1),
)
const BUTTON_INNER_LOCAL = new Matrix4().compose(
  new Vector3(0, 0, 1.13),
  new Quaternion().setFromEuler(new Euler(Math.PI / 2, 0, 0)),
  new Vector3(1, 1, 1),
)

export function createKantoWorld({
  scene,
  camera,
  renderer,
  host,
  quality,
  reducedMotion,
  aspect,
}: KantoWorldOptions): KantoWorldRuntime {
  const count = quality === 'high' ? HIGH_QUALITY_BALLS : LOW_QUALITY_BALLS
  let layout = createBallLayout(count, aspect)
  let lastTime = 0

  scene.background = new Color('#050a12')
  scene.fog = new Fog('#050a12', 12, 44)
  camera.position.set(0, 0.4, 11)
  camera.lookAt(0, 0, -10)

  const root = new Group()
  root.name = 'pokeball-world'
  scene.add(root)

  const atmosphereGeometry = new SphereGeometry(1, 20, 12)
  const atmosphereMaterial = new ShaderMaterial({
    side: BackSide,
    depthWrite: false,
    toneMapped: false,
    uniforms: {
      uTop: { value: new Color('#050a12') },
      uHorizon: { value: new Color('#26364a') },
    },
    vertexShader: `
      varying vec3 vDirection;
      void main() {
        vDirection = normalize(position);
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      varying vec3 vDirection;
      uniform vec3 uTop;
      uniform vec3 uHorizon;
      void main() {
        float heightMix = pow(clamp(vDirection.y * 0.5 + 0.5, 0.0, 1.0), 0.7);
        gl_FragColor = vec4(mix(uHorizon, uTop, heightMix), 1.0);
      }
    `,
  })
  const atmosphere = new Mesh(atmosphereGeometry, atmosphereMaterial)
  atmosphere.name = 'atmosphere'
  atmosphere.scale.setScalar(80)
  atmosphere.frustumCulled = false
  root.add(atmosphere)

  const widthSegments = quality === 'high' ? 22 : 16
  const heightSegments = quality === 'high' ? 12 : 9
  const radialSegments = quality === 'high' ? 16 : 12
  const topGeometry = new SphereGeometry(1, widthSegments, heightSegments, 0, Math.PI * 2, 0, Math.PI / 2)
  const bottomGeometry = new SphereGeometry(1, widthSegments, heightSegments, 0, Math.PI * 2, Math.PI / 2, Math.PI / 2)
  const bandGeometry = new TorusGeometry(1.005, 0.075, 6, widthSegments)
  const outerGeometry = new CylinderGeometry(0.29, 0.29, 0.16, radialSegments)
  const innerGeometry = new CylinderGeometry(0.18, 0.18, 0.17, radialSegments)
  const topMaterial = new MeshStandardMaterial({ color: POKEBALL_RED, roughness: 0.31, metalness: 0.03 })
  const bottomMaterial = new MeshStandardMaterial({ color: POKEBALL_WHITE, roughness: 0.38, metalness: 0.02 })
  const bandMaterial = new MeshStandardMaterial({ color: POKEBALL_BLACK, roughness: 0.5 })
  const outerMaterial = new MeshStandardMaterial({ color: POKEBALL_BLACK, roughness: 0.45 })
  const innerMaterial = new MeshStandardMaterial({ color: POKEBALL_WHITE, roughness: 0.24 })
  const top = new InstancedMesh(topGeometry, topMaterial, count)
  const bottom = new InstancedMesh(bottomGeometry, bottomMaterial, count)
  const band = new InstancedMesh(bandGeometry, bandMaterial, count)
  const buttonOuter = new InstancedMesh(outerGeometry, outerMaterial, count)
  const buttonInner = new InstancedMesh(innerGeometry, innerMaterial, count)
  const meshes = [top, bottom, band, buttonOuter, buttonInner]
  meshes.forEach((mesh) => {
    mesh.instanceMatrix.setUsage(DynamicDrawUsage)
    root.add(mesh)
  })

  const key = new DirectionalLight('#fff4dc', 4.2)
  key.position.set(-7, 10, 8)
  const rim = new DirectionalLight('#d9e8ff', 1.15)
  rim.position.set(8, -2, 6)
  root.add(new HemisphereLight('#fff7e6', '#05070b', 2.1), key, rim)

  const scratchPosition = new Vector3()
  const scratchRotation = new Euler()
  const scratchQuaternion = new Quaternion()
  const scratchScale = new Vector3()
  const rootMatrix = new Matrix4()
  const worldMatrix = new Matrix4()

  const writeMatrices = (time: number) => {
    lastTime = time
    layout.forEach((ball, index) => {
      const drift = quality === 'high' && !reducedMotion ? Math.sin(time * 0.42 + ball.phase) * 0.18 : 0
      const spin = quality === 'high' && !reducedMotion ? time * ball.speed * ball.direction : 0
      scratchPosition.set(ball.position[0], ball.position[1] + drift, ball.position[2])
      scratchRotation.set(
        ball.rotation[0] + spin * 0.34,
        ball.rotation[1] + spin,
        ball.rotation[2] + spin * 0.18,
      )
      scratchQuaternion.setFromEuler(scratchRotation)
      scratchScale.setScalar(ball.scale)
      rootMatrix.compose(scratchPosition, scratchQuaternion, scratchScale)

      top.setMatrixAt(index, rootMatrix)
      bottom.setMatrixAt(index, rootMatrix)
      worldMatrix.multiplyMatrices(rootMatrix, RING_LOCAL)
      band.setMatrixAt(index, worldMatrix)
      worldMatrix.multiplyMatrices(rootMatrix, BUTTON_OUTER_LOCAL)
      buttonOuter.setMatrixAt(index, worldMatrix)
      worldMatrix.multiplyMatrices(rootMatrix, BUTTON_INNER_LOCAL)
      buttonInner.setMatrixAt(index, worldMatrix)
    })
    meshes.forEach((mesh) => { mesh.instanceMatrix.needsUpdate = true })
  }

  const refreshBounds = () => meshes.forEach((mesh) => mesh.computeBoundingSphere())
  writeMatrices(0)
  refreshBounds()
  const sideGaps = (side: -1 | 1) => {
    const positions = layout
      .filter((ball) => ball.side === side)
      .map((ball) => ball.screenY)
      .sort((a, b) => a - b)
    return {
      gap: Math.min(...positions.slice(1).map((position, index) => position - positions[index])),
      span: positions.at(-1)! - positions[0],
    }
  }
  const leftLayout = sideGaps(-1)
  const rightLayout = sideGaps(1)
  host.dataset.ballCount = String(count)
  host.dataset.ballSizeVariants = String(BALL_SCALE_TIERS.length)
  host.dataset.ballLayout = 'balanced-side-zones'
  host.dataset.minVerticalGap = Math.min(leftLayout.gap, rightLayout.gap).toFixed(2)
  host.dataset.minVerticalSpan = Math.min(leftLayout.span, rightLayout.span).toFixed(2)

  const geometries = [atmosphereGeometry, topGeometry, bottomGeometry, bandGeometry, outerGeometry, innerGeometry]
  const materials = [atmosphereMaterial, topMaterial, bottomMaterial, bandMaterial, outerMaterial, innerMaterial]

  return {
    update(time) {
      if (quality === 'high' && !reducedMotion) writeMatrices(time)
    },
    resize(nextAspect) {
      layout = createBallLayout(count, nextAspect)
      writeMatrices(lastTime)
      refreshBounds()
    },
    updateDiagnostics() {
      host.dataset.drawCalls = String(renderer.info.render.calls)
      host.dataset.triangles = String(renderer.info.render.triangles)
      host.dataset.geometries = String(renderer.info.memory.geometries)
      host.dataset.textures = String(renderer.info.memory.textures)
      host.dataset.materials = String(materials.length)
    },
    dispose() {
      scene.remove(root)
      geometries.forEach((geometry) => geometry.dispose())
      materials.forEach((material) => material.dispose())
      scene.background = null
      scene.fog = null
    },
  }
}
