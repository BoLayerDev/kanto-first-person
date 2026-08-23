import { useEffect, useRef, useState } from 'react'
import {
  ACESFilmicToneMapping,
  PerspectiveCamera,
  Scene,
  SRGBColorSpace,
  WebGLRenderer,
} from 'three'
import { useJourneyStore } from '../state/journey'
import { createKantoWorld } from './KantoWorld'

type WorldCanvasProps = {
  onReady?: () => void
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

export default function WorldCanvas({ onReady }: WorldCanvasProps) {
  const hostRef = useRef<HTMLDivElement>(null)
  const readyRef = useRef(onReady)
  const quality = useJourneyStore((state) => state.quality)
  const reducedMotion = usePrefersReducedMotion()
  const [error, setError] = useState(false)

  useEffect(() => { readyRef.current = onReady }, [onReady])

  useEffect(() => {
    const host = hostRef.current
    if (!host) return

    let renderer: WebGLRenderer
    try {
      renderer = new WebGLRenderer({ antialias: false, powerPreference: 'high-performance' })
    } catch {
      setError(true)
      readyRef.current?.()
      return
    }

    setError(false)
    renderer.outputColorSpace = SRGBColorSpace
    renderer.toneMapping = ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.05
    renderer.setPixelRatio(quality === 'high' ? Math.min(window.devicePixelRatio, 1.5) : 1)
    renderer.domElement.setAttribute('aria-hidden', 'true')
    host.append(renderer.domElement)

    const scene = new Scene()
    const camera = new PerspectiveCamera(50, 1, 0.08, 90)
    let width = 1
    let height = 1
    let frame = 0
    let animationFrame = 0
    let ready = false
    let running = quality === 'high' && !reducedMotion
    const world = createKantoWorld({ scene, camera, renderer, host, quality, reducedMotion, aspect: 1 })

    const render = (time = 0) => {
      world.update(time / 1000)
      renderer.render(scene, camera)
      frame += 1
      if (frame === 1 || frame % 30 === 0) world.updateDiagnostics()
      if (!ready) {
        ready = true
        host.dataset.worldReady = 'true'
        readyRef.current?.()
      }
    }

    const animate = (time: number) => {
      render(time)
      if (running) animationFrame = window.requestAnimationFrame(animate)
    }

    const resize = () => {
      const nextWidth = Math.max(1, host.clientWidth)
      const nextHeight = Math.max(1, host.clientHeight)
      if (nextWidth === width && nextHeight === height) return
      width = nextWidth
      height = nextHeight
      camera.aspect = width / height
      camera.updateProjectionMatrix()
      renderer.setSize(width, height, false)
      world.resize(camera.aspect)
      if (!running) render()
    }

    const handleVisibility = () => {
      const shouldRun = quality === 'high' && !reducedMotion && !document.hidden
      if (shouldRun === running) return
      running = shouldRun
      if (running) animationFrame = window.requestAnimationFrame(animate)
      else window.cancelAnimationFrame(animationFrame)
    }

    const resizeObserver = new ResizeObserver(resize)
    resizeObserver.observe(host)
    document.addEventListener('visibilitychange', handleVisibility)
    resize()
    animationFrame = window.requestAnimationFrame(animate)

    return () => {
      running = false
      window.cancelAnimationFrame(animationFrame)
      resizeObserver.disconnect()
      document.removeEventListener('visibilitychange', handleVisibility)
      world.dispose()
      renderer.dispose()
      renderer.domElement.remove()
      delete host.dataset.worldReady
    }
  }, [quality, reducedMotion])

  return (
    <div
      ref={hostRef}
      className={`world-canvas world-pokeballs${error ? ' has-error' : ''}`}
      data-scene-mode="pokeballs-only"
      data-menu-reactive="false"
      data-quality={quality}
      aria-hidden="true"
    >
      {error ? <div className="webgl-fallback">3D preview unavailable. All menu options remain available.</div> : null}
    </div>
  )
}
