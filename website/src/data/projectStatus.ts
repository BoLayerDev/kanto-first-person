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
  ci: {
    state: 'success' | 'unknown'
    runId: string
    runUrl: string
    passed: number
    total: number
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
  ci: {
    state: 'success',
    runId: '32571329500',
    runUrl: 'https://github.com/BoLayerDev/kanto-first-person/actions/runs/32571329500',
    passed: 11,
    total: 11,
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
    && typeof candidate.ci?.runUrl === 'string'
    && typeof candidate.release?.available === 'boolean'
}

export function useProjectStatus() {
  const [status, setStatus] = useState(FALLBACK_PROJECT_STATUS)

  useEffect(() => {
    const controller = new AbortController()
    fetch(`${import.meta.env.BASE_URL}project-status.json`, {
      cache: 'no-store',
      signal: controller.signal,
    })
      .then((response) => {
        if (!response.ok) throw new Error(`Status request failed: ${response.status}`)
        return response.json()
      })
      .then((value: unknown) => {
        if (isProjectStatus(value)) setStatus(value)
      })
      .catch(() => undefined)

    return () => controller.abort()
  }, [])

  return status
}
