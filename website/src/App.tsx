import { lazy, Suspense, useEffect, useRef, type CSSProperties, type ReactNode } from 'react'
import { useJourneyStore } from './state/journey'
import { PALETTES, type Edition } from './world/palettes'

const REPO = 'https://github.com/BoLayerDev/kanto-first-person'
const BRANCH = `${REPO}/blob/v2-rewrite`
const WorldCanvas = lazy(() => import('./scene/WorldCanvas'))

type MenuItem = {
  label: string
  eyebrow: string
  title: string
  summary: string
}

const MENU_ITEMS: MenuItem[] = [
  {
    label: 'KANTO FIRST PERSON',
    eyebrow: 'PROJECT FILE / 001',
    title: 'A new point of view.',
    summary:
      'A world-detail graphics overhaul for Gen1recomp. Rooms gain depth. Caves gain roofs. Routes reach the horizon.',
  },
  {
    label: 'FIELD FEATURES',
    eyebrow: 'FIELD DATA / 025',
    title: 'The world gets bigger.',
    summary:
      'Interiors, forests, caves, horizons, weather, camera motion, and ambient sound rebuild the visual shape of Kanto.',
  },
  {
    label: 'TRAINER GUIDE',
    eyebrow: 'MANUAL / SAFE START',
    title: 'Enter prepared.',
    summary:
      'KFP is an Alpha source candidate. A signed package and released API v1 host adapter are required before player installation.',
  },
  {
    label: 'SUPPORT CENTER',
    eyebrow: 'LINK CENTER / ONLINE',
    title: 'Evidence before guesses.',
    summary:
      'Check compatibility, known limits, device testing, security guidance, and the issue tracker from one place.',
  },
  {
    label: 'OPEN GITHUB',
    eyebrow: 'SOURCE / PUBLIC',
    title: 'See how it works.',
    summary:
      'Read the source, architecture, tests, roadmap, release gates, and complete project history on GitHub.',
  },
]

const EDITIONS: Edition[] = ['red', 'blue', 'yellow']
const PRIMARY_LINKS = [
  `${BRANCH}/README.md`,
  `${BRANCH}/docs/feature-parity.md`,
  `${BRANCH}/docs/upgrade-v1-to-v2.md`,
  `${BRANCH}/docs/compatibility.md`,
  REPO,
]

function DetailLinks({ children }: { children: ReactNode }) {
  return <div className="detail-links">{children}</div>
}

function MenuDetail({ index }: { index: number }) {
  if (index === 0) {
    return (
      <>
        <div className="stat-row"><span>TYPE</span><b>GRAPHICS OVERHAUL</b></div>
        <div className="stat-row"><span>GAMES</span><b>RED · BLUE · YELLOW</b></div>
        <div className="stat-row"><span>ENGINE</span><b>GEN1RECOMP API 2</b></div>
        <div className="alpha-notice"><i /> 2.0.0-ALPHA.1 SOURCE CANDIDATE</div>
        <DetailLinks>
          <a href={`${BRANCH}/README.md`} target="_blank" rel="noreferrer">PROJECT OVERVIEW <span>↗</span></a>
          <a href={`${BRANCH}/ROADMAP.md`} target="_blank" rel="noreferrer">ROADMAP <span>↗</span></a>
        </DetailLinks>
      </>
    )
  }

  if (index === 1) {
    return (
      <>
        <div className="feature-list">
          <span>01</span><b>INTERIORS</b><small>Walls, ceilings, windows, doors, and light</small>
          <span>02</span><b>OPEN WORLD</b><small>Terrain aprons, trees, mountains, and horizons</small>
          <span>03</span><b>ATMOSPHERE</b><small>Clouds, rain, storms, fog, stars, and particles</small>
          <span>04</span><b>CAVES</b><small>Uneven roofs, pools, stone columns, and sconces</small>
        </div>
        <DetailLinks>
          <a href={`${BRANCH}/docs/feature-parity.md`} target="_blank" rel="noreferrer">FULL FEATURE LEDGER <span>↗</span></a>
        </DetailLinks>
      </>
    )
  }

  if (index === 2) {
    return (
      <>
        <div className="warning-box">
          <b>WAIT FOR A SIGNED PRERELEASE.</b>
          <p>Do not use GitHub&apos;s automatic source ZIP as a mod package.</p>
        </div>
        <ol className="install-steps">
          <li><b>01</b><span>Install one released compatible voxel host.</span></li>
          <li><b>02</b><span>Import the signed KFP package.</span></li>
          <li><b>03</b><span>Enable KFP and restart Gen1recomp.</span></li>
          <li><b>04</b><span>Confirm API v1 attachment.</span></li>
        </ol>
        <DetailLinks>
          <a href={`${BRANCH}/docs/upgrade-v1-to-v2.md`} target="_blank" rel="noreferrer">SAFE UPGRADE GUIDE <span>↗</span></a>
          <a href={`${BRANCH}/docs/options-migration.md`} target="_blank" rel="noreferrer">OPTION MIGRATION <span>↗</span></a>
        </DetailLinks>
      </>
    )
  }

  if (index === 3) {
    return (
      <DetailLinks>
        <a href={`${BRANCH}/docs/compatibility.md`} target="_blank" rel="noreferrer">COMPATIBILITY MATRIX <span>↗</span></a>
        <a href={`${BRANCH}/docs/known-limitations.md`} target="_blank" rel="noreferrer">KNOWN LIMITATIONS <span>↗</span></a>
        <a href={`${BRANCH}/docs/device-test-guide.md`} target="_blank" rel="noreferrer">DEVICE TEST GUIDE <span>↗</span></a>
        <a href={`${BRANCH}/SECURITY.md`} target="_blank" rel="noreferrer">SECURITY POLICY <span>↗</span></a>
        <a href={`${REPO}/issues/new/choose`} target="_blank" rel="noreferrer">REPORT AN ISSUE <span>↗</span></a>
      </DetailLinks>
    )
  }

  return (
    <div className="github-launch">
      <div className="repo-mark" aria-hidden="true">&lt;/&gt;</div>
      <p>Public source · MIT code · ROM-free tests · Reproducible release gates</p>
      <a className="launch-button" href={REPO} target="_blank" rel="noreferrer">
        OPEN REPOSITORY <span>↗</span>
      </a>
    </div>
  )
}

function OptionsMenu() {
  const menuIndex = useJourneyStore((state) => state.menuIndex)
  const edition = useJourneyStore((state) => state.edition)
  const quality = useJourneyStore((state) => state.quality)
  const setMenuIndex = useJourneyStore((state) => state.setMenuIndex)
  const setEdition = useJourneyStore((state) => state.setEdition)
  const setQuality = useJourneyStore((state) => state.setQuality)
  const menuButtons = useRef<Array<HTMLButtonElement | null>>([])
  const item = MENU_ITEMS[menuIndex]

  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      if (event.altKey || event.ctrlKey || event.metaKey) return
      if (event.target instanceof HTMLAnchorElement) return
      const key = event.key.toLowerCase()
      const isMenuButton = event.target instanceof HTMLButtonElement
        && menuButtons.current.includes(event.target)
      if (['arrowup', 'w'].includes(key)) {
        event.preventDefault()
        const nextIndex = (menuIndex - 1 + MENU_ITEMS.length) % MENU_ITEMS.length
        setMenuIndex(nextIndex)
        menuButtons.current[nextIndex]?.focus()
      } else if (['arrowdown', 's'].includes(key)) {
        event.preventDefault()
        const nextIndex = (menuIndex + 1) % MENU_ITEMS.length
        setMenuIndex(nextIndex)
        menuButtons.current[nextIndex]?.focus()
      } else if (['arrowleft', 'a'].includes(key)) {
        event.preventDefault()
        const index = EDITIONS.indexOf(edition)
        setEdition(EDITIONS[(index - 1 + EDITIONS.length) % EDITIONS.length])
      } else if (['arrowright', 'd'].includes(key)) {
        event.preventDefault()
        const index = EDITIONS.indexOf(edition)
        setEdition(EDITIONS[(index + 1) % EDITIONS.length])
      } else if (['enter', ' ', 'z'].includes(key)) {
        if (event.target instanceof HTMLButtonElement && !isMenuButton && key !== 'z') return
        event.preventDefault()
        window.open(PRIMARY_LINKS[menuIndex], '_blank', 'noopener,noreferrer')
      } else if (['escape', 'x'].includes(key)) {
        event.preventDefault()
        setMenuIndex(0)
        menuButtons.current[0]?.focus()
      }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [edition, menuIndex, setEdition, setMenuIndex])

  return (
    <main className="terminal-shell">
      <section className="title-strip" aria-labelledby="site-title">
        <div className="split-core" aria-hidden="true"><span /></div>
        <div>
          <span>KFP // FIELD OPTIONS</span>
          <h1 id="site-title">KANTO FIRST PERSON</h1>
        </div>
        <div className="alpha-chip"><i /> ALPHA</div>
      </section>

      <div className="terminal-grid">
        <nav className="menu-window pixel-window" aria-label="Main options">
          <div className="window-label">OPTIONS</div>
          {MENU_ITEMS.map((menuItem, index) => (
            <button
              type="button"
              className={index === menuIndex ? 'is-selected' : ''}
              aria-current={index === menuIndex ? 'page' : undefined}
              key={menuItem.label}
              ref={(button) => { menuButtons.current[index] = button }}
              onClick={() => setMenuIndex(index)}
              onPointerEnter={() => setMenuIndex(index)}
            >
              <span className="menu-cursor" aria-hidden="true">▶</span>
              <span>{menuItem.label}</span>
            </button>
          ))}

          <div className="menu-divider" />
          <div className="inline-option">
            <span>VERSION</span>
            <div aria-label="Version palette">
              {EDITIONS.map((value) => (
                <button
                  type="button"
                  className={edition === value ? 'is-active' : ''}
                  aria-pressed={edition === value}
                  onClick={() => setEdition(value)}
                  key={value}
                >
                  {value.slice(0, 1).toUpperCase()}
                </button>
              ))}
            </div>
          </div>
          <div className="inline-option">
            <span>EFFECTS</span>
            <button
              type="button"
              className="quality-toggle"
              onClick={() => setQuality(quality === 'high' ? 'low' : 'high')}
              aria-label={`Effects quality ${quality}`}
            >
              ◀ {quality.toUpperCase()} ▶
            </button>
          </div>
        </nav>

        <section className="detail-window pixel-window" aria-live="polite" aria-labelledby="detail-title">
          <div className="window-label">{item.eyebrow}</div>
          <div className="detail-copy">
            <h2 id="detail-title">{item.title}</h2>
            <p className="detail-summary">{item.summary}</p>
            <MenuDetail index={menuIndex} />
          </div>
        </section>
      </div>

      <footer className="control-strip">
        <div><kbd>↑↓</kbd><span>SELECT</span></div>
        <div><kbd>←→</kbd><span>VERSION</span></div>
        <div><kbd>ENTER</kbd><span>OPEN</span></div>
        <div><kbd>ESC</kbd><span>BACK</span></div>
        <p>Independent fan project · No ROM data · Not affiliated with Nintendo, Game Freak, Creatures, or The Pokémon Company.</p>
      </footer>
    </main>
  )
}

export function App() {
  const edition = useJourneyStore((state) => state.edition)
  const setQuality = useJourneyStore((state) => state.setQuality)
  const palette = PALETTES[edition]

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
  } as CSSProperties

  return (
    <div className={`app edition-${edition}`} style={themeStyle}>
      <Suspense fallback={<div className="world-canvas world-loading">LOADING WORLD DATA...</div>}>
        <WorldCanvas />
      </Suspense>
      <div className="screen-treatment" aria-hidden="true" />
      <OptionsMenu />
    </div>
  )
}
