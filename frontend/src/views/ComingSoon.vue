<template>
  <div class="container coming-soon">
    <p class="eyebrow">Coming next</p>
    <h1>{{ title }}</h1>
    <p>{{ message }}</p>
    <router-link :to="backTo">Back to client</router-link>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const clientId = route.params.id
const backTo = computed(() => `/app/clients/${clientId}`)
const isReview = computed(() => route.path.includes('/review'))
const title = computed(() => (isReview.value ? 'Review queue' : 'Receipt archive'))
const message = computed(() =>
  isReview.value
    ? 'The split-screen invoice validation workspace is the next implementation slice.'
    : 'Archive search, filters, and BIR-ready exports will build on the receipt processing flow.'
)
</script>

<style scoped>
.coming-soon {
  padding: 48px 24px 72px;
  max-width: 720px;
}
.eyebrow {
  color: var(--accent-hover);
  font-size: 0.78em;
  font-weight: 700;
  margin-bottom: 4px;
  text-transform: uppercase;
}
h1 {
  margin-bottom: 12px;
}
p {
  color: var(--muted);
  margin-bottom: 18px;
}
</style>
