<script lang="ts">
	import { onMount } from 'svelte';

	function copyText(text: string, btn: HTMLButtonElement) {
		navigator.clipboard.writeText(text).then(() => {
			const orig = btn.textContent ?? '';
			btn.textContent = 'Copied ✓';
			btn.style.color = 'var(--accent)';
			btn.style.borderColor = 'var(--accent)';
			setTimeout(() => {
				btn.textContent = orig;
				btn.style.color = '';
				btn.style.borderColor = '';
			}, 1500);
		});
	}

	let activeStep = $state(1);

	onMount(() => {
		const steps = document.querySelectorAll<HTMLElement>('[data-step]');
		const io = new IntersectionObserver(
			(entries) => {
				entries.forEach((e) => {
					if (e.isIntersecting) {
						activeStep = Number((e.target as HTMLElement).dataset.step ?? 1);
					}
				});
			},
			{ rootMargin: '-30% 0px -60% 0px' }
		);
		steps.forEach((s) => io.observe(s));
		return () => io.disconnect();
	});
</script>

<svelte:head>
	<title>Quick Start — Ezra × Google Cloud ADK</title>
</svelte:head>

<main class="qs-shell">
	<!-- Sidebar -->
	<aside class="qs-sidebar">
		<div class="qs-sidebar-inner">
			<div class="qs-sidebar-label">// Google Cloud ADK</div>
			<ol class="qs-steps-nav">
				{#each [[1, 'Prerequisites'], [2, 'Install Ezra'], [3, 'Google Cloud Auth'], [4, 'Configure Ezra'], [5, 'First ADK Agent'], [6, 'Run & Verify'], [7, 'Next Steps']] as [n, label]}
					<li>
						<a href="#step-{n}" class:active={activeStep === n}>
							<span class="qs-step-num">{n}</span>
							{label}
						</a>
					</li>
				{/each}
			</ol>

			<div class="qs-sidebar-sep"></div>

			<div class="qs-sidebar-links">
				<a href="/docs">← Full Docs</a>
				<a href="/docs/sdk">Python SDK</a>
				<a href="/docs/rest-api">REST API</a>
			</div>
		</div>
	</aside>

	<!-- Content -->
	<div class="qs-content">
		<!-- Header -->
		<div class="qs-header">
			<div class="qs-breadcrumb">
				<a href="/">Ezra</a>
				<span>/</span>
				<a href="/docs">Docs</a>
				<span>/</span>
				<span>Quick Start</span>
			</div>
			<h1>Google Cloud ADK<br /><em>Connector</em></h1>
			<p class="qs-intro">
				Get a multi-agent system running on Google Cloud with Ezra memory and belief tracking in
				under 15 minutes. This guide uses Google ADK (Agent Development Kit) with GKE, Secret
				Manager, and MongoDB Atlas.
			</p>

			<div class="qs-prereq-badge">
				<span>⏱ ~15 min</span>
				<span>·</span>
				<span>Python 3.12</span>
				<span>·</span>
				<span>Google Cloud Project required</span>
			</div>
		</div>

		<!-- Step 1 -->
		<section id="step-1" data-step="1" class="qs-section">
			<div class="qs-step-label">
				<span class="qs-step-n">01</span>
				<h2>Prerequisites</h2>
			</div>

			<p>Before starting, ensure you have:</p>

			<ul class="qs-checklist">
				<li><span class="ck">✓</span> Python 3.12</li>
				<li>
					<span class="ck">✓</span>
					<a href="https://cloud.google.com/sdk/docs/install" target="_blank" rel="noopener"
						>Google Cloud SDK</a
					>
					(<code>gcloud</code>) installed and authenticated
				</li>
				<li><span class="ck">✓</span> A Google Cloud project with billing enabled</li>
				<li><span class="ck">✓</span> A MongoDB Atlas cluster (free tier works for this guide)</li>
				<li>
					<span class="ck">✓</span> Redis — local Docker or
					<a href="https://cloud.google.com/memorystore" target="_blank" rel="noopener"
						>Memorystore</a
					> on GCP
				</li>
			</ul>

			<div class="qs-callout">
				<span class="qs-callout-label">// GCP APIs to enable</span>
				<div class="qs-code-wrap">
					<div class="qs-code-bar">
						<span>bash</span>
						<button
							onclick={(e) =>
								copyText(
									'gcloud services enable container.googleapis.com secretmanager.googleapis.com aiplatform.googleapis.com',
									e.currentTarget as HTMLButtonElement
								)}>Copy</button
						>
					</div>
					<pre class="qs-code">gcloud services enable \
  container.googleapis.com \
  secretmanager.googleapis.com \
  aiplatform.googleapis.com</pre>
				</div>
			</div>
		</section>

		<!-- Step 2 -->
		<section id="step-2" data-step="2" class="qs-section">
			<div class="qs-step-label">
				<span class="qs-step-n">02</span>
				<h2>Install Ezra</h2>
			</div>

			<p>Install the platform with the ADK extension:</p>

			<div class="qs-code-wrap">
				<div class="qs-code-bar">
					<span>bash</span>
					<button
						onclick={(e) =>
							copyText('pip install "ezra-platform[adk]"', e.currentTarget as HTMLButtonElement)}
						>Copy</button
					>
				</div>
				<pre class="qs-code"><span class="kw">pip install</span> <span class="str"
						>"ezra-platform[adk]"</span
					></pre>
			</div>

			<p>Verify the installation:</p>

			<div class="qs-code-wrap">
				<div class="qs-code-bar">
					<span>bash</span>
					<button
						onclick={(e) =>
							copyText(
								'python -c "import ezra_core; print(ezra_core.__version__)"',
								e.currentTarget as HTMLButtonElement
							)}>Copy</button
					>
				</div>
				<pre class="qs-code"><span class="kw">python</span> -c <span class="str"
						>"import ezra_core; print(ezra_core.__version__)"</span
					>
<span class="cm"># Expected: 0.1.0</span></pre>
			</div>
		</section>

		<!-- Step 3 -->
		<section id="step-3" data-step="3" class="qs-section">
			<div class="qs-step-label">
				<span class="qs-step-n">03</span>
				<h2>Google Cloud Auth</h2>
			</div>

			<p>
				Create a service account for Ezra with the minimum required roles. Ezra uses this account to
				read from Secret Manager and optionally write to Cloud Logging.
			</p>

			<div class="qs-code-wrap">
				<div class="qs-code-bar">
					<span>bash</span>
					<button onclick={(e) => copyText('', e.currentTarget as HTMLButtonElement)}>Copy</button>
				</div>
				<pre class="qs-code"><span class="cm"># Create a service account</span>
gcloud iam service-accounts create ezra-runtime \
  --display-name=<span class="str">"Ezra Runtime"</span>

<span class="cm"># Grant Secret Manager access</span>
gcloud projects add-iam-policy-binding <span class="str">$PROJECT_ID</span> \
  --member=<span class="str">"serviceAccount:ezra-runtime@$PROJECT_ID.iam.gserviceaccount.com"</span
					> \
  --role=<span class="str">"roles/secretmanager.secretAccessor"</span>

<span class="cm"
						># Keyless: bind the GKE service account to this GSA (Workload Identity — no key files)</span
					>
gcloud iam service-accounts add-iam-policy-binding \
  ezra-runtime@<span class="str">$PROJECT_ID</span>.iam.gserviceaccount.com \
  --role=<span class="str">"roles/iam.workloadIdentityUser"</span> \
  --member=<span class="str">"serviceAccount:$PROJECT_ID.svc.id.goog[ezra/ezra-api]"</span></pre>
			</div>

			<div class="qs-callout teal">
				<span class="qs-callout-label">// Production</span>
				On GKE, use <strong>Workload Identity</strong> instead of key files. Annotate the Kubernetes
				service account to impersonate <code>ezra-runtime@...</code> and skip
				<code>GOOGLE_APPLICATION_CREDENTIALS</code> entirely — no key ever touches disk.
			</div>

			<p>Store your MongoDB URI and Redis URL in Secret Manager:</p>

			<div class="qs-code-wrap">
				<div class="qs-code-bar">
					<span>bash</span>
					<button onclick={(e) => copyText('', e.currentTarget as HTMLButtonElement)}>Copy</button>
				</div>
				<pre class="qs-code">printf <span class="str"
						>"mongodb+srv://user:pass@cluster.mongodb.net"</span
					> | \
  gcloud secrets create EZRA_MONGO_URI --data-file=-

printf <span class="str">"redis://10.0.0.1:6379"</span> | \
  gcloud secrets create EZRA_REDIS_URL --data-file=-</pre>
			</div>
		</section>

		<!-- Step 4 -->
		<section id="step-4" data-step="4" class="qs-section">
			<div class="qs-step-label">
				<span class="qs-step-n">04</span>
				<h2>Configure Ezra</h2>
			</div>

			<p>
				Create a <code>.env</code> file for local development. In production these values are pulled automatically
				from Secret Manager.
			</p>

			<div class="qs-code-wrap">
				<div class="qs-code-bar">
					<span>.env</span>
					<button onclick={(e) => copyText('', e.currentTarget as HTMLButtonElement)}>Copy</button>
				</div>
				<pre class="qs-code"><span class="cm"># Google Cloud</span>
GOOGLE_APPLICATION_CREDENTIALS=<span class="str">./ezra-key.json</span>
GCP_PROJECT=<span class="str">my-project-id</span>
GCP_LOCATION=<span class="str">us-central1</span>

<span class="cm"># Storage</span>
EZRA_MONGO_URI=<span class="str">mongodb+srv://user:pass@cluster.mongodb.net</span>
EZRA_REDIS_URL=<span class="str">redis://localhost:6379</span>

<span class="cm"># Ezra core</span>
EZRA_API_KEY=<span class="str">sk-ezra-local-dev</span>
EZRA_BELIEF_STRATEGY=<span class="str">last_write</span>
EZRA_LOG_LEVEL=<span class="str">INFO</span></pre>
			</div>
		</section>

		<!-- Step 5 -->
		<section id="step-5" data-step="5" class="qs-section">
			<div class="qs-step-label">
				<span class="qs-step-n">05</span>
				<h2>First ADK Agent</h2>
			</div>

			<p>
				Create a simple ADK agent that uses Ezra for memory recall and belief tracking. This pattern
				wraps any Google ADK agent with the <code>EzraService</code> adapter.
			</p>

			<div class="qs-code-wrap">
				<div class="qs-code-bar">
					<span>agent.py</span>
					<button onclick={(e) => copyText('', e.currentTarget as HTMLButtonElement)}>Copy</button>
				</div>
				<pre class="qs-code"><span class="kw">import</span> asyncio
<span class="kw">from</span> dotenv <span class="kw">import</span> load_dotenv
<span class="kw">from</span> ezra.adk_service <span class="kw">import</span> EzraService
<span class="kw">from</span> google.adk.agents <span class="kw">import</span> LlmAgent

load_dotenv()

<span class="cm"># Initialise Ezra — connects to Redis (hot tier) and MongoDB (cold tier)</span>
ezra = EzraService(
    session_graph_id=<span class="str">"demo-fleet"</span>,
    project=<span class="str">"my-project-id"</span>,
    location=<span class="str">"us-central1"</span>,
)

<span class="kw">class</span> <span class="fn">AnalystAgent</span>(LlmAgent):
    <span class="str">"""An ADK agent with Ezra memory and belief tracking."""</span>

    agent_id = <span class="str">"analyst"</span>
    permission_scope = [<span class="str">"market_data"</span>, <span class="str">"reports"</span>]

    <span class="kw">async def</span> <span class="fn">before_model_call</span>(self, ctx):
        <span class="cm"># Hydrate memory from all three tiers (hot → warm → cold)</span>
        memory = <span class="kw">await</span> ezra.recall(
            agent_id=self.agent_id,
            scope=self.permission_scope,
        )
        ctx.inject_memory(memory)

    <span class="kw">async def</span> <span class="fn">after_model_call</span>(self, ctx, response):
        <span class="cm"># Commit any beliefs the agent asserted</span>
        <span class="kw">await</span> ezra.commit(
            agent_id=self.agent_id,
            beliefs=response.asserted_beliefs,
            sources=ctx.sources_used,
        )

<span class="kw">async def</span> <span class="fn">main</span>():
    agent = AnalystAgent(model=<span class="str">"gemini-3.5-flash"</span>)

    result = <span class="kw">await</span> agent.run(
        prompt=<span class="str">"Summarise Q1 2026 revenue trends and flag any anomalies."</span>,
        sources=[<span class="str">"mongodb://cluster/financials"</span>],
    )

    print(result.content)
    print(<span class="str">f"\nBelief snapshot ID: </span>&#123;result.belief_id&#125;<span
						class="str">"</span
					>)

asyncio.run(main())</pre>
			</div>
		</section>

		<!-- Step 6 -->
		<section id="step-6" data-step="6" class="qs-section">
			<div class="qs-step-label">
				<span class="qs-step-n">06</span>
				<h2>Run & Verify</h2>
			</div>

			<p>Run the agent locally:</p>

			<div class="qs-code-wrap">
				<div class="qs-code-bar">
					<span>bash</span>
					<button onclick={(e) => copyText('python agent.py', e.currentTarget as HTMLButtonElement)}
						>Copy</button
					>
				</div>
				<pre class="qs-code">python agent.py</pre>
			</div>

			<p>Verify the Ezra runtime is healthy:</p>

			<div class="qs-code-wrap">
				<div class="qs-code-bar">
					<span>bash</span>
					<button
						onclick={(e) =>
							copyText(
								'curl http://localhost:8080/ezra/health',
								e.currentTarget as HTMLButtonElement
							)}>Copy</button
					>
				</div>
				<pre class="qs-code">curl http://localhost:8080/ezra/health
<span class="cm"># Expected:</span>
&#123; <span class="str">"status"</span>: <span class="str">"ok"</span>, <span class="str"
						>"hot_tier"</span
					>: <span class="str">"connected"</span>, <span class="str">"cold_tier"</span>: <span
						class="str">"connected"</span
					> &#125;</pre>
			</div>

			<p>Check that the belief was written to MongoDB:</p>

			<div class="qs-code-wrap">
				<div class="qs-code-bar">
					<span>bash</span>
					<button onclick={(e) => copyText('', e.currentTarget as HTMLButtonElement)}>Copy</button>
				</div>
				<pre class="qs-code">curl -X POST http://localhost:8080/ezra/belief/snapshot \
  -H <span class="str">"Content-Type: application/json"</span> \
  -d <span class="str">'&#123;"agent_id": "analyst", "session": "demo-fleet"&#125;'</span></pre>
			</div>

			<div class="qs-callout teal">
				<span class="qs-callout-label">// Expected output</span>
				A JSON snapshot with <code>belief_id</code>, <code>timestamp</code>, all committed facts,
				and their attributed sources. This is your audit record.
			</div>
		</section>

		<!-- Step 7 -->
		<section id="step-7" data-step="7" class="qs-section">
			<div class="qs-step-label">
				<span class="qs-step-n">07</span>
				<h2>Next Steps</h2>
			</div>

			<div class="qs-next-grid">
				<a href="/docs/branching" class="qs-next-card">
					<div class="qnc-tag">// Replay</div>
					<h4>Branching Replay</h4>
					<p>
						Reconstruct what the agent believed at any prior point. The compliance and root-cause
						tool.
					</p>
				</a>
				<a href="/docs/beliefs" class="qs-next-card">
					<div class="qnc-tag">// Beliefs</div>
					<h4>Belief System</h4>
					<p>
						Configure reconciliation strategies. Set up custom resolvers for conflicting agent
						beliefs.
					</p>
				</a>
				<a href="/docs/memory" class="qs-next-card">
					<div class="qnc-tag">// Memory</div>
					<h4>Memory Tiers</h4>
					<p>
						Tune eviction schedules, salience thresholds, and warm-tier compaction for your
						workload.
					</p>
				</a>
				<a href="/docs/federation" class="qs-next-card">
					<div class="qnc-tag">// Federation</div>
					<h4>Add More Connectors</h4>
					<p>Connect Snowflake, BigQuery, and REST sources for pushdown federated queries.</p>
				</a>
			</div>

			<div class="qs-final-cta">
				<a class="cta-btn" href="/docs">Full Documentation <span class="arrow">→</span></a>
				<a class="cta-btn ghost" href="mailto:field@ezra.dev">Get Support</a>
			</div>
		</section>
	</div>
</main>

<style>
	/* ── Shell ── */
	.qs-shell {
		display: grid;
		grid-template-columns: 240px 1fr;
		min-height: calc(100vh - var(--nav-h));
		position: relative;
	}

	/* ── Sidebar ── */
	.qs-sidebar {
		position: sticky;
		top: var(--nav-h);
		height: calc(100vh - var(--nav-h));
		overflow-y: auto;
		border-right: 1px solid var(--line);
		background: rgba(7, 23, 26, 0.5);
	}
	.qs-sidebar-inner {
		padding: 36px 20px;
	}
	.qs-sidebar-label {
		font-family: var(--f-mono);
		font-size: 9.5px;
		letter-spacing: 0.22em;
		text-transform: uppercase;
		color: var(--accent);
		margin-bottom: 20px;
	}

	.qs-steps-nav {
		list-style: none;
		padding: 0;
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: 2px;
	}
	.qs-steps-nav a {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 8px 10px;
		font-family: var(--f-mono);
		font-size: 11.5px;
		color: var(--fg-3);
		text-decoration: none;
		border-radius: 2px;
		transition:
			color 0.15s,
			background 0.15s;
	}
	.qs-steps-nav a:hover {
		color: var(--fg);
		background: rgba(45, 199, 184, 0.05);
	}
	.qs-steps-nav a:global(.active) {
		color: var(--accent);
		background: rgba(45, 199, 184, 0.08);
	}

	.qs-step-num {
		width: 20px;
		height: 20px;
		border: 1px solid var(--line);
		border-radius: 50%;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 9px;
		letter-spacing: 0;
		flex-shrink: 0;
		color: var(--fg-4);
	}
	:global(.active) .qs-step-num {
		border-color: var(--accent);
		color: var(--accent);
	}

	.qs-sidebar-sep {
		height: 1px;
		background: var(--line);
		margin: 24px 0;
	}
	.qs-sidebar-links {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}
	.qs-sidebar-links a {
		font-family: var(--f-mono);
		font-size: 11px;
		color: var(--fg-4);
		text-decoration: none;
		padding: 4px 10px;
		transition: color 0.15s;
	}
	.qs-sidebar-links a:hover {
		color: var(--accent);
	}

	/* ── Content ── */
	.qs-content {
		padding: 52px 80px 120px;
		max-width: 820px;
	}

	.qs-breadcrumb {
		display: flex;
		align-items: center;
		gap: 10px;
		font-family: var(--f-mono);
		font-size: 11px;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: var(--fg-4);
		margin-bottom: 40px;
	}
	.qs-breadcrumb a {
		color: var(--fg-4);
		text-decoration: none;
	}
	.qs-breadcrumb a:hover {
		color: var(--accent);
	}

	/* ── Header ── */
	.qs-header {
		margin-bottom: 60px;
	}
	h1 {
		margin: 0 0 16px;
		font-family: var(--f-sans);
		font-size: clamp(28px, 3.5vw, 52px);
		font-weight: 500;
		letter-spacing: -0.025em;
		text-transform: uppercase;
		line-height: 0.95;
		color: var(--fg);
	}
	h1 em {
		font-family: var(--f-display);
		font-style: italic;
		font-weight: 400;
		text-transform: none;
		color: var(--accent);
	}

	.qs-intro {
		font-size: 14.5px;
		line-height: 1.7;
		color: var(--fg-2);
		max-width: 58ch;
		margin: 0 0 24px;
	}

	.qs-prereq-badge {
		display: inline-flex;
		align-items: center;
		gap: 10px;
		padding: 8px 16px;
		border: 1px solid var(--line);
		font-family: var(--f-mono);
		font-size: 10.5px;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: var(--fg-3);
	}

	/* ── Sections ── */
	.qs-section {
		padding: 48px 0;
		border-top: 1px solid var(--line-2);
		scroll-margin-top: calc(var(--nav-h) + 20px);
	}
	.qs-section:first-of-type {
		border-top: 0;
		padding-top: 0;
	}

	.qs-step-label {
		display: flex;
		align-items: baseline;
		gap: 20px;
		margin-bottom: 20px;
	}
	.qs-step-n {
		font-family: var(--f-display);
		font-style: italic;
		font-size: 44px;
		color: var(--accent);
		line-height: 1;
		flex-shrink: 0;
	}
	h2 {
		margin: 0;
		font-family: var(--f-sans);
		font-size: 22px;
		font-weight: 500;
		text-transform: uppercase;
		letter-spacing: -0.01em;
		color: var(--fg);
	}

	p {
		margin: 0 0 16px;
		font-size: 13.5px;
		color: var(--fg-3);
		line-height: 1.7;
	}
	a {
		color: var(--accent);
		text-decoration: none;
	}
	a:hover {
		text-decoration: underline;
	}
	code {
		font-family: var(--f-mono);
		font-size: 12px;
		color: var(--accent-2);
		background: rgba(45, 199, 184, 0.08);
		padding: 2px 6px;
		border-radius: 2px;
	}
	strong {
		color: var(--fg);
	}

	/* ── Checklist ── */
	.qs-checklist {
		list-style: none;
		padding: 0;
		margin: 0 0 24px;
		display: flex;
		flex-direction: column;
		gap: 8px;
	}
	.qs-checklist li {
		display: flex;
		align-items: baseline;
		gap: 10px;
		font-family: var(--f-mono);
		font-size: 12.5px;
		color: var(--fg-3);
		line-height: 1.6;
	}
	.ck {
		color: var(--accent);
		font-size: 12px;
		flex-shrink: 0;
	}

	/* ── Code blocks ── */
	.qs-code-wrap {
		border: 1px solid var(--line);
		margin: 12px 0 20px;
		background: rgba(0, 0, 0, 0.3);
	}
	.qs-code-bar {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 8px 14px;
		border-bottom: 1px solid var(--line);
		font-family: var(--f-mono);
		font-size: 10px;
		letter-spacing: 0.16em;
		text-transform: uppercase;
		color: var(--fg-4);
	}
	.qs-code-bar button {
		background: none;
		border: 1px solid var(--line);
		color: var(--fg-4);
		font-family: var(--f-mono);
		font-size: 9px;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		padding: 3px 8px;
		cursor: pointer;
		transition: all 0.2s;
	}
	.qs-code-bar button:hover {
		border-color: var(--accent);
		color: var(--accent);
	}

	.qs-code {
		margin: 0;
		padding: 18px 16px;
		font-family: var(--f-mono);
		font-size: 12px;
		line-height: 1.7;
		color: var(--fg-2);
		overflow-x: auto;
		white-space: pre;
	}
	.qs-code :global(.kw) {
		color: var(--accent);
	}
	.qs-code :global(.str) {
		color: var(--accent-2);
	}
	.qs-code :global(.cm) {
		color: var(--fg-4);
		font-style: italic;
	}
	.qs-code :global(.fn) {
		color: var(--fg);
	}

	/* ── Callout ── */
	.qs-callout {
		border-left: 3px solid var(--line);
		padding: 14px 16px;
		margin: 16px 0;
		background: rgba(232, 220, 196, 0.03);
		font-family: var(--f-mono);
		font-size: 12px;
		line-height: 1.65;
		color: var(--fg-3);
	}
	.qs-callout.teal {
		border-left-color: var(--accent);
		background: rgba(45, 199, 184, 0.04);
	}
	.qs-callout-label {
		display: block;
		font-size: 9.5px;
		letter-spacing: 0.18em;
		text-transform: uppercase;
		color: var(--fg-4);
		margin-bottom: 8px;
	}
	.qs-callout.teal .qs-callout-label {
		color: var(--accent);
	}

	/* ── Next steps grid ── */
	.qs-next-grid {
		display: grid;
		grid-template-columns: repeat(2, 1fr);
		gap: 0;
		border: 1px solid var(--line);
		margin: 16px 0 32px;
	}
	.qs-next-card {
		padding: 28px 24px;
		border-left: 1px solid var(--line);
		border-bottom: 1px solid var(--line);
		text-decoration: none;
		transition: background 0.2s;
	}
	.qs-next-card:nth-child(odd) {
		border-left: 0;
	}
	.qs-next-card:nth-child(n + 3) {
		border-bottom: 0;
	}
	.qs-next-card:hover {
		background: rgba(45, 199, 184, 0.04);
	}
	.qnc-tag {
		font-family: var(--f-mono);
		font-size: 10px;
		letter-spacing: 0.18em;
		text-transform: uppercase;
		color: var(--accent);
		margin-bottom: 8px;
	}
	.qs-next-card h4 {
		margin: 0 0 6px;
		font-family: var(--f-sans);
		font-weight: 500;
		font-size: 15px;
		text-transform: uppercase;
		letter-spacing: 0.01em;
		color: var(--fg);
	}
	.qs-next-card p {
		margin: 0;
		font-size: 12px;
		color: var(--fg-4);
		line-height: 1.6;
	}

	/* ── Final CTA ── */
	.qs-final-cta {
		display: flex;
		gap: 14px;
		flex-wrap: wrap;
	}
	.cta-btn {
		display: inline-flex;
		align-items: center;
		gap: 12px;
		padding: 12px 24px;
		background: transparent;
		color: var(--fg);
		border: 1px solid var(--fg);
		text-decoration: none;
		font-family: var(--f-mono);
		font-size: 12px;
		letter-spacing: 0.18em;
		text-transform: uppercase;
		font-weight: 600;
		transition: all 0.2s;
	}
	.cta-btn:hover {
		background: var(--fg);
		color: var(--bg);
	}
	.cta-btn.ghost {
		border-color: var(--line);
	}
	.cta-btn.ghost:hover {
		border-color: var(--fg);
		background: transparent;
	}
	.arrow {
		font-size: 14px;
	}

	/* ── Responsive ── */
	@media (max-width: 900px) {
		.qs-shell {
			grid-template-columns: 1fr;
		}
		.qs-sidebar {
			position: relative;
			top: 0;
			height: auto;
			border-right: 0;
			border-bottom: 1px solid var(--line);
		}
		.qs-sidebar-inner {
			padding: 20px;
		}
		.qs-steps-nav {
			flex-direction: row;
			flex-wrap: wrap;
		}
		.qs-content {
			padding: 32px 24px 80px;
			max-width: 100%;
		}
		.qs-next-grid {
			grid-template-columns: 1fr;
		}
		.qs-next-card {
			border-left: 0;
			border-bottom: 1px solid var(--line);
		}
		.qs-next-card:nth-child(n + 3) {
			border-bottom: 1px solid var(--line);
		}
		.qs-next-card:last-child {
			border-bottom: 0;
		}
	}
</style>
