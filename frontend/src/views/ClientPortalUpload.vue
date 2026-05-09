<template>
  <div class="portal-page">
    <div class="card">
      <header>
        <p class="brand">PesoBooks</p>
        <h1 v-if="info">{{ info.client_name }}</h1>
        <p v-if="info?.label" class="label">{{ info.label }}</p>
      </header>

      <div v-if="loading" class="empty">Loading...</div>
      <div v-else-if="loadError" class="error">
        <strong>This link can't accept uploads right now.</strong>
        <p>{{ loadError }}</p>
      </div>
      <template v-else-if="info">
        <p class="instructions">
          Snap a photo of your receipt or invoice and upload here. JPEG, PNG, WebP, or PDF — up to {{ maxMb }} MB each.
        </p>

        <p v-if="info.uploads_remaining !== null" class="meta">
          {{ info.uploads_remaining }} upload{{ info.uploads_remaining === 1 ? '' : 's' }} remaining
          <span v-if="info.expires_at"> · expires {{ formatDate(info.expires_at) }}</span>
        </p>
        <p v-else-if="info.expires_at" class="meta">Expires {{ formatDate(info.expires_at) }}</p>

        <form @submit.prevent="upload">
          <label class="picker">
            <input
              ref="fileInput"
              type="file"
              multiple
              accept="image/jpeg,image/png,image/webp,application/pdf"
              capture="environment"
              @change="onFilesChange"
            />
            <span class="picker-cta">{{ files.length === 0 ? 'Choose files or take photo' : `${files.length} file${files.length === 1 ? '' : 's'} selected` }}</span>
          </label>
          <button type="submit" :disabled="files.length === 0 || uploading">
            {{ uploading ? 'Uploading...' : 'Upload' }}
          </button>
        </form>

        <div v-if="successCount" class="success">
          <strong>{{ successCount }} file{{ successCount === 1 ? '' : 's' }} uploaded.</strong>
          <p>Your bookkeeper will see them shortly. You can keep uploading more from this link.</p>
        </div>
        <p v-if="uploadError" class="error">{{ uploadError }}</p>
      </template>
    </div>
    <p class="footer">Secured by PesoBooks · <router-link to="/">claideco.work</router-link></p>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { API_BASE_URL } from '../api'

const route = useRoute()
const token = route.params.token

const info = ref(null)
const loading = ref(true)
const loadError = ref('')
const files = ref([])
const uploading = ref(false)
const uploadError = ref('')
const successCount = ref(0)
const fileInput = ref(null)
const maxMb = 20

onMounted(async () => {
  try {
    const res = await fetch(`${API_BASE_URL}/portal/${token}`)
    const data = await res.json().catch(() => null)
    if (!res.ok) throw new Error(data?.detail || 'This link is not valid.')
    info.value = data
  } catch (err) {
    loadError.value = err.message
  } finally {
    loading.value = false
  }
})

function onFilesChange(event) {
  files.value = Array.from(event.target.files || [])
  successCount.value = 0
  uploadError.value = ''
}

async function upload() {
  if (files.value.length === 0) return
  uploading.value = true
  uploadError.value = ''
  successCount.value = 0
  try {
    const body = new FormData()
    files.value.forEach((file) => body.append('files', file))
    const res = await fetch(`${API_BASE_URL}/portal/${token}/upload`, { method: 'POST', body })
    const data = await res.json().catch(() => null)
    if (!res.ok) throw new Error(data?.detail || 'Upload failed.')
    successCount.value = data.receipts.length
    files.value = []
    if (fileInput.value) fileInput.value.value = ''
    // Refresh remaining count
    const refreshed = await fetch(`${API_BASE_URL}/portal/${token}`)
    if (refreshed.ok) info.value = await refreshed.json()
  } catch (err) {
    uploadError.value = err.message
  } finally {
    uploading.value = false
  }
}

function formatDate(value) {
  if (!value) return ''
  return new Date(value).toLocaleDateString()
}
</script>

<style scoped>
.portal-page {
  min-height: 100vh;
  background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
  color: #f1f5f9;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 24px 16px 48px;
  gap: 24px;
}
.card {
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 16px;
  width: min(440px, 100%);
  padding: 28px 24px;
  display: grid;
  gap: 18px;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.35);
}
.brand {
  text-transform: uppercase;
  letter-spacing: 0.18em;
  font-size: 0.78em;
  color: #38bdf8;
  margin: 0;
}
h1 {
  margin: 4px 0 0;
  font-size: 1.6em;
}
.label {
  margin: 4px 0 0;
  color: #cbd5f5;
}
.instructions {
  margin: 0;
  font-size: 1em;
  color: #e2e8f0;
}
.meta {
  margin: 0;
  font-size: 0.86em;
  color: #94a3b8;
}
form {
  display: grid;
  gap: 12px;
}
.picker {
  background: rgba(56, 189, 248, 0.08);
  border: 2px dashed rgba(56, 189, 248, 0.35);
  border-radius: 12px;
  padding: 22px;
  text-align: center;
  cursor: pointer;
  display: block;
}
.picker input {
  display: none;
}
.picker-cta {
  font-weight: 600;
  font-size: 1.02em;
}
button[type='submit'] {
  background: #38bdf8;
  border: none;
  border-radius: 12px;
  color: #082f49;
  font-weight: 700;
  font-size: 1.05em;
  padding: 14px 18px;
  cursor: pointer;
  min-height: 52px;
}
button[type='submit']:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.success {
  background: rgba(34, 197, 94, 0.12);
  border: 1px solid rgba(34, 197, 94, 0.35);
  border-radius: 10px;
  padding: 12px 14px;
}
.success p {
  margin: 4px 0 0;
  color: #bbf7d0;
  font-size: 0.92em;
}
.error {
  background: rgba(248, 113, 113, 0.1);
  border: 1px solid rgba(248, 113, 113, 0.35);
  border-radius: 10px;
  padding: 12px 14px;
  color: #fecaca;
}
.error strong {
  display: block;
  margin-bottom: 4px;
}
.empty {
  color: #94a3b8;
}
.footer {
  color: #64748b;
  font-size: 0.86em;
}
.footer a {
  color: #94a3b8;
}
</style>
