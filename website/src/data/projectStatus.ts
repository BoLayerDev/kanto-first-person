import { useEffect, useState } from 'react'

export type ActivityScope = 'mod' | 'site' | 'ops'

type WeeklyCounts = {
  features: number
  fixes: number
  performance: number
  tests: number
  documentation: number
  milestones: number
}

export type ProjectStatus = {
  schemaVersion: 1
  version: string
  experimental: boolean
  branch: string
  commit: string
  shortSha: string
  commitMessage: string
  commitUrl: string
  generatedAt: string
  activity: Array<{
    sha: string
    shortSha: string
    message: string
    date: string
    author: string
    type: string
    scope: ActivityScope
    isMerge: boolean
    url: string
    ci?: {
      runId?: string
      durationSeconds: number
      runUrl: string
      startedAt?: string
      completedAt?: string
      passed?: number
      total?: number
    }
  }>
  missions: Array<{
    slot: 'NOW' | 'NEXT' | 'BLOCKED'
    title: string
    url: string
    source: 'issue' | 'roadmap'
    updatedAt: string
  }>
  releaseJourney: Array<{
    id: 'rewrite' | 'host' | 'device' | 'package' | 'release'
    label: string
    state: 'complete' | 'active' | 'blocked' | 'pending'
    summary: string
    url: string
  }>
  weeklyReport: {
    startedAt: string
    endedAt: string
    total: number
    counts: WeeklyCounts
    scopes: Record<ActivityScope, {
      total: number
      counts: WeeklyCounts
    }>
    mergeCommitsExcluded: boolean
  }
  proof: {
    tier: 'device' | 'benchmark' | 'ci'
    kind: string
    label: string
    version: string
    commit: string
    capturedAt: string
    environment: string
    url: string
  }
  receipt: {
    id: string
    issuedAt: string
    rows: Array<{
      id: 'source' | 'lab' | 'history' | 'package'
      label: string
      value: string
      detail: string
      state: string
      url: string
    }>
  }
  devStats: {
    rewriteStartedAt: string
    activeDays: number
    successfulLabRuns: number
    labRuntimeSeconds: number
    mergedPullRequests: number
    medianPullRequestSeconds: number
    scopeCommits: Record<ActivityScope, number>
  }
  pullRequests: Array<{
    number: number
    title: string
    url: string
    createdAt: string
    mergedAt: string
    deliverySeconds: number
    scope: ActivityScope
  }>
  ci: {
    state: 'success' | 'unknown'
    runId: string
    runUrl: string
    passed: number
    total: number
    startedAt?: string
    completedAt?: string
    durationSeconds?: number
  }
  release: {
    available: boolean
    label: string
    tag: string
    url: string
  }
}

export const FALLBACK_PROJECT_STATUS: ProjectStatus = {
  schemaVersion: 1,
  version: '2.0.0-alpha.1',
  experimental: true,
  branch: 'v2-rewrite',
  commit: '79b385131d3628f405ad264a01973c479991fc43',
  shortSha: '79b3851',
  commitMessage: 'docs(release): bind alpha evidence to cfc checkpoint',
  commitUrl: 'https://github.com/BoLayerDev/kanto-first-person/commit/79b385131d3628f405ad264a01973c479991fc43',
  generatedAt: '2026-08-22T11:49:22Z',
  activity: [
    ['79b385131d3628f405ad264a01973c479991fc43', '2026-08-22T05:49:22-06:00', 'docs(release): bind alpha evidence to cfc checkpoint', 'FIELD NOTES'],
    ['cfc045bec72c2ceecd558b24bcd643c8e0b720dc', '2026-08-22T05:20:50-06:00', 'fix(render): canonicalize numeric packet hashes', 'HP RESTORED'],
    ['6682cc4369a4e9536ec7cd243922fc71dcdbad50', '2026-08-22T05:10:27-06:00', 'ci: pin exact LuaJIT sources', 'LAB VERIFIED'],
    ['136d67c4802450e20fb2d64ae024a7af3194a385', '2026-08-22T04:29:43-06:00', 'docs(release): fail closed during evidence refresh', 'FIELD NOTES'],
    ['719acbfe9250062fbe97546df03819d82fa824b2', '2026-08-22T04:24:04-06:00', 'perf(render): cache packet hash frames and layouts', 'SPEED +1'],
    ['d54933db7efc1854ecdf0aa981932d7725ebca1b', '2026-08-22T04:20:09-06:00', 'fix(benchmark): bind production world index', 'HP RESTORED'],
    ['f1939259b5b9b5bc3af8938ab0f54651d5087303', '2026-08-22T04:11:00-06:00', 'perf(world): reuse snapshot index for anchors', 'SPEED +1'],
    ['c5936f96468830cd560243d1746c511b8820e9cc', '2026-08-22T03:59:52-06:00', 'perf(weather): hoist compile invariants', 'SPEED +1'],
  ].map(([sha, date, message, type], index) => ({
    sha,
    shortSha: sha.slice(0, 7),
    message,
    date,
    author: 'Bo Layer',
    type,
    scope: 'mod',
    isMerge: false,
    url: `https://github.com/BoLayerDev/kanto-first-person/commit/${sha}`,
    ...(index === 0 ? {
      ci: {
        runId: '32571329500',
        durationSeconds: 39,
        runUrl: 'https://github.com/BoLayerDev/kanto-first-person/actions/runs/32571329500',
        startedAt: '2026-08-22T11:49:44Z',
        completedAt: '2026-08-22T11:50:23Z',
        passed: 11,
        total: 11,
      },
    } : {}),
  })),
  missions: [
    {
      slot: 'NOW',
      title: 'Continue the verified 2.0 rewrite',
      url: 'https://github.com/BoLayerDev/kanto-first-person/commits/v2-rewrite',
      source: 'roadmap',
      updatedAt: '2026-08-22T11:49:22Z',
    },
    {
      slot: 'NEXT',
      title: 'Complete live device acceptance',
      url: 'https://github.com/BoLayerDev/kanto-first-person/blob/v2-rewrite/docs/device-test-guide.md',
      source: 'roadmap',
      updatedAt: '2026-08-22T11:49:22Z',
    },
    {
      slot: 'BLOCKED',
      title: 'Signed package and compatible Voxel Companion API v1 host release',
      url: 'https://github.com/BoLayerDev/kanto-first-person/blob/v2-rewrite/docs/known-limitations.md',
      source: 'roadmap',
      updatedAt: '2026-08-22T11:49:22Z',
    },
  ],
  releaseJourney: [
    { id: 'rewrite', label: 'REWRITE', state: 'active', summary: 'Alpha source work is active.', url: 'https://github.com/BoLayerDev/kanto-first-person/commits/v2-rewrite' },
    { id: 'host', label: 'HOST READY', state: 'active', summary: 'One released host has static API v1 proof. Live acceptance is open.', url: 'https://github.com/BoLayerDev/kanto-first-person/blob/v2-rewrite/docs/compatibility.md' },
    { id: 'device', label: 'DEVICE TESTED', state: 'pending', summary: 'Live GPU and game acceptance are open.', url: 'https://github.com/BoLayerDev/kanto-first-person/blob/v2-rewrite/docs/device-test-guide.md' },
    { id: 'package', label: 'PACKAGE SIGNED', state: 'pending', summary: 'No signed player package is published.', url: 'https://github.com/BoLayerDev/kanto-first-person/blob/v2-rewrite/docs/release-process.md' },
    { id: 'release', label: 'RELEASED', state: 'pending', summary: 'KFP 2.0 is not released.', url: 'https://github.com/BoLayerDev/kanto-first-person/releases' },
  ],
  weeklyReport: {
    startedAt: '2026-08-15T11:49:22Z',
    endedAt: '2026-08-22T11:49:22Z',
    total: 8,
    counts: { features: 0, fixes: 2, performance: 3, tests: 1, documentation: 2, milestones: 0 },
    scopes: {
      mod: { total: 8, counts: { features: 0, fixes: 2, performance: 3, tests: 1, documentation: 2, milestones: 0 } },
      site: { total: 0, counts: { features: 0, fixes: 0, performance: 0, tests: 0, documentation: 0, milestones: 0 } },
      ops: { total: 0, counts: { features: 0, fixes: 0, performance: 0, tests: 0, documentation: 0, milestones: 0 } },
    },
    mergeCommitsExcluded: true,
  },
  proof: {
    tier: 'benchmark',
    kind: 'BENCHMARK PROOF',
    label: 'ROM-FREE BENCHMARKS PASS',
    version: '2.0.0-alpha.1',
    commit: '79b3851',
    capturedAt: '2026-08-22T06:29:19Z',
    environment: 'GEN1RECOMP v0.2.19',
    url: 'https://github.com/BoLayerDev/kanto-first-person/blob/v2-rewrite/docs/release-evidence/gen1recomp-2026-08-22.json',
  },
  receipt: {
    id: 'OAK-79B3851-32571329500',
    issuedAt: '2026-08-22T11:50:23Z',
    rows: [
      { id: 'source', label: 'SOURCE LOCK', value: 'COMMIT 79B3851', detail: 'V2-REWRITE SOURCE', state: 'VERIFIED', url: 'https://github.com/BoLayerDev/kanto-first-person/commit/79b385131d3628f405ad264a01973c479991fc43' },
      { id: 'lab', label: 'MOD LAB SCAN', value: '11/11 CHECKS PASSED', detail: 'MOD COMMIT CHECKS · 39S', state: 'PASSED', url: 'https://github.com/BoLayerDev/kanto-first-person/actions/runs/32571329500' },
      { id: 'history', label: 'MOD HISTORY', value: '8 VERIFIED COMMITS', detail: '1 ACTIVE FIELD DAY', state: 'TRACKED', url: 'https://github.com/BoLayerDev/kanto-first-person/commits/v2-rewrite' },
      { id: 'package', label: 'PLAYER PACKAGE', value: 'NOT RELEASED', detail: 'RELEASE GATES STILL OPEN', state: 'WAITING', url: 'https://github.com/BoLayerDev/kanto-first-person/releases' },
    ],
  },
  devStats: {
    rewriteStartedAt: '2026-08-21T16:42:07-06:00',
    activeDays: 1,
    successfulLabRuns: 1,
    labRuntimeSeconds: 39,
    mergedPullRequests: 0,
    medianPullRequestSeconds: 0,
    scopeCommits: { mod: 8, site: 0, ops: 0 },
  },
  pullRequests: [],
  ci: {
    state: 'success',
    runId: '32571329500',
    runUrl: 'https://github.com/BoLayerDev/kanto-first-person/actions/runs/32571329500',
    passed: 11,
    total: 11,
    startedAt: '2026-08-22T11:49:44Z',
    completedAt: '2026-08-22T11:50:23Z',
    durationSeconds: 39,
  },
  release: {
    available: false,
    label: 'NOT RELEASED',
    tag: '',
    url: 'https://github.com/BoLayerDev/kanto-first-person/releases',
  },
}

function isProjectStatus(value: unknown): value is ProjectStatus {
  if (!value || typeof value !== 'object') return false
  const candidate = value as Partial<ProjectStatus>
  return candidate.schemaVersion === 1
    && typeof candidate.version === 'string'
    && typeof candidate.shortSha === 'string'
    && typeof candidate.commitUrl === 'string'
    && typeof candidate.generatedAt === 'string'
    && Array.isArray(candidate.activity)
    && candidate.activity.every((entry) => typeof entry.sha === 'string'
      && typeof entry.message === 'string'
      && typeof entry.author === 'string'
      && typeof entry.type === 'string'
      && ['mod', 'site', 'ops'].includes(entry.scope)
      && typeof entry.isMerge === 'boolean'
      && typeof entry.url === 'string'
      && (entry.ci === undefined
        || (typeof entry.ci.durationSeconds === 'number'
          && typeof entry.ci.runUrl === 'string')))
    && (candidate.missions === undefined || (Array.isArray(candidate.missions)
      && candidate.missions.every((mission) => typeof mission.title === 'string'
        && typeof mission.url === 'string'
        && typeof mission.updatedAt === 'string')))
    && (candidate.releaseJourney === undefined || (Array.isArray(candidate.releaseJourney)
      && candidate.releaseJourney.every((gate) => typeof gate.label === 'string'
        && typeof gate.state === 'string'
        && typeof gate.url === 'string')))
    && (candidate.weeklyReport === undefined || (typeof candidate.weeklyReport.total === 'number'
      && typeof candidate.weeklyReport.scopes?.mod?.total === 'number'
      && typeof candidate.weeklyReport.scopes?.site?.total === 'number'
      && typeof candidate.weeklyReport.scopes?.ops?.total === 'number'))
    && (candidate.proof === undefined || (typeof candidate.proof.url === 'string'
      && ['device', 'benchmark', 'ci'].includes(candidate.proof.tier)))
    && (candidate.receipt === undefined || (typeof candidate.receipt.id === 'string'
      && typeof candidate.receipt.issuedAt === 'string'
      && Array.isArray(candidate.receipt.rows)
      && candidate.receipt.rows.length > 0
      && candidate.receipt.rows.every((row) => typeof row.label === 'string'
        && typeof row.value === 'string'
        && typeof row.detail === 'string'
        && typeof row.state === 'string'
        && typeof row.url === 'string')))
    && typeof candidate.devStats?.rewriteStartedAt === 'string'
    && typeof candidate.devStats?.activeDays === 'number'
    && typeof candidate.devStats?.successfulLabRuns === 'number'
    && typeof candidate.devStats?.labRuntimeSeconds === 'number'
    && typeof candidate.devStats?.mergedPullRequests === 'number'
    && typeof candidate.devStats?.medianPullRequestSeconds === 'number'
    && typeof candidate.devStats?.scopeCommits?.mod === 'number'
    && typeof candidate.devStats?.scopeCommits?.site === 'number'
    && typeof candidate.devStats?.scopeCommits?.ops === 'number'
    && Array.isArray(candidate.pullRequests)
    && candidate.pullRequests.every((pull) => typeof pull.number === 'number'
      && typeof pull.title === 'string'
      && typeof pull.url === 'string'
      && typeof pull.createdAt === 'string'
      && typeof pull.mergedAt === 'string'
      && typeof pull.deliverySeconds === 'number'
      && ['mod', 'site', 'ops'].includes(pull.scope))
    && typeof candidate.ci?.runUrl === 'string'
    && typeof candidate.release?.available === 'boolean'
}

function inferredScope(message: string): ActivityScope {
  const scope = message.match(/^[a-z]+\(([^)]+)\):/i)?.[1]?.toLowerCase() || ''
  if (/\b(?:website|site|pages|frontend|ui)\b/.test(scope)) return 'site'
  if (/\b(?:github pages|pages publication|website)\b/i.test(message)) return 'site'
  return 'mod'
}

function normalizeProjectStatus(value: unknown): unknown {
  if (!value || typeof value !== 'object') return value
  const source = value as Record<string, any>
  if (!Array.isArray(source.activity)) return value

  const activity = source.activity.map((entry: Record<string, any>) => {
    const inferred = inferredScope(String(entry.message || ''))
    return {
      ...entry,
      scope: entry.scope === 'site' || inferred === 'site' ? 'site' : 'mod',
      isMerge: entry.isMerge === true || /^Merge pull request\b/i.test(String(entry.message || '')),
    }
  }).filter((entry: Record<string, any>) => entry.scope === 'mod') as ProjectStatus['activity']
  const emptyCounts = (): WeeklyCounts => ({
    features: 0,
    fixes: 0,
    performance: 0,
    tests: 0,
    documentation: 0,
    milestones: 0,
  })
  const scopes: ProjectStatus['weeklyReport']['scopes'] = {
    mod: { total: 0, counts: emptyCounts() },
    site: { total: 0, counts: emptyCounts() },
    ops: { total: 0, counts: emptyCounts() },
  }
  const reportStart = Date.parse(source.weeklyReport?.startedAt || '')
  for (const entry of activity) {
    if (entry.isMerge || (Number.isFinite(reportStart) && Date.parse(entry.date) < reportStart)) continue
    const stream = scopes[entry.scope as ActivityScope]
    stream.total += 1
    const type = String(entry.type || '')
    const category = type === 'NEW MOVE' ? 'features'
      : type === 'HP RESTORED' ? 'fixes'
        : type === 'SPEED +1' ? 'performance'
          : type === 'LAB VERIFIED' ? 'tests'
            : type === 'FIELD NOTES' ? 'documentation'
              : type === 'EVOLVED' ? 'milestones' : null
    if (category) stream.counts[category] += 1
  }
  const scopeCommits = activity.reduce((totals: Record<ActivityScope, number>, entry: ProjectStatus['activity'][number]) => {
    if (!entry.isMerge) totals[entry.scope] += 1
    return totals
  }, { mod: 0, site: 0, ops: 0 })

  return {
    ...source,
    activity,
    missions: Array.isArray(source.missions)
      ? source.missions.map((mission: Record<string, any>) => ({
        ...mission,
        source: mission.source === 'issue' ? 'issue' : 'roadmap',
      }))
      : source.missions,
    weeklyReport: source.weeklyReport ? {
      ...source.weeklyReport,
      total: scopes.mod.total,
      counts: scopes.mod.counts,
      scopes,
      mergeCommitsExcluded: true,
    } : source.weeklyReport,
    proof: source.proof ? {
      ...source.proof,
      tier: ['device', 'benchmark', 'ci'].includes(source.proof.tier) ? source.proof.tier : 'ci',
    } : source.proof,
    devStats: source.devStats ? {
      ...source.devStats,
      scopeCommits: source.devStats.scopeCommits || scopeCommits,
    } : source.devStats,
    pullRequests: Array.isArray(source.pullRequests)
      ? source.pullRequests.map((pull: Record<string, any>) => ({
        ...pull,
        scope: pull.scope === 'site' || inferredScope(String(pull.title || '')) === 'site' ? 'site' : 'mod',
      })).filter((pull: Record<string, any>) => pull.scope === 'mod')
      : source.pullRequests,
  }
}

export function useProjectStatus() {
  const [status, setStatus] = useState(FALLBACK_PROJECT_STATUS)
  const [isLoaded, setIsLoaded] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    let active = true

    fetch(`${import.meta.env.BASE_URL}project-status.json`, {
      cache: 'no-store',
      signal: controller.signal,
    })
      .then((response) => {
        if (!response.ok) throw new Error(`Status request failed: ${response.status}`)
        return response.json()
      })
      .then((value: unknown) => {
        const normalized = normalizeProjectStatus(value)
        if (active && isProjectStatus(normalized)) {
          setStatus({
            ...FALLBACK_PROJECT_STATUS,
            ...normalized,
            missions: normalized.missions ?? FALLBACK_PROJECT_STATUS.missions,
            releaseJourney: normalized.releaseJourney ?? FALLBACK_PROJECT_STATUS.releaseJourney,
            weeklyReport: normalized.weeklyReport ?? FALLBACK_PROJECT_STATUS.weeklyReport,
            proof: normalized.proof ?? FALLBACK_PROJECT_STATUS.proof,
            receipt: normalized.receipt ?? FALLBACK_PROJECT_STATUS.receipt,
          })
        }
      })
      .catch(() => undefined)
      .finally(() => {
        if (active) setIsLoaded(true)
      })

    return () => {
      active = false
      controller.abort()
    }
  }, [])

  return { status, isLoaded }
}
