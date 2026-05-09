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

    <details v-if="client" class="client-details">
      <summary>
        <span>Client details</span>
        <strong>{{ client.tin || 'TIN not set' }} · {{ softwareLabel(client.software) }}</strong>
      </summary>
      <section class="detail-grid">
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
    </details>

    <section class="upload-panel">
      <div>
        <p class="eyebrow">Batch upload</p>
        <h2>Invoices and receipts</h2>
        <p>Upload up to 50 JPEG, PNG, WebP, or PDF files. Documents will be queued for OCR extraction immediately.</p>
      </div>
      <form @submit.prevent="uploadFiles">
        <label :class="['file-picker', { selected: selectedFiles.length > 0 }]">
          <input
            ref="fileInput"
            type="file"
            multiple
            accept="image/jpeg,image/png,image/webp,application/pdf"
            @change="onFilesChange"
          />
          <span>Choose files</span>
          <strong>{{ filePickerLabel }}</strong>
        </label>
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
      <router-link :to="`/app/clients/${clientId}/compliance`">
        <h2>BIR compliance</h2>
        <p>SLSP, SAWT, 4-column journal, and upcoming BIR filing deadlines.</p>
      </router-link>
    </section>

    <section class="portal-panel">
      <div class="section-head">
        <div>
          <p class="eyebrow">Client portal</p>
          <h2>Public upload links</h2>
          <p class="muted">Share a link so the client can drop receipts straight into the queue from their phone — no login required.</p>
        </div>
        <button type="button" @click="loadLinks">Refresh</button>
      </div>

      <form class="link-form" @submit.prevent="createLink">
        <label>
          Label
          <input v-model="newLink.label" type="text" maxlength="120" placeholder="e.g. Q2 2026 receipts" />
        </label>
        <label>
          Expires in (days)
          <input v-model.number="newLink.expires_in_days" type="number" min="1" max="365" placeholder="optional" />
        </label>
        <label>
          Max uploads
          <input v-model.number="newLink.max_uploads" type="number" min="1" max="1000" placeholder="optional" />
        </label>
        <button type="submit" :disabled="creatingLink">
          {{ creatingLink ? 'Creating...' : 'Create link' }}
        </button>
      </form>

      <div v-if="links.length === 0" class="empty">No upload links yet.</div>
      <table v-else class="link-table">
        <thead>
          <tr>
            <th>Label</th>
            <th>URL</th>
            <th>Uploads</th>
            <th>Expires</th>
            <th>Status</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="link in links" :key="link.id" :class="{ revoked: link.revoked_at }">
            <td>{{ link.label || 'Unlabeled' }}</td>
            <td class="url">
              <code>{{ portalUrl(link.token) }}</code>
              <button type="button" class="copy" @click="copyLink(link)">{{ copiedToken === link.token ? 'Copied' : 'Copy' }}</button>
            </td>
            <td>{{ link.uploads_count }}<span v-if="link.max_uploads"> / {{ link.max_uploads }}</span></td>
            <td>{{ formatDate(link.expires_at) || 'Never' }}</td>
            <td>{{ linkStatus(link) }}</td>
            <td>
              <button v-if="!link.revoked_at" type="button" class="danger" @click="revokeLink(link)">Revoke</button>
            </td>
          </tr>
        </tbody>
      </table>
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
import { computed, onMounted, ref } from 'vue'
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
const filePickerLabel = computed(() => {
  if (selectedFiles.value.length === 0) return 'No files selected'
  if (selectedFiles.value.length === 1) return selectedFiles.value[0].name
  return `${selectedFiles.value.length} files selected`
})

const links = ref([])
const newLink = ref({ label: '', expires_in_days: null, max_uploads: null })
const creatingLink = ref(false)
const copiedToken = ref('')

onMounted(async () => {
  try {
    client.value = await apiFetch(`/clients/${clientId}`)
    await Promise.all([loadReceipts(), loadLinks()])
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

async function loadLinks() {
  try {
    const data = await apiFetch(`/clients/${clientId}/upload-links`)
    links.value = data.links || []
  } catch (err) {
    error.value = err.message
  }
}

async function createLink() {
  creatingLink.value = true
  error.value = ''
  try {
    const payload = {
      label: newLink.value.label || null,
      expires_in_days: newLink.value.expires_in_days || null,
      max_uploads: newLink.value.max_uploads || null,
    }
    await apiFetch(`/clients/${clientId}/upload-links`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
    newLink.value = { label: '', expires_in_days: null, max_uploads: null }
    await loadLinks()
  } catch (err) {
    error.value = err.message
  } finally {
    creatingLink.value = false
  }
}

async function revokeLink(link) {
  if (!confirm('Revoke this upload link? The client will no longer be able to upload through it.')) return
  try {
    await apiFetch(`/clients/${clientId}/upload-links/${link.id}`, { method: 'DELETE' })
    await loadLinks()
  } catch (err) {
    error.value = err.message
  }
}

function portalUrl(token) {
  return `${window.location.origin}/portal/${token}`
}

async function copyLink(link) {
  try {
    await navigator.clipboard.writeText(portalUrl(link.token))
    copiedToken.value = link.token
    setTimeout(() => {
      if (copiedToken.value === link.token) copiedToken.value = ''
    }, 1500)
  } catch {
    // ignore
  }
}

function linkStatus(link) {
  if (link.revoked_at) return 'Revoked'
  if (link.expires_at && new Date(link.expires_at) < new Date()) return 'Expired'
  if (link.max_uploads && link.uploads_count >= link.max_uploads) return 'Exhausted'
  return 'Active'
}

function formatDate(value) {
  if (!value) return ''
  return new Date(value).toLocaleDateString()
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
  padding: 16px 24px 64px;
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
.client-details,
.workflows,
.receipt-list {
  margin-top: 28px;
}
.workflows {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}
.client-details {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  margin-bottom: 18px;
}
.client-details summary {
  align-items: center;
  cursor: pointer;
  display: flex;
  gap: 16px;
  justify-content: space-between;
  list-style: none;
  padding: 14px 18px;
}
.client-details summary::-webkit-details-marker {
  display: none;
}
.client-details summary span {
  color: var(--text);
  font-weight: 600;
}
.client-details summary strong {
  color: var(--muted);
  font-size: 0.9em;
  font-weight: 500;
}
.client-details summary::after {
  color: var(--muted);
  content: "Show";
  font-size: 0.85em;
  margin-left: auto;
}
.client-details[open] summary {
  border-bottom: 1px solid var(--border);
}
.client-details[open] summary::after {
  content: "Hide";
}
.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  padding: 14px;
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
.workflows a {
  transition: border-color 0.14s ease, background-color 0.14s ease, transform 0.08s ease;
}
.workflows a:hover {
  background: var(--surface-2);
  border-color: var(--accent);
}
.workflows a:active {
  transform: translateY(1px) scale(0.996);
}
.detail-grid div {
  background: var(--bg);
  padding: 14px;
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
.receipt-list,
.portal-panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 20px;
}
.portal-panel {
  margin-top: 28px;
  display: grid;
  gap: 16px;
}
.portal-panel .muted {
  color: var(--muted);
  font-size: 0.92em;
  margin-top: 4px;
}
.link-form {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr auto;
  gap: 10px;
  align-items: end;
}
.link-form label {
  display: flex;
  flex-direction: column;
  font-size: 0.78em;
  color: var(--muted);
  text-transform: uppercase;
  gap: 4px;
}
.link-form input {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text);
  padding: 8px 10px;
}
.link-table .url {
  display: flex;
  gap: 8px;
  align-items: center;
}
.link-table .url code {
  background: var(--bg);
  border-radius: 4px;
  font-size: 0.82em;
  padding: 4px 6px;
  word-break: break-all;
}
.link-table .copy {
  font-size: 0.82em;
  padding: 4px 8px;
}
.link-table tr.revoked {
  opacity: 0.55;
}
button.danger {
  border-color: rgba(248, 113, 113, 0.45);
  color: #fca5a5;
  font-size: 0.85em;
  padding: 6px 10px;
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
  align-items: center;
  display: grid;
  grid-template-columns: minmax(260px, 1fr) auto;
  gap: 10px;
  justify-content: stretch;
  min-width: min(420px, 100%);
}
.file-picker {
  align-items: center;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--muted);
  display: grid;
  gap: 10px;
  grid-template-columns: auto minmax(0, 1fr);
  min-height: 48px;
  padding: 6px;
}
.file-picker:hover,
.file-picker.selected {
  border-color: var(--accent);
}
.file-picker.selected strong {
  color: var(--text);
}
.file-picker input {
  display: none;
}
.file-picker span {
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text);
  cursor: pointer;
  font-size: 0.92em;
  font-weight: 600;
  padding: 7px 10px;
  white-space: nowrap;
}
.file-picker strong {
  font-size: 0.9em;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
  min-height: 48px;
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
    grid-template-columns: 1fr;
    min-width: 0;
  }
  table {
    display: block;
    overflow-x: auto;
  }
  .link-form {
    grid-template-columns: 1fr;
  }
}
</style>
