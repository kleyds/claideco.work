<template>
  <div class="container compliance-page">
    <header>
      <div>
        <p class="eyebrow">BIR Compliance</p>
        <h1>{{ client?.name || 'Compliance' }}</h1>
      </div>
      <router-link :to="`/app/clients/${clientId}`">Back to client</router-link>
    </header>

    <p v-if="error" class="error">{{ error }}</p>

    <section class="card">
      <header>
        <p class="eyebrow">Quarterly</p>
        <h2>Summary List of Purchases (SLSP)</h2>
        <p>Aggregates approved expense receipts per supplier TIN for the selected quarter. Pair with BIR Form 2550Q.</p>
      </header>
      <div class="row">
        <label>
          Quarter
          <select v-model="slspQuarter">
            <option v-for="quarter in quarters" :key="quarter" :value="quarter">{{ quarter }}</option>
          </select>
        </label>
        <button type="button" @click="downloadSlsp" :disabled="busy.slsp">
          {{ busy.slsp ? 'Preparing...' : 'Download SLSP CSV' }}
        </button>
      </div>
    </section>

    <section class="card">
      <header>
        <p class="eyebrow">Quarterly</p>
        <h2>Summary Alphalist of Withholding Taxes (SAWT)</h2>
        <p>Lists every reconciliation flagged for a Form 2307 in the quarter, with computed withheld amount and ATC.</p>
      </header>
      <div class="row">
        <label>
          Quarter
          <select v-model="sawtQuarter">
            <option v-for="quarter in quarters" :key="quarter" :value="quarter">{{ quarter }}</option>
          </select>
        </label>
        <button type="button" @click="downloadSawt" :disabled="busy.sawt">
          {{ busy.sawt ? 'Preparing...' : 'Download SAWT CSV' }}
        </button>
      </div>
    </section>

    <section class="card">
      <header>
        <p class="eyebrow">Monthly</p>
        <h2>4-Column Journal</h2>
        <p>Date, Particulars, PR, Debit, Credit. One entry per approved receipt with input VAT split out where applicable.</p>
      </header>
      <div class="row">
        <label>
          Month
          <input v-model="journalMonth" type="month" />
        </label>
        <button type="button" @click="downloadJournal" :disabled="busy.journal">
          {{ busy.journal ? 'Preparing...' : 'Download Journal CSV' }}
        </button>
      </div>
    </section>

    <section class="card">
      <header>
        <p class="eyebrow">BIR Calendar</p>
        <h2>Upcoming Deadlines</h2>
        <p>Standard filing dates for the next 120 days. Verify against your client's specific tax type and registered forms.</p>
      </header>
      <div v-if="loadingDeadlines" class="empty">Loading deadlines...</div>
      <table v-else-if="deadlines.length">
        <thead>
          <tr>
            <th>Form</th>
            <th>Description</th>
            <th>Covers</th>
            <th>Due</th>
            <th>Days left</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in deadlines" :key="`${item.form}-${item.due}`" :class="urgencyClass(item.due)">
            <td><strong>{{ item.form }}</strong></td>
            <td>{{ item.label }}</td>
            <td>{{ item.covers }}</td>
            <td>{{ item.due }}</td>
            <td>{{ daysUntil(item.due) }}</td>
          </tr>
        </tbody>
      </table>
      <div v-else class="empty">No deadlines in the next 120 days.</div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { API_BASE_URL, apiFetch, clearToken, getToken } from '../api'

const route = useRoute()
const clientId = route.params.id

const client = ref(null)
const error = ref('')
const deadlines = ref([])
const loadingDeadlines = ref(false)

const today = new Date()
const currentYear = today.getFullYear()
const currentQuarter = Math.floor(today.getMonth() / 3) + 1
const defaultQuarter = `${currentYear}-Q${currentQuarter}`
const defaultMonth = `${currentYear}-${String(today.getMonth() + 1).padStart(2, '0')}`

const slspQuarter = ref(defaultQuarter)
const sawtQuarter = ref(defaultQuarter)
const journalMonth = ref(defaultMonth)
const busy = reactive({ slsp: false, sawt: false, journal: false })

const quarters = computed(() => {
  const list = []
  for (let yearOffset = 0; yearOffset >= -1; yearOffset--) {
    const year = currentYear + yearOffset
    for (let quarter = 4; quarter >= 1; quarter--) {
      list.push(`${year}-Q${quarter}`)
    }
  }
  return list
})

onMounted(async () => {
  await Promise.all([loadClient(), loadDeadlines()])
})

async function loadClient() {
  try {
    client.value = await apiFetch(`/clients/${clientId}`)
  } catch (err) {
    handleError(err)
  }
}

async function loadDeadlines() {
  loadingDeadlines.value = true
  try {
    const data = await apiFetch(`/clients/${clientId}/compliance/deadlines`)
    deadlines.value = data.deadlines || []
  } catch (err) {
    handleError(err)
  } finally {
    loadingDeadlines.value = false
  }
}

async function downloadSlsp() {
  await downloadCsv('slsp', `/clients/${clientId}/exports/slsp?quarter=${slspQuarter.value}`,
    `slsp-${clientId}-${slspQuarter.value}.csv`)
}

async function downloadSawt() {
  await downloadCsv('sawt', `/clients/${clientId}/exports/sawt?quarter=${sawtQuarter.value}`,
    `sawt-${clientId}-${sawtQuarter.value}.csv`)
}

async function downloadJournal() {
  await downloadCsv('journal', `/clients/${clientId}/exports/journal?month=${journalMonth.value}`,
    `journal-${clientId}-${journalMonth.value}.csv`)
}

async function downloadCsv(key, path, filename) {
  error.value = ''
  busy[key] = true
  try {
    const res = await fetch(`${API_BASE_URL}${path}`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    })
    if (!res.ok) {
      const data = await res.json().catch(() => null)
      throw new Error(data?.detail || 'Export failed')
    }
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  } catch (err) {
    handleError(err)
  } finally {
    busy[key] = false
  }
}

function daysUntil(iso) {
  const due = new Date(`${iso}T00:00:00`)
  const start = new Date()
  start.setHours(0, 0, 0, 0)
  return Math.round((due - start) / (1000 * 60 * 60 * 24))
}

function urgencyClass(iso) {
  const days = daysUntil(iso)
  if (days <= 7) return 'urgent'
  if (days <= 30) return 'soon'
  return ''
}

function handleError(err) {
  if (err.message?.includes('credentials')) {
    clearToken()
  }
  error.value = err.message || String(err)
}
</script>

<style scoped>
.compliance-page {
  display: grid;
  gap: 1.5rem;
}
.compliance-page > header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}
.eyebrow {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 0.75rem;
  color: var(--muted, #6b7280);
  margin: 0 0 0.25rem;
}
.card {
  background: var(--surface, #fff);
  border: 1px solid var(--border, #e5e7eb);
  border-radius: 12px;
  padding: 1.25rem 1.5rem;
  display: grid;
  gap: 1rem;
}
.card > header h2 {
  margin: 0 0 0.25rem;
}
.card > header p {
  margin: 0;
  color: var(--muted, #6b7280);
}
.row {
  display: flex;
  flex-wrap: wrap;
  align-items: end;
  gap: 1rem;
}
.row label {
  display: flex;
  flex-direction: column;
  font-size: 0.85rem;
  gap: 0.25rem;
}
.row select,
.row input[type='month'] {
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--border, #d1d5db);
  border-radius: 8px;
  min-width: 12rem;
}
.row button {
  padding: 0.55rem 1rem;
}
table {
  width: 100%;
  border-collapse: collapse;
}
th,
td {
  padding: 0.55rem 0.75rem;
  text-align: left;
  border-bottom: 1px solid var(--border, #e5e7eb);
}
tr.urgent {
  background: rgba(239, 68, 68, 0.08);
}
tr.soon {
  background: rgba(234, 179, 8, 0.08);
}
.empty {
  color: var(--muted, #6b7280);
  font-style: italic;
}
.error {
  color: #b91c1c;
}
</style>
