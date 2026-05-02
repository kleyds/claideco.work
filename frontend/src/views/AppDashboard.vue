<template>
  <div class="container app-page">
    <header>
      <div>
        <p class="eyebrow">Workspace</p>
        <h1>Clients</h1>
      </div>
      <div class="actions">
        <router-link to="/app/clients/new" class="primary">New client</router-link>
        <button type="button" @click="logout">Log out</button>
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
            <dd>0</dd>
          </div>
          <div>
            <dt>Unreconciled bank entries</dt>
            <dd>0</dd>
          </div>
          <div>
            <dt>Missing 2307s</dt>
            <dd>0</dd>
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
const loading = ref(true)
const error = ref('')

const openWorkCount = computed(() => 0)

onMounted(loadDashboard)

async function loadDashboard() {
  try {
    const [me, clientData] = await Promise.all([
      apiFetch('/auth/me'),
      apiFetch('/clients'),
    ])
    user.value = me.user
    clients.value = clientData.clients
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

function logout() {
  clearToken()
  router.push('/login')
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

function deadlineStatus() {
  return 'green'
}

function deadlineLabel() {
  return 'On track'
}
</script>

<style scoped>
.app-page {
  padding: 32px 24px 64px;
}
header,
.actions {
  display: flex;
  gap: 16px;
  align-items: center;
}
header {
  justify-content: space-between;
  margin-bottom: 28px;
}
.eyebrow {
  color: var(--accent-hover);
  font-size: 0.78em;
  font-weight: 700;
  margin-bottom: 4px;
  text-transform: uppercase;
}
button,
.primary {
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text);
  cursor: pointer;
  font: inherit;
  padding: 10px 14px;
}
.primary {
  background: var(--accent);
  border-color: var(--accent);
  color: white;
  font-weight: 600;
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
  border-color: var(--accent);
  color: var(--text);
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
