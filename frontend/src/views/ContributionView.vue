<template>
  <section class="page contribution-page">
    <header class="page-head">
      <div>
        <h2>成交贡献明细</h2>
        <p class="page-desc">
          按两组圈选名单复算统计窗口内的成交金额；交叠订单在汇总时只计一次，各组下钻可核对本组实际计入的部分。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn" data-testid="refresh-membership" type="button" @click="refreshMembership">
          模拟次日名单变化
        </button>
        <button class="btn" data-testid="reload-view" type="button" @click="reloadAll">重新读取视图</button>
      </div>
    </header>

    <p v-if="errorMessage" class="banner error" data-testid="contribution-error">{{ errorMessage }}</p>
    <p v-if="noticeMessage" class="banner" data-testid="contribution-notice">{{ noticeMessage }}</p>

    <form class="analysis-form" data-testid="publish-form" @submit.prevent="publish">
      <label>
        <span>圈选组 A</span>
        <select v-model.number="form.cohortA" data-testid="publish-cohort-a">
          <option v-for="item in readyCohorts" :key="`a-${item.cohort_id}`" :value="item.cohort_id">
            {{ item.cohort_name }}（{{ item.member_count }} 人）
          </option>
        </select>
      </label>
      <label>
        <span>圈选组 B</span>
        <select v-model.number="form.cohortB" data-testid="publish-cohort-b">
          <option v-for="item in readyCohorts" :key="`b-${item.cohort_id}`" :value="item.cohort_id">
            {{ item.cohort_name }}（{{ item.member_count }} 人）
          </option>
        </select>
      </label>
      <label>
        <span>统计开始</span>
        <input v-model="form.windowStart" data-testid="publish-window-start" placeholder="2026-09-01" />
      </label>
      <label>
        <span>统计结束</span>
        <input v-model="form.windowEnd" data-testid="publish-window-end" placeholder="2026-09-01" />
      </label>
      <button class="btn primary" data-testid="publish-view" type="submit" :disabled="publishing">
        {{ publishing ? '发布中…' : '发布成交贡献视图' }}
      </button>
      <span class="form-hint">口径：{{ catalog?.allocation_policy ?? '交叠均分' }}</span>
    </form>

    <div class="view-switch" v-if="views.length">
      <span class="view-switch-label">已发布视图</span>
      <button
        v-for="item in views"
        :key="String(item.view_id)"
        class="btn"
        :class="{ primary: item.view_id === currentViewId }"
        type="button"
        :data-testid="`view-${item.view_id}`"
        @click="openView(Number(item.view_id))"
      >
        #{{ item.view_id }} {{ item.label }}
        <small>{{ item.period_start.slice(0, 10) }} ~ {{ item.period_end.slice(0, 10) }}</small>
      </button>
    </div>

    <template v-if="detail">
      <div class="stat-row" data-testid="contribution-summary">
        <article class="stat-card">
          <span class="stat-label">A 组计入金额</span>
          <strong class="stat-value" data-testid="summary-group-a">{{ money(detail.summary.group_amounts.A) }}</strong>
          <span class="stat-sub">原金额 {{ money(detail.summary.raw_group_amounts.A) }}</span>
        </article>
        <article class="stat-card">
          <span class="stat-label">B 组计入金额</span>
          <strong class="stat-value" data-testid="summary-group-b">{{ money(detail.summary.group_amounts.B) }}</strong>
          <span class="stat-sub">原金额 {{ money(detail.summary.raw_group_amounts.B) }}</span>
        </article>
        <article class="stat-card">
          <span class="stat-label">两组计入合计</span>
          <strong class="stat-value" data-testid="summary-group-sum">{{ money(detail.summary.group_sum_amount) }}</strong>
          <span class="stat-sub">交叠扣减 {{ money(detail.summary.dedup_adjustment_amount) }}</span>
        </article>
        <article class="stat-card">
          <span class="stat-label">窗口内去重订单金额</span>
          <strong class="stat-value" data-testid="summary-distinct">{{ money(detail.summary.distinct_order_amount) }}</strong>
          <span class="stat-sub">{{ detail.summary.distinct_order_count }} 笔去重订单</span>
        </article>
        <article class="stat-card">
          <span class="stat-label">对平结果</span>
          <strong
            class="stat-value"
            :class="detail.summary.reconciled ? 'trend-up' : 'trend-down'"
            data-testid="summary-reconciled"
          >
            {{ detail.summary.reconciled ? '已对平' : `差异 ${money(detail.summary.difference_amount)}` }}
          </strong>
          <span class="stat-sub">交叠订单 {{ detail.summary.overlap_order_count }} 笔</span>
        </article>
      </div>

      <section class="panel">
        <header class="panel-head">
          <h3>贡献看板</h3>
          <span class="panel-meta">
            视图 #{{ detail.view.view_id }} · {{ detail.view.label }} ·
            {{ detail.view.period_start }} ~ {{ detail.view.period_end }} ·
            发布 {{ detail.view.published_at }} · 复算 {{ detail.compute_basis.recomputed_at }}
          </span>
        </header>
        <table class="data-table">
          <thead>
            <tr>
              <th>圈选组</th><th>分群</th><th>名单版本</th><th>计入金额</th>
              <th>独占金额</th><th>交叠计入</th><th>订单数</th><th>用户数</th><th>名单变化</th><th>下钻</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="group in detail.groups" :key="group.group_key" :data-testid="`group-row-${group.group_key}`">
              <td><strong>{{ group.group_key }}</strong></td>
              <td>{{ group.cohort_name }}</td>
              <td>{{ group.membership_version }}（发布快照 {{ group.snapshot_member_count }} 人）</td>
              <td :data-testid="`group-amount-${group.group_key}`">{{ money(group.amount) }}</td>
              <td>{{ money(group.exclusive_amount) }}</td>
              <td>{{ money(group.shared_amount) }}</td>
              <td>{{ group.order_count }}</td>
              <td>{{ group.user_count }}</td>
              <td>
                <span v-if="!group.added_since_publish.length && !group.removed_since_publish.length">与当前名单一致</span>
                <span v-else class="warn-text">
                  当前新增 {{ group.added_since_publish.join('、') || '无' }}；
                  移出 {{ group.removed_since_publish.join('、') || '无' }}
                </span>
              </td>
              <td>
                <button
                  class="link"
                  type="button"
                  :data-testid="`drill-${group.group_key}`"
                  @click="drill(group.group_key)"
                >
                  按组下钻
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <section class="panel">
        <header class="panel-head">
          <h3>交叠订单计入方式</h3>
          <span class="panel-meta">同一订单同时在两组名单内，按{{ detail.summary.allocation_policy }}拆分，两组相加等于原金额</span>
        </header>
        <table class="data-table">
          <thead>
            <tr>
              <th>订单号</th><th>用户</th><th>成交时间</th><th>原金额</th>
              <th>命中组</th><th>计入方式</th><th>A 组计入</th><th>B 组计入</th><th>汇总只计一次</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="order in detail.overlap_orders" :key="order.order_no" :data-testid="`overlap-${order.order_no}`">
              <td>{{ order.order_no }}</td>
              <td>{{ order.user_id }}</td>
              <td>{{ order.paid_at }}</td>
              <td>{{ money(order.original_amount) }}</td>
              <td>{{ order.matched_groups.join(' + ') }}</td>
              <td>{{ order.allocation_method }}</td>
              <td>{{ money(order.allocations.A ?? 0) }}</td>
              <td>{{ money(order.allocations.B ?? 0) }}</td>
              <td>{{ money(order.counted_once_amount) }}</td>
            </tr>
            <tr v-if="!detail.overlap_orders.length">
              <td colspan="9" class="empty-state">本窗口没有同时命中两组的订单</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section class="panel" v-if="drillDetail">
        <header class="panel-head">
          <h3>按组下钻复算 · {{ drillDetail.group_key }} 组（{{ drillDetail.cohort_name }}）</h3>
          <button class="btn ghost" type="button" @click="drillDetail = null">收起</button>
        </header>
        <p class="panel-meta" data-testid="drill-meta">
          名单版本 {{ drillDetail.membership_version }} · 金额来源 {{ drillDetail.amount_source }} ·
          组内计入 {{ money(drillDetail.summary.group_amount) }} ·
          原金额 {{ money(drillDetail.summary.original_order_amount) }} ·
          去重订单 {{ money(drillDetail.reconciliation.distinct_order_amount) }} ·
          {{ drillDetail.reconciliation.reconciled ? '两组汇总已对平' : '两组汇总未对平' }}
        </p>
        <table class="data-table">
          <thead>
            <tr>
              <th>订单号</th><th>用户</th><th>成交时间</th><th>原金额</th>
              <th>命中组</th><th>本组计入</th><th>计入方式</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="order in drillDetail.orders" :key="order.order_no" :data-testid="`drill-order-${order.order_no}`">
              <td>{{ order.order_no }}</td>
              <td>{{ order.user_id }}</td>
              <td>{{ order.paid_at }}</td>
              <td>{{ money(order.original_amount) }}</td>
              <td>{{ order.matched_groups.join(' + ') }}</td>
              <td data-testid="drill-order-group-amount">{{ money(order.allocations[drillDetail.group_key] ?? 0) }}</td>
              <td>{{ order.allocation_method }}</td>
            </tr>
          </tbody>
        </table>

        <h4 class="sub-title">用户核对</h4>
        <table class="data-table">
          <thead>
            <tr>
              <th>用户</th><th>订单数</th><th>原金额</th><th>本组实际计入</th>
              <th>另一组计入</th><th>汇总只计一次</th><th>是否同时在两组</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in drillDetail.users" :key="user.user_id" :data-testid="`drill-user-${user.user_id}`">
              <td>{{ user.user_id }}</td>
              <td>{{ user.order_count }}</td>
              <td>{{ money(user.original_amount) }}</td>
              <td data-testid="drill-user-counted">{{ money(user.counted_amount) }}</td>
              <td>
                <span v-if="user.in_both_groups">
                  {{ otherGroupLabel(user.other_group_amounts, drillDetail.group_key) }}
                </span>
                <span v-else>—</span>
              </td>
              <td>{{ money(user.counted_once_amount) }}</td>
              <td>{{ user.in_both_groups ? '是' : '否' }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section class="panel" v-if="chainAudit">
        <header class="panel-head">
          <h3>用户分析下钻核对</h3>
          <span class="panel-meta" v-if="chainAudit.available && chainAudit.view">
            读取成交贡献明细视图 #{{ chainAudit.view.view_id }} 的数据，
            按圈选组核对订单号、原金额和组内计入金额
          </span>
        </header>
        <p v-if="!chainAudit.available" class="empty-state">
          {{ chainAudit.reason ?? '该分群尚未发布成交贡献视图' }}
        </p>
        <template v-else>
          <table class="data-table">
            <thead>
              <tr>
                <th>圈选组</th><th>分群</th><th>计入金额</th><th>原金额</th>
                <th>订单数</th><th>用户数</th><th>名单版本</th><th>对平</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="group in chainAudit.groups" :key="`audit-${group.group_key}`">
                <td>{{ group.group_key }}</td>
                <td>{{ group.cohort_name }}</td>
                <td>{{ money(group.amount) }}</td>
                <td>{{ money(group.original_order_amount) }}</td>
                <td>{{ group.order_count }}</td>
                <td>{{ group.user_count }}</td>
                <td>{{ group.membership_version }}</td>
                <td>{{ group.reconciled ? '已对平' : '未对平' }}</td>
              </tr>
            </tbody>
          </table>
          <table class="data-table">
            <thead>
              <tr>
                <th>圈选组</th><th>订单号</th><th>用户</th><th>成交时间</th>
                <th>原金额</th><th>组内计入金额</th><th>命中组</th><th>计入方式</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="order in chainAudit.orders" :key="`${order.group_key}-${order.order_no}`">
                <td>{{ order.group_key }}</td>
                <td>{{ order.order_no }}</td>
                <td>{{ order.user_id }}</td>
                <td>{{ order.paid_at }}</td>
                <td>{{ money(order.original_amount) }}</td>
                <td>{{ money(order.group_amount) }}</td>
                <td>{{ order.matched_groups.join(' + ') }}</td>
                <td>{{ order.allocation_method }}</td>
              </tr>
            </tbody>
          </table>
        </template>
      </section>

      <section class="panel">
        <header class="panel-head">
          <h3>窗口内订单明细</h3>
          <span class="panel-meta">全部由原始订单数据复算，单位：元</span>
        </header>
        <table class="data-table">
          <thead>
            <tr>
              <th>订单号</th><th>用户</th><th>成交时间</th><th>渠道</th><th>原金额</th>
              <th>命中组</th><th>计入方式</th><th>A 组计入</th><th>B 组计入</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="order in detail.order_details" :key="order.order_no">
              <td>{{ order.order_no }}</td>
              <td>{{ order.user_id }}</td>
              <td>{{ order.paid_at }}</td>
              <td>{{ order.channel }}</td>
              <td>{{ money(order.original_amount) }}</td>
              <td>{{ order.matched_groups.join(' + ') }}</td>
              <td>{{ order.allocation_method }}</td>
              <td>{{ order.allocations.A === undefined ? '—' : money(order.allocations.A) }}</td>
              <td>{{ order.allocations.B === undefined ? '—' : money(order.allocations.B) }}</td>
            </tr>
            <tr v-if="!detail.order_details.length">
              <td colspan="9" class="empty-state">统计窗口内没有命中圈选组的成交订单</td>
            </tr>
          </tbody>
        </table>
      </section>
    </template>

    <p v-else-if="loading" class="empty-state">正在读取成交贡献视图…</p>
    <p v-else class="empty-state">暂无成交贡献视图，可先按两组圈选名单发布一期。</p>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import {
  drillContributionGroup,
  listContributionViews,
  loadContributionCatalog,
  loadContributionView,
  publishContributionView,
  refreshContributionMembership,
} from '@/api/backend-service'
import { fetchJson } from '@/api/client'
import type {
  ContributionCatalog,
  ContributionDetail,
  ContributionDrill,
  ContributionGroup,
  ContributionViewRow,
} from '@/data/contribution'

type ChainAudit = {
  available: boolean
  reason?: string
  view?: { view_id: number }
  groups: {
    group_key: string
    cohort_name: string
    amount: number
    original_order_amount: number
    order_count: number
    user_count: number
    membership_version: string
    reconciled: boolean
  }[]
  orders: {
    group_key: string
    order_no: string
    user_id: string
    paid_at: string
    original_amount: number
    group_amount: number
    matched_groups: string[]
    allocation_method: string
  }[]
}

type ChainCohortAnalysis = { contribution_orders?: ChainAudit }

const loading = ref(true)
const publishing = ref(false)
const errorMessage = ref('')
const noticeMessage = ref('')
const catalog = ref<ContributionCatalog | null>(null)
const views = ref<ContributionViewRow[]>([])
const detail = ref<ContributionDetail | null>(null)
const drillDetail = ref<ContributionDrill | null>(null)
const chainAudit = ref<ChainAudit | null>(null)
const currentViewId = ref<number | null>(null)
const form = ref({ cohortA: 1, cohortB: 2, windowStart: '2026-09-01', windowEnd: '2026-09-01' })

const readyCohorts = computed(() => catalog.value?.cohorts.filter((item) => item.contribution_ready) ?? [])

function money(value: number | undefined) {
  return `${Number(value ?? 0).toFixed(2)} 元`
}

function otherGroupLabel(
  amounts: Partial<Record<ContributionGroup, number>>,
  current: ContributionGroup,
) {
  return Object.entries(amounts)
    .filter(([group, value]) => group !== current && Number(value ?? 0) > 0)
    .map(([group, value]) => `${group} 组 ${money(Number(value))}`)
    .join('，')
}

function showError(error: unknown, fallback: string) {
  errorMessage.value = error instanceof Error ? error.message : fallback
}

async function loadCatalog() {
  catalog.value = await loadContributionCatalog()
}

async function loadViews() {
  views.value = await listContributionViews()
}

async function openView(viewId: number) {
  errorMessage.value = ''
  drillDetail.value = null
  chainAudit.value = null
  try {
    detail.value = await loadContributionView(viewId)
    currentViewId.value = viewId
    const cohortId = detail.value.groups[0]?.cohort_id
    if (cohortId) {
      chainAudit.value = await fetchJson<ChainCohortAnalysis>(
        `/api/chains/cohort-analysis/${cohortId}?view_id=${viewId}`,
      )
        .then((payload) => payload.contribution_orders ?? null)
        .catch(() => null)
    }
  } catch (error) {
    showError(error, '成交贡献视图读取失败')
  }
}

async function reloadAll() {
  errorMessage.value = ''
  loading.value = true
  try {
    await loadCatalog()
    await loadViews()
    const target = currentViewId.value ?? views.value[0]?.view_id ?? null
    if (target) {
      await openView(Number(target))
    } else {
      detail.value = null
    }
  } catch (error) {
    showError(error, '成交贡献数据读取失败')
  } finally {
    loading.value = false
  }
}

async function publish() {
  publishing.value = true
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    if (form.value.cohortA === form.value.cohortB) {
      throw new Error('两组圈选名单不能相同')
    }
    const published = await publishContributionView({
      cohort_a_id: form.value.cohortA,
      cohort_b_id: form.value.cohortB,
      window_start: form.value.windowStart,
      window_end: form.value.windowEnd,
    })
    const viewId = Number(published.view.view_id)
    currentViewId.value = viewId
    drillDetail.value = null
    await loadViews()
    await openView(viewId)
    noticeMessage.value = `已发布视图 #${viewId}，两组合计 ${money(published.summary.group_sum_amount)}，去重订单 ${money(published.summary.distinct_order_amount)}。`
  } catch (error) {
    showError(error, '成交贡献视图发布失败')
  } finally {
    publishing.value = false
  }
}

async function drill(groupKey: ContributionGroup) {
  if (!currentViewId.value) return
  errorMessage.value = ''
  try {
    drillDetail.value = await drillContributionGroup(currentViewId.value, groupKey)
  } catch (error) {
    showError(error, '按组下钻失败')
  }
}

async function refreshMembership() {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    await Promise.all([
      refreshContributionMembership(1),
      refreshContributionMembership(2),
    ])
    await loadCatalog()
    await loadViews()
    noticeMessage.value = '两组名单已刷新到次日版本；已发布视图仍按发布时的快照复算，可在名单变化列查看差异。'
    if (currentViewId.value) {
      await openView(currentViewId.value)
      drillDetail.value = null
    }
  } catch (error) {
    showError(error, '圈选名单刷新失败')
  }
}

onMounted(reloadAll)
</script>
