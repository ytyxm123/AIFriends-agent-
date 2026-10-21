<script setup>
import {onMounted, ref} from "vue";
import {useRouter} from "vue-router";
import api from "@/js/http/api.js";

const router = useRouter()

const days = ref(7)
const stats = ref(null)
const traces = ref([])
const hasMore = ref(false)
const loading = ref(false)
const errorMsg = ref('')

const statusFilter = ref('')
const keyword = ref('')

const statusLabel = {
  success: '成功',
  failed: '失败',
  running: '进行中',
}

async function loadStats() {
  const res = await api.get('/api/observability/stats/', {params: {days: days.value}})
  stats.value = res.data
}

async function loadTraces(reset = false) {
  if (loading.value) return
  if (reset) {
    traces.value = []
  }
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await api.get('/api/observability/traces/', {
      params: {
        days: days.value,
        items_count: reset ? 0 : traces.value.length,
        status: statusFilter.value || undefined,
        keyword: keyword.value || undefined,
      },
    })
    if (res.data.result === 'success') {
      traces.value.push(...res.data.traces)
      hasMore.value = res.data.has_more
    }
  } catch (e) {
    if (e.response?.status === 403) {
      errorMsg.value = '仅管理员可访问运营后台'
    } else {
      errorMsg.value = '加载失败，请稍后重试'
    }
  } finally {
    loading.value = false
  }
}

async function switchDays(value) {
  days.value = value
  await Promise.all([loadStats(), loadTraces(true)])
}

async function applyFilters() {
  await loadTraces(true)
}

function openDetail(traceId) {
  router.push({name: 'trace-admin-detail', params: {trace_id: traceId}})
}

function formatDuration(ms) {
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(2)}s`
}

onMounted(async () => {
  await Promise.all([loadStats(), loadTraces(true)])
})
</script>

<template>
  <div class="max-w-6xl mx-auto p-6">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold">链路追踪</h1>
      <div class="flex items-center gap-2">
        <RouterLink :to="{name:'mcp-admin-index'}" class="btn btn-sm btn-ghost">MCP 工具</RouterLink>
        <div class="join">
          <button class="join-item btn btn-sm" :class="days===7?'btn-primary':''" @click="switchDays(7)">近7天</button>
          <button class="join-item btn btn-sm" :class="days===30?'btn-primary':''" @click="switchDays(30)">近30天</button>
          <button class="join-item btn btn-sm" :class="days===1?'btn-primary':''" @click="switchDays(1)">今日</button>
        </div>
      </div>
    </div>

    <div v-if="errorMsg" class="alert alert-error mb-4">{{ errorMsg }}</div>

    <div v-if="stats" class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
      <div class="stat bg-base-100 rounded-lg shadow-sm border">
        <div class="stat-title text-sm">总请求</div>
        <div class="stat-value text-2xl">{{ stats.total }}</div>
        <div class="stat-desc text-xs">成功 {{ stats.success }} / 失败 {{ stats.failed }} / 进行中 {{ stats.running }}</div>
      </div>
      <div class="stat bg-base-100 rounded-lg shadow-sm border">
        <div class="stat-title text-sm">成功率</div>
        <div class="stat-value text-2xl" :class="stats.success_rate>=95?'text-green-600':'text-red-600'">{{ stats.success_rate }}%</div>
        <div class="stat-desc text-xs">平均 {{ formatDuration(stats.avg_duration_ms) }}</div>
      </div>
      <div class="stat bg-base-100 rounded-lg shadow-sm border">
        <div class="stat-title text-sm">Token 消耗</div>
        <div class="stat-value text-2xl">{{ (stats.total_input_tokens + stats.total_output_tokens).toLocaleString() }}</div>
        <div class="stat-desc text-xs">输入 {{ stats.total_input_tokens.toLocaleString() }} / 输出 {{ stats.total_output_tokens.toLocaleString() }}</div>
      </div>
      <div class="stat bg-base-100 rounded-lg shadow-sm border">
        <div class="stat-title text-sm">估算成本</div>
        <div class="stat-value text-2xl">¥{{ stats.total_cost }}</div>
        <div class="stat-desc text-xs">按模型 Token 单价估算</div>
      </div>
    </div>

    <div class="flex flex-wrap gap-2 items-center mb-4">
      <select v-model="statusFilter" class="select select-bordered select-sm" @change="applyFilters">
        <option value="">全部状态</option>
        <option value="success">成功</option>
        <option value="failed">失败</option>
        <option value="running">进行中</option>
      </select>
      <input v-model="keyword" class="input input-bordered input-sm" placeholder="按用户名搜索" @keyup.enter="applyFilters"/>
      <button class="btn btn-sm btn-outline" @click="applyFilters">筛选</button>
    </div>

    <div class="overflow-x-auto bg-base-100 rounded-lg border">
      <table class="table table-sm">
        <thead>
        <tr>
          <th>时间</th>
          <th>用户</th>
          <th>角色</th>
          <th>输入</th>
          <th>状态</th>
          <th>耗时</th>
          <th>Token</th>
          <th>成本</th>
        </tr>
        </thead>
        <tbody>
        <tr v-for="trace in traces" :key="trace.trace_id" class="hover cursor-pointer" @click="openDetail(trace.trace_id)">
          <td class="whitespace-nowrap text-xs">{{ trace.started_at }}</td>
          <td>{{ trace.username }}</td>
          <td>{{ trace.character }}</td>
          <td class="max-w-48 truncate">{{ trace.input }}</td>
          <td>
            <span class="badge badge-sm"
                  :class="trace.status==='success'?'badge-success':trace.status==='failed'?'badge-error':'badge-ghost'">
              {{ statusLabel[trace.status] || trace.status }}
            </span>
          </td>
          <td class="whitespace-nowrap">{{ formatDuration(trace.duration_ms) }}</td>
          <td>{{ trace.total_tokens }}</td>
          <td class="whitespace-nowrap">¥{{ trace.cost }}</td>
        </tr>
        </tbody>
      </table>
      <div v-if="!loading && traces.length===0" class="text-center text-gray-400 py-10">暂无数据</div>
    </div>

    <div class="text-center mt-4">
      <button v-if="hasMore" class="btn btn-sm btn-outline" :disabled="loading" @click="loadTraces(false)">
        {{ loading ? '加载中...' : '加载更多' }}
      </button>
    </div>
  </div>
</template>
