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
  padding: 16px 24px 64px;
}
.compliance-page > header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}
.eyebrow {
  text-transform: uppercase;
  letter-spacing: 0;
  font-size: 0.78em;
  font-weight: 700;
  color: var(--workflow-eyebrow);
  margin: 0 0 0.25rem;
}
.card {
  background: linear-gradient(180deg, var(--workflow-panel-strong), var(--workflow-panel));
  border: 1px solid var(--workflow-line);
  border-radius: 10px;
  box-shadow: var(--workflow-panel-shadow);
  padding: 1.25rem 1.5rem;
  display: grid;
  gap: 1rem;
}
.card:hover {
  border-color: rgba(147, 197, 253, 0.28);
}
.card > header h2 {
  margin: 0 0 0.25rem;
  font-size: 1.08em;
}
.card > header p {
  margin: 0;
  color: var(--workflow-muted);
}
.card > header .eyebrow {
  color: var(--workflow-eyebrow);
  margin-bottom: 0.25rem;
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
  color: var(--workflow-muted);
  font-size: 0.85rem;
  gap: 0.25rem;
}
.row select,
.row input[type='month'] {
  background: var(--workflow-input);
  color: var(--workflow-text);
  font: inherit;
  padding: 0.58rem 0.75rem;
  border: 1px solid var(--workflow-line);
  border-radius: 8px;
  min-width: 12rem;
}
.row select:focus-visible,
.row input[type='month']:focus-visible {
  outline-color: var(--workflow-accent-2);
}
.row button {
  background: linear-gradient(135deg, var(--workflow-accent), #5b5df6);
  border: 1px solid transparent;
  border-radius: 8px;
  color: white;
  cursor: pointer;
  font: inherit;
  font-weight: 600;
  min-height: 42px;
  padding: 0.58rem 1rem;
}
.row button:hover:not(:disabled) {
  background: linear-gradient(135deg, #8b5cf6, #6366f1);
}
.row button:disabled {
  cursor: wait;
  opacity: 0.7;
}
table {
  background: var(--workflow-input);
  border: 1px solid var(--workflow-soft-line);
  border-radius: 8px;
  border-collapse: separate;
  border-spacing: 0;
  overflow: hidden;
  width: 100%;
}
th,
td {
  padding: 0.55rem 0.75rem;
  text-align: left;
  border-bottom: 1px solid var(--workflow-soft-line);
}
th {
  color: var(--workflow-muted);
  font-size: 0.78em;
  text-transform: uppercase;
}
td {
  color: var(--workflow-text);
}
tbody tr:last-child td {
  border-bottom: 0;
}
tbody tr:hover {
  background: rgba(148, 163, 184, 0.05);
}
tr.urgent {
  background: rgba(248, 113, 113, 0.1);
}
tr.soon {
  background: rgba(250, 204, 21, 0.09);
}
.empty {
  color: var(--workflow-muted);
}
.error {
  color: #fda4af;
}
@media (max-width: 760px) {
  .compliance-page > header,
  .row {
    align-items: flex-start;
    flex-direction: column;
  }
  .row select,
  .row input[type='month'],
  .row button {
    width: 100%;
  }
  table {
    display: block;
    overflow-x: auto;
  }
}
</style>
