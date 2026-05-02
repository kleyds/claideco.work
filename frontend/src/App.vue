<template>
  <div class="layout">
    <Nav />
    <main>
      <router-view />
    </main>
    <footer>
      <div class="container">
        <p>&copy; 2026 Claideco &middot; Independent software studio.</p>
      </div>
    </footer>
  </div>
</template>

<script setup>
import Nav from './components/Nav.vue'
</script>

<style scoped>
.layout {
  min-height: 100%;
  display: flex;
  flex-direction: column;
}
main {
  flex: 1;
  padding: 48px 0 96px;
}
footer {
  border-top: 1px solid var(--border);
  padding: 24px 0;
  color: var(--muted);
  font-size: 0.9em;
}
</style>
