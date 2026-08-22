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
  const records = git('log', '-8', '--format=%H%x1f%cI%x1f%s').split('\n').filter(Boolean)
  activity = records.map((record) => {
    const [sha, date, message] = record.split('\x1f')
    return {
      sha,
      shortSha: sha.slice(0, 7),
      message,
      date,
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

let ciRunId = clean(process.env.SITE_CI_RUN_ID)
let ciRunUrl = clean(process.env.SITE_CI_RUN_URL)
let ciConclusion = clean(process.env.SITE_CI_CONCLUSION)
let ciHeadSha = clean(process.env.SITE_CI_HEAD_SHA)
let generatedAt = clean(process.env.SITE_GENERATED_AT, new Date().toISOString())

if (!ciRunId && token) {
  const runs = await github(
    `/actions/workflows/ci.yml/runs?branch=${encodeURIComponent(branch)}&status=success&per_page=1`,
  )
  const run = runs?.workflow_runs?.[0]
  if (run) {
    ciRunId = String(run.id)
    ciRunUrl = run.html_url
    ciConclusion = run.conclusion
    ciHeadSha = run.head_sha
  }
}

let passed = Number.parseInt(clean(process.env.SITE_CI_PASSED, '0'), 10) || 0
let total = Number.parseInt(clean(process.env.SITE_CI_TOTAL, '0'), 10) || 0

if (ciRunId && token && (!passed || !total)) {
  const result = await github(`/actions/runs/${encodeURIComponent(ciRunId)}/jobs?per_page=100`)
  const jobs = Array.isArray(result?.jobs) ? result.jobs : []
  total = jobs.length
  passed = jobs.filter((job) => job.conclusion === 'success').length
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
  ci: {
    state: ciConclusion === 'success' ? 'success' : 'unknown',
    runId: ciRunId,
    runUrl: ciRunUrl || `${repositoryUrl}/actions/workflows/ci.yml`,
    passed,
    total,
  },
  release,
}

await mkdir(path.dirname(outputPath), { recursive: true })
await writeFile(outputPath, `${JSON.stringify(status, null, 2)}\n`, 'utf8')
console.log(`Generated ${path.relative(repositoryRoot, outputPath)} for ${shortSha}.`)
