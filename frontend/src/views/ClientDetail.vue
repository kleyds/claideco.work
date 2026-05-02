<template>
  <div class="container detail-page">
    <header>
      <div>
        <p class="eyebrow">Client</p>
        <h1>{{ client?.name || 'Loading...' }}</h1>
      </div>
      <router-link to="/app">Back to clients</router-link>
    </header>

    <p v-if="error" class="error">{{ error }}</p>

    <section v-if="client" class="detail-grid">
      <div>
        <span>TIN</span>
        <strong>{{ client.tin || 'Not set' }}</strong>
      </div>
      <div>
        <span>Address</span>
        <strong>{{ client.address || 'Not set' }}</strong>
      </div>
      <div>
        <span>Industry</span>
        <strong>{{ client.industry || 'Not set' }}</strong>
      </div>
      <div>
        <span>Accounting software</span>
        <strong>{{ softwareLabel(client.software) }}</strong>
      </div>
    </section>

    <section class="upload-panel">
      <div>
        <p class="eyebrow">Batch upload</p>
        <h2>Invoices and receipts</h2>
        <p>Upload up to 50 JPEG, PNG, WebP, or PDF files. Image files will be queued for OCR extraction immediately.</p>
      </div>
      <form @submit.prevent="uploadFiles">
        <input
          ref="fileInput"
          type="file"
          multiple
          accept="image/jpeg,image/png,image/webp,application/pdf"
          @change="onFilesChange"
        />
        <button type="submit" :disabled="uploading || selectedFiles.length === 0">
          {{ uploading ? 'Uploading...' : `Upload ${selectedFiles.length || ''}` }}
        </button>
      </form>
      <p v-if="uploadMessage" class="notice">{{ uploadMessage }}</p>
    </section>

    <section class="workflows">
      <router-link :to="`/app/clients/${clientId}/review`">
        <h2>Review queue</h2>
        <p>Invoice split-screen validation lands after batch upload.</p>
      </router-link>
      <router-link :to="`/app/clients/${clientId}/archive`">
        <h2>Archive</h2>
        <p>Search approved documents and export BIR-ready reports.</p>
      </router-link>
      <router-link :to="`/app/clients/${clientId}/reconciliation`">
        <h2>Bank reconciliation</h2>
        <p>Import bank CSVs and find invoice matches with withholding variance checks.</p>
      </router-link>
    </section>

    <section class="receipt-list">
      <div class="section-head">
        <h2>Recent uploads</h2>
        <button type="button" @click="loadReceipts">Refresh</button>
      </div>
      <div v-if="receipts.length === 0" class="empty">
        No uploads yet.
      </div>
      <table v-else>
        <thead>
          <tr>
            <th>File</th>
            <th>Status</th>
            <th>Vendor</th>
            <th>Total</th>
            <th>Confidence</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="receipt in receipts" :key="receipt.id">
            <td>{{ receipt.original_name || `Receipt #${receipt.id}` }}</td>
            <td><span :class="['status', receipt.status]">{{ receipt.status }}</span></td>
            <td>{{ receipt.data?.vendor || '-' }}</td>
            <td>{{ formatAmount(receipt.data?.total, receipt.data?.currency) }}</td>
            <td>{{ formatConfidence(receipt.data?.confidence) }}</td>
          </tr>
        </tbody>
      </table>
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
const receipts = ref([])
const error = ref('')
const uploadMessage = ref('')
const uploading = ref(false)
const selectedFiles = ref([])
const fileInput = ref(null)

onMounted(async () => {
  try {
    client.value = await apiFetch(`/clients/${clientId}`)
    await loadReceipts()
  } catch (err) {
    if (err.message.includes('credentials')) {
      clearToken()
      router.push('/login')
      return
    }
    error.value = err.message
  }
})

async function loadReceipts() {
  const data = await apiFetch(`/clients/${clientId}/receipts`)
  receipts.value = data.receipts
}

function onFilesChange(event) {
  selectedFiles.value = Array.from(event.target.files || [])
  uploadMessage.value = ''
}

async function uploadFiles() {
  if (selectedFiles.value.length === 0) return
  uploading.value = true
  uploadMessage.value = ''
  error.value = ''

  const body = new FormData()
  selectedFiles.value.forEach((file) => body.append('files', file))

  try {
    const data = await apiFetch(`/clients/${clientId}/receipts/upload`, {
      method: 'POST',
      body,
    })
    uploadMessage.value = `${data.receipts.length} file${data.receipts.length === 1 ? '' : 's'} uploaded.`
    selectedFiles.value = []
    if (fileInput.value) fileInput.value.value = ''
    await loadReceipts()
  } catch (err) {
    if (err.message.includes('credentials')) {
      clearToken()
      router.push('/login')
      return
    }
    error.value = err.message
  } finally {
    uploading.value = false
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
</script>

<style scoped>
.detail-page {
  padding: 32px 24px 64px;
}
header {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: center;
  margin-bottom: 28px;
}
.eyebrow {
  color: var(--accent-hover);
  font-size: 0.78em;
  font-weight: 700;
  margin-bottom: 4px;
  text-transform: uppercase;
}
.detail-grid,
.workflows,
.receipt-list {
  margin-top: 28px;
}
.workflows {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}
.detail-grid {
  margin-bottom: 28px;
}
.detail-grid div,
.workflows a,
.workflows div {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text);
  padding: 20px;
}
.detail-grid span {
  color: var(--muted);
  display: block;
  font-size: 0.8em;
  margin-bottom: 4px;
  text-transform: uppercase;
}
.detail-grid strong {
  font-size: 1em;
}
.workflows h2 {
  font-size: 1.05em;
  margin-bottom: 8px;
}
.workflows p {
  color: var(--muted);
  font-size: 0.94em;
}
.upload-panel,
.receipt-list {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 20px;
}
.upload-panel {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 20px;
  align-items: center;
  margin-bottom: 28px;
}
.upload-panel h2 {
  font-size: 1.1em;
  margin-bottom: 6px;
}
.upload-panel p {
  color: var(--muted);
  font-size: 0.94em;
}
.upload-panel form {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: flex-end;
}
input[type="file"] {
  color: var(--muted);
  max-width: 320px;
}
button {
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text);
  cursor: pointer;
  font: inherit;
  padding: 10px 14px;
}
button[type="submit"] {
  background: var(--accent);
  border-color: var(--accent);
  color: white;
  font-weight: 600;
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
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
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
}
th {
  color: var(--muted);
  font-size: 0.78em;
  text-transform: uppercase;
}
.status {
  border-radius: 999px;
  display: inline-flex;
  font-size: 0.78em;
  padding: 3px 8px;
}
.status.pending,
.status.processing {
  background: rgba(250, 204, 21, 0.14);
  color: #fde68a;
}
.status.done {
  background: rgba(34, 197, 94, 0.14);
  color: #86efac;
}
.status.error {
  background: rgba(248, 113, 113, 0.14);
  color: #fca5a5;
}
.empty {
  color: var(--muted);
}
.error {
  color: #fca5a5;
}
@media (max-width: 640px) {
  header {
    align-items: flex-start;
    flex-direction: column;
  }
  .upload-panel {
    grid-template-columns: 1fr;
  }
  .upload-panel form {
    justify-content: flex-start;
  }
  table {
    display: block;
    overflow-x: auto;
  }
}
</style>
