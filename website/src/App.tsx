import { lazy, Suspense, useEffect, type CSSProperties } from 'react'
import { useJourneyStore } from './state/journey'
import { AtmosphereSwitch, GuideAndSupport, QualityControl, ScannerPanel } from './ui/FieldTerminal'
import { PALETTES } from './world/palettes'

const REPO = 'https://github.com/BoLayerDev/kanto-first-person'
const WorldCanvas = lazy(() => import('./scene/WorldCanvas'))

function BootSequence() {
  const booted = useJourneyStore((state) => state.booted)
  const setBooted = useJourneyStore((state) => state.setBooted)
  if (booted) return null

  return (
    <div className="boot-screen" role="dialog" aria-modal="true" aria-labelledby="boot-title">
      <div className="boot-noise" aria-hidden="true" />
      <div className="boot-core" aria-hidden="true">
        <span />
      </div>
      <div className="boot-copy">
        <div className="boot-kicker">GEN1RECOMP FIELD SYSTEM</div>
        <h1 id="boot-title">KANTO<br />FIRST PERSON</h1>
        <p>A new point of view for the classic Kanto journey.</p>
        <button type="button" onClick={() => setBooted(true)}>
          <span>ENTER THE WORLD</span>
          <span aria-hidden="true">▶</span>
        </button>
        <small>Original fan project · No ROM data included</small>
      </div>
    </div>
  )
}

function StoryJourney() {
  return (
    <main className="story-journey" id="journey">
      <section className="story-section story-hero" aria-labelledby="hero-title">
        <div className="story-card">
          <span className="eyebrow">KANTO FIRST PERSON 2.0</span>
          <h1 id="hero-title">THE WORLD<br />HAS <em>DEPTH.</em></h1>
          <p>
            Rooms gain walls. Routes reach the horizon. Caves close around you. The voxel host
            stays safe and in control.
          </p>
          <div className="hero-actions">
            <a className="primary-action" href="#field-guide">OPEN FIELD GUIDE</a>
            <a className="secondary-action" href={REPO} target="_blank" rel="noreferrer">
              VIEW SOURCE <span aria-hidden="true">↗</span>
            </a>
          </div>
        </div>
        <div className="scroll-cue" aria-hidden="true"><span /> SCROLL TO WALK</div>
      </section>

      <section className="story-section story-interior" aria-labelledby="interior-title">
        <div className="story-card story-card-right">
          <span className="chapter-number">01 / INTERIORS</span>
          <h2 id="interior-title">Every room becomes a real place.</h2>
          <p>
            Ceilings, windows, rails, posters, doorway light, and deliberate cutaways restore the
            shapes that the top-down view could only suggest.
          </p>
          <div className="feature-tags"><span>CEILINGS</span><span>LIGHT</span><span>DEPTH</span></div>
        </div>
      </section>

      <section className="story-section story-route" aria-labelledby="route-title">
        <div className="story-card">
          <span className="chapter-number">02 / THE OPEN WORLD</span>
          <h2 id="route-title">The map edge disappears.</h2>
          <p>
            Raised trees, neighboring terrain, mountains, clouds, grass, wind, fog, and rain make
            each route feel connected to a world beyond the tiles.
          </p>
          <div className="feature-tags"><span>WEATHER</span><span>HORIZONS</span><span>FLORA</span></div>
        </div>
      </section>

      <section className="story-section story-cave" aria-labelledby="cave-title">
        <div className="story-card story-card-right">
          <span className="chapter-number">03 / BELOW KANTO</span>
          <h2 id="cave-title">Caves finally have a roof.</h2>
          <p>
            Uneven stone, pools, columns, depth fog, and bounded practical light turn a flat room
            into a place that surrounds you.
          </p>
          <div className="feature-tags"><span>VOLUME</span><span>FOG</span><span>ATMOSPHERE</span></div>
        </div>
      </section>

      <section className="story-section story-terminal" id="camera-end" aria-labelledby="terminal-title">
        <div className="terminal-callout">
          <span className="eyebrow">VOXEL COMPANION API v1</span>
          <h2 id="terminal-title">One host. One safe contract. A much bigger world.</h2>
          <p>
            KFP does not patch or replace another mod. The selected voxel host owns the renderer
            and calls KFP through a bounded extension API.
          </p>
          <a href={`${REPO}/blob/v2-rewrite/docs/architecture.md`} target="_blank" rel="noreferrer">
            EXPLORE THE ARCHITECTURE <span aria-hidden="true">→</span>
          </a>
        </div>
      </section>

      <GuideAndSupport />

      <footer className="site-footer">
        <div>
          <strong>KANTO FIRST PERSON</strong>
          <span>2.0.0-alpha.1 source candidate</span>
        </div>
        <p>
          Independent fan project. Not affiliated with or endorsed by Nintendo, Game Freak,
          Creatures, or The Pokémon Company.
        </p>
        <nav aria-label="Project links">
          <a href={REPO} target="_blank" rel="noreferrer">GitHub</a>
          <a href={`${REPO}/blob/v2-rewrite/README.md`} target="_blank" rel="noreferrer">Docs</a>
          <a href={`${REPO}/blob/v2-rewrite/THIRD_PARTY_NOTICES.md`} target="_blank" rel="noreferrer">Notices</a>
        </nav>
      </footer>
    </main>
  )
}

export function App() {
  const edition = useJourneyStore((state) => state.edition)
  const scannerEnabled = useJourneyStore((state) => state.scannerEnabled)
  const progress = useJourneyStore((state) => state.progress)
  const setProgress = useJourneyStore((state) => state.setProgress)
  const setQuality = useJourneyStore((state) => state.setQuality)
  const palette = PALETTES[edition]

  useEffect(() => {
    const updateProgress = () => {
      const cameraEnd = document.getElementById('camera-end')
      const available = cameraEnd
        ? cameraEnd.offsetTop + cameraEnd.offsetHeight - window.innerHeight
        : document.documentElement.scrollHeight - window.innerHeight
      setProgress(available > 0 ? window.scrollY / available : 0)
    }
    updateProgress()
    window.addEventListener('scroll', updateProgress, { passive: true })
    window.addEventListener('resize', updateProgress)
    return () => {
      window.removeEventListener('scroll', updateProgress)
      window.removeEventListener('resize', updateProgress)
    }
  }, [setProgress])

  useEffect(() => {
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)')
    const limitedDevice = navigator.hardwareConcurrency !== undefined && navigator.hardwareConcurrency <= 4
    if (reducedMotion.matches || limitedDevice) setQuality('low')
  }, [setQuality])

  const themeStyle = {
    '--accent': palette.accent,
    '--accent-bright': palette.accentBright,
    '--accent-soft': palette.accentSoft,
    '--ink': palette.ink,
    '--panel': palette.panel,
    '--journey-progress': `${progress * 100}%`,
  } as CSSProperties

  return (
    <div className={`app edition-${edition} ${scannerEnabled ? 'scanner-is-active' : ''}`} style={themeStyle}>
      <a className="skip-link" href="#field-guide">Skip to field guide</a>
      <Suspense fallback={<div className="world-canvas world-loading">BUILDING KANTO...</div>}>
        <WorldCanvas />
      </Suspense>
      <div className="screen-treatment" aria-hidden="true" />
      {scannerEnabled && <div className="scan-reticle" aria-hidden="true"><span /></div>}

      <header className="site-header">
        <a className="wordmark" href="#journey" aria-label="Kanto First Person home">
          <span>KFP</span>
          <b>FIELD<br />TERMINAL</b>
        </a>
        <div className="header-status"><i /> ALPHA SIGNAL</div>
        <QualityControl />
      </header>

      <div className="journey-meter" aria-hidden="true"><span /></div>
      <AtmosphereSwitch />
      <ScannerPanel />
      <StoryJourney />
      <BootSequence />
    </div>
  )
}
