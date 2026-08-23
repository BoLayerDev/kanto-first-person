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
  const modSha = 'abcdef1234567890abcdef1234567890abcdef12'
  const privateMetricLabel = ['AI', 'token'].join(' ')
  const activity = [
    {
      sha: sourceSha,
      shortSha: '1234567',
      message: `feat(website): Remove ${privateMetricLabel} content`,
      date: '2026-08-22T12:00:00Z',
      author: 'Site Trainer',
      type: 'NEW MOVE',
      url: `https://github.com/BoLayerDev/kanto-first-person/commit/${sourceSha}`,
    },
    {
      sha: modSha,
      shortSha: 'abcdef1',
      message: 'fix(render): canonicalize packet hashes',
      date: '2026-08-22T11:30:00Z',
      author: 'Mod Trainer',
      type: 'HP RESTORED',
      url: `https://github.com/BoLayerDev/kanto-first-person/commit/${modSha}`,
    },
  ]
  const ciRuns = [
    {
      id: 42,
      conclusion: 'success',
      head_sha: sourceSha,
      html_url: 'https://github.com/BoLayerDev/kanto-first-person/actions/runs/42',
      run_started_at: '2026-08-22T11:58:15Z',
      updated_at: '2026-08-22T12:00:00Z',
      passed: 11,
      total: 11,
    },
    {
      id: 41,
      conclusion: 'success',
      head_sha: modSha,
      html_url: 'https://github.com/BoLayerDev/kanto-first-person/actions/runs/41',
      run_started_at: '2026-08-22T11:28:00Z',
      updated_at: '2026-08-22T11:30:00Z',
      passed: 11,
      total: 11,
    },
  ]
  const pullRequests = [
    {
      number: 12,
      title: `fix(website): Remove ${privateMetricLabel} content`,
      html_url: 'https://github.com/BoLayerDev/kanto-first-person/pull/12',
      created_at: '2026-08-22T11:55:00Z',
      merged_at: '2026-08-22T12:00:00Z',
      merge_commit_sha: sourceSha,
    },
    {
      number: 11,
      title: 'fix(render): canonicalize packet hashes',
      html_url: 'https://github.com/BoLayerDev/kanto-first-person/pull/11',
      created_at: '2026-08-22T11:25:00Z',
      merged_at: '2026-08-22T11:30:00Z',
      merge_commit_sha: modSha,
    },
  ]
  const issues = [
    {
      number: 31,
      title: 'Capture live route evidence',
      html_url: 'https://github.com/BoLayerDev/kanto-first-person/issues/31',
      updated_at: '2026-08-22T11:59:00Z',
      labels: [{ name: 'mission:now' }, { name: 'scope:mod' }],
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
        SITE_COMMIT_MESSAGE: `Remove ${privateMetricLabel} content`,
        SITE_DEPLOY_RUN_ID: '84',
        SITE_DEPLOY_RUN_URL: 'https://github.com/BoLayerDev/kanto-first-person/actions/runs/84',
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
    assert.equal(status.commit, modSha)
    assert.equal(status.shortSha, 'abcdef1')
    assert.equal(status.ci.state, 'success')
    assert.deepEqual([status.ci.passed, status.ci.total], [11, 11])
    assert.equal(status.ci.runId, '41')
    assert.equal(status.ci.durationSeconds, 120)
    assert.equal(status.ci.startedAt, '2026-08-22T11:28:00Z')
    assert.deepEqual(status.activity[0].ci, {
      runId: '41',
      durationSeconds: 120,
      runUrl: 'https://github.com/BoLayerDev/kanto-first-person/actions/runs/41',
      startedAt: '2026-08-22T11:28:00Z',
      completedAt: '2026-08-22T11:30:00Z',
      passed: 11,
      total: 11,
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
    assert.equal(status.missions[1].source, 'roadmap')
    assert.equal(status.releaseJourney.length, 5)
    assert.equal(status.releaseJourney[0].state, 'active')
    assert.deepEqual(status.weeklyReport.counts, {
      features: 0,
      fixes: 1,
      performance: 0,
      tests: 0,
      documentation: 0,
      milestones: 0,
    })
    assert.equal(status.weeklyReport.total, 1)
    assert.deepEqual(status.weeklyReport.scopes, {
      mod: { total: 1, counts: { features: 0, fixes: 1, performance: 0, tests: 0, documentation: 0, milestones: 0 } },
      site: { total: 0, counts: { features: 0, fixes: 0, performance: 0, tests: 0, documentation: 0, milestones: 0 } },
      ops: { total: 0, counts: { features: 0, fixes: 0, performance: 0, tests: 0, documentation: 0, milestones: 0 } },
    })
    assert.equal(status.weeklyReport.mergeCommitsExcluded, true)
    assert.deepEqual(status.proof, {
      tier: 'benchmark',
      kind: 'BENCHMARK PROOF',
      label: 'ROM-FREE BENCHMARKS PASS',
      version: '2.0.0-alpha.1',
      commit: 'abcdef1',
      capturedAt: '2026-08-22T06:29:19Z',
      environment: 'GEN1RECOMP v0.2.19',
      url: 'https://github.com/BoLayerDev/kanto-first-person/blob/v2-rewrite/docs/release-evidence/gen1recomp-2026-08-22.json',
    })
    assert.equal(status.receipt.id, 'OAK-ABCDEF1-41')
    assert.equal(status.receipt.issuedAt, '2026-08-22T11:30:00Z')
    assert.deepEqual(status.receipt.rows.map((row) => row.id), ['source', 'lab', 'history', 'package'])
    assert.deepEqual(status.receipt.rows.map((row) => row.state), ['VERIFIED', 'PASSED', 'TRACKED', 'WAITING'])
    assert.equal(status.receipt.rows[0].url, `https://github.com/BoLayerDev/kanto-first-person/commit/${modSha}`)
    assert.equal(status.receipt.rows[1].url, 'https://github.com/BoLayerDev/kanto-first-person/actions/runs/41')
    assert.equal(status.receipt.rows[2].url, 'https://github.com/BoLayerDev/kanto-first-person/commits/v2-rewrite')
    assert.equal(status.receipt.rows[3].url, 'https://github.com/BoLayerDev/kanto-first-person/releases')
    assert.equal(status.commitMessage, 'fix(render): canonicalize packet hashes')
    assert.deepEqual(status.activity[0], {
      ...activity[1],
      scope: 'mod',
      isMerge: false,
      ci: status.activity[0].ci,
    })
    assert.equal(status.activity.length, 1)
    assert.deepEqual(status.devStats, {
      rewriteStartedAt: '',
      activeDays: 1,
      successfulLabRuns: 1,
      labRuntimeSeconds: 120,
      mergedPullRequests: 1,
      medianPullRequestSeconds: 300,
      scopeCommits: { mod: 1, site: 0, ops: 0 },
    })
    assert.deepEqual(status.pullRequests[0], {
      number: 11,
      title: 'fix(render): canonicalize packet hashes',
      url: 'https://github.com/BoLayerDev/kanto-first-person/pull/11',
      createdAt: '2026-08-22T11:25:00Z',
      mergedAt: '2026-08-22T11:30:00Z',
      deliverySeconds: 300,
      scope: 'mod',
    })
    assert.equal(status.pullRequests.length, 1)
    assert.doesNotMatch(JSON.stringify(status), new RegExp(privateMetricLabel, 'i'))
    assert.match(status.commitUrl, new RegExp(modSha))
    assert.doesNotMatch(JSON.stringify(status), /feat\(website\)/i)

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
