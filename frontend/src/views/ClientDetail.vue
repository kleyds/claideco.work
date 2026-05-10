<template>
  <div class="container detail-page">
    <header>
      <div>
        <p class="eyebrow">Client</p>
        <h1>{{ client?.name || 'Loading...' }}</h1>
      </div>
      <button type="button" class="header-link" @click="showWorkspaceConfirm = true">Back to workspace</button>
    </header>

    <p v-if="error" class="error">{{ error }}</p>

    <details v-if="client" class="client-details">
      <summary>
        <span class="eyebrow">Client details</span>
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
        <h2
          class="title-row hover-tooltip"
          tabindex="0"
          aria-label="Invoices and receipts. Upload up to 50 JPEG, PNG, WebP, or PDF files. Documents will be queued for OCR extraction immediately."
          data-tooltip="Upload up to 50 JPEG, PNG, WebP, or PDF files. Documents will be queued for OCR extraction immediately."
        >
          Invoices and receipts
          <span class="info-tooltip" aria-hidden="true">?</span>
        </h2>
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

    <section class="workflow-panel">
      <p class="eyebrow">Workflows</p>
      <nav class="workflows" aria-label="Client workflows">
      <router-link
        :to="`/app/clients/${clientId}/review`"
        aria-label="Review queue. Invoice split-screen validation lands after batch upload."
        data-tooltip="Invoice split-screen validation lands after batch upload."
      >
        <span>Review queue</span>
        <span class="sr-only">Invoice split-screen validation lands after batch upload.</span>
      </router-link>
      <router-link
        :to="`/app/clients/${clientId}/archive`"
        aria-label="Archive. Search approved documents and export BIR-ready reports."
        data-tooltip="Search approved documents and export BIR-ready reports."
      >
        <span>Archive</span>
        <span class="sr-only">Search approved documents and export BIR-ready reports.</span>
      </router-link>
      <router-link
        :to="`/app/clients/${clientId}/reconciliation`"
        aria-label="Bank reconciliation. Import bank CSVs and find invoice matches with withholding variance checks."
        data-tooltip="Import bank CSVs and find invoice matches with withholding variance checks."
      >
        <span>Bank reconciliation</span>
        <span class="sr-only">Import bank CSVs and find invoice matches with withholding variance checks.</span>
      </router-link>
      <router-link
        :to="`/app/clients/${clientId}/compliance`"
        aria-label="BIR compliance. SLSP, SAWT, 4-column journal, and upcoming BIR filing deadlines."
        data-tooltip="SLSP, SAWT, 4-column journal, and upcoming BIR filing deadlines."
      >
        <span>BIR compliance</span>
        <span class="sr-only">SLSP, SAWT, 4-column journal, and upcoming BIR filing deadlines.</span>
      </router-link>
      </nav>
    </section>

    <section class="portal-panel">
      <div class="section-head">
        <div>
          <p class="eyebrow">Client portal</p>
          <h2
            class="title-row hover-tooltip"
            tabindex="0"
            aria-label="Public upload links. Share a link so the client can drop receipts straight into the queue from their phone. No login required."
            data-tooltip="Share a link so the client can drop receipts straight into the queue from their phone. No login required."
          >
            Public upload links
            <span class="info-tooltip" aria-hidden="true">?</span>
          </h2>
          <p class="activity">
            Portal activity: <strong>{{ totalUnreadPortalComments }}</strong> unread client comment{{ totalUnreadPortalComments === 1 ? '' : 's' }}
          </p>
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
        <div>
          <p class="eyebrow">Uploads</p>
          <h2 class="title-row">Recent uploads</h2>
        </div>
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
            <th>Comments</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="receipt in receipts" :key="receipt.id">
            <td>{{ receipt.original_name || `Receipt #${receipt.id}` }}</td>
            <td><span :class="['status', receipt.status]">{{ receipt.status }}</span></td>
            <td>{{ receipt.data?.vendor || '-' }}</td>
            <td>{{ formatAmount(receipt.data?.total, receipt.data?.currency) }}</td>
            <td>{{ formatConfidence(receipt.data?.confidence) }}</td>
            <td>
              <button type="button" class="comment-button" @click="openComments(receipt)">
                {{ receipt.comment_count || 0 }}
                <span v-if="receipt.unread_portal_comment_count">({{ receipt.unread_portal_comment_count }} unread)</span>
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <section v-if="commentReceipt" class="comment-overlay" role="dialog" aria-modal="true" aria-labelledby="comment-title">
      <div class="comment-panel">
        <header>
          <div>
            <p class="eyebrow">Clarifications</p>
            <h2 id="comment-title">{{ commentReceipt.original_name || `Receipt #${commentReceipt.id}` }}</h2>
          </div>
          <button type="button" @click="closeComments">Close</button>
        </header>

        <div v-if="commentsLoading" class="empty">Loading comments...</div>
        <div v-else class="thread">
          <p v-if="comments.length === 0" class="empty">No comments yet.</p>
          <article v-for="comment in comments" :key="comment.id" :class="['comment', comment.author_type]">
            <div>
              <strong>{{ comment.author_name }}</strong>
              <span>{{ comment.author_type === 'bookkeeper' ? 'Bookkeeper' : 'Client' }} · {{ formatDateTime(comment.created_at) }}</span>
            </div>
            <p>{{ comment.body }}</p>
          </article>
        </div>

        <form class="comment-form" @submit.prevent="replyToComment">
          <label>
            Reply
            <textarea v-model="replyBody" maxlength="2000" required placeholder="Reply to the client"></textarea>
          </label>
          <button type="submit" :disabled="replying">
            {{ replying ? 'Sending...' : 'Send reply' }}
          </button>
        </form>
        <p v-if="commentError" class="error">{{ commentError }}</p>
      </div>
    </section>

    <section
      v-if="showWorkspaceConfirm"
      class="confirm-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="workspace-confirm-title"
    >
      <div class="confirm-panel">
        <p class="eyebrow">Workspace</p>
        <h2 id="workspace-confirm-title">Go back to workspace?</h2>
        <p>You will leave this client homepage and return to the workspace list.</p>
        <div class="confirm-actions">
          <button type="button" class="confirm-yes" @click="goToWorkspace">Yes</button>
          <button type="button" class="secondary" @click="showWorkspaceConfirm = false">No</button>
        </div>
      </div>
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
const totalUnreadPortalComments = computed(() =>
  receipts.value.reduce((sum, receipt) => sum + Number(receipt.unread_portal_comment_count || 0), 0)
)
const commentReceipt = ref(null)
const comments = ref([])
const commentsLoading = ref(false)
const commentError = ref('')
const replyBody = ref('')
const replying = ref(false)
const showWorkspaceConfirm = ref(false)

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
  if (commentReceipt.value) {
    commentReceipt.value = receipts.value.find((receipt) => receipt.id === commentReceipt.value.id) || commentReceipt.value
  }
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

async function openComments(receipt) {
  commentReceipt.value = receipt
  commentsLoading.value = true
  commentError.value = ''
  replyBody.value = ''
  try {
    const data = await apiFetch(`/receipts/${receipt.id}/comments/read`, { method: 'POST' })
    comments.value = data.comments || []
    await loadReceipts()
  } catch (err) {
    commentError.value = err.message
  } finally {
    commentsLoading.value = false
  }
}

function closeComments() {
  commentReceipt.value = null
  comments.value = []
  commentError.value = ''
  replyBody.value = ''
}

function goToWorkspace() {
  showWorkspaceConfirm.value = false
  router.push('/app')
}

async function replyToComment() {
  if (!commentReceipt.value) return
  replying.value = true
  commentError.value = ''
  try {
    await apiFetch(`/receipts/${commentReceipt.value.id}/comments`, {
      method: 'POST',
      body: JSON.stringify({ body: replyBody.value }),
    })
    replyBody.value = ''
    const data = await apiFetch(`/receipts/${commentReceipt.value.id}/comments`)
    comments.value = data.comments || []
    await loadReceipts()
  } catch (err) {
    commentError.value = err.message
  } finally {
    replying.value = false
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

function formatDateTime(value) {
  if (!value) return ''
  return new Date(value).toLocaleString()
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
  --detail-bg: #0b1020;
  --detail-panel: #151b2a;
  --detail-panel-strong: #1b2334;
  --detail-input: #0d1322;
  --detail-line: #2a3550;
  --detail-soft-line: rgba(148, 163, 184, 0.16);
  --detail-text: #f8fafc;
  --detail-muted: #a7b0c0;
  --detail-accent: #7c3aed;
  --detail-accent-2: #14b8a6;
  --detail-danger: #fb7185;
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
  color: #93c5fd;
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
.hover-tooltip::after,
.workflows a::before {
  background: #111827;
  border: 1px solid var(--detail-line);
  border-radius: 8px;
  bottom: calc(100% + 8px);
  box-shadow: 0 14px 30px rgba(0, 0, 0, 0.3);
  color: var(--text);
  content: attr(data-tooltip);
  font-size: 0.78rem;
  font-weight: 500;
  left: 50%;
  line-height: 1.45;
  max-width: min(300px, calc(100vw - 48px));
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
.hover-tooltip:focus-visible::after,
.workflows a:hover::before,
.workflows a:focus-visible::before {
  opacity: 1;
  transform: translate(-50%, 0);
  visibility: visible;
}
.hover-tooltip:focus-visible {
  outline: 2px solid var(--detail-accent-2);
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
.sr-only {
  border: 0;
  clip: rect(0, 0, 0, 0);
  height: 1px;
  margin: -1px;
  overflow: hidden;
  padding: 0;
  position: absolute;
  white-space: nowrap;
  width: 1px;
}
.client-details,
.workflow-panel,
.receipt-list {
  margin-top: 28px;
}
.client-details {
  background: var(--detail-panel);
  border: 1px solid var(--detail-line);
  border-radius: 10px;
  margin-bottom: 18px;
}
.client-details summary {
  align-items: center;
  cursor: pointer;
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 16px;
  list-style: none;
  padding: 14px 18px;
}
.client-details summary::-webkit-details-marker {
  display: none;
}
.client-details summary .eyebrow {
  color: #93c5fd;
  font-size: 0.78em;
  font-weight: 700;
  margin-bottom: 0;
  text-transform: uppercase;
}
.client-details summary strong {
  color: var(--detail-muted);
  font-size: 0.9em;
  font-weight: 500;
  line-height: 1;
}
.client-details summary::after {
  color: var(--detail-muted);
  content: "Show";
  font-size: 0.85em;
  justify-self: end;
}
.client-details[open] summary {
  border-bottom: 1px solid var(--detail-line);
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
.detail-grid div {
  background: var(--detail-input);
  border: 1px solid var(--detail-soft-line);
  border-radius: 8px;
  color: var(--detail-text);
  padding: 20px;
}
.workflows a {
  align-items: center;
  border: 1px solid transparent;
  border-radius: 8px;
  color: var(--detail-text);
  display: inline-flex;
  flex: 1 1 160px;
  font-weight: 700;
  gap: 8px;
  justify-content: center;
  min-height: 40px;
  min-width: 0;
  padding: 8px 12px;
  position: relative;
  text-align: center;
  transition: border-color 0.14s ease, background-color 0.14s ease, color 0.14s ease, transform 0.08s ease;
}
.workflows a::after {
  background: linear-gradient(90deg, var(--detail-accent), var(--detail-accent-2));
  border-radius: 999px;
  bottom: 5px;
  content: "";
  height: 2px;
  left: 18px;
  opacity: 0;
  position: absolute;
  right: 18px;
  transform: scaleX(0.55);
  transition: opacity 0.14s ease, transform 0.14s ease;
}
.workflows a:hover,
.workflows a:focus-visible,
.workflows a.router-link-active {
  background: rgba(124, 58, 237, 0.16);
  border-color: rgba(167, 139, 250, 0.42);
  color: var(--detail-text);
  outline: none;
}
.workflows a:hover::after,
.workflows a:focus-visible::after,
.workflows a.router-link-active::after {
  opacity: 1;
  transform: scaleX(1);
}
.workflows a:active {
  transform: translateY(1px) scale(0.996);
}
.detail-grid div {
  background: var(--detail-input);
  padding: 14px;
}
.detail-grid span {
  color: var(--detail-muted);
  display: block;
  font-size: 0.8em;
  margin-bottom: 4px;
  text-transform: uppercase;
}
.detail-grid strong {
  font-size: 1em;
}
.upload-panel,
.workflow-panel,
.receipt-list,
.portal-panel {
  background: linear-gradient(180deg, var(--detail-panel-strong), var(--detail-panel));
  border: 1px solid var(--detail-line);
  border-radius: 10px;
  box-shadow: 0 18px 50px rgba(2, 6, 23, 0.18);
  padding: 20px;
}
.workflow-panel {
  display: grid;
  gap: 12px;
}
.workflows {
  align-items: stretch;
  background: var(--detail-input);
  border: 1px solid var(--detail-soft-line);
  border-radius: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding: 4px;
}
.portal-panel {
  margin-top: 28px;
  display: grid;
  gap: 16px;
}
.portal-panel .muted {
  color: var(--detail-muted);
  font-size: 0.92em;
  margin-top: 4px;
}
.activity {
  color: var(--detail-muted);
  font-size: 0.9em;
  margin-top: 8px;
}
.activity strong {
  color: var(--detail-text);
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
  color: var(--detail-muted);
  text-transform: uppercase;
  gap: 4px;
}
.link-form input {
  background: var(--detail-input);
  border: 1px solid var(--detail-line);
  border-radius: 8px;
  color: var(--detail-text);
  padding: 9px 10px;
}
.link-table .url {
  display: flex;
  gap: 8px;
  align-items: center;
}
.link-table .url code {
  background: var(--detail-input);
  border: 1px solid var(--detail-soft-line);
  border-radius: 6px;
  display: inline-block;
  font-size: 0.82em;
  max-width: 460px;
  overflow: hidden;
  padding: 4px 6px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.link-table .copy {
  font-size: 0.82em;
  min-height: 0;
  padding: 5px 9px;
}
.link-table tr.revoked {
  opacity: 0.55;
}
button.danger {
  border-color: rgba(251, 113, 133, 0.45);
  color: #fda4af;
  font-size: 0.85em;
  padding: 6px 10px;
}
button.danger:hover:not(:disabled) {
  background: rgba(251, 113, 133, 0.1);
  border-color: rgba(251, 113, 133, 0.72);
  color: #fecdd3;
}
.comment-button {
  font-size: 0.85em;
  padding: 6px 10px;
}
.comment-button span {
  color: #fda4af;
}
.upload-panel {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 22px;
  align-items: center;
  margin-bottom: 24px;
}
.upload-panel h2,
.portal-panel h2,
.receipt-list h2 {
  font-size: 1.08em;
}
.upload-panel .eyebrow,
.portal-panel .eyebrow,
.workflow-panel .eyebrow,
.receipt-list .eyebrow {
  color: #93c5fd;
  font-size: 0.78em;
  font-weight: 700;
}
.title-row .info-tooltip {
  margin-left: 2px;
  transform: translateY(-1px);
}
.upload-panel p {
  color: var(--detail-muted);
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
  background: var(--detail-input);
  border: 1px solid var(--detail-line);
  border-radius: 8px;
  color: var(--detail-muted);
  display: grid;
  gap: 10px;
  grid-template-columns: auto minmax(0, 1fr);
  min-height: 48px;
  padding: 6px;
}
.file-picker:hover,
.file-picker.selected {
  border-color: rgba(20, 184, 166, 0.7);
}
.file-picker.selected strong {
  color: var(--detail-text);
}
.file-picker input {
  display: none;
}
.file-picker span {
  background: rgba(148, 163, 184, 0.12);
  border: 1px solid var(--detail-soft-line);
  border-radius: 6px;
  color: var(--detail-text);
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
  border: 1px solid var(--detail-line);
  border-radius: 8px;
  background: rgba(148, 163, 184, 0.08);
  color: var(--detail-text);
  cursor: pointer;
  font: inherit;
  padding: 10px 14px;
}
.header-link {
  background: transparent;
  border-color: transparent;
  color: var(--accent);
  padding: 0;
}
.header-link:hover:not(:disabled) {
  background: transparent;
  border-color: transparent;
  color: var(--accent-hover);
}
button[type="submit"] {
  background: linear-gradient(135deg, var(--detail-accent), #5b5df6);
  border-color: transparent;
  color: white;
  font-weight: 600;
  min-height: 48px;
}
button:hover:not(:disabled) {
  border-color: rgba(167, 139, 250, 0.52);
  background: rgba(148, 163, 184, 0.14);
}
button[type="submit"]:hover:not(:disabled) {
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
.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}
table {
  border-collapse: collapse;
  font-size: 0.94em;
  width: 100%;
}
th,
td {
  border-bottom: 1px solid var(--detail-soft-line);
  padding: 11px 8px;
  text-align: left;
}
th {
  color: var(--detail-muted);
  font-size: 0.78em;
  text-transform: uppercase;
}
tbody tr:hover {
  background: rgba(148, 163, 184, 0.05);
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
  color: var(--detail-muted);
}
.error {
  color: #fda4af;
}
.comment-overlay {
  align-items: center;
  background: rgba(2, 6, 23, 0.72);
  bottom: 0;
  display: flex;
  justify-content: center;
  left: 0;
  padding: 24px;
  position: fixed;
  right: 0;
  top: 0;
  z-index: 50;
}
.confirm-overlay {
  align-items: center;
  background: rgba(2, 6, 23, 0.72);
  bottom: 0;
  display: flex;
  justify-content: center;
  left: 0;
  padding: 24px;
  position: fixed;
  right: 0;
  top: 0;
  z-index: 60;
}
.confirm-panel {
  background: var(--detail-panel);
  border: 1px solid var(--detail-line);
  border-radius: 10px;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.38);
  display: grid;
  gap: 12px;
  padding: 20px;
  width: min(420px, 100%);
}
.confirm-panel h2 {
  font-size: 1.12em;
}
.confirm-panel p:not(.eyebrow) {
  color: var(--detail-muted);
}
.confirm-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 4px;
}
.confirm-yes {
  background: linear-gradient(135deg, var(--detail-accent), #5b5df6);
  border-color: transparent;
  color: white;
  font-weight: 600;
}
.confirm-yes:hover:not(:disabled) {
  background: linear-gradient(135deg, #8b5cf6, #6366f1);
}
.comment-panel {
  background: var(--detail-panel);
  border: 1px solid var(--detail-line);
  border-radius: 8px;
  display: grid;
  gap: 16px;
  max-height: min(720px, calc(100vh - 48px));
  overflow: auto;
  padding: 20px;
  width: min(680px, 100%);
}
.comment-panel header {
  margin-bottom: 0;
}
.thread {
  display: grid;
  gap: 10px;
}
.comment {
  background: var(--detail-input);
  border: 1px solid var(--detail-line);
  border-radius: 8px;
  padding: 12px;
}
.comment.bookkeeper {
  border-color: var(--detail-accent);
}
.comment div {
  display: flex;
  gap: 12px;
  justify-content: space-between;
}
.comment span {
  color: var(--detail-muted);
  font-size: 0.8em;
}
.comment p {
  margin: 8px 0 0;
  white-space: pre-wrap;
}
.comment-form {
  display: grid;
  gap: 10px;
}
.comment-form label {
  color: var(--detail-muted);
  display: grid;
  font-size: 0.78em;
  gap: 5px;
  text-transform: uppercase;
}
.comment-form textarea {
  background: var(--detail-input);
  border: 1px solid var(--detail-line);
  border-radius: 8px;
  color: var(--detail-text);
  font: inherit;
  min-height: 110px;
  padding: 10px;
  resize: vertical;
  text-transform: none;
}
@media (max-width: 640px) {
  header {
    align-items: flex-start;
    flex-direction: column;
  }
  .workflows a {
    flex-basis: calc(50% - 4px);
    padding-inline: 8px;
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
@media (max-width: 420px) {
  .workflows a {
    flex-basis: 100%;
  }
}
</style>
