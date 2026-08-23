import { execFileSync } from 'node:child_process'
import { mkdir, readFile, readdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url))
const repositoryRoot = path.resolve(scriptDirectory, '..', '..')
const outputPath = path.resolve(
  repositoryRoot,
  process.env.SITE_STATUS_OUTPUT || 'website/public/project-status.json',
)
const manifest = JSON.parse(await readFile(path.join(repositoryRoot, 'manifest.json'), 'utf8'))

function git(...args) {
  try {
    return execFileSync('git', args, {
      cwd: repositoryRoot,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    }).trim()
  } catch {
    return ''
  }
}

function clean(value, fallback = '') {
  return typeof value === 'string' && value.trim() ? value.trim() : fallback
}

function elapsedSeconds(startedAt, completedAt) {
  const started = Date.parse(startedAt)
  const completed = Date.parse(completedAt)
  if (!Number.isFinite(started) || !Number.isFinite(completed) || completed < started) return 0
  return Math.max(1, Math.round((completed - started) / 1000))
}

function activityType(message) {
  const prefix = message.match(/^([a-z]+)(?:\([^)]+\))?:/i)?.[1]?.toLowerCase()
  if (prefix === 'feat') return 'NEW MOVE'
  if (prefix === 'fix') return 'HP RESTORED'
  if (prefix === 'perf') return 'SPEED +1'
  if (prefix === 'ci' || prefix === 'test') return 'LAB VERIFIED'
  if (prefix === 'docs') return 'FIELD NOTES'
  if (prefix === 'refactor') return 'EVOLVED'
  return 'RESEARCH UPDATE'
}

const repository = clean(process.env.SITE_REPOSITORY, manifest.github)
const branch = clean(process.env.SITE_SOURCE_BRANCH, git('branch', '--show-current') || 'v2-rewrite')
const commit = clean(process.env.SITE_SOURCE_SHA, git('rev-parse', 'HEAD'))
const shortSha = commit ? commit.slice(0, 7) : 'UNKNOWN'
const commitMessage = clean(
  process.env.SITE_COMMIT_MESSAGE,
  git('show', '-s', '--format=%s', commit || 'HEAD') || 'Source status unavailable',
)
const repositoryUrl = `https://github.com/${repository}`
const token = clean(process.env.GITHUB_TOKEN)
const activityOverride = clean(process.env.SITE_ACTIVITY_JSON)
let activity = []

if (activityOverride) {
  try {
    activity = JSON.parse(activityOverride)
  } catch {
    activity = []
  }
} else {
  const records = git('log', '--format=%H%x1f%cI%x1f%an%x1f%s', commit || 'HEAD').split('\n').filter(Boolean)
  activity = records.map((record) => {
    const [sha, date, author, message] = record.split('\x1f')
    return {
      sha,
      shortSha: sha.slice(0, 7),
      message,
      date,
      author,
      type: activityType(message),
      url: `${repositoryUrl}/commit/${sha}`,
    }
  })
}

async function github(pathname) {
  if (!token) return null

  try {
    const response = await fetch(`https://api.github.com/repos/${repository}${pathname}`, {
      headers: {
        Accept: 'application/vnd.github+json',
        Authorization: `Bearer ${token}`,
        'User-Agent': 'kanto-field-terminal-status-generator',
        'X-GitHub-Api-Version': '2022-11-28',
      },
    })
    if (!response.ok) return null
    return response.json()
  } catch {
    return null
  }
}

async function githubPages(pathname, collectionKey, maxPages = 10) {
  const records = []
  const separator = pathname.includes('?') ? '&' : '?'

  for (let page = 1; page <= maxPages; page += 1) {
    const result = await github(`${pathname}${separator}per_page=100&page=${page}`)
    const batch = collectionKey ? result?.[collectionKey] : result
    if (!Array.isArray(batch)) break
    records.push(...batch)
    if (batch.length < 100) break
  }

  return records
}

function parseJsonArray(value) {
  if (!value) return null
  try {
    const parsed = JSON.parse(value)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function median(values) {
  if (!values.length) return 0
  const sorted = [...values].sort((left, right) => left - right)
  const middle = Math.floor(sorted.length / 2)
  return sorted.length % 2
    ? sorted[middle]
    : Math.round((sorted[middle - 1] + sorted[middle]) / 2)
}

let ciRunId = clean(process.env.SITE_CI_RUN_ID)
let ciRunUrl = clean(process.env.SITE_CI_RUN_URL)
let ciConclusion = clean(process.env.SITE_CI_CONCLUSION)
let ciHeadSha = clean(process.env.SITE_CI_HEAD_SHA)
let ciStartedAt = clean(process.env.SITE_CI_STARTED_AT)
let ciCompletedAt = clean(process.env.SITE_CI_COMPLETED_AT)
let generatedAt = clean(process.env.SITE_GENERATED_AT, new Date().toISOString())
const ciRunsOverride = parseJsonArray(clean(process.env.SITE_CI_RUNS_JSON))
const completedCiRuns = ciRunsOverride ?? (token
  ? await githubPages(
    `/actions/workflows/ci.yml/runs?branch=${encodeURIComponent(branch)}&status=completed`,
    'workflow_runs',
  )
  : [])

if (!ciRunId && token) {
  const run = completedCiRuns.find((item) => item.conclusion === 'success')
  if (run) {
    ciRunId = String(run.id)
    ciRunUrl = run.html_url
    ciConclusion = run.conclusion
    ciHeadSha = run.head_sha
  }
}

let ciRunDetails = null
if (ciRunId && token) {
  ciRunDetails = await github(`/actions/runs/${encodeURIComponent(ciRunId)}`)
  ciStartedAt = clean(ciStartedAt, ciRunDetails?.run_started_at)
  ciCompletedAt = clean(ciCompletedAt, ciRunDetails?.updated_at)
}

let passed = Number.parseInt(clean(process.env.SITE_CI_PASSED, '0'), 10) || 0
let total = Number.parseInt(clean(process.env.SITE_CI_TOTAL, '0'), 10) || 0

if (ciRunId && token && (!passed || !total)) {
  const result = await github(`/actions/runs/${encodeURIComponent(ciRunId)}/jobs?per_page=100`)
  const jobs = Array.isArray(result?.jobs) ? result.jobs : []
  total = jobs.length
  passed = jobs.filter((job) => job.conclusion === 'success').length
}

const ciDurationSeconds = elapsedSeconds(ciStartedAt, ciCompletedAt)

if (completedCiRuns.length) {
  const successfulRuns = new Map()

  for (const run of completedCiRuns) {
    if (run.conclusion !== 'success' || !run.head_sha || successfulRuns.has(run.head_sha)) continue
    const durationSeconds = elapsedSeconds(run.run_started_at, run.updated_at)
    if (!durationSeconds) continue
    successfulRuns.set(run.head_sha, {
      durationSeconds,
      runUrl: run.html_url,
    })
  }

  if (ciHeadSha === commit && ciDurationSeconds && !successfulRuns.has(commit)) {
    successfulRuns.set(commit, {
      durationSeconds: ciDurationSeconds,
      runUrl: ciRunUrl,
    })
  }

  activity = activity.map((entry) => {
    const run = successfulRuns.get(entry.sha)
    return run ? { ...entry, ci: run } : entry
  })
} else if (ciHeadSha === commit && ciDurationSeconds) {
  activity = activity.map((entry) => entry.sha === commit
    ? { ...entry, ci: { durationSeconds: ciDurationSeconds, runUrl: ciRunUrl } }
    : entry)
}

const pullsOverride = parseJsonArray(clean(process.env.SITE_PULL_REQUESTS_JSON))
const pullRecords = pullsOverride ?? (token
  ? await githubPages(`/pulls?state=closed&base=${encodeURIComponent(branch)}`, '')
  : [])
const pullRequests = pullRecords
  .filter((pull) => pull.merged_at && pull.created_at)
  .map((pull) => ({
    number: Number(pull.number),
    title: clean(pull.title, `Pull request #${pull.number}`),
    url: clean(pull.html_url, `${repositoryUrl}/pull/${pull.number}`),
    createdAt: pull.created_at,
    mergedAt: pull.merged_at,
    deliverySeconds: elapsedSeconds(pull.created_at, pull.merged_at),
  }))
  .filter((pull) => Number.isFinite(pull.number) && pull.deliverySeconds > 0)
  .sort((left, right) => Date.parse(right.mergedAt) - Date.parse(left.mergedAt))

const issuesOverride = parseJsonArray(clean(process.env.SITE_ISSUES_JSON))
const issueRecords = issuesOverride ?? (token
  ? await githubPages('/issues?state=open', '')
  : [])
const openIssues = issueRecords.filter((issue) => !issue.pull_request)

function issueLabels(issue) {
  return (Array.isArray(issue.labels) ? issue.labels : [])
    .map((label) => clean(typeof label === 'string' ? label : label?.name).toLowerCase())
}

function issueForSlot(slot) {
  const expected = `status:${slot.toLowerCase()}`
  return openIssues
    .filter((issue) => issueLabels(issue).some((label) => label.replace(/\s+/g, '') === expected))
    .sort((left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at))[0]
}

function mission(slot, fallbackTitle, fallbackUrl) {
  const issue = issueForSlot(slot)
  return issue ? {
    slot,
    title: clean(issue.title, `GitHub issue #${issue.number}`),
    url: clean(issue.html_url, `${repositoryUrl}/issues/${issue.number}`),
    source: 'issue',
    updatedAt: clean(issue.updated_at, generatedAt),
  } : {
    slot,
    title: fallbackTitle,
    url: fallbackUrl,
    source: 'github',
    updatedAt: generatedAt,
  }
}

const rewriteStartSha = '0f453187210d3d388a02196affee413994df1a77'
const rewriteStartIndex = activity.findIndex((entry) => entry.sha === rewriteStartSha)
const rewriteActivity = rewriteStartIndex >= 0 ? activity.slice(0, rewriteStartIndex + 1) : activity
const rewriteStartedAt = rewriteStartIndex >= 0 ? activity[rewriteStartIndex].date : ''
const successfulCiRuns = completedCiRuns.filter((run) => run.conclusion === 'success')
const labRuntimeSeconds = successfulCiRuns.reduce(
  (totalSeconds, run) => totalSeconds + elapsedSeconds(run.run_started_at, run.updated_at),
  0,
)
const deliveryTimes = pullRequests.map((pull) => pull.deliverySeconds)
const devStats = {
  rewriteStartedAt,
  activeDays: new Set(rewriteActivity.map((entry) => entry.date.slice(0, 10))).size,
  successfulLabRuns: successfulCiRuns.length,
  labRuntimeSeconds,
  mergedPullRequests: pullRequests.length,
  medianPullRequestSeconds: median(deliveryTimes),
}

if (process.env.SITE_REQUIRE_VERIFIED_CI === 'true') {
  const verified = ciConclusion === 'success'
    && ciRunId
    && ciHeadSha === commit
    && total > 0
    && passed === total
  if (!verified) {
    throw new Error('Refusing to generate a deployable status: the checked-out source is not fully verified by CI.')
  }
}

let release = {
  available: false,
  label: 'NOT RELEASED',
  tag: '',
  url: `${repositoryUrl}/releases`,
}

if (token) {
  const releases = await github('/releases?per_page=100')
  const current = Array.isArray(releases)
    ? releases.find((item) => !item.draft && /^v?2(?:\.|$)/i.test(item.tag_name || ''))
    : null
  const packageAsset = current?.assets?.find((asset) => /\.modpkg$/i.test(asset.name || ''))
  if (current && packageAsset) {
    release = {
      available: true,
      label: current.tag_name,
      tag: current.tag_name,
      url: packageAsset.browser_download_url || current.html_url,
    }
  }
}

let hostEvidence = {}
let hostEvidenceName = ''
try {
  const evidenceDirectory = path.join(repositoryRoot, 'docs', 'release-evidence')
  const evidenceNames = (await readdir(evidenceDirectory))
    .filter((name) => /^host-release-delta-\d{4}-\d{2}-\d{2}(?:-[a-z0-9-]+)?\.json$/i.test(name))
  const evidenceRecords = await Promise.all(evidenceNames.map(async (name) => {
    try {
      return { name, value: JSON.parse(await readFile(path.join(evidenceDirectory, name), 'utf8')) }
    } catch {
      return null
    }
  }))
  const newestEvidence = evidenceRecords
    .filter(Boolean)
    .sort((left, right) => Date.parse(right.value.observed_at || '') - Date.parse(left.value.observed_at || ''))[0]
  hostEvidence = newestEvidence?.value ?? {}
  hostEvidenceName = newestEvidence?.name ?? ''
} catch {
  hostEvidence = {}
}

const hostDecision = hostEvidence?.decision ?? {}
const hostEvidenceUrl = hostEvidenceName
  ? `${repositoryUrl}/blob/${branch}/docs/release-evidence/${hostEvidenceName}`
  : `${repositoryUrl}/blob/${branch}/docs/compatibility.md`
const deviceEvidenceUrl = `${repositoryUrl}/blob/${branch}/docs/device-test-guide.md`
const releaseProcessUrl = `${repositoryUrl}/blob/${branch}/docs/release-process.md`
const compatibleHostReady = hostDecision.released_hosts === true
const compatibleHostProgress = hostDecision.battle_art_owner_release_evidence_exists === true
const deviceTested = hostDecision.live_visual_acceptance === true
const packageSigned = hostDecision.signed_tag === true

const missions = [
  mission(
    'NOW',
    activity[0] ? `Verify: ${activity[0].message}` : 'Continue the verified 2.0 rewrite',
    activity[0]?.url || `${repositoryUrl}/commits/${branch}`,
  ),
  mission(
    'NEXT',
    deviceTested ? 'Prepare the signed KFP player package' : 'Complete live device acceptance',
    deviceTested ? releaseProcessUrl : deviceEvidenceUrl,
  ),
  mission(
    'BLOCKED',
    release.available
      ? 'No verified release blocker is recorded'
      : 'Live acceptance and a signed KFP package are still required',
    release.available ? release.url : `${repositoryUrl}/blob/${branch}/docs/known-limitations.md`,
  ),
]

const releaseJourney = [
  {
    id: 'rewrite',
    label: 'REWRITE',
    state: release.available ? 'complete' : 'active',
    summary: release.available ? 'The 2.0 rewrite is released.' : 'The 2.0 alpha source rewrite is active.',
    url: `${repositoryUrl}/commits/${branch}`,
  },
  {
    id: 'host',
    label: 'HOST READY',
    state: compatibleHostReady ? 'complete' : (compatibleHostProgress ? 'active' : 'blocked'),
    summary: compatibleHostReady
      ? 'A compatible released host is verified.'
      : (compatibleHostProgress
        ? 'Battle Art release proof exists. Live acceptance is still open.'
        : 'A compatible released Voxel Companion API v1 host is required.'),
    url: hostEvidenceUrl,
  },
  {
    id: 'device',
    label: 'DEVICE TESTED',
    state: deviceTested ? 'complete' : 'pending',
    summary: deviceTested ? 'Live device acceptance is verified.' : 'Live GPU and in-game acceptance are open.',
    url: deviceEvidenceUrl,
  },
  {
    id: 'package',
    label: 'PACKAGE SIGNED',
    state: packageSigned ? 'complete' : 'pending',
    summary: packageSigned ? 'The release tag is signed.' : 'No signed player package is published.',
    url: releaseProcessUrl,
  },
  {
    id: 'release',
    label: 'RELEASED',
    state: release.available ? 'complete' : 'pending',
    summary: release.available ? `${release.label} is available.` : 'KFP 2.0 is not released.',
    url: release.url,
  },
]

function activityCategory(entry) {
  if (entry.type === 'NEW MOVE') return 'features'
  if (entry.type === 'HP RESTORED') return 'fixes'
  if (entry.type === 'SPEED +1') return 'performance'
  if (entry.type === 'LAB VERIFIED') return 'tests'
  if (entry.type === 'EVOLVED'
    || /^[a-z]+\((release|device|compat|architecture)\):/i.test(entry.message)
    || /^release:/i.test(entry.message)) return 'milestones'
  if (entry.type === 'FIELD NOTES') return 'documentation'
  return ''
}

const reportEnd = Date.parse(generatedAt)
const reportStart = Number.isFinite(reportEnd) ? reportEnd - (7 * 24 * 60 * 60 * 1000) : 0
const weeklyActivity = activity.filter((entry) => Date.parse(entry.date) >= reportStart)
const weeklyCounts = {
  features: 0,
  fixes: 0,
  performance: 0,
  tests: 0,
  documentation: 0,
  milestones: 0,
}
for (const entry of weeklyActivity) {
  const category = activityCategory(entry)
  if (category) weeklyCounts[category] += 1
}

const weeklyReport = {
  startedAt: new Date(reportStart).toISOString(),
  endedAt: generatedAt,
  total: weeklyActivity.length,
  counts: weeklyCounts,
}

const proof = {
  kind: 'CI RUN',
  label: ciConclusion === 'success' && total > 0 ? `${passed}/${total} CHECKS PASSED` : 'CHECK CI EVIDENCE',
  version: clean(manifest.version, 'UNKNOWN'),
  commit: shortSha,
  capturedAt: clean(ciCompletedAt, generatedAt),
  environment: 'GITHUB ACTIONS',
  url: ciRunUrl || `${repositoryUrl}/actions/workflows/ci.yml`,
}

const status = {
  schemaVersion: 1,
  version: clean(manifest.version, 'UNKNOWN'),
  experimental: manifest.experimental === true,
  branch,
  commit,
  shortSha,
  commitMessage,
  commitUrl: commit ? `${repositoryUrl}/commit/${commit}` : repositoryUrl,
  generatedAt,
  activity,
  missions,
  releaseJourney,
  weeklyReport,
  proof,
  devStats,
  pullRequests,
  ci: {
    state: ciConclusion === 'success' ? 'success' : 'unknown',
    runId: ciRunId,
    runUrl: ciRunUrl || `${repositoryUrl}/actions/workflows/ci.yml`,
    passed,
    total,
    startedAt: ciStartedAt,
    completedAt: ciCompletedAt,
    durationSeconds: ciDurationSeconds,
  },
  release,
}

await mkdir(path.dirname(outputPath), { recursive: true })
await writeFile(outputPath, `${JSON.stringify(status, null, 2)}\n`, 'utf8')
console.log(`Generated ${path.relative(repositoryRoot, outputPath)} for ${shortSha}.`)
