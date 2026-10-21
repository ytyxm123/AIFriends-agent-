<script setup>
import {computed, onMounted, ref} from "vue";
import {useRoute, useRouter} from "vue-router";
import api from "@/js/http/api.js";

const route = useRoute()
const router = useRouter()

const trace = ref(null)
const spans = ref([])
const errorMsg = ref('')
const expanded = ref({})

const typeColor = {
  llm: 'bg-blue-500',
  tool: 'bg-amber-500',
  retrieval: 'bg-purple-500',
  tts: 'bg-teal-500',
  asr: 'bg-pink-500',
}
const typeLabel = {
  llm: 'LLM',
  tool: '工具',
  retrieval: '检索',
  tts: '语音合成',
  asr: '语音识别',
}

const timelineWidth = computed(() => {
  if (!spans.value.length || !trace.value) return 100
  const total = Math.max(trace.value.duration_ms, 1)
  return total
})

function barStyle(span) {
  const total = Math.max(trace.value.duration_ms, 1)
  const left = Math.min(99, Math.max(0, (span.offset_ms / total) * 100))
  const width = Math.min(100 - left, Math.max(1, (span.duration_ms / total) * 100))
  return {
    left: `${left}%`,
    width: `${width}%`,
  }
}

function formatDuration(ms) {
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(2)}s`
}

function toggle(index) {
  expanded.value[index] = !expanded.value[index]
}

function formatInput(input) {
  if (!input) return ''
  if (typeof input === 'string') return input
  try {
    return JSON.stringify(input, null, 2)
  } catch {
    return String(input)
  }
}

onMounted(async () => {
  try {
    const res = await api.get(
      `/api/observability/traces/${route.params.trace_id}/`)
    trace.value = res.data.trace
    spans.value = res.data.spans
  } catch (e) {
    errorMsg.value = e.response?.status === 403 ? '仅管理员可访问' : '记录不存在或加载失败'
  }
})
</script>

<template>
  <div class="max-w-5xl mx-auto p-6">
    <button class="btn btn-ghost btn-sm mb-4" @click="router.back()">&larr; 返回列表</button>
    <div v-if="errorMsg" class="alert alert-error">{{ errorMsg }}</div>

    <div v-if="trace">
      <div class="bg-base-100 rounded-lg border p-5 mb-6">
        <div class="flex items-center gap-3 mb-3">
          <h1 class="text-xl font-bold">Trace 详情</h1>
          <span class="badge"
                :class="trace.status==='success'?'badge-success':trace.status==='failed'?'badge-error':'badge-ghost'">
            {{ trace.status }}
          </span>
        </div>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
          <div><span class="text-gray-500">用户：</span>{{ trace.username }}</div>
          <div><span class="text-gray-500">角色：</span>{{ trace.character }}</div>
          <div><span class="text-gray-500">模型：</span>{{ trace.model || '-' }}</div>
          <div><span class="text-gray-500">总耗时：</span>{{ formatDuration(trace.duration_ms) }}</div>
          <div><span class="text-gray-500">输入 Token：</span>{{ trace.input_tokens }}</div>
          <div><span class="text-gray-500">输出 Token：</span>{{ trace.output_tokens }}</div>
          <div><span class="text-gray-500">总 Token：</span>{{ trace.total_tokens }}</div>
          <div><span class="text-gray-500">成本：</span>¥{{ trace.cost }}</div>
          <div class="col-span-2 md:col-span-4"><span class="text-gray-500">Trace ID：</span>{{ trace.trace_id }}</div>
          <div class="col-span-2 md:col-span-4"><span class="text-gray-500">开始：</span>{{ trace.started_at }}</div>
        </div>
        <div v-if="trace.error" class="alert alert-error mt-3 text-sm">{{ trace.error }}</div>
        <div class="mt-4">
          <div class="text-gray-500 text-sm mb-1">用户输入</div>
          <div class="bg-gray-50 rounded p-3 whitespace-pre-wrap break-all">{{ trace.input }}</div>
        </div>
        <div class="mt-3">
          <div class="text-gray-500 text-sm mb-1">模型输出</div>
          <div class="bg-gray-50 rounded p-3 whitespace-pre-wrap break-all">{{ trace.output || '（无输出）' }}</div>
        </div>
      </div>

      <h2 class="text-lg font-bold mb-3">调用链路（{{ spans.length }} 个步骤）</h2>
      <div class="space-y-2">
        <div v-for="(span, index) in spans" :key="index" class="bg-base-100 rounded-lg border">
          <div class="flex items-center gap-3 p-3 cursor-pointer" @click="toggle(index)">
            <div class="w-20 text-xs">
              <span class="badge badge-sm text-white" :class="typeColor[span.span_type]">
                {{ typeLabel[span.span_type] || span.span_type }}
              </span>
            </div>
            <div class="w-56 font-mono text-sm truncate">{{ span.name }}</div>
            <div class="flex-1 relative h-4 bg-gray-100 rounded">
              <div class="absolute h-4 rounded"
                   :class="[typeColor[span.span_type], span.status==='failed'?'!bg-red-600':'opacity-70']"
                   :style="barStyle(span)"></div>
            </div>
            <div class="w-24 text-right text-xs text-gray-500">{{ formatDuration(span.duration_ms) }}</div>
            <div class="w-10 text-xs"
                 :class="span.status==='failed'?'text-red-600':'text-green-600'">
              {{ span.status==='failed' ? '失败' : '成功' }}
            </div>
          </div>
          <div v-if="expanded[index]" class="px-4 pb-4 text-sm border-t pt-3 space-y-2">
            <div v-if="span.model">
              <span class="text-gray-500">模型：</span>{{ span.model }}
              <span v-if="span.input_tokens" class="ml-3 text-gray-500">
                输入 {{ span.input_tokens }} / 输出 {{ span.output_tokens }}
              </span>
            </div>
            <div v-if="span.error">
              <span class="text-red-600 font-bold">错误：</span>
              <pre class="bg-red-50 p-2 rounded text-xs whitespace-pre-wrap break-all">{{ span.error }}</pre>
            </div>
            <div>
              <div class="text-gray-500 mb-1">输入</div>
              <pre class="bg-gray-50 p-2 rounded text-xs whitespace-pre-wrap break-all max-h-60 overflow-auto">{{ formatInput(span.input) }}</pre>
            </div>
            <div v-if="span.output">
              <div class="text-gray-500 mb-1">输出</div>
              <pre class="bg-gray-50 p-2 rounded text-xs whitespace-pre-wrap break-all max-h-60 overflow-auto">{{ span.output }}</pre>
            </div>
          </div>
        </div>
      </div>
      <div v-if="spans.length===0" class="text-gray-400 text-center py-8">该请求没有记录到调用步骤</div>
    </div>
  </div>
</template>
