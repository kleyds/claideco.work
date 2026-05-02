<template>
  <div>
    <section class="hero">
      <div class="container">
        <span class="badge">Now in private beta &middot; Philippines</span>
        <h1>Stop typing resibos.</h1>
        <p class="lead">
          PesoBooks turns receipts, invoices, and GCash statements into clean accounting
          entries &mdash; for Filipino bookkeepers who are tired of doing it by hand.
        </p>
        <div class="cta">
          <a href="#waitlist" class="btn">Join the waitlist</a>
          <a href="#how" class="btn secondary">How it works</a>
        </div>
      </div>
    </section>

    <section class="container problem">
      <h2>The problem</h2>
      <div class="problem-grid">
        <div>
          <h3>Hours per week, gone</h3>
          <p>The average bookkeeper retypes hundreds of receipts a week. That's billable time you can't bill.</p>
        </div>
        <div>
          <h3>Global tools don't speak BIR</h3>
          <p>Hubdoc and Dext skip TIN, OR/SI, ATP fields. Textract chokes on handwritten palengke receipts.</p>
        </div>
        <div>
          <h3>GCash, Maya, BPI, BDO &mdash; every format different</h3>
          <p>Five banks, five PDF layouts. You parse them by hand or you don't reconcile at all.</p>
        </div>
        <div>
          <h3>Clients send chaos</h3>
          <p>Phone photos in Viber, screenshots in Messenger, scanned PDFs over email. Nothing's tidy.</p>
        </div>
      </div>
    </section>

    <section id="how" class="container how">
      <h2>How it works</h2>
      <ol class="steps">
        <li>
          <span class="step-num">1</span>
          <div>
            <h3>Receipts come in</h3>
            <p>Your client snaps a photo on their phone, forwards an email, or uploads a PDF. Or you drop 50 at once.</p>
          </div>
        </li>
        <li>
          <span class="step-num">2</span>
          <div>
            <h3>PesoBooks reads them</h3>
            <p>Vendor name, TIN, OR/SI number, date, VAT-able amount, VAT, total &mdash; extracted and sanity-checked.</p>
          </div>
        </li>
        <li>
          <span class="step-num">3</span>
          <div>
            <h3>You review and approve</h3>
            <p>Side-by-side photo and fields. Fix anything wrong in seconds. Audit trail kept for BIR.</p>
          </div>
        </li>
        <li>
          <span class="step-num">4</span>
          <div>
            <h3>One click to your software</h3>
            <p>Push to QuickBooks Online, Xero, JuanTax, or export a clean CSV. No copy-paste.</p>
          </div>
        </li>
      </ol>
    </section>

    <section class="container why">
      <h2>Why PesoBooks (and not Hubdoc, Dext, or Textract)</h2>
      <div class="compare">
        <div class="compare-row head">
          <div></div>
          <div>PesoBooks</div>
          <div>Global tools</div>
        </div>
        <div class="compare-row">
          <div>Handwritten Filipino receipts</div>
          <div class="yes">Built for them</div>
          <div class="no">Often unreadable</div>
        </div>
        <div class="compare-row">
          <div>BIR OR format (TIN, ATP, OR/SI #)</div>
          <div class="yes">First-class fields</div>
          <div class="no">Not parsed</div>
        </div>
        <div class="compare-row">
          <div>GCash, Maya, BPI, BDO statements</div>
          <div class="yes">Out of the box</div>
          <div class="no">Manual mapping</div>
        </div>
        <div class="compare-row">
          <div>Tagalog &amp; Bisaya OCR</div>
          <div class="yes">Yes</div>
          <div class="no">English-only models</div>
        </div>
        <div class="compare-row">
          <div>Pricing in pesos</div>
          <div class="yes">Designed for PH firm sizes</div>
          <div class="no">USD, enterprise tiers</div>
        </div>
        <div class="compare-row">
          <div>Free seats for your SMB clients</div>
          <div class="yes">Yes &mdash; you pay, they upload</div>
          <div class="no">Per-seat pricing for everyone</div>
        </div>
      </div>
    </section>

    <section class="container built-for">
      <h2>Built for bookkeepers</h2>
      <div class="features-grid">
        <div class="feature">
          <h3>Multi-client workspace</h3>
          <p>Manage all your clients in one workspace. Switch between books in two clicks.</p>
        </div>
        <div class="feature">
          <h3>Client portal &mdash; free for them</h3>
          <p>Your SMB clients get a simple page to upload receipts. They never see the accounting layer.</p>
        </div>
        <div class="feature">
          <h3>Bulk processing</h3>
          <p>Drop 200 receipts at once. Walk away. Come back to a review queue.</p>
        </div>
        <div class="feature">
          <h3>Audit-friendly</h3>
          <p>Original image, extracted data, edits, and approver are all logged. BIR-ready.</p>
        </div>
        <div class="feature">
          <h3>Direct exports</h3>
          <p>QuickBooks Online, Xero, JuanTax, or CSV. We meet your stack, not the other way around.</p>
        </div>
        <div class="feature">
          <h3>API access</h3>
          <p>Power-user firms can hit our HTTP API directly. <router-link to="/docs">See the docs</router-link>.</p>
        </div>
      </div>
    </section>

    <section id="waitlist" class="container waitlist">
      <div class="waitlist-inner">
        <h2>Join the private beta</h2>
        <p>
          We're working with a small group of Filipino bookkeepers and accounting firms before
          public release. Early access gets locked-in launch pricing and a direct line to the founder.
        </p>
        <form @submit.prevent="onSubmit" class="form">
          <input
            v-model="email"
            type="email"
            required
            placeholder="you@yourfirm.ph"
            aria-label="Your email"
          />
          <button type="submit" class="btn">Request access</button>
        </form>
        <p v-if="submitted" class="success">
          Thanks! We'll be in touch within a week.
        </p>
        <p class="hint">
          Or email <a href="mailto:hello@claideco.work">hello@claideco.work</a> directly.
        </p>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const email = ref('')
const submitted = ref(false)

function onSubmit() {
  // TODO wire to backend waitlist endpoint
  submitted.value = true
  email.value = ''
}
</script>

<style scoped>
.hero {
  padding: 96px 0 72px;
  text-align: center;
  background:
    radial-gradient(circle at 20% 0%, rgba(99, 102, 241, 0.18), transparent 50%),
    radial-gradient(circle at 80% 20%, rgba(129, 140, 248, 0.12), transparent 50%);
  border-bottom: 1px solid var(--border);
}
.badge {
  display: inline-block;
  padding: 4px 12px;
  background: var(--surface-2);
  color: var(--muted);
  border-radius: 999px;
  font-size: 0.8em;
  margin-bottom: 24px;
  letter-spacing: 0.02em;
}
.hero h1 {
  font-size: clamp(2.4em, 5.5vw, 3.6em);
  margin-bottom: 20px;
  background: linear-gradient(120deg, #e7e9ee 0%, #818cf8 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.lead {
  font-size: 1.18em;
  color: var(--muted);
  max-width: 680px;
  margin: 0 auto 32px;
}
.cta {
  display: flex;
  gap: 12px;
  justify-content: center;
  flex-wrap: wrap;
}
.btn {
  display: inline-block;
  padding: 12px 24px;
  border-radius: 8px;
  background: var(--accent);
  color: white;
  font-weight: 500;
  border: none;
  cursor: pointer;
  font-size: 1em;
  transition: background 0.15s ease;
}
.btn:hover {
  background: var(--accent-hover);
  color: white;
}
.btn.secondary {
  background: var(--surface-2);
  color: var(--text);
}
.btn.secondary:hover {
  background: var(--border);
  color: var(--text);
}

section {
  padding: 64px 24px;
}
section h2 {
  font-size: 1.6em;
  margin-bottom: 28px;
  text-align: center;
}

.problem-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 24px;
}
.problem-grid h3 {
  margin-bottom: 8px;
  font-size: 1.05em;
}
.problem-grid p {
  color: var(--muted);
  font-size: 0.95em;
}

.steps {
  list-style: none;
  max-width: 720px;
  margin: 0 auto;
  padding: 0;
}
.steps li {
  display: flex;
  gap: 20px;
  margin-bottom: 28px;
  align-items: flex-start;
}
.step-num {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: var(--accent);
  color: white;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
}
.steps h3 {
  margin-bottom: 4px;
  font-size: 1.05em;
}
.steps p {
  color: var(--muted);
  font-size: 0.95em;
}

.compare {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
  max-width: 860px;
  margin: 0 auto;
}
.compare-row {
  display: grid;
  grid-template-columns: 1.4fr 1fr 1fr;
  padding: 14px 20px;
  border-bottom: 1px solid var(--border);
  font-size: 0.95em;
  align-items: center;
}
.compare-row:last-child {
  border-bottom: none;
}
.compare-row.head {
  background: var(--surface-2);
  color: var(--muted);
  font-size: 0.85em;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 500;
}
.compare-row .yes {
  color: var(--accent-hover);
}
.compare-row .no {
  color: var(--muted);
}

.features-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 20px;
}
.feature {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 24px;
}
.feature h3 {
  margin-bottom: 8px;
  font-size: 1.05em;
}
.feature p {
  color: var(--muted);
  font-size: 0.95em;
}

.waitlist-inner {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 48px 32px;
  text-align: center;
  max-width: 640px;
  margin: 0 auto;
}
.waitlist-inner h2 {
  margin-bottom: 12px;
}
.waitlist-inner p {
  color: var(--muted);
  margin-bottom: 24px;
}
.form {
  display: flex;
  gap: 8px;
  max-width: 480px;
  margin: 0 auto;
  flex-wrap: wrap;
  justify-content: center;
}
.form input {
  flex: 1;
  min-width: 220px;
  padding: 12px 16px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--text);
  font-size: 1em;
}
.form input:focus {
  outline: none;
  border-color: var(--accent);
}
.success {
  margin-top: 16px;
  color: var(--accent-hover);
  font-size: 0.95em;
}
.hint {
  margin-top: 20px;
  font-size: 0.9em;
  color: var(--muted);
}

@media (max-width: 640px) {
  .compare-row {
    grid-template-columns: 1fr;
    gap: 6px;
  }
  .compare-row.head {
    display: none;
  }
}
</style>
