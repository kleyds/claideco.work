<template>
  <nav>
    <div class="container nav-inner">
      <router-link to="/" class="brand">
        <span class="logo">C</span>
        <span>Claideco</span>
      </router-link>
      <div class="links">
        <router-link to="/products">Products</router-link>
        <router-link to="/docs">Docs</router-link>
        <router-link to="/about">About</router-link>
      </div>
    </div>
  </nav>
</template>

<style scoped>
nav {
  border-bottom: 1px solid var(--border);
  padding: 16px 0;
  background: var(--surface);
  position: sticky;
  top: 0;
  z-index: 10;
}
.nav-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 600;
  font-size: 1.05em;
  color: var(--text);
}
.logo {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  background: var(--accent);
  color: white;
  font-size: 0.9em;
  font-weight: 700;
}
.links {
  display: flex;
  gap: 24px;
}
.links a {
  color: var(--muted);
  font-size: 0.95em;
}
.links a:hover,
.links a.router-link-active {
  color: var(--text);
}
</style>
