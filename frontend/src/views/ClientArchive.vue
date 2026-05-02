<template>
  <div class="container archive-page">
    <header>
      <div>
        <p class="eyebrow">Archive</p>
        <h1>{{ client?.name || 'Receipts' }}</h1>
      </div>
      <router-link :to="`/app/clients/${clientId}`">Back to client</router-link>
    </header>

    <section class="filters">
      <label>
        Month
        <input v-model="filters.month" type="month" />
      </label>
      <label>
        Vendor
        <input v-model="filters.vendor" type="search" placeholder="Vendor name" />
      </label>
      <label>
        Document type
        <select v-model="filters.doc_type">
          <option value="">All</option>
          <option value="official_receipt">Official receipt</option>
          <option value="sales_invoice">Sales invoice</option>
          <option value="gcash">GCash</option>
          <option value="maya">Maya</option>
          <option value="bank_statement">Bank statement</option>
          <option value="other">Other</option>
        </select>
      </label>
      <label>
        VAT type
        <select v-model="filters.vat_type">
          <option value="">All</option>
          <option value="vatable">Vatable</option>
          <option value="zero_rated">Zero-rated</option>
          <option value="exempt">Exempt</option>
          <option value="non_vat">Non-VAT</option>
        </select>
      </label>
      <label>
        Min amount
        <input v-model="filters.min_total" type="number" step="0.01" />
      </label>
      <label>
        Max amount
        <input v-model="filters.max_total" type="number" step="0.01" />
      </label>
      <div class="filter-actions">
        <button type="button" @click="loadArchive">Apply</button>
        <button type="button" class="secondary" @click="resetFilters">Reset</button>
      </div>
    </section>

    <p v-if="error" class="error">{{ error }}</p>

    <section class="summary">
      <div>
        <span>Approved receipts</span>
        <strong>{{ receipts.length }}</strong>
      </div>
      <div>
        <span>Total amount</span>
        <strong>{{ formatAmount(totalAmount) }}</strong>
      </div>
      <div>
        <span>Low confidence</span>
        <strong>{{ lowConfidenceCount }}</strong>
      </div>
    </section>

    <section class="export-panel">
      <div>
        <p class="eyebrow">Export</p>
        <h2>Download approved receipts</h2>
        <p>Exports use the same filters currently applied to the archive.</p>
      </div>
      <div class="export-actions">
        <select v-model="exportFormat" aria-label="Export format">
          <option value="generic">Generic CSV</option>
          <option value="qbo">QuickBooks CSV</option>
          <option value="xero">Xero CSV</option>
        </select>
        <button type="button" @click="downloadExport">Download CSV</button>
      </div>
    </section>

    <section class="archive-list">
      <div class="section-head">
        <h2>Approved documents</h2>
        <router-link :to="`/app/clients/${clientId}/review`">Open review queue</router-link>
      </div>

      <div v-if="loading" class="empty">Loading archive...</div>
      <div v-else-if="receipts.length === 0" class="empty">No approved receipts match these filters.</div>
      <table v-else>
        <thead>
          <tr>
            <th>Date</th>
            <th>Vendor</th>
            <th>TIN</th>
            <th>Reference</th>
            <th>Doc type</th>
            <th>VAT</th>
            <th>Total</th>
            <th>Confidence</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="receipt in receipts" :key="receipt.id">
            <td>{{ receipt.data?.date || '-' }}</td>
            <td>
              <strong>{{ receipt.data?.vendor || receipt.original_name || `Receipt #${receipt.id}` }}</strong>
              <span>{{ receipt.original_name }}</span>
            </td>
            <td>{{ receipt.data?.vendor_tin || '-' }}</td>
            <td>{{ receipt.data?.or_number || receipt.data?.si_number || '-' }}</td>
            <td>{{ label(receipt.data?.doc_type) }}</td>
            <td>{{ label(receipt.data?.vat_type) }}</td>
            <td>{{ formatAmount(receipt.data?.total, receipt.data?.currency) }}</td>
            <td>
              <span :class="['confidence', confidenceClass(receipt.data?.confidence)]">
                {{ formatConfidence(receipt.data?.confidence) }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { API_BASE_URL, apiFetch, clearToken, getToken } from '../api'

const route = useRoute()
const router = useRouter()
const clientId = route.params.id
const client = ref(null)
const receipts = ref([])
const loading = ref(true)
const error = ref('')
const exportFormat = ref('generic')
const filters = reactive(defaultFilters())

const totalAmount = computed(() =>
  receipts.value.reduce((sum, receipt) => sum + Number(receipt.data?.total || 0), 0)
)
const lowConfidenceCount = computed(() =>
  receipts.value.filter((receipt) => receipt.data?.confidence !== null && receipt.data?.confidence < 0.9).length
)

onMounted(async () => {
  try {
    client.value = await apiFetch(`/clients/${clientId}`)
    await loadArchive()
  } catch (err) {
    handleError(err)
  }
})

function defaultFilters() {
  return {
    month: '',
    vendor: '',
    doc_type: '',
    vat_type: '',
    min_total: '',
    max_total: '',
  }
}

async function loadArchive() {
  loading.value = true
  error.value = ''
  try {
    const params = buildFilterParams()
    params.set('status', 'approved')
    const data = await apiFetch(`/clients/${clientId}/receipts?${params.toString()}`)
    receipts.value = data.receipts
  } catch (err) {
    handleError(err)
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  Object.assign(filters, defaultFilters())
  loadArchive()
}

async function downloadExport() {
  error.value = ''
  try {
    const params = buildFilterParams()
    params.set('format', exportFormat.value)
    const res = await fetch(`${API_BASE_URL}/clients/${clientId}/export?${params.toString()}`, {
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
    link.download = exportFilename()
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  } catch (err) {
    handleError(err)
  }
}

function buildFilterParams() {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value !== '') params.set(key, value)
  }
  return params
}

function exportFilename() {
  const month = filters.month || 'all'
  return `pesobooks-${clientId}-${exportFormat.value}-${month}.csv`
}

function handleError(err) {
  if (err.message.includes('credentials')) {
    clearToken()
    router.push('/login')
    return
  }
  error.value = err.message
}

function label(value) {
  if (!value) return '-'
  return value.replaceAll('_', ' ')
}

function formatAmount(value, currency = 'PHP') {
  if (value === null || value === undefined) return '-'
  return new Intl.NumberFormat('en-PH', {
    style: 'currency',
    currency: currency || 'PHP',
  }).format(value)
}

function formatConfidence(value) {
  if (value === null || value === undefined) return '-'
  return `${Math.round(value * 100)}%`
}

function confidenceClass(value) {
  if (value === null || value === undefined) return 'unknown'
  if (value < 0.75) return 'low'
  if (value < 0.9) return 'medium'
  return 'high'
}
</script>

<style scoped>
.archive-page {
  padding: 32px 24px 64px;
}
header {
  align-items: center;
  display: flex;
  gap: 20px;
  justify-content: space-between;
  margin-bottom: 24px;
}
.eyebrow {
  color: var(--accent-hover);
  font-size: 0.78em;
  font-weight: 700;
  margin-bottom: 4px;
  text-transform: uppercase;
}
.filters,
.summary,
.export-panel,
.archive-list {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 18px;
}
.filters {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 14px;
  margin-bottom: 18px;
}
label {
  color: var(--muted);
  display: grid;
  gap: 6px;
  font-size: 0.88em;
}
input,
select {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text);
  font: inherit;
  padding: 10px 12px;
}
.filter-actions {
  align-items: end;
  display: flex;
  gap: 8px;
}
button {
  background: var(--accent);
  border: 1px solid var(--accent);
  border-radius: 8px;
  color: white;
  cursor: pointer;
  font: inherit;
  font-weight: 600;
  padding: 10px 14px;
}
button.secondary {
  background: var(--surface-2);
  border-color: var(--border);
  color: var(--text);
}
.summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}
.summary div {
  border-right: 1px solid var(--border);
  padding-right: 16px;
}
.summary span {
  color: var(--muted);
  display: block;
  font-size: 0.82em;
  margin-bottom: 4px;
}
.summary strong {
  font-size: 1.1em;
}
.export-panel {
  align-items: center;
  display: flex;
  gap: 20px;
  justify-content: space-between;
  margin-bottom: 18px;
}
.export-panel h2 {
  font-size: 1.05em;
  margin-bottom: 4px;
}
.export-panel p {
  color: var(--muted);
  font-size: 0.92em;
}
.export-actions {
  display: flex;
  gap: 10px;
}
.section-head {
  align-items: center;
  display: flex;
  gap: 16px;
  justify-content: space-between;
  margin-bottom: 14px;
}
table {
  border-collapse: collapse;
  width: 100%;
}
th,
td {
  border-bottom: 1px solid var(--border);
  padding: 10px 8px;
  text-align: left;
  vertical-align: top;
}
th {
  color: var(--muted);
  font-size: 0.78em;
  text-transform: uppercase;
}
td span {
  color: var(--muted);
  display: block;
  font-size: 0.85em;
}
.confidence {
  border-radius: 999px;
  display: inline-flex;
  padding: 3px 8px;
}
.confidence.high {
  background: rgba(34, 197, 94, 0.14);
  color: #86efac;
}
.confidence.medium {
  background: rgba(250, 204, 21, 0.14);
  color: #fde68a;
}
.confidence.low {
  background: rgba(248, 113, 113, 0.14);
  color: #fca5a5;
}
.confidence.unknown {
  background: var(--surface-2);
  color: var(--muted);
}
.empty {
  color: var(--muted);
  padding: 18px 0;
}
.error {
  color: #fca5a5;
  margin-bottom: 18px;
}
@media (max-width: 760px) {
  header,
  .section-head,
  .export-panel {
    align-items: flex-start;
    flex-direction: column;
  }
  .export-actions {
    width: 100%;
  }
  .export-actions select,
  .export-actions button {
    flex: 1;
  }
  table {
    display: block;
    overflow-x: auto;
  }
}
</style>
