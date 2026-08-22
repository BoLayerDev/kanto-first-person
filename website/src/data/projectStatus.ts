import { useEffect, useState } from 'react'

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
    url: string
    ci?: {
      durationSeconds: number
      runUrl: string
    }
  }>
  missions: Array<{
    slot: 'NOW' | 'NEXT' | 'BLOCKED'
    title: string
    url: string
    source: 'issue' | 'github'
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
    counts: {
      features: number
      fixes: number
      performance: number
      tests: number
      documentation: number
      milestones: number
    }
  }
  proof: {
    kind: string
    label: string
    version: string
    commit: string
    capturedAt: string
    environment: string
    url: string
  }
  devStats: {
    rewriteStartedAt: string
    activeDays: number
    successfulLabRuns: number
    labRuntimeSeconds: number
    mergedPullRequests: number
    medianPullRequestSeconds: number
    aiUsage: {
      state: 'available' | 'unavailable'
      label: string
      note: string
      totalTokens?: number
      taskCount?: number
    }
  }
  pullRequests: Array<{
    number: number
    title: string
    url: string
    createdAt: string
    mergedAt: string
    deliverySeconds: number
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
    url: `https://github.com/BoLayerDev/kanto-first-person/commit/${sha}`,
    ...(index === 0 ? {
      ci: {
        durationSeconds: 39,
        runUrl: 'https://github.com/BoLayerDev/kanto-first-person/actions/runs/32571329500',
      },
    } : {}),
  })),
  missions: [
    {
      slot: 'NOW',
      title: 'Continue the verified 2.0 rewrite',
      url: 'https://github.com/BoLayerDev/kanto-first-person/commits/v2-rewrite',
      source: 'github',
      updatedAt: '2026-08-22T11:49:22Z',
    },
    {
      slot: 'NEXT',
      title: 'Complete live device acceptance',
      url: 'https://github.com/BoLayerDev/kanto-first-person/blob/v2-rewrite/docs/device-test-guide.md',
      source: 'github',
      updatedAt: '2026-08-22T11:49:22Z',
    },
    {
      slot: 'BLOCKED',
      title: 'Signed package and compatible Voxel Companion API v1 host release',
      url: 'https://github.com/BoLayerDev/kanto-first-person/blob/v2-rewrite/docs/known-limitations.md',
      source: 'github',
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
  },
  proof: {
    kind: 'CI RUN',
    label: '11/11 CHECKS PASSED',
    version: '2.0.0-alpha.1',
    commit: '79b3851',
    capturedAt: '2026-08-22T11:50:23Z',
    environment: 'GITHUB ACTIONS',
    url: 'https://github.com/BoLayerDev/kanto-first-person/actions/runs/32571329500',
  },
  devStats: {
    rewriteStartedAt: '2026-08-21T16:42:07-06:00',
    activeDays: 2,
    successfulLabRuns: 39,
    labRuntimeSeconds: 1611,
    mergedPullRequests: 11,
    medianPullRequestSeconds: 59,
    aiUsage: {
      state: 'unavailable',
      label: 'NOT TRACKED',
      note: 'Codex task token usage is private and is not exported to this public GitHub site.',
    },
  },
  pullRequests: [
    {
      number: 11,
      title: 'feat(website): add automatic Trainer Clock',
      url: 'https://github.com/BoLayerDev/kanto-first-person/pull/11',
      createdAt: '2026-08-22T20:22:56Z',
      mergedAt: '2026-08-22T20:25:58Z',
      deliverySeconds: 182,
    },
    {
      number: 10,
      title: 'fix(website): show verified rewrite start date',
      url: 'https://github.com/BoLayerDev/kanto-first-person/pull/10',
      createdAt: '2026-08-22T20:08:09Z',
      mergedAt: '2026-08-22T20:08:57Z',
      deliverySeconds: 48,
    },
  ],
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
    && (candidate.weeklyReport === undefined || typeof candidate.weeklyReport.total === 'number')
    && (candidate.proof === undefined || typeof candidate.proof.url === 'string')
    && typeof candidate.devStats?.rewriteStartedAt === 'string'
    && typeof candidate.devStats?.activeDays === 'number'
    && typeof candidate.devStats?.successfulLabRuns === 'number'
    && typeof candidate.devStats?.labRuntimeSeconds === 'number'
    && typeof candidate.devStats?.mergedPullRequests === 'number'
    && typeof candidate.devStats?.medianPullRequestSeconds === 'number'
    && typeof candidate.devStats?.aiUsage?.state === 'string'
    && Array.isArray(candidate.pullRequests)
    && candidate.pullRequests.every((pull) => typeof pull.number === 'number'
      && typeof pull.title === 'string'
      && typeof pull.url === 'string'
      && typeof pull.createdAt === 'string'
      && typeof pull.mergedAt === 'string'
      && typeof pull.deliverySeconds === 'number')
    && typeof candidate.ci?.runUrl === 'string'
    && typeof candidate.release?.available === 'boolean'
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
        if (active && isProjectStatus(value)) {
          setStatus({ ...FALLBACK_PROJECT_STATUS, ...value })
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
