<template>
  <div class="container products">
    <header>
      <h1>Products</h1>
      <p class="lead">
        Small, focused tools we run ourselves. Each one ships with an HTTP API and is
        self-hostable on a single machine.
      </p>
    </header>

    <div class="grid">
      <router-link to="/pesobooks" class="card">
        <div class="card-head">
          <div class="icon">₱</div>
          <span class="status live">Private beta</span>
        </div>
        <h2>PesoBooks</h2>
        <p class="tagline">Bookkeeping infrastructure for Filipino accounting firms.</p>
        <p class="desc">
          Receipts, invoices, and GCash statements turned into clean entries for
          QuickBooks, Xero, or JuanTax. Built for bookkeepers tired of typing.
        </p>
        <span class="link">Learn more &rarr;</span>
      </router-link>

      <div class="card disabled">
        <div class="card-head">
          <div class="icon muted">?</div>
          <span class="status soon">Planned</span>
        </div>
        <h2>Coming soon</h2>
        <p class="tagline">Another tool, in the same opinionated mold.</p>
        <p class="desc">
          We're shipping one product at a time and only adding the next when the current one
          earns it. Tell us what you'd buy.
        </p>
      </div>

      <div class="card disabled">
        <div class="card-head">
          <div class="icon muted">?</div>
          <span class="status soon">Idea</span>
        </div>
        <h2>Got a problem?</h2>
        <p class="tagline">We work with design partners on each new product.</p>
        <p class="desc">
          If you have a recurring back-office headache that a small, sharp tool would solve,
          <router-link to="/about">get in touch</router-link>.
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.products {
  padding: 32px 24px 64px;
}
header {
  margin-bottom: 40px;
  max-width: 720px;
}
header h1 {
  margin-bottom: 12px;
}
.lead {
  color: var(--muted);
  font-size: 1.1em;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 20px;
}
.card {
  display: block;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 28px;
  color: var(--text);
  transition: border-color 0.15s ease, transform 0.15s ease;
}
.card:hover:not(.disabled) {
  border-color: var(--accent);
  transform: translateY(-2px);
  color: var(--text);
}
.card.disabled {
  opacity: 0.65;
  cursor: default;
}
.card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.icon {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  background: var(--accent);
  color: white;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
}
.icon.muted {
  background: var(--surface-2);
  color: var(--muted);
}
.status {
  font-size: 0.75em;
  padding: 3px 10px;
  border-radius: 999px;
  letter-spacing: 0.04em;
}
.status.live {
  background: rgba(99, 102, 241, 0.15);
  color: var(--accent-hover);
}
.status.soon {
  background: var(--surface-2);
  color: var(--muted);
}
.card h2 {
  margin-bottom: 4px;
  font-size: 1.3em;
}
.tagline {
  color: var(--muted);
  margin-bottom: 14px;
  font-size: 0.95em;
}
.desc {
  color: var(--muted);
  font-size: 0.95em;
  margin-bottom: 16px;
}
.link {
  color: var(--accent);
  font-size: 0.95em;
}
</style>
