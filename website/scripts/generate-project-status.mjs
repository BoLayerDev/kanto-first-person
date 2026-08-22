import { execFileSync } from 'node:child_process'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
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
  aiUsage: {
    state: 'unavailable',
    label: 'LOCKED',
    note: 'GitHub does not receive trusted Codex task token totals.',
  },
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
