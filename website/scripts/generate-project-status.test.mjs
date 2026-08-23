import assert from 'node:assert/strict'
import { mkdtemp, readFile, rm } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import { spawnSync } from 'node:child_process'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url))
const generator = path.join(scriptDirectory, 'generate-project-status.mjs')

test('generates a complete offline GitHub status snapshot', async () => {
  const temporaryDirectory = await mkdtemp(path.join(os.tmpdir(), 'kfp-status-'))
  const outputPath = path.join(temporaryDirectory, 'project-status.json')
  const sourceSha = '1234567890abcdef1234567890abcdef12345678'
  const activity = [{
    sha: sourceSha,
    shortSha: '1234567',
    message: 'feat(world): Open a new route',
    date: '2026-08-22T12:00:00Z',
    author: 'Test Trainer',
    type: 'NEW MOVE',
    url: `https://github.com/BoLayerDev/kanto-first-person/commit/${sourceSha}`,
  }]
  const ciRuns = [{
    id: 42,
    conclusion: 'success',
    head_sha: sourceSha,
    html_url: 'https://github.com/BoLayerDev/kanto-first-person/actions/runs/42',
    run_started_at: '2026-08-22T11:58:15Z',
    updated_at: '2026-08-22T12:00:00Z',
  }]
  const pullRequests = [{
    number: 12,
    title: 'feat(website): Add verified dev stats',
    html_url: 'https://github.com/BoLayerDev/kanto-first-person/pull/12',
    created_at: '2026-08-22T11:55:00Z',
    merged_at: '2026-08-22T12:00:00Z',
  }]
  const issues = [
    {
      number: 31,
      title: 'Capture live route evidence',
      html_url: 'https://github.com/BoLayerDev/kanto-first-person/issues/31',
      updated_at: '2026-08-22T11:59:00Z',
      labels: [{ name: 'status:now' }],
    },
  ]

  try {
    const result = spawnSync(process.execPath, [generator], {
      encoding: 'utf8',
      env: {
        ...process.env,
        GITHUB_TOKEN: '',
        SITE_CI_CONCLUSION: 'success',
        SITE_CI_HEAD_SHA: sourceSha,
        SITE_CI_STARTED_AT: '2026-08-22T11:58:15Z',
        SITE_CI_COMPLETED_AT: '2026-08-22T12:00:00Z',
        SITE_CI_PASSED: '11',
        SITE_CI_RUN_ID: '42',
        SITE_CI_RUN_URL: 'https://github.com/BoLayerDev/kanto-first-person/actions/runs/42',
        SITE_CI_TOTAL: '11',
        SITE_COMMIT_MESSAGE: 'Test source state',
        SITE_GENERATED_AT: '2026-08-22T12:00:00Z',
        SITE_ISSUES_JSON: JSON.stringify(issues),
        SITE_REPOSITORY: 'BoLayerDev/kanto-first-person',
        SITE_REQUIRE_VERIFIED_CI: 'true',
        SITE_ACTIVITY_JSON: JSON.stringify(activity),
        SITE_CI_RUNS_JSON: JSON.stringify(ciRuns),
        SITE_PULL_REQUESTS_JSON: JSON.stringify(pullRequests),
        SITE_SOURCE_BRANCH: 'v2-rewrite',
        SITE_SOURCE_SHA: sourceSha,
        SITE_STATUS_OUTPUT: outputPath,
      },
    })

    assert.equal(result.status, 0, result.stderr)
    const status = JSON.parse(await readFile(outputPath, 'utf8'))
    assert.equal(status.schemaVersion, 1)
    assert.equal(status.version, '2.0.0-alpha.1')
    assert.equal(status.branch, 'v2-rewrite')
    assert.equal(status.commit, sourceSha)
    assert.equal(status.shortSha, '1234567')
    assert.equal(status.ci.state, 'success')
    assert.deepEqual([status.ci.passed, status.ci.total], [11, 11])
    assert.equal(status.ci.durationSeconds, 105)
    assert.equal(status.ci.startedAt, '2026-08-22T11:58:15Z')
    assert.deepEqual(status.activity[0].ci, {
      durationSeconds: 105,
      runUrl: 'https://github.com/BoLayerDev/kanto-first-person/actions/runs/42',
    })
    assert.equal(status.release.available, false)
    assert.deepEqual(status.missions[0], {
      slot: 'NOW',
      title: 'Capture live route evidence',
      url: 'https://github.com/BoLayerDev/kanto-first-person/issues/31',
      source: 'issue',
      updatedAt: '2026-08-22T11:59:00Z',
    })
    assert.equal(status.missions[1].slot, 'NEXT')
    assert.equal(status.missions[1].source, 'github')
    assert.equal(status.releaseJourney.length, 5)
    assert.equal(status.releaseJourney[0].state, 'active')
    assert.deepEqual(status.weeklyReport.counts, {
      features: 1,
      fixes: 0,
      performance: 0,
      tests: 0,
      documentation: 0,
      milestones: 0,
    })
    assert.equal(status.weeklyReport.total, 1)
    assert.deepEqual(status.proof, {
      kind: 'CI RUN',
      label: '11/11 CHECKS PASSED',
      version: '2.0.0-alpha.1',
      commit: '1234567',
      capturedAt: '2026-08-22T12:00:00Z',
      environment: 'GITHUB ACTIONS',
      url: 'https://github.com/BoLayerDev/kanto-first-person/actions/runs/42',
    })
    assert.deepEqual(status.activity[0], { ...activity[0], ci: status.activity[0].ci })
    assert.deepEqual(status.devStats, {
      rewriteStartedAt: '',
      activeDays: 1,
      successfulLabRuns: 1,
      labRuntimeSeconds: 105,
      mergedPullRequests: 1,
      medianPullRequestSeconds: 300,
    })
    assert.deepEqual(status.pullRequests[0], {
      number: 12,
      title: 'feat(website): Add verified dev stats',
      url: 'https://github.com/BoLayerDev/kanto-first-person/pull/12',
      createdAt: '2026-08-22T11:55:00Z',
      mergedAt: '2026-08-22T12:00:00Z',
      deliverySeconds: 300,
    })
    assert.match(status.commitUrl, new RegExp(sourceSha))

    const rejected = spawnSync(process.execPath, [generator], {
      encoding: 'utf8',
      env: {
        ...process.env,
        GITHUB_TOKEN: '',
        SITE_CI_CONCLUSION: 'success',
        SITE_CI_HEAD_SHA: '0000000000000000000000000000000000000000',
        SITE_CI_PASSED: '11',
        SITE_CI_RUN_ID: '42',
        SITE_CI_TOTAL: '11',
        SITE_REQUIRE_VERIFIED_CI: 'true',
        SITE_SOURCE_SHA: sourceSha,
        SITE_STATUS_OUTPUT: outputPath,
      },
    })
    assert.notEqual(rejected.status, 0)
    assert.match(rejected.stderr, /not fully verified by CI/)
  } finally {
    await rm(temporaryDirectory, { recursive: true, force: true })
  }
})
