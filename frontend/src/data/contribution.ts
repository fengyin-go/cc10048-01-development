/** 成交贡献明细视图的前端契约，与后端 /api/cohort-contribution 返回一致。 */

export type ContributionGroup = 'A' | 'B'

export type ContributionGroupSummary = {
  group_key: ContributionGroup
  cohort_id: number
  cohort_name: string
  amount: number
  original_order_amount: number
  exclusive_amount: number
  shared_amount: number
  order_count: number
  user_count: number
  user_ids: string[]
  membership_version: string
  membership_source: string
  snapshot_member_count: number
  current_member_count: number
  added_since_publish: string[]
  removed_since_publish: string[]
  member_ids: string[]
}

export type ContributionOrderLine = {
  order_no: string
  user_id: string
  paid_at: string
  channel: string
  original_amount: number
  matched_groups: ContributionGroup[]
  allocation_method: string
  allocations: Partial<Record<ContributionGroup, number>>
  counted_once_amount: number
}

export type ContributionSummary = {
  currency: string
  allocation_policy: string
  group_amounts: Record<ContributionGroup, number>
  group_sum_amount: number
  raw_group_amounts: Record<ContributionGroup, number>
  raw_group_sum_amount: number
  dedup_adjustment_amount: number
  distinct_order_count: number
  distinct_order_amount: number
  overlap_order_count: number
  reconciled: boolean
  difference_amount: number
  recomputed_at: string
}

export type ContributionViewMeta = {
  view_id: number | null
  label: string
  period_start: string
  period_end: string
  published_at: string | null
  status: string
  group_a_cohort_id: number
  group_b_cohort_id: number
}

export type ContributionDetail = {
  published: boolean
  view: ContributionViewMeta
  summary: ContributionSummary
  groups: ContributionGroupSummary[]
  overlap_orders: ContributionOrderLine[]
  order_details: ContributionOrderLine[]
  compute_basis: { orders: string; membership: string; recomputed_at: string }
}

export type ContributionViewRow = ContributionViewMeta & {
  group_amounts: Record<ContributionGroup, number>
  group_sum_amount: number
  distinct_order_amount: number
  reconciled: boolean
}

export type ContributionDrillUser = {
  user_id: string
  order_count: number
  original_amount: number
  counted_amount: number
  other_group_amounts: Partial<Record<ContributionGroup, number>>
  counted_once_amount: number
  in_both_groups: boolean
}

export type ContributionDrill = {
  view_id: number
  group_key: ContributionGroup
  cohort_id: number
  cohort_name: string
  membership_version: string
  period_start: string
  period_end: string
  recomputed: boolean
  amount_source: string
  recomputed_at: string
  summary: {
    group_amount: number
    original_order_amount: number
    exclusive_amount: number
    shared_amount: number
    order_count: number
    user_count: number
  }
  reconciliation: {
    group_amounts: Record<ContributionGroup, number>
    group_sum_amount: number
    distinct_order_amount: number
    reconciled: boolean
  }
  orders: ContributionOrderLine[]
  users: ContributionDrillUser[]
}

export type ContributionCohort = {
  cohort_id: number
  cohort_name: string
  status: string
  base_date: string
  contribution_ready: boolean
  membership_version: string | null
  updated_at: string | null
  member_count: number
}

export type ContributionCatalog = {
  cohorts: ContributionCohort[]
  group_keys: ContributionGroup[]
  default_window: { start: string; end: string }
  allocation_policy: string
  order_total: number
  view_count: number
}
