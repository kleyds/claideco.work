<template>
  <div class="container form-page">
    <header>
      <div>
        <p class="eyebrow">New client</p>
        <h1>Add company</h1>
      </div>
      <router-link to="/app">Back to clients</router-link>
    </header>

    <form @submit.prevent="onSubmit">
      <label>
        Company name
        <input v-model="form.name" type="text" required autocomplete="organization" />
      </label>
      <label>
        TIN
        <input v-model="form.tin" type="text" placeholder="000-000-000-00000" />
      </label>
      <label>
        Address
        <textarea v-model="form.address" rows="3" />
      </label>
      <label>
        Industry
        <input v-model="form.industry" type="text" placeholder="Retail, services, food, etc." />
      </label>
      <label>
        Accounting software
        <select v-model="form.software">
          <option value="quickbooks">QuickBooks</option>
          <option value="xero">Xero</option>
          <option value="juantax">JuanTax</option>
          <option value="excel">Excel</option>
          <option value="other">Other</option>
        </select>
      </label>

      <p v-if="error" class="error">{{ error }}</p>
      <button type="submit" :disabled="loading">
        {{ loading ? 'Saving...' : 'Create client' }}
      </button>
    </form>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { apiFetch, clearToken } from '../api'

const router = useRouter()
const loading = ref(false)
const error = ref('')
const form = reactive({
  name: '',
  tin: '',
  address: '',
  industry: '',
  software: 'other',
})

async function onSubmit() {
  loading.value = true
  error.value = ''

  try {
    await apiFetch('/clients', {
      method: 'POST',
      body: JSON.stringify(form),
    })
    router.push('/app')
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
</script>

<style scoped>
.form-page {
  max-width: 760px;
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
form {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  display: grid;
  gap: 18px;
  padding: 24px;
}
label {
  color: var(--muted);
  display: grid;
  gap: 6px;
  font-size: 0.92em;
}
input,
textarea,
select {
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg);
  color: var(--text);
  font: inherit;
  padding: 12px 14px;
}
input:focus,
textarea:focus,
select:focus {
  outline: none;
  border-color: var(--accent);
}
button {
  border: 0;
  border-radius: 8px;
  background: var(--accent);
  color: white;
  cursor: pointer;
  font: inherit;
  font-weight: 600;
  justify-self: start;
  padding: 12px 16px;
}
button:disabled {
  cursor: wait;
  opacity: 0.7;
}
.error {
  color: #fca5a5;
  font-size: 0.92em;
}
@media (max-width: 640px) {
  header {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
