<template>
  <div class="auth-page">
    <section class="auth-panel">
      <p class="eyebrow">PesoBooks</p>
      <h1>Create account</h1>
      <form @submit.prevent="onSubmit">
        <label>
          Name
          <input v-model="name" type="text" autocomplete="name" required />
        </label>
        <label>
          Email
          <input v-model="email" type="email" autocomplete="email" required />
        </label>
        <label>
          Password
          <input v-model="password" type="password" autocomplete="new-password" minlength="8" required />
        </label>
        <p v-if="error" class="error">{{ error }}</p>
        <button type="submit" :disabled="loading">
          {{ loading ? 'Creating account...' : 'Create account' }}
        </button>
      </form>
      <p class="switch">
        Already have an account?
        <router-link to="/login">Log in</router-link>
      </p>
    </section>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { apiFetch, setToken } from '../api'

const router = useRouter()
const name = ref('')
const email = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

async function onSubmit() {
  loading.value = true
  error.value = ''

  try {
    const data = await apiFetch('/auth/register', {
      method: 'POST',
      body: JSON.stringify({
        name: name.value,
        email: email.value,
        password: password.value,
      }),
    })
    setToken(data.access_token)
    router.push('/app')
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-page {
  min-height: 520px;
  display: grid;
  place-items: center;
  padding: 24px;
}
.auth-panel {
  width: min(100%, 420px);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 32px;
}
.eyebrow {
  color: var(--accent-hover);
  font-size: 0.8em;
  font-weight: 700;
  margin-bottom: 8px;
  text-transform: uppercase;
}
h1 {
  margin-bottom: 24px;
}
form {
  display: grid;
  gap: 16px;
}
label {
  display: grid;
  gap: 6px;
  color: var(--muted);
  font-size: 0.92em;
}
input {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg);
  color: var(--text);
  padding: 12px 14px;
  font: inherit;
}
input:focus {
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
.switch {
  color: var(--muted);
  margin-top: 20px;
  font-size: 0.92em;
}
</style>
