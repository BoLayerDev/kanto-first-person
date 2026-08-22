import { HOTSPOTS } from '../data/hotspots'
import { useJourneyStore, type HotspotId } from '../state/journey'
import { PALETTES, type Edition } from '../world/palettes'

const EDITIONS: Edition[] = ['red', 'blue', 'yellow']
const REPO = 'https://github.com/BoLayerDev/kanto-first-person'
const BRANCH = `${REPO}/blob/v2-rewrite`

export function AtmosphereSwitch() {
  const edition = useJourneyStore((state) => state.edition)
  const setEdition = useJourneyStore((state) => state.setEdition)

  return (
    <section className="edition-switch" aria-labelledby="edition-title">
      <div className="control-label" id="edition-title">
        VERSION SHIFT
      </div>
      <div className="edition-buttons">
        {EDITIONS.map((value) => (
          <button
            className={`edition-button edition-${value}`}
            type="button"
            key={value}
            aria-pressed={edition === value}
            onClick={() => setEdition(value)}
          >
            <span className="edition-light" aria-hidden="true" />
            {value.slice(0, 1).toUpperCase()}
          </button>
        ))}
      </div>
      <p>{PALETTES[edition].fieldNote}</p>
    </section>
  )
}

export function ScannerPanel() {
  const scannerEnabled = useJourneyStore((state) => state.scannerEnabled)
  const selected = useJourneyStore((state) => state.selectedHotspot)
  const hovered = useJourneyStore((state) => state.hoveredHotspot)
  const setScannerEnabled = useJourneyStore((state) => state.setScannerEnabled)
  const setSelected = useJourneyStore((state) => state.setSelectedHotspot)
  const active = selected ?? hovered
  const record = active ? HOTSPOTS[active] : null

  return (
    <aside className={`scanner-panel ${scannerEnabled ? 'is-active' : ''}`} aria-live="polite">
      <button
        className="scanner-toggle"
        type="button"
        aria-pressed={scannerEnabled}
        onClick={() => setScannerEnabled(!scannerEnabled)}
      >
        <span className="scanner-icon" aria-hidden="true" />
        {scannerEnabled ? 'SCANNER ONLINE' : 'ENABLE FIELD SCANNER'}
      </button>

      {scannerEnabled && (
        <div className="scanner-body">
          <div className="scanner-status">
            {record ? `${record.location} / DATA FOUND` : 'SELECT A SIGNAL IN THE WORLD'}
          </div>
          {record ? (
            <div className="scan-record" key={record.id}>
              <div className="scan-number">No. {record.number}</div>
              <div className="scan-label">{record.label}</div>
              <h2>{record.title}</h2>
              <p>{record.summary}</p>
              <ul>
                {record.facts.map((fact) => (
                  <li key={fact}>{fact}</li>
                ))}
              </ul>
            </div>
          ) : (
            <div className="scanner-grid" aria-label="Scanner targets">
              {(Object.keys(HOTSPOTS) as HotspotId[]).map((id) => (
                <button type="button" key={id} onClick={() => setSelected(id)}>
                  {HOTSPOTS[id].number} / {HOTSPOTS[id].label}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </aside>
  )
}

const GUIDE_LINKS = [
  ['Compatibility matrix', `${BRANCH}/docs/compatibility.md`],
  ['Safe v1 → v2 upgrade', `${BRANCH}/docs/upgrade-v1-to-v2.md`],
  ['Options and migration', `${BRANCH}/docs/options-migration.md`],
  ['Known limitations', `${BRANCH}/docs/known-limitations.md`],
] as const

const SUPPORT_LINKS = [
  ['Device test guide', `${BRANCH}/docs/device-test-guide.md`],
  ['Runtime QA matrix', `${BRANCH}/docs/qa-matrix.md`],
  ['Security policy', `${BRANCH}/SECURITY.md`],
  ['Report an issue', `${REPO}/issues/new/choose`],
] as const

export function GuideAndSupport() {
  return (
    <section className="guide-shell" id="field-guide" aria-labelledby="guide-title">
      <div className="guide-heading">
        <span className="eyebrow">TRAINER FIELD MANUAL</span>
        <h2 id="guide-title">Enter prepared.</h2>
        <p>
          Kanto First Person is a graphics overhaul for Gen1recomp voxel hosts. It adds depth,
          atmosphere, and world detail without taking control away from the selected host.
        </p>
      </div>

      <div className="guide-grid">
        <article className="guide-card guide-card-alert">
          <div className="guide-card-index">ALPHA NOTICE</div>
          <h3>Source candidate. Not a player release.</h3>
          <p>
            A signed KFP package and released API v1 host adapters are still required. Do not use
            GitHub&apos;s automatic source ZIP as a mod package.
          </p>
          <a href={`${BRANCH}/README.md#-clean-installation`} target="_blank" rel="noreferrer">
            Read the current install gate <span aria-hidden="true">↗</span>
          </a>
        </article>

        <article className="guide-card">
          <div className="guide-card-index">FIELD GUIDES</div>
          <h3>Install, migrate, and configure safely.</h3>
          <nav aria-label="Field guides">
            {GUIDE_LINKS.map(([label, href]) => (
              <a href={href} target="_blank" rel="noreferrer" key={label}>
                <span>{label}</span><span aria-hidden="true">→</span>
              </a>
            ))}
          </nav>
        </article>

        <article className="guide-card">
          <div className="guide-card-index">SUPPORT CENTER</div>
          <h3>Evidence before guesses.</h3>
          <nav aria-label="Support resources">
            {SUPPORT_LINKS.map(([label, href]) => (
              <a href={href} target="_blank" rel="noreferrer" key={label}>
                <span>{label}</span><span aria-hidden="true">→</span>
              </a>
            ))}
          </nav>
        </article>
      </div>

      <div className="install-path" aria-label="Future safe installation path">
        <div><b>01</b><span>Install one released voxel host</span></div>
        <div><b>02</b><span>Import the signed KFP package</span></div>
        <div><b>03</b><span>Enable KFP and restart Gen1recomp</span></div>
        <div><b>04</b><span>Confirm API v1 attachment</span></div>
      </div>
    </section>
  )
}

export function QualityControl() {
  const quality = useJourneyStore((state) => state.quality)
  const setQuality = useJourneyStore((state) => state.setQuality)
  return (
    <button
      type="button"
      className="quality-control"
      onClick={() => setQuality(quality === 'high' ? 'low' : 'high')}
      aria-label={`Graphics quality: ${quality}. Activate to switch quality.`}
    >
      FX {quality === 'high' ? 'HI' : 'LO'}
    </button>
  )
}
