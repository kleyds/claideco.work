<template>
  <div class="review-page">
    <header class="review-header">
      <div>
        <p class="eyebrow">Review queue</p>
        <h1>{{ client?.name || 'Client' }}</h1>
      </div>
      <div class="header-actions">
        <span>{{ currentIndex + 1 || 0 }} of {{ queue.length }} remaining</span>
        <router-link :to="`/app/clients/${clientId}`">Back to client</router-link>
      </div>
    </header>

    <p v-if="error" class="error">{{ error }}</p>

    <section v-if="loading" class="empty">Loading review queue...</section>
    <section v-else-if="queue.length === 0" class="empty">
      No receipts need review.
    </section>

    <section v-else class="review-shell">
      <aside class="queue-list">
        <button
          v-for="(receipt, index) in queue"
          :key="receipt.id"
          type="button"
          :class="{ active: receipt.id === currentReceipt?.id }"
          @click="selectReceipt(index)"
        >
          <strong>{{ receipt.original_name || `Receipt #${receipt.id}` }}</strong>
          <span :class="['status', receipt.status]">{{ receipt.status }}</span>
        </button>
      </aside>

      <main class="document-pane">
        <div class="document-toolbar">
          <button type="button" @click="zoom = Math.max(0.5, zoom - 0.1)">-</button>
          <span>{{ Math.round(zoom * 100) }}%</span>
          <button type="button" @click="zoom = Math.min(2, zoom + 0.1)">+</button>
        </div>
        <div class="document-view">
          <img
            v-if="isImage(currentReceipt)"
            :src="fileUrl(currentReceipt)"
            :style="{ transform: `scale(${zoom})` }"
            alt="Uploaded receipt"
          />
          <div v-else class="pdf-placeholder">
            <h2>Preview unavailable</h2>
            <p>PDF rendering is not implemented yet. The file is stored and attached to this receipt.</p>
            <a :href="fileUrl(currentReceipt)" target="_blank" rel="noreferrer">Open file</a>
          </div>
        </div>
      </main>

      <form class="fields-pane" @submit.prevent="approve">
        <div class="form-head">
          <div>
            <h2>Extracted fields</h2>
            <p>{{ currentReceipt?.original_name }}</p>
          </div>
          <span :class="['confidence', confidenceClass]">{{ confidenceLabel }}</span>
        </div>

        <label :class="fieldClass">
          Vendor
          <input v-model="form.vendor" type="text" />
        </label>
        <label :class="fieldClass">
          Vendor TIN
          <input v-model="form.vendor_tin" type="text" placeholder="000-000-000-00000" />
        </label>
        <div class="two-col">
          <label :class="fieldClass">
            OR number
            <input v-model="form.or_number" type="text" />
          </label>
          <label :class="fieldClass">
            SI number
            <input v-model="form.si_number" type="text" />
          </label>
        </div>
        <div class="two-col">
          <label :class="fieldClass">
            Date
            <input v-model="form.date" type="date" />
          </label>
          <label :class="fieldClass">
            Document type
            <select v-model="form.doc_type">
              <option value="">Unknown</option>
              <option value="official_receipt">Official receipt</option>
              <option value="sales_invoice">Sales invoice</option>
              <option value="gcash">GCash</option>
              <option value="maya">Maya</option>
              <option value="bank_statement">Bank statement</option>
              <option value="other">Other</option>
            </select>
          </label>
        </div>
        <div class="two-col">
          <label :class="fieldClass">
            VAT type
            <select v-model="form.vat_type">
              <option value="">Unknown</option>
              <option value="vatable">Vatable</option>
              <option value="zero_rated">Zero-rated</option>
              <option value="exempt">Exempt</option>
              <option value="non_vat">Non-VAT</option>
            </select>
          </label>
          <label :class="fieldClass">
            Currency
            <input v-model="form.currency" type="text" maxlength="3" />
          </label>
        </div>
        <div class="two-col">
          <label :class="fieldClass">
            Vatable amount
            <input v-model.number="form.vatable_amount" type="number" step="0.01" />
          </label>
          <label :class="fieldClass">
            VAT amount
            <input v-model.number="form.vat_amount" type="number" step="0.01" />
          </label>
        </div>
        <div class="two-col">
          <label :class="fieldClass">
            Subtotal
            <input v-model.number="form.subtotal" type="number" step="0.01" />
          </label>
          <label :class="fieldClass">
            Total
            <input v-model.number="form.total" type="number" step="0.01" />
          </label>
        </div>

        <label>
          Raw OCR text
          <textarea :value="currentReceipt?.raw_text || ''" readonly rows="5" />
        </label>

        <div class="form-actions">
          <button type="button" class="secondary" @click="reject">Reject</button>
          <button type="submit">Approve</button>
        </div>
      </form>
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
const queue = ref([])
const currentIndex = ref(0)
const loading = ref(true)
const error = ref('')
const zoom = ref(1)

const form = reactive(emptyForm())

const currentReceipt = computed(() => queue.value[currentIndex.value] || null)
const confidence = computed(() => currentReceipt.value?.data?.confidence ?? null)
const confidenceLabel = computed(() => {
  if (confidence.value === null) return 'No confidence score'
  return `${Math.round(confidence.value * 100)}% confidence`
})
const confidenceClass = computed(() => {
  if (confidence.value === null) return 'unknown'
  if (confidence.value < 0.75) return 'low'
  if (confidence.value < 0.9) return 'medium'
  return 'high'
})
const fieldClass = computed(() => ({
  caution: confidence.value !== null && confidence.value < 0.9,
  danger: confidence.value !== null && confidence.value < 0.75,
}))

onMounted(async () => {
  await loadQueue()
  window.addEventListener('keydown', onKeydown)
})

async function loadQueue() {
  loading.value = true
  error.value = ''
  try {
    const [clientData, queueData] = await Promise.all([
      apiFetch(`/clients/${clientId}`),
      apiFetch(`/clients/${clientId}/receipts/queue`),
    ])
    client.value = clientData
    queue.value = queueData.receipts
    currentIndex.value = 0
    syncForm()
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

function emptyForm() {
  return {
    vendor: '',
    vendor_tin: '',
    or_number: '',
    si_number: '',
    date: '',
    currency: 'PHP',
    subtotal: null,
    tax: null,
    vat_type: '',
    vatable_amount: null,
    vat_amount: null,
    total: null,
    doc_type: '',
    confidence: null,
  }
}

function syncForm() {
  Object.assign(form, emptyForm(), currentReceipt.value?.data || {})
}

function selectReceipt(index) {
  currentIndex.value = index
  zoom.value = 1
  syncForm()
}

function fileUrl(receipt) {
  if (!receipt) return ''
  return `${API_BASE_URL}/receipts/${receipt.id}/file?token=${encodeURIComponent(getToken())}`
}

function isImage(receipt) {
  return receipt?.mime_type?.startsWith('image/')
}

async function approve() {
  await saveReceipt('approved')
}

async function reject() {
  await saveReceipt('rejected')
}

async function saveReceipt(status) {
  if (!currentReceipt.value) return
  error.value = ''
  try {
    await apiFetch(`/receipts/${currentReceipt.value.id}`, {
      method: 'PATCH',
      body: JSON.stringify({
        status,
        data: normalizeForm(),
      }),
    })
    queue.value.splice(currentIndex.value, 1)
    if (currentIndex.value >= queue.value.length) {
      currentIndex.value = Math.max(0, queue.value.length - 1)
    }
    syncForm()
  } catch (err) {
    error.value = err.message
  }
}

function normalizeForm() {
  const data = { ...form }
  for (const key of Object.keys(data)) {
    if (data[key] === '') data[key] = null
  }
  data.currency = data.currency || 'PHP'
  data.confidence = confidence.value
  return data
}

function onKeydown(event) {
  if (event.key === 'Enter' && event.target?.tagName !== 'TEXTAREA') {
    event.preventDefault()
    approve()
  }
}
</script>

<style scoped>
.review-page {
  padding: 24px;
}
.review-header {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: center;
  margin: 0 auto 20px;
  max-width: 1440px;
}
.eyebrow {
  color: var(--accent-hover);
  font-size: 0.78em;
  font-weight: 700;
  margin-bottom: 4px;
  text-transform: uppercase;
}
.header-actions {
  display: flex;
  gap: 16px;
  align-items: center;
  color: var(--muted);
}
.review-shell {
  display: grid;
  grid-template-columns: 260px minmax(360px, 1fr) minmax(360px, 520px);
  gap: 16px;
  max-width: 1440px;
  margin: 0 auto;
  min-height: 680px;
}
.queue-list,
.document-pane,
.fields-pane,
.empty {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
}
.queue-list {
  display: grid;
  align-content: start;
  gap: 8px;
  padding: 12px;
}
.queue-list button {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text);
  cursor: pointer;
  display: grid;
  gap: 8px;
  padding: 12px;
  text-align: left;
}
.queue-list button.active {
  border-color: var(--accent);
}
.status,
.confidence {
  border-radius: 999px;
  display: inline-flex;
  font-size: 0.78em;
  padding: 3px 8px;
  width: fit-content;
}
.status.pending,
.status.processing,
.confidence.medium {
  background: rgba(250, 204, 21, 0.14);
  color: #fde68a;
}
.status.done,
.status.approved,
.confidence.high {
  background: rgba(34, 197, 94, 0.14);
  color: #86efac;
}
.status.error,
.status.rejected,
.confidence.low {
  background: rgba(248, 113, 113, 0.14);
  color: #fca5a5;
}
.confidence.unknown {
  background: var(--surface-2);
  color: var(--muted);
}
.document-pane {
  overflow: hidden;
}
.document-toolbar {
  border-bottom: 1px solid var(--border);
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 10px 12px;
}
button {
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-2);
  color: var(--text);
  cursor: pointer;
  font: inherit;
  padding: 8px 12px;
}
.document-view {
  display: grid;
  min-height: 620px;
  overflow: auto;
  place-items: center;
  padding: 24px;
}
.document-view img {
  max-width: 100%;
  transform-origin: center;
  transition: transform 0.12s ease;
}
.pdf-placeholder {
  max-width: 420px;
  text-align: center;
}
.pdf-placeholder h2 {
  margin-bottom: 8px;
}
.pdf-placeholder p {
  color: var(--muted);
  margin-bottom: 14px;
}
.fields-pane {
  display: grid;
  gap: 14px;
  align-content: start;
  padding: 18px;
}
.form-head {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: start;
}
.form-head h2 {
  font-size: 1.1em;
}
.form-head p {
  color: var(--muted);
  font-size: 0.9em;
}
label {
  color: var(--muted);
  display: grid;
  gap: 5px;
  font-size: 0.88em;
}
.two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
input,
select,
textarea {
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg);
  color: var(--text);
  font: inherit;
  padding: 10px 12px;
}
label.caution input,
label.caution select {
  border-color: #ca8a04;
}
label.danger input,
label.danger select {
  border-color: #ef4444;
}
textarea {
  resize: vertical;
}
.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
.form-actions button[type="submit"] {
  background: var(--accent);
  border-color: var(--accent);
  color: white;
  font-weight: 600;
}
.secondary {
  color: #fca5a5;
}
.empty {
  color: var(--muted);
  margin: 40px auto;
  max-width: 720px;
  padding: 28px;
}
.error {
  color: #fca5a5;
  margin: 0 auto 16px;
  max-width: 1440px;
}
@media (max-width: 1100px) {
  .review-shell {
    grid-template-columns: 1fr;
  }
  .queue-list {
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  }
}
@media (max-width: 640px) {
  .review-header,
  .header-actions,
  .two-col {
    align-items: flex-start;
    flex-direction: column;
    grid-template-columns: 1fr;
  }
}
</style>
