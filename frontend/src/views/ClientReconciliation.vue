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
        <h2>Import bank CSV</h2>
        <p>Supports common Date, Description, Amount, Debit/Credit, and Reference columns from PH bank exports.</p>
      </div>
      <form @submit.prevent="importCsv">
        <input v-model="bankName" type="text" placeholder="Bank name, e.g. BPI" />
        <input ref="fileInput" type="file" accept=".csv,text/csv" @change="onFileChange" />
        <button type="submit" :disabled="uploading || !selectedFile">
          {{ uploading ? 'Importing...' : 'Import CSV' }}
        </button>
      </form>
      <p v-if="message" class="notice">{{ message }}</p>
    </section>

    <p v-if="error" class="error">{{ error }}</p>

    <section class="transaction-list">
      <div class="section-head">
        <h2>Unreconciled bank entries</h2>
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
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { apiFetch, clearToken } from '../api'

const route = useRoute()
const router = useRouter()
const clientId = route.params.id
const client = ref(null)
const transactions = ref([])
const matchResult = ref(null)
const selectedFile = ref(null)
const selectedTransactions = ref([])
const fileInput = ref(null)
const bankName = ref('')
const bulkCategory = ref('')
const loading = ref(true)
const uploading = ref(false)
const error = ref('')
const message = ref('')

onMounted(async () => {
  try {
    client.value = await apiFetch(`/clients/${clientId}`)
    await loadTransactions()
  } catch (err) {
    handleError(err)
  }
})

function onFileChange(event) {
  selectedFile.value = event.target.files?.[0] || null
  message.value = ''
}

async function importCsv() {
  if (!selectedFile.value) return
  uploading.value = true
  error.value = ''
  message.value = ''

  const body = new FormData()
  body.append('file', selectedFile.value)

  try {
    const query = bankName.value ? `?bank_name=${encodeURIComponent(bankName.value)}` : ''
    const data = await apiFetch(`/clients/${clientId}/bank/import${query}`, {
      method: 'POST',
      body,
    })
    message.value = `${data.imported} bank transaction${data.imported === 1 ? '' : 's'} imported.`
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
  try {
    matchResult.value = await apiFetch(`/clients/${clientId}/bank/transactions/${transactionId}/matches`)
  } catch (err) {
    handleError(err)
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
    await loadTransactions()
  } catch (err) {
    handleError(err)
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

function formatAmount(value, currency = 'PHP') {
  if (value === null || value === undefined) return '-'
  return new Intl.NumberFormat('en-PH', {
    style: 'currency',
    currency: currency || 'PHP',
  }).format(value)
}
</script>

<style scoped>
.recon-page {
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
.import-panel,
.transaction-list,
.matches {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 20px;
}
.import-panel {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 20px;
  margin-bottom: 20px;
}
.import-panel p,
.empty,
.transaction p,
.section-head span,
.reasons {
  color: var(--muted);
}
form,
.toolbar {
  align-items: end;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: flex-end;
}
input {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text);
  font: inherit;
  padding: 10px 12px;
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
button:disabled {
  cursor: wait;
  opacity: 0.7;
}
.notice {
  color: #86efac !important;
  grid-column: 1 / -1;
}
.section-head {
  align-items: center;
  display: flex;
  gap: 16px;
  justify-content: space-between;
  margin-bottom: 14px;
}
.section-head button,
.transaction button {
  background: var(--surface-2);
  border-color: var(--border);
  color: var(--text);
}
.rows {
  display: grid;
  gap: 10px;
}
.transaction,
.match-card {
  align-items: center;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  display: grid;
  gap: 16px;
  grid-template-columns: auto 1fr auto auto;
  padding: 14px;
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
  color: var(--muted);
  font-size: 0.82em;
}
.tx-amount {
  display: grid;
  justify-items: end;
}
.tx-amount span {
  color: var(--muted);
  font-size: 0.82em;
}
.matches {
  margin-top: 20px;
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
  color: var(--accent-hover);
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
  .transaction,
  .match-card {
    align-items: flex-start;
    grid-template-columns: 1fr;
  }
  form,
  .toolbar {
    justify-content: flex-start;
  }
}
</style>
