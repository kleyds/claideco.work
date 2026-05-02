<template>
  <div class="container app-page">
    <header>
      <div>
        <p class="eyebrow">Workspace</p>
        <h1>Clients</h1>
      </div>
    </header>

    <section class="summary">
      <div>
        <span>Signed in as</span>
        <strong>{{ user?.email || 'Loading...' }}</strong>
      </div>
      <div>
        <span>Plan</span>
        <strong>{{ user?.plan || 'free' }}</strong>
      </div>
      <div>
        <span>Managed clients</span>
        <strong>{{ clients.length }}</strong>
      </div>
      <div>
        <span>Open work</span>
        <strong>{{ openWorkCount }}</strong>
      </div>
    </section>

    <p v-if="error" class="error">{{ error }}</p>

    <section v-if="loading" class="empty">
      <h2>Loading clients...</h2>
    </section>

    <section v-else-if="clients.length === 0" class="empty">
      <h2>No clients yet</h2>
      <p>Add the first company you manage. Receipts, bank transactions, and BIR exports will live under each client.</p>
      <router-link to="/app/clients/new">Create a client</router-link>
    </section>

    <section v-else class="client-grid">
      <router-link
        v-for="client in clients"
        :key="client.id"
        :to="`/app/clients/${client.id}`"
        class="client-card"
      >
        <div class="card-top">
          <h2>{{ client.name }}</h2>
          <span :class="['status', deadlineStatus(client)]">{{ deadlineLabel(client) }}</span>
        </div>
        <dl>
          <div>
            <dt>TIN</dt>
            <dd>{{ client.tin || 'Not set' }}</dd>
          </div>
          <div>
            <dt>Software</dt>
            <dd>{{ softwareLabel(client.software) }}</dd>
          </div>
          <div>
            <dt>Unprocessed invoices</dt>
            <dd>{{ clientMetrics(client.id).unprocessed_invoices }}</dd>
          </div>
          <div>
            <dt>Unreconciled bank entries</dt>
            <dd>{{ clientMetrics(client.id).unreconciled_bank_entries }}</dd>
          </div>
          <div>
            <dt>Missing 2307s</dt>
            <dd>{{ clientMetrics(client.id).missing_2307s }}</dd>
          </div>
        </dl>
      </router-link>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { apiFetch, clearToken } from '../api'

const router = useRouter()
const user = ref(null)
const clients = ref([])
const metricsByClient = ref({})
const loading = ref(true)
const error = ref('')

const openWorkCount = computed(() =>
  Object.values(metricsByClient.value).reduce(
    (total, metrics) =>
      total + metrics.unprocessed_invoices + metrics.unreconciled_bank_entries + metrics.missing_2307s,
    0
  )
)

onMounted(loadDashboard)

async function loadDashboard() {
  try {
    const [me, clientData, metricsData] = await Promise.all([
      apiFetch('/auth/me'),
      apiFetch('/clients'),
      apiFetch('/clients/metrics'),
    ])
    user.value = me.user
    clients.value = clientData.clients
    metricsByClient.value = Object.fromEntries(metricsData.metrics.map((metrics) => [metrics.client_id, metrics]))
  } catch (err) {
    if (err.message.includes('credentials')) {
      clearToken()
      router.push('/login')
      return
    }
    error.value = err.message
  } finally {
    loading.value = false
  }
}

function softwareLabel(value) {
  const labels = {
    quickbooks: 'QuickBooks',
    xero: 'Xero',
    juantax: 'JuanTax',
    excel: 'Excel',
    other: 'Other',
  }
  return labels[value] || 'Other'
}

function clientMetrics(clientId) {
  return metricsByClient.value[clientId] || {
    unprocessed_invoices: 0,
    unreconciled_bank_entries: 0,
    missing_2307s: 0,
  }
}

function clientOpenWork(client) {
  const metrics = clientMetrics(client.id)
  return metrics.unprocessed_invoices + metrics.unreconciled_bank_entries + metrics.missing_2307s
}

function deadlineStatus(client) {
  const openWork = clientOpenWork(client)
  if (openWork === 0) return 'green'
  if (openWork <= 5) return 'yellow'
  return 'red'
}

function deadlineLabel(client) {
  const openWork = clientOpenWork(client)
  return openWork === 0 ? 'On track' : `${openWork} open`
}
</script>

<style scoped>
.app-page {
  padding: 16px 24px 64px;
}
header {
  margin-bottom: 28px;
}
.eyebrow {
  color: var(--accent-hover);
  font-size: 0.78em;
  font-weight: 700;
  margin-bottom: 4px;
  text-transform: uppercase;
}
.summary,
.client-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}
.summary {
  margin-bottom: 32px;
}
.summary div,
.empty,
.client-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 20px;
}
.summary span {
  color: var(--muted);
  display: block;
  font-size: 0.85em;
  margin-bottom: 4px;
}
.summary strong {
  font-size: 1.05em;
}
.empty {
  max-width: 640px;
}
.empty h2 {
  margin-bottom: 8px;
}
.empty p {
  color: var(--muted);
  margin-bottom: 16px;
}
.client-card {
  color: var(--text);
}
.client-card:hover {
  background: var(--surface-2);
  border-color: var(--accent);
  color: var(--text);
}
.client-card:active {
  transform: translateY(1px) scale(0.996);
}
.card-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: start;
  margin-bottom: 18px;
}
.card-top h2 {
  font-size: 1.1em;
}
.status {
  border-radius: 999px;
  font-size: 0.75em;
  padding: 3px 9px;
  white-space: nowrap;
}
.status.green {
  background: rgba(34, 197, 94, 0.14);
  color: #86efac;
}
.status.yellow {
  background: rgba(234, 179, 8, 0.14);
  color: #fde68a;
}
.status.red {
  background: rgba(239, 68, 68, 0.14);
  color: #fca5a5;
}
dl {
  display: grid;
  gap: 12px;
}
dt {
  color: var(--muted);
  font-size: 0.78em;
  text-transform: uppercase;
}
dd {
  color: var(--text);
  font-size: 0.95em;
}
.error {
  color: #fca5a5;
  margin-bottom: 20px;
}
@media (max-width: 720px) {
  header {
    align-items: flex-start;
    flex-direction: column;
  }
  .actions {
    flex-wrap: wrap;
  }
}
</style>
