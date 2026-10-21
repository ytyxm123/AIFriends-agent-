<script setup>
import {computed, onMounted, ref} from "vue";
import api from "@/js/http/api.js";

const servers = ref([])
const tools = ref([])
const errorMsg = ref('')
const loading = ref(false)

const showForm = ref(false)
const editing = ref(null)
const form = ref(emptyForm())
const formError = ref('')
const testing = ref({})
const saving = ref(false)
const testResult = ref({})

const schemaTool = ref(null)

function emptyForm() {
  return {
    name: '', transport: 'stdio', command: '', argsText: '',
    envText: '', url: '', headersText: '', enabled: true,
    failure_threshold: 3, has_env: false, has_headers: false,
  }
}

const isStdio = computed(() => form.value.transport === 'stdio')

const statusBadge = {
  healthy: 'badge-success',
  unhealthy: 'badge-error',
  unknown: 'badge-ghost',
}

async function loadAll() {
  loading.value = true
  errorMsg.value = ''
  try {
    const [s, t] = await Promise.all([
      api.get('/api/mcp/servers/'),
      api.get('/api/mcp/tools/'),
    ])
    servers.value = s.data.servers
    tools.value = t.data.tools
  } catch (e) {
    errorMsg.value = e.response?.status === 403 ? '仅管理员可访问' : '加载失败'
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  form.value = emptyForm()
  formError.value = ''
  showForm.value = true
}

function openEdit(server) {
  editing.value = server
  form.value = {
    name: server.name,
    transport: server.transport,
    command: server.command,
    argsText: JSON.stringify(server.args || [], null, 2),
    envText: '',
    url: server.url,
    headersText: '',
    enabled: server.enabled,
    failure_threshold: server.failure_threshold,
    has_env: server.has_env,
    has_headers: server.has_headers,
  }
  formError.value = ''
  showForm.value = true
}

function buildPayload() {
  const payload = {
    name: form.value.name,
    transport: form.value.transport,
    enabled: form.value.enabled,
    failure_threshold: form.value.failure_threshold,
  }
  if (isStdio.value) {
    payload.command = form.value.command
    const args = parseJson(form.value.argsText, 'args')
    if (args === undefined) return null
    payload.args = args || []
  } else {
    payload.url = form.value.url
  }
  if (form.value.envText.trim()) {
    const env = parseJson(form.value.envText, 'env')
    if (env === undefined) return null
    payload.env = env
  }
  if (form.value.headersText.trim()) {
    const headers = parseJson(form.value.headersText, 'headers')
    if (headers === undefined) return null
    payload.headers = headers
  }
  return payload
}

function parseJson(text, label) {
  if (!text.trim()) return label === 'args' ? [] : {}
  try {
    return JSON.parse(text)
  } catch {
    formError.value = `${label} 不是合法的 JSON`
    return undefined
  }
}

async function submitForm() {
  if (saving.value) return
  formError.value = ''
  const payload = buildPayload()
  if (!payload) return
  saving.value = true
  try {
    if (editing.value) {
      await api.patch(`/api/mcp/servers/${editing.value.id}/`, payload)
    } else {
      await api.post('/api/mcp/servers/', payload)
    }
    showForm.value = false
    await loadAll()
  } catch (e) {
    formError.value = e.response?.data?.result || '保存失败'
  } finally {
    saving.value = false
  }
}

async function toggleServer(server) {
  await api.post(`/api/mcp/servers/${server.id}/toggle/`)
  await loadAll()
}

async function removeServer(server) {
  if (!confirm(`确认删除服务「${server.name}」及其工具配置？`)) return
  await api.delete(`/api/mcp/servers/${server.id}/`)
  await loadAll()
}

async function testConnection(server) {
  testing.value[server.id] = true
  testResult.value[server.id] = null
  try {
    const res = await api.post(`/api/mcp/servers/${server.id}/test_connection/`)
    testResult.value[server.id] = {ok: true, tools: res.data.tools}
  } catch (e) {
    testResult.value[server.id] = {ok: false, message: e.response?.data?.result || '连接失败'}
  } finally {
    testing.value[server.id] = false
    await loadAll()
  }
}

async function refreshTools(server) {
  testing.value[server.id] = true
  try {
    await api.post(`/api/mcp/servers/${server.id}/refresh_tools/`)
    testResult.value[server.id] = {ok: true, refreshed: true}
  } catch (e) {
    testResult.value[server.id] = {ok: false, message: e.response?.data?.result || '连接失败'}
  } finally {
    testing.value[server.id] = false
    await loadAll()
  }
}

async function toggleTool(tool) {
  await api.post(`/api/mcp/tools/${tool.id}/toggle/`)
  await loadAll()
}

onMounted(loadAll)
</script>

<template>
  <div class="max-w-6xl mx-auto p-6">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold">MCP 工具管理</h1>
      <div class="flex gap-2">
        <RouterLink :to="{name:'trace-admin-index'}" class="btn btn-sm btn-ghost">链路追踪</RouterLink>
        <button class="btn btn-sm btn-primary" @click="openCreate">+ 添加服务</button>
      </div>
    </div>

    <div v-if="errorMsg" class="alert alert-error mb-4">{{ errorMsg }}</div>

    <!-- Server list -->
    <div class="overflow-x-auto bg-base-100 rounded-lg border mb-8">
      <table class="table table-sm">
        <thead>
        <tr>
          <th>名称</th><th>方式</th><th>状态</th><th>连接</th>
          <th>工具数</th><th>启用</th><th>操作</th>
        </tr>
        </thead>
        <tbody>
        <tr v-for="s in servers" :key="s.id">
          <td>
            <div class="font-bold">{{ s.name }}</div>
            <div class="text-xs text-gray-500">{{ s.command || s.url }}</div>
            <div v-if="s.circuit_open" class="text-xs text-red-600">熔断中（连续失败 {{ s.failure_count }} 次）</div>
            <div v-if="s.last_error" class="text-xs text-red-400 truncate max-w-64">{{ s.last_error }}</div>
            <div v-if="testResult[s.id]" class="text-xs mt-1">
              <span v-if="testResult[s.id].ok" class="text-green-600">
                连接成功<template v-if="testResult[s.id].tools">，发现 {{ testResult[s.id].tools.length }} 个工具：
                  {{ testResult[s.id].tools.map(t=>t.name).join(', ') }}
                </template>
                <template v-if="testResult[s.id].refreshed">，工具已同步</template>
              </span>
              <span v-else class="text-red-600">{{ testResult[s.id].message }}</span>
            </div>
          </td>
          <td><span class="badge badge-sm">{{ s.transport }}</span></td>
          <td><span class="badge badge-sm" :class="statusBadge[s.status]">{{ s.status }}</span></td>
          <td class="text-xs">{{ s.last_connected_at || '从未连接' }}</td>
          <td>{{ s.tool_count }}</td>
          <td>
            <input type="checkbox" class="toggle toggle-sm" :checked="s.enabled"
                   @change="toggleServer(s)"/>
          </td>
          <td>
            <div class="flex gap-1">
              <button class="btn btn-xs btn-outline" :disabled="testing[s.id]"
                      @click="testConnection(s)">测试</button>
              <button class="btn btn-xs btn-outline" :disabled="testing[s.id]"
                      @click="refreshTools(s)">同步工具</button>
              <button class="btn btn-xs btn-ghost" @click="openEdit(s)">编辑</button>
              <button class="btn btn-xs btn-ghost text-red-600" @click="removeServer(s)">删除</button>
            </div>
          </td>
        </tr>
        </tbody>
      </table>
      <div v-if="!loading && servers.length===0" class="text-center text-gray-400 py-10">
        还没有 MCP 服务，点击右上角「添加服务」
      </div>
    </div>

    <!-- Tools -->
    <h2 class="text-lg font-bold mb-3">已发现工具（{{ tools.length }}）</h2>
    <div class="overflow-x-auto bg-base-100 rounded-lg border">
      <table class="table table-sm">
        <thead>
        <tr><th>工具</th><th>所属服务</th><th>描述</th><th>启用</th><th>Schema</th></tr>
        </thead>
        <tbody>
        <tr v-for="t in tools" :key="t.id">
          <td class="font-mono">{{ t.name }}</td>
          <td>{{ t.server_name }}</td>
          <td class="max-w-96 truncate">{{ t.description }}</td>
          <td><input type="checkbox" class="toggle toggle-sm" :checked="t.enabled"
                      @change="toggleTool(t)"/></td>
          <td><button class="btn btn-xs btn-ghost" @click="schemaTool=t">查看</button></td>
        </tr>
        </tbody>
      </table>
      <div v-if="tools.length===0" class="text-center text-gray-400 py-8">
        添加服务后点「同步工具」，工具会出现在这里
      </div>
    </div>

    <!-- Server form modal -->
    <dialog v-if="showForm" class="modal modal-open service-modal" aria-modal="true"
            aria-labelledby="service-form-title" @keydown.esc="!saving && (showForm=false)">
      <form class="modal-box service-form" @submit.prevent="submitForm">
        <header class="service-header">
          <div>
            <h3 id="service-form-title">{{ editing ? '编辑服务' : '添加 MCP 服务' }}</h3>
            <p>连接工具服务，供 AI 在对话中按需调用。</p>
          </div>
          <button type="button" class="btn btn-sm btn-ghost btn-circle" aria-label="关闭"
                  :disabled="saving" @click="showForm=false">✕</button>
        </header>

        <div class="service-body">
          <section class="service-section" aria-labelledby="basic-settings">
            <h4 id="basic-settings">基本信息</h4>
            <label class="service-field">
              <span>服务名称 <span class="required-mark">*</span></span>
              <input v-model="form.name" required maxlength="100" class="input" placeholder="例如：weather"/>
            </label>
            <label class="service-field">
              <span>连接方式</span>
              <select v-model="form.transport" class="select">
                <option value="stdio">本地进程 · stdio</option>
                <option value="streamable_http">远程服务 · Streamable HTTP</option>
                <option value="sse">远程服务 · SSE</option>
              </select>
              <small>{{ isStdio ? '通过命令启动本机的 MCP 服务。' : '连接已经运行的 MCP 服务地址。' }}</small>
            </label>
          </section>

          <section class="service-section" aria-labelledby="connection-settings">
            <h4 id="connection-settings">{{ isStdio ? '启动配置' : '连接配置' }}</h4>
            <template v-if="isStdio">
              <label class="service-field">
                <span>启动命令 <span class="required-mark">*</span></span>
                <input v-model="form.command" required class="input code-field" placeholder="例如：npx"/>
                <small>支持 npx、uvx、python 等已允许的命令。</small>
              </label>
              <label class="service-field">
                <span>命令参数 <span class="field-tag">JSON 数组</span></span>
                <textarea v-model="form.argsText" class="textarea code-field" rows="3" spellcheck="false"
                          placeholder='["-y", "@modelcontextprotocol/server-xxx"]'></textarea>
                <small>每个参数用双引号包裹；没有参数时可留空。</small>
              </label>
              <label class="service-field">
                <span>环境变量 <span class="field-tag">可选</span></span>
                <textarea v-model="form.envText" class="textarea code-field" rows="3" spellcheck="false"
                          placeholder='{"API_KEY": "你的密钥"}'></textarea>
                <small>{{ editing && form.has_env ? '已保存环境变量，留空保留原配置。' : '服务需要密钥时填写，使用 JSON 对象格式。' }}</small>
              </label>
            </template>
            <template v-else>
              <label class="service-field">
                <span>服务地址 <span class="required-mark">*</span></span>
                <input v-model="form.url" required type="url" class="input code-field"
                       placeholder="http://127.0.0.1:9000/mcp"/>
              </label>
              <label class="service-field">
                <span>鉴权请求头 <span class="field-tag">可选</span></span>
                <textarea v-model="form.headersText" class="textarea code-field" rows="3" spellcheck="false"
                          placeholder='{"Authorization": "Bearer 你的令牌"}'></textarea>
                <small>{{ editing && form.has_headers ? '已保存请求头，留空保留原配置。' : '仅在服务要求身份验证时填写，使用 JSON 对象格式。' }}</small>
              </label>
            </template>
          </section>

          <section class="service-section" aria-labelledby="availability-settings">
            <h4 id="availability-settings">运行设置</h4>
            <label class="service-field">
              <span>连续失败上限</span>
              <input v-model.number="form.failure_threshold" type="number" required min="1"
                     class="input threshold-input"/>
              <small>达到上限后暂停连接，避免持续失败影响聊天。</small>
            </label>
            <label class="service-enabled">
              <span><strong>启用此服务</strong><small>启用后还需同步并选择工具。</small></span>
              <input type="checkbox" class="toggle toggle-primary toggle-sm" v-model="form.enabled"/>
            </label>
          </section>
          <p v-if="formError" role="alert" class="service-error">{{ formError }}</p>
        </div>

        <footer class="service-footer">
          <button type="button" class="btn btn-sm" :disabled="saving" @click="showForm=false">取消</button>
          <button type="submit" class="btn btn-sm btn-primary" :disabled="saving">
            {{ saving ? '正在保存…' : '保存服务' }}
          </button>
        </footer>
      </form>
    </dialog>

    <!-- Schema modal -->
    <dialog v-if="schemaTool" class="modal modal-open" @click.self="schemaTool=null">
      <div class="modal-box max-w-xl">
        <h3 class="text-lg font-bold mb-2 font-mono">{{ schemaTool.name }}</h3>
        <p class="text-sm text-gray-600 mb-3">{{ schemaTool.description }}</p>
        <pre class="bg-gray-50 p-3 rounded text-xs overflow-auto max-h-96">{{ JSON.stringify(schemaTool.input_schema, null, 2) }}</pre>
        <div class="modal-action">
          <button class="btn btn-sm" @click="schemaTool=null">关闭</button>
        </div>
      </div>
    </dialog>
  </div>
</template>

<style scoped>
.service-modal { padding: 20px; }
.service-form {
  width: min(600px, 100%);
  max-width: 600px;
  max-height: calc(100dvh - 40px);
  padding: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid color-mix(in srgb, currentColor 14%, transparent);
  border-radius: 16px;
  background: var(--color-base-100, #fff);
  color: var(--color-base-content, #1f2937);
}
.service-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  padding: 24px 28px 20px;
  border-bottom: 1px solid color-mix(in srgb, currentColor 12%, transparent);
}
.service-header h3 { margin: 0; font-size: 20px; font-weight: 700; }
.service-header p { margin: 6px 0 0; font-size: 13px; opacity: .65; line-height: 1.6; }
.service-body { padding: 24px 28px; overflow-y: auto; min-height: 0; }
.service-section { display: flex; flex-direction: column; gap: 17px; }
.service-section + .service-section {
  margin-top: 24px;
  padding-top: 22px;
  border-top: 1px solid color-mix(in srgb, currentColor 12%, transparent);
}
.service-section h4 { margin: 0; font-size: 14px; font-weight: 700; }
.service-field { display: flex; flex-direction: column; gap: 7px; min-width: 0; }
.service-field > span { font-size: 13px; font-weight: 500; line-height: 1.5; }
.service-field .input, .service-field .select, .service-field .textarea {
  box-sizing: border-box;
  width: 100%;
  max-width: none;
  border: 1px solid color-mix(in srgb, currentColor 20%, transparent);
  border-radius: 8px;
  background: var(--color-base-100, #fff);
  color: inherit;
  font-size: 14px;
}
.service-field .input, .service-field .select { height: 42px; padding-inline: 12px; }
.service-field .textarea { padding: 11px 12px; min-height: 88px; resize: vertical; line-height: 1.6; }
.service-field .code-field { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 12px; }
.service-field small, .service-enabled small { font-size: 12px; line-height: 1.6; opacity: .65; }
.service-field .threshold-input { width: 100px; }
.field-tag { margin-left: 6px; font-size: 11px; font-weight: 400; opacity: .6; }
.required-mark { color: var(--color-error, #dc2626); }
.service-enabled { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.service-enabled > span { display: flex; flex-direction: column; gap: 3px; }
.service-enabled strong { font-size: 13px; font-weight: 500; }
.service-error { color: var(--color-error, #dc2626); font-size: 13px; line-height: 1.6; margin-top: 20px; }
.service-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 16px 28px;
  border-top: 1px solid color-mix(in srgb, currentColor 12%, transparent);
}
@media (max-width: 480px) {
  .service-modal { padding: 10px; }
  .service-form { max-height: calc(100dvh - 20px); }
  .service-header, .service-body { padding: 18px; }
  .service-footer { padding: 14px 18px; }
}
</style>
