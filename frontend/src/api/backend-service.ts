import { request } from './client'
import { moduleMeta } from '@/data/modules'
import type {
  ContributionCatalog,
  ContributionDetail,
  ContributionDrill,
  ContributionViewRow,
} from '@/data/contribution'
import type { ActionResult, EntryRow, OverviewResult, PageResult } from '@/data/types'

export { moduleMeta }

export async function listEntries(
  key: string,
  filters: Record<string, string> = {},
): Promise<PageResult> {
  const query = new URLSearchParams(filters).toString()
  const response = await request(`/api/${key}?${query}`)
  if (!response.ok) throw new Error('业务数据读取失败')
  return await response.json()
}

export async function createEntry(
  key: string,
  values: Record<string, string>,
): Promise<ActionResult> {
  const response = await request(`/api/${key}`, {
    method: 'POST',
    body: JSON.stringify({ values }),
  })
  return await response.json()
}

export async function runAction(
  key: string,
  id: number,
  action: string,
): Promise<ActionResult> {
  const response = await request(`/api/${key}/${id}/actions`, {
    method: 'POST',
    body: JSON.stringify({ action }),
  })
  return await response.json()
}

export async function downloadEntries(
  key: string,
  filters: Record<string, string> = {},
): Promise<void> {
  const query = new URLSearchParams(filters).toString()
  const response = await request(`/api/${key}/export?${query}`)
  if (!response.ok) throw new Error('业务数据导出失败')
  const url = URL.createObjectURL(await response.blob())
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `${key}.csv`
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
  URL.revokeObjectURL(url)
}

export async function loadOverview(): Promise<OverviewResult> {
  const response = await request('/api/overview')
  if (!response.ok) throw new Error('运营概览读取失败')
  return await response.json()
}

export async function loadContributionCatalog(): Promise<ContributionCatalog> {
  const response = await request('/api/cohort-contribution/catalog')
  if (!response.ok) throw new Error('成交贡献圈选名单读取失败')
  return await response.json()
}

export async function listContributionViews(): Promise<ContributionViewRow[]> {
  const response = await request('/api/cohort-contribution/views')
  if (!response.ok) throw new Error('成交贡献视图列表读取失败')
  const payload = (await response.json()) as { items: ContributionViewRow[] }
  return payload.items
}

export async function publishContributionView(input: {
  cohort_a_id: number
  cohort_b_id: number
  window_start: string
  window_end: string
  label?: string
}): Promise<ContributionDetail> {
  const response = await request('/api/cohort-contribution/views', {
    method: 'POST',
    body: JSON.stringify(input),
  })
  if (!response.ok) throw new Error(await readError(response, '成交贡献视图发布失败'))
  return await response.json()
}

export async function loadContributionView(viewId: number): Promise<ContributionDetail> {
  const response = await request(`/api/cohort-contribution/views/${viewId}`)
  if (!response.ok) throw new Error(await readError(response, '成交贡献视图读取失败'))
  return await response.json()
}

export async function drillContributionGroup(
  viewId: number,
  groupKey: string,
): Promise<ContributionDrill> {
  const response = await request(`/api/cohort-contribution/views/${viewId}/groups/${groupKey}`)
  if (!response.ok) throw new Error(await readError(response, '按组下钻复算失败'))
  return await response.json()
}

export async function refreshContributionMembership(cohortId: number): Promise<void> {
  const response = await request(`/api/cohort-contribution/cohorts/${cohortId}/membership/refresh`, {
    method: 'POST',
    body: JSON.stringify({}),
  })
  if (!response.ok) throw new Error(await readError(response, '圈选名单刷新失败'))
}

async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string }
    return payload.detail ? `${fallback}：${payload.detail}` : fallback
  } catch {
    return fallback
  }
}
