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
    type: 'NEW MOVE',
    url: `https://github.com/BoLayerDev/kanto-first-person/commit/${sourceSha}`,
  }]

  try {
    const result = spawnSync(process.execPath, [generator], {
      encoding: 'utf8',
      env: {
        ...process.env,
        GITHUB_TOKEN: '',
        SITE_CI_CONCLUSION: 'success',
        SITE_CI_HEAD_SHA: sourceSha,
        SITE_CI_PASSED: '11',
        SITE_CI_RUN_ID: '42',
        SITE_CI_RUN_URL: 'https://github.com/BoLayerDev/kanto-first-person/actions/runs/42',
        SITE_CI_TOTAL: '11',
        SITE_COMMIT_MESSAGE: 'Test source state',
        SITE_GENERATED_AT: '2026-08-22T12:00:00Z',
        SITE_REPOSITORY: 'BoLayerDev/kanto-first-person',
        SITE_REQUIRE_VERIFIED_CI: 'true',
        SITE_ACTIVITY_JSON: JSON.stringify(activity),
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
    assert.equal(status.release.available, false)
    assert.deepEqual(status.activity, activity)
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
