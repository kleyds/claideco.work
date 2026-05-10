<template>
  <div class="container recon-page">
    <header>
      <div>
        <p class="eyebrow">Reconciliation</p>
        <h1>{{ client?.name || 'Bank feed' }}</h1>
      </div>
      <router-link :to="`/app/clients/${clientId}`">Back to client</router-link>
    </header>

    <section class="import-panel">
      <div>
        <p class="eyebrow">Bank feed</p>
        <h2
          class="title-row hover-tooltip"
          tabindex="0"
          aria-label="Import bank CSV. Supports common Date, Description, Amount, Debit/Credit, and Reference columns from PH bank exports."
          data-tooltip="Supports common Date, Description, Amount, Debit/Credit, and Reference columns from PH bank exports."
        >
          Import CSV
          <span class="info-tooltip" aria-hidden="true">?</span>
        </h2>
      </div>
      <form @submit.prevent="importCsv">
        <select v-model="bankTemplate" aria-label="Bank CSV template">
          <option v-for="template in bankTemplates" :key="template.value" :value="template.value">
            {{ template.label }}
          </option>
        </select>
        <input v-model="bankName" type="text" placeholder="Bank name, e.g. BPI" />
        <label :class="['file-picker', { selected: selectedFile }]">
          <input ref="fileInput" type="file" accept=".csv,text/csv" @change="onFileChange" />
          <span>Choose CSV</span>
          <strong>{{ filePickerLabel }}</strong>
        </label>
        <button type="submit" :disabled="uploading || !selectedFile">
          {{ uploading ? 'Importing...' : 'Import CSV' }}
        </button>
      </form>
      <p v-if="message" class="notice">{{ message }}</p>
      <div v-if="importSummary" class="import-summary">
        <span>{{ importSummary.imported }} imported</span>
        <span>{{ importSummary.skipped_duplicates }} duplicate{{ importSummary.skipped_duplicates === 1 ? '' : 's' }} skipped</span>
        <span>{{ importSummary.skipped_errors }} error{{ importSummary.skipped_errors === 1 ? '' : 's' }}</span>
      </div>
      <ul v-if="importSummary?.errors?.length" class="import-errors">
        <li v-for="item in importSummary.errors" :key="item">{{ item }}</li>
      </ul>
    </section>

    <p v-if="error" class="error">{{ error }}</p>

    <section class="transaction-list">
      <div class="section-head">
        <div>
          <p class="eyebrow">Open items</p>
          <h2>Unreconciled bank entries</h2>
        </div>
        <div class="toolbar">
          <input v-model="bulkCategory" type="text" placeholder="Category / CoA code" />
          <button type="button" :disabled="selectedTransactions.length === 0 || !bulkCategory" @click="applyCategory">
            Categorize selected
          </button>
          <button type="button" @click="loadTransactions">Refresh</button>
        </div>
      </div>

      <div v-if="loading" class="empty">Loading bank transactions...</div>
      <div v-else-if="transactions.length === 0" class="empty">No unreconciled bank entries yet.</div>
      <div v-else class="rows">
        <article v-for="transaction in transactions" :key="transaction.id" class="transaction">
          <label class="select-row">
            <input v-model="selectedTransactions" type="checkbox" :value="transaction.id" />
          </label>
          <div class="tx-main">
            <span>{{ transaction.transaction_date || '-' }}</span>
            <h3>{{ transaction.description }}</h3>
            <p>
              {{ transaction.bank_name || 'Bank' }}
              {{ transaction.reference ? `- ${transaction.reference}` : '' }}
              {{ transaction.category ? `- ${transaction.category}` : '' }}
            </p>
          </div>
          <div class="tx-amount">
            <strong>{{ formatAmount(transaction.amount) }}</strong>
            <span>{{ transaction.direction }}</span>
          </div>
          <button type="button" @click="loadMatches(transaction.id)">Find matches</button>
        </article>
      </div>
    </section>

    <section v-if="matchResult" class="matches">
      <div class="section-head">
        <h2>Suggested matches</h2>
        <span>{{ matchResult.transaction.description }}</span>
      </div>
      <div v-if="matchResult.suggestions.length === 0" class="empty">No strong matches found.</div>
      <article v-for="suggestion in matchResult.suggestions" :key="suggestion.receipt.id" class="match-card">
        <div>
          <h3>{{ suggestion.receipt.data?.vendor || suggestion.receipt.original_name }}</h3>
          <p>
            {{ suggestion.receipt.data?.date || '-' }}
            - {{ formatAmount(suggestion.receipt.data?.total, suggestion.receipt.data?.currency) }}
          </p>
          <p class="reasons">{{ suggestion.reasons.join(', ') }}</p>
        </div>
        <div class="match-score">
          <strong>{{ Math.round(suggestion.score * 100) }}%</strong>
          <span v-if="suggestion.requires_2307">Needs 2307</span>
          <button type="button" @click="acceptMatch(suggestion)">Accept match</button>
        </div>
      </article>

      <div class="manual-match">
        <div>
          <h3>Manual receipt search</h3>
          <p>Search approved receipts by vendor, file name, OR number, or SI number.</p>
        </div>
        <form @submit.prevent="searchManualMatches">
          <input v-model="manualSearchQuery" type="text" placeholder="Vendor, OR/SI, file name" />
          <button type="submit" :disabled="loadingManualMatches">
            {{ loadingManualMatches ? 'Searching...' : 'Search receipts' }}
          </button>
        </form>
      </div>

      <div v-if="manualMatchResults.length" class="manual-results">
        <article v-for="suggestion in manualMatchResults" :key="suggestion.receipt.id" class="match-card">
          <div>
            <h3>{{ suggestion.receipt.data?.vendor || suggestion.receipt.original_name }}</h3>
            <p>
              {{ suggestion.receipt.data?.date || '-' }}
              - {{ formatAmount(suggestion.receipt.data?.total, suggestion.receipt.data?.currency) }}
            </p>
            <p class="reasons">{{ suggestion.reasons.join(', ') }}</p>
          </div>
          <div class="match-score">
            <strong>{{ Math.round(suggestion.score * 100) }}%</strong>
            <span v-if="suggestion.requires_2307">Needs 2307</span>
            <button type="button" @click="acceptMatch(suggestion)">Accept match</button>
          </div>
        </article>
      </div>
      <div v-else-if="manualSearchRan && !loadingManualMatches" class="empty">No approved receipts matched that search.</div>
    </section>

    <section class="reconciled-panel">
      <div class="section-head">
        <div>
          <p class="eyebrow">Matched</p>
          <h2
            class="title-row hover-tooltip"
            tabindex="0"
            aria-label="Reconciled transactions. Matched bank entries and their approved receipts."
            data-tooltip="Matched bank entries and their approved receipts."
          >
            Reconciled transactions
            <span class="info-tooltip" aria-hidden="true">?</span>
          </h2>
        </div>
        <button type="button" @click="loadReconciledItems">Refresh</button>
      </div>

      <div v-if="loadingReconciled" class="empty">Loading reconciled transactions...</div>
      <div v-else-if="reconciledItems.length === 0" class="empty">No reconciled transactions yet.</div>
      <div v-else class="reconciled-rows">
        <article v-for="item in reconciledItems" :key="item.id" class="reconciled-card">
          <div class="reconciled-main">
            <span>{{ item.bank_transaction.transaction_date || item.receipt.data?.date || '-' }}</span>
            <h3>{{ item.bank_transaction.description }}</h3>
            <p>
              {{ item.receipt.data?.vendor || item.receipt.original_name || `Receipt #${item.receipt_id}` }}
              - {{ formatAmount(item.receipt.data?.total, item.receipt.data?.currency) }}
            </p>
          </div>
          <div class="tx-amount">
            <strong>{{ formatAmount(item.bank_transaction.amount) }}</strong>
            <span>{{ Math.round((item.match_score || 0) * 100) }}% match</span>
          </div>
          <div class="reconciled-actions">
            <span v-if="item.requires_2307 === 'true'" :class="['status-pill', item.form_2307_status]">
              2307 {{ statusLabel(item.form_2307_status) }}
            </span>
            <button type="button" :disabled="undoingReconciliation[item.id]" @click="undoReconciliation(item)">
              {{ undoingReconciliation[item.id] ? 'Undoing...' : 'Undo match' }}
            </button>
          </div>
        </article>
      </div>
    </section>

    <section class="form-2307-panel">
      <div class="section-head">
        <div>
          <p class="eyebrow">Certificates</p>
          <h2
            class="title-row hover-tooltip"
            tabindex="0"
            aria-label="Form 2307 follow-up. Withholding variance matches that need certificates."
            data-tooltip="Withholding variance matches that need certificates."
          >
            Form 2307 follow-up
            <span class="info-tooltip" aria-hidden="true">?</span>
          </h2>
        </div>
        <div class="toolbar">
          <select v-model="form2307StatusFilter" aria-label="Form 2307 status filter" @change="loadForm2307Items">
            <option value="">All statuses</option>
            <option v-for="status in form2307Statuses" :key="status" :value="status">
              {{ statusLabel(status) }}
            </option>
          </select>
          <button type="button" @click="loadForm2307Items">Refresh</button>
        </div>
      </div>

      <div v-if="loading2307" class="empty">Loading Form 2307 follow-ups...</div>
      <div v-else-if="form2307Items.length === 0" class="empty">No Form 2307 follow-ups yet.</div>
      <div v-else class="form-2307-rows">
        <article v-for="item in form2307Items" :key="item.id" class="form-2307-card">
          <div class="form-2307-main">
            <span>{{ item.receipt.data?.date || item.bank_transaction.transaction_date || '-' }}</span>
            <h3>{{ item.receipt.data?.vendor || item.receipt.original_name || `Receipt #${item.receipt_id}` }}</h3>
            <p>
              Invoice {{ formatAmount(item.receipt.data?.total, item.receipt.data?.currency) }}
              - Paid {{ formatAmount(item.bank_transaction.amount) }}
            </p>
            <p>
              {{ item.bank_transaction.description }}
              {{ item.bank_transaction.reference ? `- ${item.bank_transaction.reference}` : '' }}
            </p>
            <dl class="form-2307-timeline">
              <div>
                <dt>Requested</dt>
                <dd>{{ formatDateTime(item.form_2307_requested_at) }}</dd>
              </div>
              <div>
                <dt>Received</dt>
                <dd>{{ formatDateTime(item.form_2307_received_at) }}</dd>
              </div>
              <div>
                <dt>Attached</dt>
                <dd>{{ formatDateTime(item.form_2307_uploaded_at) }}</dd>
              </div>
            </dl>
          </div>

          <div class="form-2307-status">
            <span :class="['status-pill', item.form_2307_status]">{{ statusLabel(item.form_2307_status) }}</span>
            <select
              :value="item.form_2307_status"
              :disabled="updating2307[item.id]"
              aria-label="Form 2307 status"
              @change="updateForm2307Status(item, $event.target.value)"
            >
              <option
                v-for="status in form2307Statuses"
                :key="status"
                :value="status"
                :disabled="status === 'attached' && !item.has_form_2307_file"
              >
                {{ statusLabel(status) }}
              </option>
            </select>
          </div>

          <form class="form-2307-upload" @submit.prevent>
            <input
              type="file"
              accept="application/pdf,image/jpeg,image/png,image/webp"
              :disabled="uploading2307[item.id]"
              @change="uploadForm2307File(item, $event)"
            />
            <button
              v-if="item.has_form_2307_file"
              type="button"
              class="link-button"
              @click="openForm2307File(item)"
            >
              {{ item.form_2307_original_name || 'Open attached 2307' }}
            </button>
          </form>

          <form class="form-2307-notes" @submit.prevent="saveForm2307Notes(item)">
            <textarea
              v-model="item.form_2307_notes"
              rows="3"
              maxlength="2000"
              placeholder="Follow-up notes"
              :disabled="updating2307[item.id]"
            ></textarea>
            <button type="submit" :disabled="updating2307[item.id]">
              {{ updating2307[item.id] ? 'Saving...' : 'Save notes' }}
            </button>
          </form>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { apiFetch, apiFetchBlob, clearToken } from '../api'

const route = useRoute()
const router = useRouter()
const clientId = route.params.id
const client = ref(null)
const transactions = ref([])
const matchResult = ref(null)
const reconciledItems = ref([])
const form2307Items = ref([])
const manualMatchResults = ref([])
const manualSearchQuery = ref('')
const selectedFile = ref(null)
const selectedTransactions = ref([])
const fileInput = ref(null)
const bankName = ref('')
const bankTemplate = ref('generic')
const bulkCategory = ref('')
const form2307StatusFilter = ref('')
const importSummary = ref(null)
const loading = ref(true)
const loadingReconciled = ref(true)
const loading2307 = ref(true)
const loadingManualMatches = ref(false)
const uploading = ref(false)
const uploading2307 = ref({})
const updating2307 = ref({})
const undoingReconciliation = ref({})
const manualSearchRan = ref(false)
const error = ref('')
const message = ref('')
const form2307Statuses = ['missing', 'requested', 'received', 'attached']
const bankTemplates = [
  { value: 'generic', label: 'Generic CSV' },
  { value: 'bdo', label: 'BDO' },
  { value: 'bpi', label: 'BPI' },
  { value: 'metrobank', label: 'Metrobank' },
  { value: 'unionbank', label: 'UnionBank' },
]
const filePickerLabel = computed(() => selectedFile.value?.name || 'No file selected')

onMounted(async () => {
  try {
    client.value = await apiFetch(`/clients/${clientId}`)
    await Promise.all([loadTransactions(), loadReconciledItems(), loadForm2307Items()])
  } catch (err) {
    handleError(err)
  }
})

function onFileChange(event) {
  selectedFile.value = event.target.files?.[0] || null
  message.value = ''
  importSummary.value = null
}

async function importCsv() {
  if (!selectedFile.value) return
  uploading.value = true
  error.value = ''
  message.value = ''
  importSummary.value = null

  const body = new FormData()
  body.append('file', selectedFile.value)

  try {
    const params = new URLSearchParams({ bank_template: bankTemplate.value })
    if (bankName.value) params.set('bank_name', bankName.value)
    const data = await apiFetch(`/clients/${clientId}/bank/import?${params.toString()}`, {
      method: 'POST',
      body,
    })
    importSummary.value = data
    message.value = importMessage(data)
    selectedFile.value = null
    if (fileInput.value) fileInput.value.value = ''
    await loadTransactions()
  } catch (err) {
    handleError(err)
  } finally {
    uploading.value = false
  }
}

async function loadTransactions() {
  loading.value = true
  error.value = ''
  try {
    const data = await apiFetch(`/clients/${clientId}/bank/transactions?status=unreconciled`)
    transactions.value = data.transactions
    selectedTransactions.value = selectedTransactions.value.filter((id) =>
      transactions.value.some((transaction) => transaction.id === id)
    )
  } catch (err) {
    handleError(err)
  } finally {
    loading.value = false
  }
}

async function loadReconciledItems() {
  loadingReconciled.value = true
  error.value = ''
  try {
    const data = await apiFetch(`/clients/${clientId}/bank/reconciliations`)
    reconciledItems.value = data.reconciliations
  } catch (err) {
    handleError(err)
  } finally {
    loadingReconciled.value = false
  }
}

async function loadForm2307Items() {
  loading2307.value = true
  error.value = ''
  try {
    const params = new URLSearchParams({ requires_2307: 'true' })
    if (form2307StatusFilter.value) params.set('form_2307_status', form2307StatusFilter.value)
    const data = await apiFetch(`/clients/${clientId}/bank/reconciliations?${params.toString()}`)
    form2307Items.value = data.reconciliations
  } catch (err) {
    handleError(err)
  } finally {
    loading2307.value = false
  }
}

async function applyCategory() {
  error.value = ''
  message.value = ''
  try {
    const data = await apiFetch(`/clients/${clientId}/bank/transactions/category`, {
      method: 'PATCH',
      body: JSON.stringify({
        transaction_ids: selectedTransactions.value,
        category: bulkCategory.value,
      }),
    })
    message.value = `${data.updated} transaction${data.updated === 1 ? '' : 's'} categorized.`
    selectedTransactions.value = []
    bulkCategory.value = ''
    await loadTransactions()
  } catch (err) {
    handleError(err)
  }
}

async function loadMatches(transactionId) {
  error.value = ''
  manualMatchResults.value = []
  manualSearchQuery.value = ''
  manualSearchRan.value = false
  try {
    matchResult.value = await apiFetch(`/clients/${clientId}/bank/transactions/${transactionId}/matches`)
  } catch (err) {
    handleError(err)
  }
}

async function searchManualMatches() {
  if (!matchResult.value) return
  loadingManualMatches.value = true
  manualSearchRan.value = true
  error.value = ''
  try {
    const params = new URLSearchParams()
    if (manualSearchQuery.value.trim()) params.set('q', manualSearchQuery.value.trim())
    const query = params.toString() ? `?${params.toString()}` : ''
    const data = await apiFetch(
      `/clients/${clientId}/bank/transactions/${matchResult.value.transaction.id}/manual-matches${query}`
    )
    manualMatchResults.value = data.suggestions
  } catch (err) {
    handleError(err)
  } finally {
    loadingManualMatches.value = false
  }
}

async function acceptMatch(suggestion) {
  if (!matchResult.value) return
  error.value = ''
  message.value = ''
  try {
    await apiFetch(`/clients/${clientId}/bank/transactions/${matchResult.value.transaction.id}/reconcile`, {
      method: 'POST',
      body: JSON.stringify({
        receipt_id: suggestion.receipt.id,
        match_score: suggestion.score,
        requires_2307: suggestion.requires_2307,
      }),
    })
    message.value = suggestion.requires_2307
      ? 'Match accepted. This transaction needs Form 2307 follow-up.'
      : 'Match accepted.'
    matchResult.value = null
    manualMatchResults.value = []
    manualSearchQuery.value = ''
    manualSearchRan.value = false
    await refreshReconciliationWork()
  } catch (err) {
    handleError(err)
  }
}

async function undoReconciliation(item) {
  undoingReconciliation.value = { ...undoingReconciliation.value, [item.id]: true }
  error.value = ''
  message.value = ''
  try {
    await apiFetch(`/clients/${clientId}/bank/reconciliations/${item.id}`, {
      method: 'DELETE',
    })
    message.value = 'Match undone. Bank transaction returned to unreconciled.'
    await refreshReconciliationWork()
  } catch (err) {
    handleError(err)
  } finally {
    const next = { ...undoingReconciliation.value }
    delete next[item.id]
    undoingReconciliation.value = next
  }
}

async function refreshReconciliationWork() {
  await Promise.all([loadTransactions(), loadReconciledItems(), loadForm2307Items()])
}

async function updateForm2307Status(item, status) {
  if (status === item.form_2307_status) return
  updating2307.value = { ...updating2307.value, [item.id]: true }
  error.value = ''
  message.value = ''
  try {
    await apiFetch(`/clients/${clientId}/bank/reconciliations/${item.id}/2307`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    })
    message.value = `Form 2307 marked ${statusLabel(status).toLowerCase()}.`
    await Promise.all([loadForm2307Items(), loadReconciledItems()])
  } catch (err) {
    handleError(err)
  } finally {
    const next = { ...updating2307.value }
    delete next[item.id]
    updating2307.value = next
  }
}

async function uploadForm2307File(item, event) {
  const file = event.target.files?.[0]
  if (!file) return

  uploading2307.value = { ...uploading2307.value, [item.id]: true }
  error.value = ''
  message.value = ''

  const body = new FormData()
  body.append('file', file)

  try {
    await apiFetch(`/clients/${clientId}/bank/reconciliations/${item.id}/2307/file`, {
      method: 'POST',
      body,
    })
    message.value = 'Form 2307 attached.'
    event.target.value = ''
    await Promise.all([loadForm2307Items(), loadReconciledItems()])
  } catch (err) {
    handleError(err)
  } finally {
    const next = { ...uploading2307.value }
    delete next[item.id]
    uploading2307.value = next
  }
}

function importMessage(data) {
  const pieces = [`${data.imported} imported`]
  if (data.skipped_duplicates) {
    pieces.push(`${data.skipped_duplicates} duplicate${data.skipped_duplicates === 1 ? '' : 's'} skipped`)
  }
  if (data.skipped_errors) pieces.push(`${data.skipped_errors} row error${data.skipped_errors === 1 ? '' : 's'}`)
  return `Bank import complete: ${pieces.join(', ')}.`
}

async function saveForm2307Notes(item) {
  updating2307.value = { ...updating2307.value, [item.id]: true }
  error.value = ''
  message.value = ''
  try {
    await apiFetch(`/clients/${clientId}/bank/reconciliations/${item.id}/2307`, {
      method: 'PATCH',
      body: JSON.stringify({ notes: item.form_2307_notes || '' }),
    })
    message.value = 'Form 2307 notes saved.'
    await Promise.all([loadForm2307Items(), loadReconciledItems()])
  } catch (err) {
    handleError(err)
  } finally {
    const next = { ...updating2307.value }
    delete next[item.id]
    updating2307.value = next
  }
}

function handleError(err) {
  if (err.message.includes('credentials')) {
    clearToken()
    router.push('/login')
    return
  }
  error.value = err.message
}

async function openForm2307File(item) {
  error.value = ''
  try {
    const blob = await apiFetchBlob(
      `/clients/${clientId}/bank/reconciliations/${item.id}/2307/file`,
    )
    const url = URL.createObjectURL(blob)
    const opened = window.open(url, '_blank', 'noopener,noreferrer')
    if (!opened) {
      const link = document.createElement('a')
      link.href = url
      link.target = '_blank'
      link.rel = 'noopener noreferrer'
      link.download = item.form_2307_original_name || 'form-2307'
      document.body.appendChild(link)
      link.click()
      link.remove()
    }
    setTimeout(() => URL.revokeObjectURL(url), 60_000)
  } catch (err) {
    handleError(err)
  }
}

function statusLabel(status) {
  const labels = {
    missing: 'Missing',
    requested: 'Requested',
    received: 'Received',
    attached: 'Attached',
  }
  return labels[status] || 'Missing'
}

function formatAmount(value, currency = 'PHP') {
  if (value === null || value === undefined) return '-'
  return new Intl.NumberFormat('en-PH', {
    style: 'currency',
    currency: currency || 'PHP',
  }).format(value)
}

function formatDateTime(value) {
  if (!value) return '-'
  return new Intl.DateTimeFormat('en-PH', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}
</script>

<style scoped>
.recon-page {
  padding: 16px 24px 64px;
}
header {
  align-items: center;
  display: flex;
  gap: 20px;
  justify-content: space-between;
  margin-bottom: 24px;
}
.eyebrow {
  color: var(--workflow-eyebrow);
  font-size: 0.78em;
  font-weight: 700;
  letter-spacing: 0;
  margin-bottom: 4px;
  text-transform: uppercase;
}
.title-row {
  align-items: center;
  display: inline-flex;
  gap: 8px;
  min-width: 0;
}
.hover-tooltip {
  cursor: help;
  position: relative;
}
.hover-tooltip::after {
  background: #111827;
  border: 1px solid var(--workflow-line);
  border-radius: 8px;
  bottom: calc(100% + 8px);
  box-shadow: 0 14px 30px rgba(0, 0, 0, 0.3);
  color: var(--workflow-text);
  content: attr(data-tooltip);
  font-size: 0.78rem;
  font-weight: 500;
  left: 50%;
  line-height: 1.45;
  max-width: min(320px, calc(100vw - 48px));
  opacity: 0;
  padding: 8px 10px;
  pointer-events: none;
  position: absolute;
  text-align: left;
  text-transform: none;
  transform: translate(-50%, 4px);
  transition: opacity 0.14s ease, transform 0.14s ease;
  visibility: hidden;
  width: max-content;
  z-index: 20;
}
.hover-tooltip:hover::after,
.hover-tooltip:focus-visible::after {
  opacity: 1;
  transform: translate(-50%, 0);
  visibility: visible;
}
.hover-tooltip:focus-visible {
  outline: 2px solid var(--workflow-accent-2);
  outline-offset: 4px;
}
.info-tooltip {
  align-items: center;
  background: rgba(124, 58, 237, 0.14);
  border: 1px solid rgba(167, 139, 250, 0.32);
  border-radius: 999px;
  color: #c4b5fd;
  display: inline-flex;
  flex: 0 0 auto;
  font-size: 0.7rem;
  font-weight: 800;
  height: 18px;
  justify-content: center;
  line-height: 1;
  width: 18px;
}
.hover-tooltip:hover .info-tooltip,
.hover-tooltip:focus-visible .info-tooltip {
  background: rgba(20, 184, 166, 0.14);
  border-color: rgba(45, 212, 191, 0.48);
  color: #99f6e4;
}
.import-panel,
.transaction-list,
.matches,
.reconciled-panel,
.form-2307-panel {
  background: linear-gradient(180deg, var(--workflow-panel-strong), var(--workflow-panel));
  border: 1px solid var(--workflow-line);
  border-radius: 10px;
  box-shadow: var(--workflow-panel-shadow);
  padding: 20px;
}
.import-panel {
  align-items: center;
  display: grid;
  grid-template-columns: minmax(180px, 220px) minmax(0, 1fr);
  gap: 28px;
  margin-bottom: 20px;
  min-height: 92px;
  overflow: hidden;
}
.import-panel h2,
.transaction-list h2,
.matches h2,
.reconciled-panel h2,
.form-2307-panel h2 {
  font-size: 1.08em;
  font-weight: 700;
  line-height: 1.25;
}
.import-panel form {
  display: grid;
  grid-template-columns: minmax(126px, 150px) minmax(150px, 1fr) minmax(210px, 1.35fr) minmax(112px, 116px);
  gap: 10px;
  justify-content: stretch;
  min-width: 0;
  width: 100%;
}
.import-panel form > * {
  min-width: 0;
}
.import-panel input,
.import-panel select,
.import-panel button {
  min-height: 48px;
}
.import-panel button {
  min-width: 0;
  padding-inline: 12px;
  white-space: nowrap;
  width: 100%;
}
.file-picker {
  align-items: center;
  background: var(--workflow-input);
  border: 1px solid var(--workflow-line);
  border-radius: 8px;
  color: var(--workflow-muted);
  display: grid;
  gap: 10px;
  grid-template-columns: auto minmax(0, 1fr);
  min-height: 48px;
  min-width: 0;
  padding: 6px;
}
.file-picker:hover,
.file-picker.selected {
  border-color: rgba(20, 184, 166, 0.7);
}
.file-picker input {
  display: none;
}
.file-picker span {
  background: rgba(148, 163, 184, 0.12);
  border: 1px solid var(--workflow-soft-line);
  border-radius: 6px;
  color: var(--workflow-text);
  cursor: pointer;
  font-size: 0.92em;
  font-weight: 600;
  padding: 7px 10px;
  white-space: nowrap;
}
.file-picker strong {
  color: var(--workflow-muted);
  font-size: 0.9em;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.file-picker.selected strong {
  color: var(--workflow-text);
}
.import-panel p,
.empty,
.transaction p,
.reconciled-card p,
.form-2307-card p,
.manual-match p,
.section-head span,
.reasons {
  color: var(--workflow-muted);
}
.import-panel .eyebrow,
.transaction-list .section-head .eyebrow,
.reconciled-panel .section-head .eyebrow,
.form-2307-panel .section-head .eyebrow {
  color: var(--workflow-eyebrow);
  margin-top: 0;
}
form,
.toolbar {
  align-items: end;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: flex-end;
}
input,
select,
textarea {
  background: var(--workflow-input);
  border: 1px solid var(--workflow-line);
  border-radius: 8px;
  color: var(--workflow-text);
  font: inherit;
  padding: 10px 12px;
}
input:focus-visible,
select:focus-visible,
textarea:focus-visible {
  outline-color: var(--workflow-accent-2);
}
textarea {
  min-width: 240px;
  resize: vertical;
}
button {
  background: linear-gradient(135deg, var(--workflow-accent), #5b5df6);
  border: 1px solid transparent;
  border-radius: 8px;
  color: white;
  cursor: pointer;
  font: inherit;
  font-weight: 600;
  padding: 10px 14px;
}
button:hover:not(:disabled) {
  background: linear-gradient(135deg, #8b5cf6, #6366f1);
}
button:disabled {
  cursor: wait;
  opacity: 0.7;
}
.notice {
  color: #86efac !important;
  grid-column: 1 / -1;
}
.import-summary {
  color: var(--workflow-muted);
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  grid-column: 1 / -1;
}
.import-summary span {
  background: var(--workflow-input);
  border: 1px solid var(--workflow-soft-line);
  border-radius: 999px;
  padding: 4px 9px;
}
.import-errors {
  color: #fca5a5;
  font-size: 0.9em;
  grid-column: 1 / -1;
  list-style-position: inside;
}
.section-head {
  align-items: center;
  display: flex;
  gap: 16px;
  justify-content: space-between;
  margin-bottom: 14px;
}
.section-head button,
.transaction button,
.reconciled-actions button {
  background: rgba(148, 163, 184, 0.08);
  border-color: var(--workflow-line);
  color: var(--workflow-text);
}
.section-head button:hover:not(:disabled),
.transaction button:hover:not(:disabled),
.reconciled-actions button:hover:not(:disabled) {
  background: rgba(148, 163, 184, 0.14);
  border-color: rgba(167, 139, 250, 0.52);
}
.rows {
  display: grid;
  gap: 10px;
}
.transaction,
.match-card,
.reconciled-card,
.form-2307-card {
  align-items: center;
  background: var(--workflow-input);
  border: 1px solid var(--workflow-soft-line);
  border-radius: 8px;
  display: grid;
  gap: 16px;
  grid-template-columns: auto 1fr auto auto;
  padding: 14px;
}
.transaction h3,
.match-card h3,
.reconciled-card h3,
.form-2307-card h3 {
  font-size: 1em;
  font-weight: 700;
}
.transaction:hover,
.match-card:hover,
.reconciled-card:hover,
.form-2307-card:hover {
  border-color: rgba(147, 197, 253, 0.28);
}
.select-row {
  display: grid;
  place-items: center;
}
.select-row input {
  height: 18px;
  width: 18px;
}
.tx-main span {
  color: var(--workflow-muted);
  font-size: 0.82em;
}
.tx-amount {
  display: grid;
  justify-items: end;
}
.tx-amount span {
  color: var(--workflow-muted);
  font-size: 0.82em;
}
.matches {
  margin-top: 20px;
}
.manual-match {
  align-items: end;
  border-top: 1px solid var(--workflow-line);
  display: grid;
  gap: 14px;
  grid-template-columns: 1fr auto;
  margin-top: 16px;
  padding-top: 16px;
}
.manual-match h3 {
  font-size: 1em;
  margin-bottom: 4px;
}
.manual-results {
  display: grid;
  gap: 10px;
  margin-top: 10px;
}
.reconciled-panel {
  margin-top: 20px;
}
.reconciled-panel .section-head p {
  color: var(--workflow-muted);
  margin-top: 4px;
}
.reconciled-rows {
  display: grid;
  gap: 10px;
}
.reconciled-card {
  grid-template-columns: 1fr auto auto;
}
.reconciled-main span {
  color: var(--workflow-muted);
  font-size: 0.82em;
}
.reconciled-actions {
  display: grid;
  gap: 8px;
  justify-items: end;
}
.form-2307-panel {
  margin-top: 20px;
}
.form-2307-panel .section-head p {
  color: var(--workflow-muted);
  margin-top: 4px;
}
.form-2307-rows {
  display: grid;
  gap: 10px;
}
.form-2307-card {
  align-items: start;
  grid-template-columns: minmax(260px, 1fr) auto minmax(220px, auto) minmax(260px, 0.8fr);
}
.form-2307-main span {
  color: var(--workflow-muted);
  font-size: 0.82em;
}
.form-2307-status,
.form-2307-upload,
.form-2307-notes {
  display: grid;
  gap: 8px;
  justify-items: end;
}
.form-2307-timeline {
  display: grid;
  gap: 4px;
  margin-top: 8px;
}
.form-2307-timeline div {
  display: flex;
  gap: 8px;
}
.form-2307-timeline dt {
  color: var(--workflow-muted);
  min-width: 76px;
}
.form-2307-timeline dd {
  color: var(--workflow-text);
}
.form-2307-upload a,
.form-2307-upload .link-button {
  color: var(--workflow-eyebrow);
  font-size: 0.9em;
  text-align: right;
}
.link-button {
  background: none;
  border: 0;
  cursor: pointer;
  font: inherit;
  padding: 0;
  text-decoration: underline;
}
.form-2307-notes textarea {
  width: 100%;
}
.status-pill {
  background: rgba(148, 163, 184, 0.08);
  border: 1px solid var(--workflow-soft-line);
  border-radius: 999px;
  color: var(--workflow-muted);
  font-size: 0.78em;
  font-weight: 700;
  padding: 4px 9px;
  text-transform: uppercase;
}
.status-pill.missing {
  color: #fca5a5;
}
.status-pill.requested {
  color: #fde68a;
}
.status-pill.received {
  color: #93c5fd;
}
.status-pill.attached {
  color: #86efac;
}
.match-card {
  grid-template-columns: 1fr auto;
  margin-top: 10px;
}
.match-score {
  display: grid;
  gap: 6px;
  justify-items: end;
}
.match-score strong {
  color: var(--workflow-eyebrow);
}
.match-score span {
  color: #fde68a;
  font-size: 0.85em;
}
.error {
  color: #fca5a5;
  margin-bottom: 18px;
}
@media (max-width: 760px) {
  header,
  .import-panel,
  .section-head,
  .manual-match,
  .transaction,
  .match-card,
  .reconciled-card,
  .form-2307-card {
    align-items: flex-start;
    grid-template-columns: 1fr;
  }
  form,
  .toolbar,
  .reconciled-actions,
  .form-2307-status,
  .form-2307-upload,
  .form-2307-notes {
    justify-content: flex-start;
    justify-items: start;
  }
  .import-panel form {
    grid-template-columns: 1fr;
  }
  .form-2307-notes textarea {
    min-width: 0;
  }
}
@media (max-width: 980px) {
  .import-panel {
    grid-template-columns: 1fr;
  }
  .import-panel form {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .import-panel button {
    grid-column: span 2;
  }
}
@media (max-width: 560px) {
  .import-panel form {
    grid-template-columns: 1fr;
  }
  .import-panel button {
    grid-column: auto;
  }
}
</style>
