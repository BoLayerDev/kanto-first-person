import { lazy, Suspense, useCallback, useEffect, useId, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { useProjectStatus, type ActivityScope, type ProjectStatus } from './data/projectStatus'
import { useJourneyStore } from './state/journey'
import { PALETTES, type Edition } from './world/palettes'

const REPO = 'https://github.com/BoLayerDev/kanto-first-person'
const BRANCH = `${REPO}/blob/v2-rewrite`
const REWRITE_START_COMMIT = '0f453187210d3d388a02196affee413994df1a77'
const MONTH_LABELS = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
const WorldCanvas = lazy(() => import('./scene/WorldCanvas'))
const MENU_SLUGS = ['home', 'features', 'activity', 'guide', 'support', 'rebuild', 'github'] as const
const AMBIENCE_MODES = ['lab', 'route', 'research', 'mist', 'signal', 'evolution', 'stars'] as const
const RELEASE_BALL_ASSETS: Record<Edition, string> = {
  red: 'ultra-ball-2d.png',
  blue: 'master-ball-2d.png',
  yellow: 'great-ball-2d.png',
}
const ACTIVITY_SCOPE_LABELS: Record<ActivityScope, string> = {
  mod: 'MOD BUILD',
  site: 'SITE LAB',
  ops: 'PROJECT OPS',
}

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
    label: 'RESEARCH LOG',
    eyebrow: 'OAK LAB / COMPLETE HISTORY',
    title: 'Every step. No mystery.',
    summary:
      'Every verified commit on the release branch lives here. New work joins the log automatically after the complete CI lab scan passes.',
  },
  {
    label: 'TRAINER GUIDE',
    eyebrow: 'MANUAL / SAFE START',
    title: 'Enter prepared.',
    summary:
      'A signed KFP package and a compatible Battle Art or Dramaless release with Voxel Companion API v1 support are required before installation.',
  },
  {
    label: 'SUPPORT CENTER',
    eyebrow: 'LINK CENTER / ONLINE',
    title: 'Evidence before guesses.',
    summary:
      'Check compatibility, known limits, device testing, security guidance, and the issue tracker from one place.',
  },
  {
    label: 'NEXT-GEN REBUILD',
    eyebrow: 'EVOLUTION FILE / 2.0',
    title: 'Same Kanto. New foundations.',
    summary:
      'This is not a patch update. KFP 2.0 is a clean companion rewrite built for safer hosts, bounded performance, and a much bigger world.',
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
  `${REPO}/commits/v2-rewrite`,
  `${BRANCH}/docs/upgrade-v1-to-v2.md`,
  `${BRANCH}/docs/compatibility.md`,
  `${BRANCH}/docs/architecture.md`,
  REPO,
]

const REWRITE_UPGRADES = [
  ['INTEGRATION', 'SPLICED HOST SOURCE', 'PUBLIC COMPANION API'],
  ['OWNERSHIP', 'BACKUPS + FILE LEDGERS', 'KFP RESOURCES ONLY'],
  ['WORLD BUILD', 'LARGE RENDER-PATH WORK', 'BUDGETED COMPILER'],
  ['STATE', 'BROAD MUTABLE TABLES', 'BOUNDED SNAPSHOTS'],
  ['RANDOMNESS', 'GLOBAL RANDOM STATE', 'LOCAL DETERMINISM'],
  ['RELEASE', 'MANUAL ARCHIVES', 'REPRODUCIBLE GATES'],
]

function DetailLinks({ children }: { children: ReactNode }) {
  return <div className="detail-links">{children}</div>
}

function publicWorkTitle(value: string) {
  const title = value.replace(/^[a-z]+(?:\([^)]+\))?:\s*/i, '')
  const privateMetric = /\b(?:ai|codex|llm)[\s-]+tokens?\b|\btokens?[\s-]+(?:usage|count|counts)\b/i
  return privateMetric.test(title) ? 'Clean up public development stats' : title
}

function activityTitle(message: string) {
  return publicWorkTitle(message)
}

type ActivityEntry = ProjectStatus['activity'][number]

function useLiveNow() {
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 30_000)
    return () => window.clearInterval(timer)
  }, [])

  return now
}

function useDeploymentTime(fallback: string) {
  const [deployedAt, setDeployedAt] = useState(fallback)

  useEffect(() => {
    const parsed = Date.parse(document.lastModified)
    if (Number.isFinite(parsed)) setDeployedAt(new Date(parsed).toISOString())
  }, [fallback])

  return deployedAt
}

function relativeTime(date: string, now: number) {
  const parsed = Date.parse(date)
  if (!Number.isFinite(parsed)) return 'TIME UNKNOWN'
  const seconds = Math.max(0, Math.floor((now - parsed) / 1000))
  if (seconds < 60) return 'JUST NOW'
  if (seconds < 3_600) return `${Math.floor(seconds / 60)}M AGO`
  if (seconds < 86_400) return `${Math.floor(seconds / 3_600)}H AGO`
  if (seconds < 604_800) return `${Math.floor(seconds / 86_400)}D AGO`
  if (seconds < 2_592_000) return `${Math.floor(seconds / 604_800)}W AGO`
  if (seconds < 31_536_000) return `${Math.floor(seconds / 2_592_000)}MO AGO`
  return `${Math.floor(seconds / 31_536_000)}Y AGO`
}

function exactTime(date: string) {
  const parsed = Date.parse(date)
  if (!Number.isFinite(parsed)) return 'Exact time unavailable'
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZoneName: 'short',
  }).format(parsed)
}

function durationLabel(seconds = 0) {
  if (!seconds) return '--'
  const minutes = Math.floor(seconds / 60)
  const remainder = seconds % 60
  return minutes ? `${minutes}M ${remainder}S` : `${remainder}S`
}

function longDurationLabel(seconds = 0) {
  if (!seconds) return '--'
  const days = Math.floor(seconds / 86_400)
  const hours = Math.floor((seconds % 86_400) / 3_600)
  const minutes = Math.floor((seconds % 3_600) / 60)
  const remainder = seconds % 60
  if (days) return `${days}D ${hours}H`
  if (hours) return `${hours}H ${minutes}M`
  if (minutes) return `${minutes}M ${remainder}S`
  return `${remainder}S`
}

function taskTitle(title: string) {
  return publicWorkTitle(title)
}

function useCountUp(target: number, active: boolean) {
  const [value, setValue] = useState(target)

  useEffect(() => {
    if (!active || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setValue(target)
      return
    }
    let frame = 0
    const startedAt = performance.now()
    const tick = (now: number) => {
      const progress = Math.min(1, (now - startedAt) / 850)
      setValue(Math.round(target * (1 - ((1 - progress) ** 3))))
      if (progress < 1) frame = window.requestAnimationFrame(tick)
    }
    setValue(0)
    frame = window.requestAnimationFrame(tick)
    return () => window.cancelAnimationFrame(frame)
  }, [active, target])

  return value
}

function PokeballLoader({ label }: { label: string }) {
  return (
    <div className="pokeball-loader" role="status">
      <span className="loader-ball" aria-hidden="true"><i /></span>
      <b>{label}</b>
    </div>
  )
}

function Timestamp({ date, now }: { date: string, now: number }) {
  const [open, setOpen] = useState(false)
  const relative = relativeTime(date, now)
  const exact = exactTime(date)

  return (
    <span className={`timestamp-wrap${open ? ' is-open' : ''}`}>
      <button
        type="button"
        className="timestamp-trigger"
        aria-label={`${relative}. ${exact}`}
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      >
        <time dateTime={date}>{relative}</time>
      </button>
      <span className="timestamp-tooltip" role="tooltip">{exact}</span>
    </span>
  )
}

function InfoTip({ label, text }: { label: string, text: string }) {
  const [open, setOpen] = useState(false)
  const [focused, setFocused] = useState(false)
  const tooltipId = useId()

  return (
    <span
      className={`info-tip${open ? ' is-open' : ''}`}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) {
          setFocused(false)
          setOpen(false)
        }
      }}
    >
      <button
        type="button"
        className="info-tip-trigger"
        aria-label={`Explain ${label}`}
        aria-describedby={tooltipId}
        aria-expanded={open || focused}
        aria-controls={tooltipId}
        onFocus={() => setFocused(true)}
        onClick={() => setOpen((current) => !current)}
        onKeyDown={(event) => {
          if (event.key === 'Escape') {
            setOpen(false)
            event.currentTarget.blur()
          }
        }}
      >
        ?
      </button>
      <span className="info-tip-tooltip" id={tooltipId} role="tooltip">{text}</span>
    </span>
  )
}

function activityState(entry: ActivityEntry, index: number, now: number) {
  if (index === 0) return 'LIVE'
  const entryDate = new Date(entry.date)
  const today = new Date(now)
  if (entryDate.getFullYear() === today.getFullYear()
    && entryDate.getMonth() === today.getMonth()
    && entryDate.getDate() === today.getDate()) return 'TODAY'
  return 'ARCHIVED'
}

function ActivityMeta({ entry, index, now }: { entry: ActivityEntry, index: number, now: number }) {
  const state = activityState(entry, index, now)
  const [open, setOpen] = useState(false)
  const exact = exactTime(entry.date)
  const relative = relativeTime(entry.date, now)
  const exactTimeId = useId()

  return (
    <>
      <div
        className="activity-meta"
        onBlur={(event) => {
          if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setOpen(false)
        }}
      >
        <span className={`activity-state is-${state.toLowerCase()}`}>{state}</span>
        <button
          type="button"
          className="activity-timestamp-trigger"
          aria-label={`${relative}. ${exact}`}
          aria-controls={exactTimeId}
          aria-expanded={open}
          onClick={() => setOpen((current) => !current)}
        >
          <time dateTime={entry.date}>{relative}</time>
        </button>
        {entry.ci ? (
          <a className="activity-ci" href={entry.ci.runUrl} target="_blank" rel="noreferrer">
            CI {durationLabel(entry.ci.durationSeconds)} ↗
          </a>
        ) : null}
      </div>
      <div className="activity-exact-time" id={exactTimeId} hidden={!open}>
        <span>EXACT COMMIT TIME</span>
        <time dateTime={entry.date}>{exact}</time>
      </div>
    </>
  )
}

function TrainerClock({ status }: { status: ProjectStatus }) {
  const now = useLiveNow()
  const lastUpdate = status.activity[0]?.date ?? status.generatedAt
  const deployedAt = useDeploymentTime(status.generatedAt)
  const sevenDaysAgo = now - (7 * 24 * 60 * 60 * 1000)
  const weeklyActivity = status.activity.filter((entry) => Date.parse(entry.date) >= sevenDaysAgo).length

  return (
    <section className="trainer-clock" aria-label="Trainer Clock">
      <span className="trainer-clock-label">TRAINER CLOCK</span>
      <div>
        <span><small>LAST UPDATE</small><Timestamp date={lastUpdate} now={now} /></span>
        <a
          href={status.ci.runUrl}
          target="_blank"
          rel="noreferrer"
          title="Run time of the latest successful GitHub Actions check"
        >
          <small>LATEST CI TIME</small><b>{durationLabel(status.ci.durationSeconds)}</b>
        </a>
        <span><small>DEPLOYED</small><Timestamp date={deployedAt} now={now} /></span>
        <span title="Commits on v2-rewrite during the last seven days">
          <small>LAST 7 DAYS</small><b>{weeklyActivity}</b>
        </span>
      </div>
    </section>
  )
}

function MissionBoard({ status }: { status: ProjectStatus }) {
  return (
    <section className="mission-board" aria-labelledby="mission-board-title">
      <header>
        <div><span>LIVE OBJECTIVES FROM GITHUB</span><b id="mission-board-title">TRAINER MISSION BOARD</b></div>
        <span><i aria-hidden="true" /> AUTO SYNC</span>
      </header>
      <div className="mission-grid">
        {status.missions.map((mission) => (
          <a
            className={`mission-card is-${mission.slot.toLowerCase()}`}
            href={mission.url}
            target="_blank"
            rel="noreferrer"
            key={mission.slot}
          >
            <span>{mission.slot}</span>
            <b>{activityTitle(mission.title)}</b>
            <small>{mission.source === 'issue' ? 'LABELED GITHUB ISSUE' : 'VERIFIED ROADMAP'} ↗</small>
          </a>
        ))}
      </div>
    </section>
  )
}

function ReleaseJourney({ status }: { status: ProjectStatus }) {
  return (
    <section className="release-journey" aria-labelledby="release-journey-title">
      <header>
        <div><span>EVIDENCE-LOCKED RELEASE PATH</span><b id="release-journey-title">THE KANTO LEAGUE ROAD</b></div>
        <span>OPEN A BADGE FOR PROOF</span>
      </header>
      <ol>
        {status.releaseJourney.map((gate, index) => (
          <li className={`is-${gate.state}`} key={gate.id}>
            <a href={gate.url} target="_blank" rel="noreferrer" title={gate.summary}>
              <i aria-hidden="true">{String(index + 1).padStart(2, '0')}</i>
              <b>{gate.label}</b>
              <span>{gate.state.toUpperCase()}</span>
            </a>
          </li>
        ))}
      </ol>
    </section>
  )
}

function WeeklyOakReport({ status }: { status: ProjectStatus }) {
  const [scope, setScope] = useState<ActivityScope>('mod')
  const scopedReport = status.weeklyReport.scopes[scope]
  const counts = scopedReport.counts
  const entries = [
    ['NEW MOVES', counts.features, 'New features. GitHub commits marked feat: count here. This shows how many new capabilities entered the project this week.'],
    ['BUGS FIXED', counts.fixes, 'Bug repairs. GitHub commits marked fix: count here. This shows how many verified corrections landed this week.'],
    ['SPEED UPS', counts.performance, 'Performance improvements. GitHub commits marked perf: count here. This tracks work that makes the mod or its tools faster and more efficient.'],
    ['LAB CHECKS', counts.tests, 'Automated tests and CI checks. GitHub commits marked test: or ci: count here. This tracks work that catches regressions.'],
    ['FIELD NOTES', counts.documentation, 'Guides and technical records. GitHub commits marked docs: count here. This tracks documentation and release instructions.'],
    ['MILESTONES', counts.milestones, 'Major refactors and release, device, compatibility, or architecture checkpoints. This shows the big project stages reached this week.'],
  ] as const

  return (
    <section className="weekly-report" aria-labelledby="weekly-report-title">
      <header><span>LAST SEVEN DAYS // MERGES EXCLUDED</span><b id="weekly-report-title">PROFESSOR OAK REPORT</b></header>
      <div className="scope-switch" role="group" aria-label="Professor Oak report work stream">
        {(Object.keys(ACTIVITY_SCOPE_LABELS) as ActivityScope[]).map((value) => (
          <button
            type="button"
            className={scope === value ? 'is-active' : ''}
            aria-pressed={scope === value}
            onClick={() => setScope(value)}
            key={value}
          >
            {ACTIVITY_SCOPE_LABELS[value]}
          </button>
        ))}
      </div>
      <div className="weekly-report-total">
        <b>{scopedReport.total}</b>
        <span className="weekly-report-total-label">
          {ACTIVITY_SCOPE_LABELS[scope]} / 7 DAYS
          <InfoTip
            label={`${ACTIVITY_SCOPE_LABELS[scope]} LAST 7 DAYS`}
            text={`Verified ${ACTIVITY_SCOPE_LABELS[scope].toLowerCase()} commits from the last seven days. Merge commits are preserved in the complete log but excluded from these progress totals.`}
          />
        </span>
      </div>
      <dl>
        {entries.map(([label, value, description]) => (
          <div key={label}>
            <dt><span>{label}</span><InfoTip label={label} text={description} /></dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

function OakLabReceipt({ status }: { status: ProjectStatus }) {
  return (
    <section className="oak-lab-receipt" aria-labelledby="oak-lab-receipt-title">
      <header>
        <div>
          <span>GITHUB ACTIONS // AUTO FILED</span>
          <b id="oak-lab-receipt-title">OAK LAB RECEIPT</b>
        </div>
        <span className="receipt-signal"><i aria-hidden="true" /> VERIFIED DATA</span>
      </header>
      <div className="receipt-paper">
        <a className={`proof-lead is-${status.proof.tier}`} href={status.proof.url} target="_blank" rel="noreferrer">
          <span>{status.proof.kind}</span>
          <b>{status.proof.label}</b>
          <small>{status.proof.environment} · {status.proof.commit} ↗</small>
        </a>
        <div className="receipt-meta">
          <span>RECEIPT {status.receipt.id}</span>
          <time dateTime={status.receipt.issuedAt}>{exactTime(status.receipt.issuedAt)}</time>
        </div>
        <ol>
          {status.receipt.rows.map((row, index) => (
            <li key={row.id}>
              <a href={row.url} target="_blank" rel="noreferrer">
                <span className="receipt-index">{String(index + 1).padStart(2, '0')}</span>
                <span className="receipt-copy"><b>{row.label}</b><small>{row.detail}</small></span>
                <strong>{row.value}</strong>
                <span className={`receipt-state is-${row.state.toLowerCase()}`}>{row.state}</span>
              </a>
            </li>
          ))}
        </ol>
        <footer>
          <span>EVERY LINE OPENS ITS GITHUB EVIDENCE</span>
          <b>NO PUBLIC API CALLS</b>
        </footer>
      </div>
    </section>
  )
}

function DevStats({ status, complete = false }: { status: ProjectStatus, complete?: boolean }) {
  const now = useLiveNow()
  const rewriteStart = Date.parse(status.devStats.rewriteStartedAt)
  const projectAgeSeconds = Number.isFinite(rewriteStart)
    ? Math.max(1, Math.floor((now - rewriteStart) / 1000))
    : 0
  const tasks = complete ? status.pullRequests : status.pullRequests.slice(0, 3)

  return (
    <section className="dev-stats" aria-labelledby={complete ? 'dev-stats-full-title' : 'dev-stats-title'}>
      <header>
        <div>
          <span>OAK LAB // SAVE FILE</span>
          <b id={complete ? 'dev-stats-full-title' : 'dev-stats-title'}>VERIFIED PROJECT STATS</b>
        </div>
        <span className="dev-stats-signal"><i aria-hidden="true" /> AUTO SYNC</span>
      </header>

      <dl>
        <div><dt>PROJECT AGE</dt><dd>{longDurationLabel(projectAgeSeconds)}</dd></div>
        <div><dt>MOD COMMITS</dt><dd>{status.devStats.scopeCommits.mod}</dd></div>
        <div><dt>ACTIVE DAYS</dt><dd>{status.devStats.activeDays}</dd></div>
        <div><dt>MERGED TASKS</dt><dd>{status.devStats.mergedPullRequests}</dd></div>
        <div><dt>TOTAL CI TIME</dt><dd>{longDurationLabel(status.devStats.labRuntimeSeconds)}</dd></div>
      </dl>

      <div className="quest-log-heading">
        <span>{complete ? 'COMPLETE MERGED TASK HISTORY' : 'LATEST MERGED TASKS'}</span>
        <b>PR QUEST LOG</b>
      </div>
      <ol className="quest-log">
        {tasks.map((task) => (
          <li key={task.number}>
            <a href={task.url} target="_blank" rel="noreferrer">
              <span>QUEST #{String(task.number).padStart(2, '0')}</span>
              <b>{taskTitle(task.title)}</b>
              <small className="quest-timing">
                AUTO DELIVERY <strong className="quest-duration">{longDurationLabel(task.deliverySeconds)}</strong>
              </small>
            </a>
          </li>
        ))}
      </ol>
      <footer>
        <span>CI TIME = GITHUB ACTIONS WALL TIME. AUTO DELIVERY = PR OPENED TO MERGED.</span>
        <span>NOT HANDS-ON HOURS.</span>
      </footer>
    </section>
  )
}

function ActivityLog({ status, newResearch = false }: { status: ProjectStatus, newResearch?: boolean }) {
  const [scope, setScope] = useState<ActivityScope>('mod')
  const scopedActivity = status.activity.filter((entry) => entry.scope === scope && !entry.isMerge)
  const updates = scopedActivity.slice(0, 4)
  const now = useLiveNow()
  const scopedDiscovery = newResearch && status.activity[0]?.scope === scope && !status.activity[0]?.isMerge
  const displayedCount = useCountUp(scopedActivity.length, scopedDiscovery)

  return (
    <section className="activity-log" aria-labelledby="activity-title">
      <div className="activity-header">
        <div>
          <span>LIVE FROM {status.branch.toUpperCase()}</span>
          <b id="activity-title">OAK RESEARCH LOG</b>
        </div>
        <span className="live-signal"><i /> WORK CONTINUES</span>
      </div>
      {newResearch ? (
        <div className="research-discovery" role="status">
          <i aria-hidden="true" /><span>NEW RESEARCH DISCOVERED</span><b>#{status.shortSha}</b>
        </div>
      ) : null}
      <div className="scope-switch activity-scope-switch" role="group" aria-label="Research Log work stream">
        {(Object.keys(ACTIVITY_SCOPE_LABELS) as ActivityScope[]).map((value) => (
          <button
            type="button"
            className={scope === value ? 'is-active' : ''}
            aria-pressed={scope === value}
            onClick={() => setScope(value)}
            key={value}
          >
            {ACTIVITY_SCOPE_LABELS[value]}
          </button>
        ))}
      </div>
      <ol>
        {updates.map((update, index) => (
          <li
            className={index === 0 && scopedDiscovery ? 'is-discovered' : ''}
            key={update.sha}
            style={{ '--log-index': index } as CSSProperties}
          >
            <a className="activity-entry-main" href={update.url} target="_blank" rel="noreferrer">
              <span className="activity-type">{update.type}</span>
              <b>{activityTitle(update.message)}</b>
              <code>{update.shortSha}</code>
            </a>
            <ActivityMeta entry={update} index={index} now={now} />
          </li>
        ))}
      </ol>
      <div className="activity-footer">
        <span className={scopedDiscovery ? 'is-counting' : ''}>
          <strong>{displayedCount}</strong> VERIFIED {ACTIVITY_SCOPE_LABELS[scope]} UPDATES
        </span>
        <a href="#activity">OPEN FULL LOG ▶</a>
      </div>
    </section>
  )
}

function ReleaseBanner({ status, edition }: { status: ProjectStatus; edition: Edition }) {
  const buildLabel = status.ci.state === 'success' && status.ci.total > 0
    ? `${status.ci.passed}/${status.ci.total} PASS`
    : 'CHECK CI'
  const packageCard = status.release.available ? (
    <a href={status.release.url} target="_blank" rel="noreferrer">
      <span>PACKAGE</span><b>{status.release.label}</b><i aria-hidden="true">↗</i>
    </a>
  ) : (
    <div><span>PACKAGE</span><b>{status.release.label}</b></div>
  )

  return (
    <section className="release-banner" aria-labelledby="site-title">
      <div className="release-core" aria-hidden="true">
        <img
          src={`${import.meta.env.BASE_URL}balls/${RELEASE_BALL_ASSETS[edition]}`}
          alt=""
          width="512"
          height="512"
        />
      </div>
      <div className="release-copy">
        <span className="release-kicker">KANTO FIRST PERSON // TRAINERS, STAND BY</span>
        <h1 id="site-title"><span>COMING</span> SOON</h1>
        <p>{status.version} tracks the verified GitHub branch. Real-game acceptance and the signed public package are still in progress.</p>
      </div>
      <div className="release-status" aria-label="Current release status">
        <a href={status.ci.runUrl} target="_blank" rel="noreferrer">
          <span>BUILD</span><b>{buildLabel}</b><i aria-hidden="true">↗</i>
        </a>
        <a href={status.commitUrl} target="_blank" rel="noreferrer">
          <span>SOURCE</span><b>{status.shortSha}</b><i aria-hidden="true">↗</i>
        </a>
        {packageCard}
      </div>
    </section>
  )
}

function RewriteComparisonGraphic() {
  return (
    <figure className="evolution-scan" aria-labelledby="evolution-scan-title">
      <header className="evolution-scan-header">
        <div>
          <span>OAK LAB // SYSTEM RECORD 002</span>
          <b id="evolution-scan-title">REWRITE EVOLUTION SCAN</b>
        </div>
        <span className="scan-signal"><i aria-hidden="true" /> ARCHITECTURE MAPPED</span>
      </header>

      <div className="evolution-forms">
        <section className="system-form is-legacy" aria-label="Legacy host-patching architecture">
          <header><span>FORM 01</span><b>HOST PATCH</b><em>V1.60</em></header>
          <div className="architecture-path is-legacy-path">
            <div className="system-node"><span>MOD</span><b>KFP</b></div>
            <span className="system-link"><i>WRITES</i></span>
            <div className="system-node is-risk"><span>PATCH</span><b>HOST FILES</b></div>
            <span className="system-link"><i>LOADS</i></span>
            <div className="system-node"><span>RUNTIME</span><b>GEN1RECOMP</b></div>
          </div>
          <div className="system-readout">
            <span><small>BOUNDARY</small><b>SHARED</b></span>
            <span><small>ROLLBACK</small><b>MANUAL</b></span>
            <span><small>FAILURE</small><b>WIDE</b></span>
          </div>
        </section>

        <div className="evolution-pulse" aria-hidden="true">
          <span>FULL</span>
          <i><b>→</b></i>
          <span>REWRITE</span>
        </div>

        <section className="system-form is-rebuild" aria-label="Rebuilt Voxel Companion API v1 architecture">
          <header><span>FORM 02</span><b>KFP REBUILD</b><em>V2.0</em></header>
          <div className="architecture-path is-rebuild-path">
            <div className="system-node"><span>MOD</span><b>KFP</b></div>
            <span className="system-link"><i>SUBMITS</i></span>
            <div className="system-node is-api"><span>VOXEL COMPANION</span><b>API v1</b></div>
            <span className="system-link"><i>VALIDATES</i></span>
            <div className="system-node"><span>OWNER</span><b>HOST</b></div>
          </div>
          <div className="system-readout">
            <span><small>BOUNDARY</small><b>ISOLATED</b></span>
            <span><small>BUILDS</small><b>REPEATABLE</b></span>
            <span><small>FAILURE</small><b>BOUNDED</b></span>
          </div>
        </section>
      </div>

      <figcaption>
        <span><i aria-hidden="true">×</i> OLD: MOD MUTATES HOST</span>
        <b aria-hidden="true">EVOLVE</b>
        <span><i aria-hidden="true">✓</i> NEW: HOST VALIDATES PACKETS</span>
      </figcaption>
    </figure>
  )
}

function RewriteDetail() {
  return (
    <div className="rewrite-page">
      <div className="rewrite-callout">
        <span>FULL SYSTEM REWRITE</span>
        <b>BUILT AGAIN.<br />BUILT TO LAST.</b>
        <p>KFP keeps the ambition of the original mod and replaces its old foundation with an isolated, testable Gen1recomp API 2 architecture.</p>
      </div>

      <RewriteComparisonGraphic />

      <section className="field-media" aria-labelledby="field-media-title">
        <figure>
          <div className="media-frame">
            <img
              src={`${import.meta.env.BASE_URL}og-kanto-rebuild-page.webp`}
              alt="Original pixel-art concept of a first-person route leading toward a wide mountain region"
              width="1200"
              height="632"
              loading="lazy"
            />
            <span>CONCEPT ART // NOT GAMEPLAY</span>
          </div>
          <figcaption><b id="field-media-title">THE 2.0 WORLD VISION</b><span>Original project artwork</span></figcaption>
        </figure>
        <div className="capture-lock">
          <span className="capture-icon" aria-hidden="true">▣</span>
          <span>DEVICE CAPTURE / SLOT 01</span>
          <b>REAL FOOTAGE UNLOCKS AFTER ACCEPTANCE</b>
          <p>No staged gameplay. No ROM data. The first real comparison will appear only after device evidence passes.</p>
          <a href={`${BRANCH}/docs/device-test-guide.md`} target="_blank" rel="noreferrer">VIEW THE CAPTURE GATE ↗</a>
        </div>
      </section>

      <div className="rebuild-vitals" aria-label="Rewrite highlights">
        <div><b>53</b><span>LEGACY SETTINGS MAPPED</span></div>
        <div><b>5</b><span>ENGINE TARGETS IN CI</span></div>
        <div><b>3</b><span>GEN 1 GAMES TARGETED</span></div>
      </div>

      <section className="upgrade-grid" aria-labelledby="upgrade-grid-title">
        <div className="upgrade-grid-title" id="upgrade-grid-title">
          <span>THEN</span><b>THE 2.0 EVOLUTION</b><span>NOW</span>
        </div>
        {REWRITE_UPGRADES.map(([area, before, after]) => (
          <div className="upgrade-row" key={area}>
            <span>{before}</span><b>{area}</b><span>{after}</span>
          </div>
        ))}
      </section>

      <section className="world-upgrades" aria-labelledby="world-upgrades-title">
        <div>
          <span>WORLD / 01</span><b id="world-upgrades-title">ROOMS BECOME PLACES</b>
          <p>Walls, ceilings, doors, windows, light fittings, cave roofs, pools, rails, and battle props add depth to familiar spaces.</p>
        </div>
        <div>
          <span>HORIZON / 02</span><b>ROUTES KEEP GOING</b>
          <p>Terrain aprons, trees, mountains, forest structures, clouds, stars, and distant activity push Kanto beyond the map edge.</p>
        </div>
        <div>
          <span>ATMOSPHERE / 03</span><b>THE WORLD HAS WEATHER</b>
          <p>Rain, storms, fog, canopy, particles, camera motion, and ambient sound are represented as bounded feature systems.</p>
        </div>
        <div>
          <span>SAFETY / 04</span><b>THE HOST STAYS IN CONTROL</b>
          <p>One host owns the renderer. KFP submits validated packets, isolates faults, and never patches, restores, or deletes host files.</p>
        </div>
      </section>

      <div className="rebuild-promise">
        <span>NEXT OBJECTIVE</span>
        <b>A BIGGER FIRST-PERSON KANTO—WITH A FOUNDATION THE COMMUNITY CAN TRUST.</b>
      </div>

      <DetailLinks>
        <a href={`${BRANCH}/docs/architecture.md`} target="_blank" rel="noreferrer">EXPLORE THE ARCHITECTURE <span>↗</span></a>
        <a href={`${BRANCH}/docs/feature-parity.md`} target="_blank" rel="noreferrer">VIEW THE FEATURE LEDGER <span>↗</span></a>
        <a href={`${BRANCH}/docs/upgrade-v1-to-v2.md`} target="_blank" rel="noreferrer">READ THE SAFE UPGRADE PATH <span>↗</span></a>
      </DetailLinks>
    </div>
  )
}

function ResearchArchive({
  status,
  unlockNewest,
  onUnlockComplete,
}: {
  status: ProjectStatus
  unlockNewest: boolean
  onUnlockComplete: () => void
}) {
  const now = useLiveNow()
  const [activityFilter, setActivityFilter] = useState('all')
  const [scopeFilter, setScopeFilter] = useState<ActivityScope | 'all'>('mod')
  const contributors = new Set(status.activity.map((entry) => entry.author)).size
  const activeDays = new Set(status.activity.map((entry) => entry.date.slice(0, 10))).size
  const rewriteStart = status.activity.find((entry) => entry.sha === REWRITE_START_COMMIT)
  const rewriteStartDate = rewriteStart?.date.slice(0, 10) ?? 'UNKNOWN'
  const rewriteStartParts = /^(\d{4})-(\d{2})-(\d{2})$/.exec(rewriteStartDate)
  const rewriteStartMonth = rewriteStartParts
    ? MONTH_LABELS[Number(rewriteStartParts[2]) - 1]
    : undefined
  const typeCounts = [...status.activity.reduce((counts, entry) => {
    counts.set(entry.type, (counts.get(entry.type) ?? 0) + 1)
    return counts
  }, new Map<string, number>())]
  const automaticMilestones = status.activity.filter((entry) => (
    ['NEW MOVE', 'EVOLVED', 'LAB VERIFIED'].includes(entry.type)
    || /^[a-z]+\((release|device|compat|architecture)\):/i.test(entry.message)
    || /^release:/i.test(entry.message)
  )).slice(0, 6)
  const filterOptions = [
    ['all', 'ALL'],
    ['features', 'FEATURES'],
    ['fixes', 'FIXES'],
    ['performance', 'PERFORMANCE'],
    ['tests', 'TESTS'],
    ['documentation', 'DOCUMENTATION'],
    ['milestones', 'MILESTONES'],
  ] as const
  const activityCategory = (entry: ActivityEntry) => {
    if (entry.type === 'NEW MOVE') return 'features'
    if (entry.type === 'HP RESTORED') return 'fixes'
    if (entry.type === 'SPEED +1') return 'performance'
    if (entry.type === 'LAB VERIFIED') return 'tests'
    if (entry.type === 'EVOLVED'
      || /^[a-z]+\((release|device|compat|architecture)\):/i.test(entry.message)
      || /^release:/i.test(entry.message)) return 'milestones'
    if (entry.type === 'FIELD NOTES') return 'documentation'
    return 'other'
  }
  const filteredActivity = status.activity.filter((entry) => (
    (scopeFilter === 'all' || entry.scope === scopeFilter)
    && (activityFilter === 'all' || activityCategory(entry) === activityFilter)
  ))

  useEffect(() => {
    if (!unlockNewest) return
    const timer = window.setTimeout(onUnlockComplete, 1800)
    return () => window.clearTimeout(timer)
  }, [onUnlockComplete, unlockNewest])

  return (
    <div className="archive-page">
      <TrainerClock status={status} />
      <div className="archive-vitals" aria-label="Complete development totals">
        <div title="All commits in the complete repository history"><b>{status.activity.length}</b><span>FULL REPO HISTORY</span></div>
        <div><b>{activeDays}</b><span>ACTIVE FIELD DAYS</span></div>
        <div><b>{contributors}</b><span>CONTRIBUTORS</span></div>
        <div className="archive-date-vital">
          {rewriteStartParts && rewriteStartMonth ? (
            <time dateTime={rewriteStartDate} aria-label={`Rewrite began ${rewriteStartDate}`}>
              <b>{rewriteStartMonth} {rewriteStartParts[3]}</b>
            </time>
          ) : <b>--.--</b>}
          <span>REWRITE BEGAN{rewriteStartParts ? ` / ${rewriteStartParts[1]}` : ''}</span>
        </div>
      </div>

      <DevStats status={status} complete />

      <section className="milestone-deck" aria-labelledby="milestone-title">
        <div className="milestone-header">
          <div><span>AUTO-SELECTED FROM VERIFIED HISTORY</span><b id="milestone-title">FIELD BADGES</b></div>
          <span>NO MANUAL LOGGING REQUIRED</span>
        </div>
        <div>
          {automaticMilestones.map((entry, index) => (
            <a
              className={index === 0 && unlockNewest ? 'is-unlocking' : ''}
              href={entry.url}
              target="_blank"
              rel="noreferrer"
              key={entry.sha}
            >
              <i aria-hidden="true">{String(index + 1).padStart(2, '0')}</i>
              <span>{entry.type}</span>
              <b>{activityTitle(entry.message)}</b>
              <small>{entry.date.slice(0, 10)} · {entry.shortSha}</small>
            </a>
          ))}
        </div>
      </section>

      <figure className="archive-system-map">
        <img
          src={`${import.meta.env.BASE_URL}activity-system-share.svg`}
          alt="Diagram showing commits passing through CI into the homepage Research Log"
          loading="lazy"
        />
        <figcaption>
          <span>THE PROGRESS PIPELINE // EVERY ENTRY LINKS TO ITS SOURCE</span>
          <a href={`${import.meta.env.BASE_URL}activity-system-share.png`} download>DOWNLOAD SHARE GRAPHIC ↓</a>
        </figcaption>
      </figure>

      <section className="archive-types" aria-labelledby="archive-types-title">
        <b id="archive-types-title">FIELD WORK INDEX</b>
        <div>
          {typeCounts.map(([type, count]) => <span key={type}><i>{count}</i>{type}</span>)}
        </div>
      </section>

      <section className="archive-filters" aria-labelledby="archive-filters-title">
        <b id="archive-filters-title">FILTER THE RESEARCH LOG</b>
        <div role="group" aria-label="Research Log work streams">
          <button
            type="button"
            className={scopeFilter === 'all' ? 'is-active' : ''}
            aria-pressed={scopeFilter === 'all'}
            onClick={() => setScopeFilter('all')}
          >
            ALL WORK
          </button>
          {(Object.keys(ACTIVITY_SCOPE_LABELS) as ActivityScope[]).map((value) => (
            <button
              type="button"
              className={scopeFilter === value ? 'is-active' : ''}
              aria-pressed={scopeFilter === value}
              onClick={() => setScopeFilter(value)}
              key={value}
            >
              {ACTIVITY_SCOPE_LABELS[value]}
            </button>
          ))}
        </div>
        <div role="group" aria-label="Research Log filters">
          {filterOptions.map(([value, label]) => (
            <button
              type="button"
              className={activityFilter === value ? 'is-active' : ''}
              aria-pressed={activityFilter === value}
              onClick={() => setActivityFilter(value)}
              key={value}
            >
              {label}
            </button>
          ))}
        </div>
      </section>

      <section className="archive-ledger" aria-labelledby="archive-ledger-title">
        <div className="archive-ledger-header">
          <div><span>DEFAULT BRANCH / {status.branch.toUpperCase()}</span><b id="archive-ledger-title">COMPLETE VERIFIED HISTORY</b></div>
          <span>{filteredActivity.length} SHOWN · NEWEST FIRST</span>
        </div>
        <ol>
          {filteredActivity.map((entry, index) => (
            <li key={entry.sha}>
              <a className="archive-entry-main" href={entry.url} target="_blank" rel="noreferrer">
                <span className="archive-number">#{String(status.activity.length - status.activity.indexOf(entry)).padStart(3, '0')}</span>
                <span className="archive-entry-type">{entry.type}</span>
                <b>{activityTitle(entry.message)}</b>
                <span className="archive-author">{ACTIVITY_SCOPE_LABELS[entry.scope]} · {entry.author}</span>
                <code>{entry.shortSha}</code>
              </a>
              <ActivityMeta entry={entry} index={index} now={now} />
            </li>
          ))}
        </ol>
      </section>

      <DetailLinks>
        <a href={`${REPO}/commits/${status.branch}`} target="_blank" rel="noreferrer">VERIFY THE FULL LOG ON GITHUB <span>↗</span></a>
      </DetailLinks>
    </div>
  )
}

function MenuDetail({
  index,
  status,
  newResearch,
  unlockNewest,
  onUnlockComplete,
}: {
  index: number
  status: ProjectStatus
  newResearch: boolean
  unlockNewest: boolean
  onUnlockComplete: () => void
}) {
  if (index === 0) {
    return (
      <>
        <div className="home-vitals">
          <span><small>VERSION</small><b>{status.version.toUpperCase()}</b></span>
          <span><small>LAB SCAN</small><b>{status.ci.passed}/{status.ci.total} PASS</b></span>
          <span><small>TARGET</small><b>RED · BLUE · YELLOW</b></span>
        </div>
        <TrainerClock status={status} />
        <MissionBoard status={status} />
        <ReleaseJourney status={status} />
        <div className="progress-proof-grid">
          <WeeklyOakReport status={status} />
          <OakLabReceipt status={status} />
        </div>
        <DevStats status={status} />
        <ActivityLog status={status} newResearch={newResearch} />
      </>
    )
  }

  if (index === 1) {
    return (
      <>
        <div className="feature-list">
          <div className="feature-list-row">
            <span>01</span><b>INTERIORS</b><small>Walls, ceilings, windows, doors, and light</small>
          </div>
          <div className="feature-list-row">
            <span>02</span><b>OPEN WORLD</b><small>Terrain aprons, trees, mountains, and horizons</small>
          </div>
          <div className="feature-list-row">
            <span>03</span><b>ATMOSPHERE</b><small>Clouds, rain, storms, fog, stars, and particles</small>
          </div>
          <div className="feature-list-row">
            <span>04</span><b>CAVES</b><small>Uneven roofs, pools, stone columns, and sconces</small>
          </div>
        </div>
        <DetailLinks>
          <a href={`${BRANCH}/docs/feature-parity.md`} target="_blank" rel="noreferrer">FULL FEATURE LEDGER <span>↗</span></a>
        </DetailLinks>
      </>
    )
  }

  if (index === 2) {
    return (
      <ResearchArchive
        status={status}
        unlockNewest={unlockNewest}
        onUnlockComplete={onUnlockComplete}
      />
    )
  }

  if (index === 3) {
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

  if (index === 4) {
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

  if (index === 5) {
    return <RewriteDetail />
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

function OptionsMenu({
  status,
  newResearch,
  unlockNewest,
  onUnlockComplete,
}: {
  status: ProjectStatus
  newResearch: boolean
  unlockNewest: boolean
  onUnlockComplete: () => void
}) {
  const menuIndex = useJourneyStore((state) => state.menuIndex)
  const edition = useJourneyStore((state) => state.edition)
  const quality = useJourneyStore((state) => state.quality)
  const setMenuIndex = useJourneyStore((state) => state.setMenuIndex)
  const setEdition = useJourneyStore((state) => state.setEdition)
  const menuButtons = useRef<Array<HTMLButtonElement | null>>([])
  const item = MENU_ITEMS[menuIndex]

  const navigateToMenu = (index: number) => {
    setMenuIndex(index)
    const nextHash = `#${MENU_SLUGS[index]}`
    if (window.location.hash !== nextHash) window.history.pushState({}, '', nextHash)
  }

  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      if (event.altKey || event.ctrlKey || event.metaKey) return
      const key = event.key.toLowerCase()
      const isAnchor = event.target instanceof HTMLAnchorElement
      const isMenuButton = event.target instanceof HTMLButtonElement
        && menuButtons.current.includes(event.target)
      if (['arrowup', 'w'].includes(key)) {
        event.preventDefault()
        const nextIndex = (menuIndex - 1 + MENU_ITEMS.length) % MENU_ITEMS.length
        navigateToMenu(nextIndex)
        menuButtons.current[nextIndex]?.focus()
      } else if (['arrowdown', 's'].includes(key)) {
        event.preventDefault()
        const nextIndex = (menuIndex + 1) % MENU_ITEMS.length
        navigateToMenu(nextIndex)
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
        if (isAnchor || (event.target instanceof HTMLButtonElement && !isMenuButton && key !== 'z')) return
        event.preventDefault()
        window.open(PRIMARY_LINKS[menuIndex], '_blank', 'noopener,noreferrer')
      } else if (['escape', 'x'].includes(key)) {
        event.preventDefault()
        navigateToMenu(0)
        menuButtons.current[0]?.focus()
      }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [edition, menuIndex, setEdition, setMenuIndex])

  return (
    <main className="terminal-shell">
      <ReleaseBanner status={status} edition={edition} />

      <div className="terminal-grid">
        <nav className="menu-window pixel-window" aria-label="Main options">
          {MENU_ITEMS.map((menuItem, index) => (
            <button
              type="button"
              className={index === menuIndex ? 'is-selected' : ''}
              aria-current={index === menuIndex ? 'page' : undefined}
              key={menuItem.label}
              ref={(button) => { menuButtons.current[index] = button }}
              onClick={() => navigateToMenu(index)}
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
        </nav>

        <section
          className="detail-window pixel-window"
          data-ambience={AMBIENCE_MODES[menuIndex]}
          data-effects={quality}
          aria-live="polite"
          aria-labelledby="detail-title"
        >
          <div className={`detail-ambience ambience-${AMBIENCE_MODES[menuIndex]}`} aria-hidden="true">
            {Array.from({ length: 8 }, (_, index) => <i key={index} style={{ '--particle': index } as CSSProperties} />)}
          </div>
          <span className="pokedex-scan" key={`scan-${menuIndex}`} aria-hidden="true" />
          <div className="window-label">{item.eyebrow}</div>
          <div className="detail-copy" key={`copy-${menuIndex}`}>
            <h2 id="detail-title">{item.title}</h2>
            <p className="detail-summary">{item.summary}</p>
            <MenuDetail
              index={menuIndex}
              status={status}
              newResearch={newResearch}
              unlockNewest={unlockNewest}
              onUnlockComplete={onUnlockComplete}
            />
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
  const { status, isLoaded: statusLoaded } = useProjectStatus()
  const edition = useJourneyStore((state) => state.edition)
  const setMenuIndex = useJourneyStore((state) => state.setMenuIndex)
  const setQuality = useJourneyStore((state) => state.setQuality)
  const palette = PALETTES[edition]

  useEffect(() => {
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)')
    const network = (navigator as Navigator & {
      connection?: { saveData?: boolean; addEventListener?: (type: string, listener: () => void) => void; removeEventListener?: (type: string, listener: () => void) => void }
      deviceMemory?: number
    }).connection
    const deviceMemory = (navigator as Navigator & { deviceMemory?: number }).deviceMemory
    const updateQuality = () => {
      const narrowViewport = window.innerWidth <= 720
      const limitedDevice = navigator.hardwareConcurrency !== undefined
        && navigator.hardwareConcurrency <= 4
        && window.innerWidth < 1100
      const limitedMemory = deviceMemory !== undefined && deviceMemory <= 2
      const dataSaver = network?.saveData === true
      setQuality(reducedMotion.matches || narrowViewport || limitedDevice || limitedMemory || dataSaver ? 'low' : 'high')
    }
    updateQuality()
    reducedMotion.addEventListener('change', updateQuality)
    network?.addEventListener?.('change', updateQuality)
    window.addEventListener('resize', updateQuality)
    return () => {
      reducedMotion.removeEventListener('change', updateQuality)
      network?.removeEventListener?.('change', updateQuality)
      window.removeEventListener('resize', updateQuality)
    }
  }, [setQuality])

  useEffect(() => {
    const syncMenuToLocation = () => {
      const slug = window.location.hash.slice(1).toLowerCase()
      const index = MENU_SLUGS.indexOf(slug as (typeof MENU_SLUGS)[number])
      setMenuIndex(index >= 0 ? index : 0)
    }
    syncMenuToLocation()
    window.addEventListener('popstate', syncMenuToLocation)
    window.addEventListener('hashchange', syncMenuToLocation)
    return () => {
      window.removeEventListener('popstate', syncMenuToLocation)
      window.removeEventListener('hashchange', syncMenuToLocation)
    }
  }, [setMenuIndex])

  const [worldReady, setWorldReady] = useState(false)
  const [worldMounted, setWorldMounted] = useState(false)
  const [newResearch, setNewResearch] = useState(false)
  const [unlockNewest, setUnlockNewest] = useState(false)

  useEffect(() => {
    if (!statusLoaded) return
    const storageKey = 'kfp-last-research-commit'
    try {
      const previousCommit = window.localStorage.getItem(storageKey)
      if (previousCommit !== status.commit) {
        setNewResearch(true)
        setUnlockNewest(true)
        window.localStorage.setItem(storageKey, status.commit)
        const timer = window.setTimeout(() => setNewResearch(false), 2800)
        return () => window.clearTimeout(timer)
      }
    } catch {
      setNewResearch(false)
    }
  }, [status.commit, statusLoaded])

  useEffect(() => {
    const windowWithIdle = window as Window & {
      requestIdleCallback?: (callback: () => void, options?: { timeout: number }) => number
      cancelIdleCallback?: (handle: number) => void
    }
    if (windowWithIdle.requestIdleCallback) {
      const handle = windowWithIdle.requestIdleCallback(() => setWorldReady(true), { timeout: 900 })
      return () => windowWithIdle.cancelIdleCallback?.(handle)
    }
    const handle = window.setTimeout(() => setWorldReady(true), 250)
    return () => window.clearTimeout(handle)
  }, [])

  const handleWorldReady = useCallback(() => setWorldMounted(true), [])
  const handleUnlockComplete = useCallback(() => setUnlockNewest(false), [])

  const themeStyle = {
    '--accent': palette.accent,
    '--accent-bright': palette.accentBright,
    '--accent-soft': palette.accentSoft,
    '--game-ink': palette.ink,
    '--paper': palette.panel,
    '--paper-dark': palette.panelDark,
    '--game-mid': palette.mid,
    '--game-pale': palette.pale,
    '--edition-banner': palette.banner,
    '--edition-deep': palette.skyTop,
    '--edition-sky': palette.skyHorizon,
    '--edition-fog': palette.fog,
    '--edition-ground': palette.ground,
    '--edition-grass': palette.grass,
    '--edition-stone': palette.stone,
    '--edition-signal': palette.signal,
  } as CSSProperties

  return (
    <div className={`app edition-${edition}`} style={themeStyle}>
      {worldReady ? (
        <Suspense fallback={<div className="world-canvas world-loading"><PokeballLoader label="LOADING WORLD DATA" /></div>}>
          <WorldCanvas onReady={handleWorldReady} />
        </Suspense>
      ) : <div className="world-canvas world-loading"><PokeballLoader label="WORLD DATA STANDBY" /></div>}
      <div className="screen-treatment" aria-hidden="true" />
      {(!statusLoaded || !worldMounted) ? (
        <div className="load-status-chip">
          <PokeballLoader label={!statusLoaded ? 'SYNCING OAK LAB' : 'WORLD READY CHECK'} />
        </div>
      ) : null}
      <OptionsMenu
        status={status}
        newResearch={newResearch}
        unlockNewest={unlockNewest}
        onUnlockComplete={handleUnlockComplete}
      />
    </div>
  )
}
