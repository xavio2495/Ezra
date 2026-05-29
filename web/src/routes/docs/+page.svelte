<script lang="ts">
	import { onMount } from 'svelte';

	function copyText(text: string, btn: HTMLButtonElement) {
		navigator.clipboard.writeText(text).then(() => {
			const orig = btn.textContent ?? '';
			btn.textContent = 'Copied';
			btn.style.color = 'var(--accent)';
			btn.style.borderColor = 'var(--accent)';
			setTimeout(() => {
				btn.textContent = orig;
				btn.style.color = '';
				btn.style.borderColor = '';
			}, 1500);
		});
	}

	let activeSection = $state('installation');

	onMount(() => {
		const sections = document.querySelectorAll<HTMLElement>('[data-section]');
		const io = new IntersectionObserver(
			(entries) => {
				entries.forEach((e) => {
					if (e.isIntersecting) {
						activeSection = (e.target as HTMLElement).dataset.section ?? '';
					}
				});
			},
			{ rootMargin: '-30% 0px -60% 0px' }
		);
		sections.forEach((s) => io.observe(s));
		return () => io.disconnect();
	});
</script>

<svelte:head>
	<title>Documentation — Ezra</title>
</svelte:head>

<div class="docs-shell">
	<!-- Sidebar -->
	<aside class="docs-sidebar">
		<div class="docs-sidebar-inner">
			<div class="ds-group">
				<h6 class="ds-group-title">Getting Started</h6>
				<ul>
					<li><a href="#installation"     class:active={activeSection === 'installation'}>Installation</a></li>
					<li><a href="#configuration"    class:active={activeSection === 'configuration'}>Configuration</a></li>
					<li><a href="#first-agent"       class:active={activeSection === 'first-agent'}>Your First Agent</a></li>
				</ul>
			</div>
			<div class="ds-group">
				<h6 class="ds-group-title">Core Concepts</h6>
				<ul>
					<li><a href="#memory-tiers"     class:active={activeSection === 'memory-tiers'}>Memory Tiers</a></li>
					<li><a href="#belief-system"    class:active={activeSection === 'belief-system'}>Belief System</a></li>
					<li><a href="#federation"       class:active={activeSection === 'federation'}>Federation</a></li>
					<li><a href="#replay"           class:active={activeSection === 'replay'}>Branching Replay</a></li>
				</ul>
			</div>
			<div class="ds-group">
				<h6 class="ds-group-title">API Reference</h6>
				<ul>
					<li><a href="#python-sdk"       class:active={activeSection === 'python-sdk'}>Python SDK</a></li>
					<li><a href="#adk-service"      class:active={activeSection === 'adk-service'}>ADK Service</a></li>
					<li><a href="#rest-api"         class:active={activeSection === 'rest-api'}>REST API</a></li>
				</ul>
			</div>
			<div class="ds-group">
				<h6 class="ds-group-title">Guides</h6>
				<ul>
					<li><a href="/quickstart">Google Cloud ADK ↗</a></li>
					<li><a href="#langgraph">LangGraph</a></li>
					<li><a href="#langchain">LangChain</a></li>
				</ul>
			</div>
		</div>
	</aside>

	<!-- Content -->
	<main class="docs-content">
		<div class="docs-breadcrumb">
			<a href="/">Ezra</a>
			<span>/</span>
			<span>Documentation</span>
		</div>

		<!-- ── Installation ── -->
		<section id="installation" data-section="installation">
			<h1>Getting Started</h1>
			<p class="ds-intro">
				Ezra is a multi-agent runtime for enterprises. It manages fleet-wide memory, belief
				reconciliation, federated data access, and branching replay — in a single Python package.
			</p>

			<h2>Installation</h2>
			<p>Requires Python 3.10 or later.</p>

			<div class="ds-code-wrap">
				<div class="ds-code-bar">
					<span>bash</span>
					<button onclick={(e) => copyText('pip install ezra-platform', e.currentTarget as HTMLButtonElement)}>Copy</button>
				</div>
				<pre class="ds-code"><span class="kw">pip install</span> ezra-platform</pre>
			</div>

			<p>For Google Cloud ADK integration:</p>
			<div class="ds-code-wrap">
				<div class="ds-code-bar">
					<span>bash</span>
					<button onclick={(e) => copyText('pip install "ezra-platform[adk]"', e.currentTarget as HTMLButtonElement)}>Copy</button>
				</div>
				<pre class="ds-code"><span class="kw">pip install</span> <span class="str">"ezra-platform[adk]"</span></pre>
			</div>

			<div class="ds-callout">
				<span class="ds-callout-label">// Note</span>
				Ezra requires a running Redis instance (hot tier) and MongoDB Atlas (cold tier). For local
				development, a <code>docker-compose.yml</code> is included in the repo.
			</div>
		</section>

		<!-- ── Configuration ── -->
		<section id="configuration" data-section="configuration">
			<h2>Configuration</h2>
			<p>
				Ezra is configured via environment variables. The minimal set for local development:
			</p>

			<div class="ds-code-wrap">
				<div class="ds-code-bar">
					<span>.env</span>
					<button onclick={(e) => copyText('EZRA_MONGO_URI=mongodb://localhost:27017\nEZRA_REDIS_URL=redis://localhost:6379\nEZRA_API_KEY=sk-ezra-...', e.currentTarget as HTMLButtonElement)}>Copy</button>
				</div>
				<pre class="ds-code"><span class="cm"># Required</span>
EZRA_MONGO_URI=<span class="str">mongodb://localhost:27017</span>
EZRA_REDIS_URL=<span class="str">redis://localhost:6379</span>
EZRA_API_KEY=<span class="str">sk-ezra-...</span>

<span class="cm"># Optional — defaults shown</span>
EZRA_HOT_TTL_SECONDS=<span class="str">3600</span>
EZRA_WARM_DECAY_DAYS=<span class="str">30</span>
EZRA_LOG_LEVEL=<span class="str">INFO</span>
EZRA_BELIEF_STRATEGY=<span class="str">last_write</span>   <span class="cm"># or: highest_trust | escalate | custom</span></pre>
			</div>

			<h3>Belief strategy</h3>
			<p>
				When agents commit conflicting beliefs, <code>EZRA_BELIEF_STRATEGY</code> controls
				resolution:
			</p>

			<table class="ds-table">
				<thead>
					<tr><th>Strategy</th><th>Behaviour</th></tr>
				</thead>
				<tbody>
					<tr><td><code>last_write</code></td><td>Most recent commit wins. Default.</td></tr>
					<tr><td><code>highest_trust</code></td><td>Agent with the highest trust score wins.</td></tr>
					<tr><td><code>escalate</code></td><td>Conflict is surfaced to human review queue.</td></tr>
					<tr><td><code>custom</code></td><td>Your resolver function is called. See <a href="#belief-system">Belief System</a>.</td></tr>
				</tbody>
			</table>
		</section>

		<!-- ── First agent ── -->
		<section id="first-agent" data-section="first-agent">
			<h2>Your First Agent</h2>
			<p>
				The minimal example: an agent that recalls memory, completes a turn, and writes beliefs.
			</p>

			<div class="ds-code-wrap">
				<div class="ds-code-bar">
					<span>python</span>
					<button onclick={(e) => copyText('', e.currentTarget as HTMLButtonElement)}>Copy</button>
				</div>
				<pre class="ds-code"><span class="kw">import</span> asyncio
<span class="kw">from</span> ezra_core <span class="kw">import</span> Ezra

<span class="kw">async def</span> <span class="fn">main</span>():
    ezra = Ezra.from_env(
        session_graph_id=<span class="str">"demo-session"</span>
    )

    <span class="cm"># Single agent turn — runs all 8 router steps</span>
    response = <span class="kw">await</span> ezra.complete(
        agent_id=<span class="str">"analyst"</span>,
        permission_scope=[<span class="str">"market_data"</span>, <span class="str">"reports"</span>],
        messages=[
            &#123;<span class="str">"role"</span>: <span class="str">"user"</span>, <span class="str">"content"</span>: <span class="str">"Summarise Q1 revenue trends"</span>&#125;
        ],
        sources=[<span class="str">"mongodb://cluster/financials"</span>],
    )

    print(response.content)
    print(<span class="str">f"Belief snapshot: </span>&#123;response.belief_id&#125;<span class="str">"</span>)

asyncio.run(main())</pre>
			</div>
		</section>

		<!-- ── Memory Tiers ── -->
		<section id="memory-tiers" data-section="memory-tiers">
			<h2>Memory Tiers</h2>
			<p>
				Ezra maintains three memory tiers per agent. Hydration (read) is automatic at step 4 of
				the router. Eviction runs as a background task.
			</p>

			<div class="ds-tier-grid">
				<div class="ds-tier hot">
					<div class="ds-tier-name">Hot</div>
					<div class="ds-tier-store">Redis · per-agent hash</div>
					<div class="ds-tier-lat">~0 ms</div>
					<p>Active turn, pinned beliefs, current mesh result. Scoped to one agent in one session. TTL-expired automatically.</p>
				</div>
				<div class="ds-tier warm">
					<div class="ds-tier-name">Warm</div>
					<div class="ds-tier-store">Qdrant · vector filtered</div>
					<div class="ds-tier-lat">5–15 ms</div>
					<p>Compressed prior turns, topic summaries, recent tool results. Semantic search with salience scoring.</p>
				</div>
				<div class="ds-tier cold">
					<div class="ds-tier-name">Cold</div>
					<div class="ds-tier-store">MongoDB Atlas · durable</div>
					<div class="ds-tier-lat">20–50 ms</div>
					<p>Episodic history, semantic core, procedural rules, and the full versioned belief log. Never evicted.</p>
				</div>
			</div>
		</section>

		<!-- ── Belief System ── -->
		<section id="belief-system" data-section="belief-system">
			<h2>Belief System</h2>
			<p>
				Every fact an agent relies on is committed as a <em>belief</em> — a versioned, attributed
				record with a source, a confidence, and an agent_id.
			</p>

			<div class="ds-code-wrap">
				<div class="ds-code-bar"><span>python</span></div>
				<pre class="ds-code"><span class="cm"># Check a belief before the agent acts on it</span>
result = <span class="kw">await</span> ezra.belief_check(
    agent_id=<span class="str">"analyst"</span>,
    claim=<span class="str">"Q1 revenue exceeded forecast"</span>,
    sources=[<span class="str">"mongodb://financials"</span>],
)

<span class="kw">if</span> result.conflict:
    <span class="cm"># Two agents disagree — apply resolution strategy</span>
    print(result.resolution_path)</pre>
			</div>
		</section>

		<!-- ── Federation ── -->
		<section id="federation" data-section="federation">
			<h2>Federation</h2>
			<p>
				Ezra routes data queries to the source at step 5 (Fetch). The agent never touches raw rows.
				Supported connectors:
			</p>
			<ul class="ds-list">
				<li><strong>MongoDB</strong> — Atlas $lookup and aggregation pipelines</li>
				<li><strong>Snowflake</strong> — SQL pushdown with result summarisation</li>
				<li><strong>BigQuery</strong> — Standard SQL, streamed in batches</li>
				<li><strong>REST</strong> — Generic HTTP with typed response schemas</li>
			</ul>

			<div class="ds-callout teal">
				<span class="ds-callout-label">// Google Cloud</span>
				Running on Google Cloud? Use <a href="/quickstart">the ADK quickstart</a> for the
				recommended setup with Cloud Run, Secret Manager, and Vertex AI.
			</div>
		</section>

		<!-- ── Replay ── -->
		<section id="replay" data-section="replay">
			<h2>Branching Replay</h2>
			<p>
				Any agent's state at any prior point in time can be reconstructed, mutated, and run
				forward. The primary compliance and root-cause tool.
			</p>

			<div class="ds-code-wrap">
				<div class="ds-code-bar"><span>python</span></div>
				<pre class="ds-code"><span class="cm"># Replay agent state as of 2 hours ago</span>
branch = <span class="kw">await</span> ezra.replay(
    agent_id=<span class="str">"analyst"</span>,
    as_of=<span class="str">"2026-05-28T10:00:00Z"</span>,
)

<span class="cm"># Mutate one belief in the branch</span>
branch.patch_belief(<span class="str">"revenue_forecast"</span>, value=<span class="str">"$4.2M"</span>)

<span class="cm"># Run the branch forward with current model</span>
result = <span class="kw">await</span> branch.run_forward(steps=<span class="num">3</span>)
diff = branch.diff(result)</pre>
			</div>
		</section>

		<!-- ── Python SDK ── -->
		<section id="python-sdk" data-section="python-sdk">
			<h2>Python SDK</h2>
			<p>Six primary methods on the <code>Ezra</code> class:</p>

			<table class="ds-table">
				<thead>
					<tr><th>Method</th><th>Description</th></tr>
				</thead>
				<tbody>
					<tr><td><code>Ezra.from_env()</code></td><td>Initialise from environment variables.</td></tr>
					<tr><td><code>await ezra.complete()</code></td><td>Run a full 8-step agent turn.</td></tr>
					<tr><td><code>await ezra.recall()</code></td><td>Hydrate memory without completing a turn.</td></tr>
					<tr><td><code>await ezra.belief_check()</code></td><td>Verify a claim against the belief store.</td></tr>
					<tr><td><code>await ezra.snapshot()</code></td><td>Export a point-in-time belief snapshot.</td></tr>
					<tr><td><code>await ezra.replay()</code></td><td>Open a branching replay session.</td></tr>
				</tbody>
			</table>
		</section>

		<!-- ── ADK Service ── -->
		<section id="adk-service" data-section="adk-service">
			<h2>ADK Service</h2>
			<p>
				<code>EzraService</code> is a drop-in Ezra adapter for Google ADK agents. It wraps the
				Python SDK into the ADK service protocol.
			</p>

			<div class="ds-code-wrap">
				<div class="ds-code-bar"><span>python</span></div>
				<pre class="ds-code"><span class="kw">from</span> ezra.adk_service <span class="kw">import</span> EzraService
<span class="kw">from</span> google.adk <span class="kw">import</span> Agent

svc = EzraService(
    session_graph_id=<span class="str">"fleet-001"</span>,
    project=<span class="str">"my-gcp-project"</span>,
    location=<span class="str">"us-central1"</span>,
)

<span class="kw">class</span> <span class="fn">MyAgent</span>(Agent):
    <span class="kw">async def</span> <span class="fn">run</span>(self, ctx):
        memory = <span class="kw">await</span> svc.recall(agent_id=self.id)
        <span class="cm"># ... use memory in your agent logic ...</span>
        <span class="kw">await</span> svc.commit(agent_id=self.id, beliefs=ctx.beliefs)</pre>
			</div>

			<p>
				See the <a href="/quickstart">Google Cloud Quickstart</a> for the full setup including
				Cloud Run deployment and Secret Manager configuration.
			</p>
		</section>

		<!-- ── REST API ── -->
		<section id="rest-api" data-section="rest-api">
			<h2>REST API</h2>
			<p>Nine endpoints. Bearer or OIDC auth. Base URL: <code>https://api.ezra.dev/v1</code></p>

			<table class="ds-table">
				<thead>
					<tr><th>Method</th><th>Path</th><th>Description</th></tr>
				</thead>
				<tbody>
					<tr><td>POST</td><td><code>/ezra/belief/check</code></td><td>Verify a claim against belief store.</td></tr>
					<tr><td>POST</td><td><code>/ezra/belief/snapshot</code></td><td>Export belief state at a timestamp.</td></tr>
					<tr><td>POST</td><td><code>/ezra/mesh/query</code></td><td>Run a federated mesh query.</td></tr>
					<tr><td>POST</td><td><code>/ezra/context/assemble</code></td><td>Assemble salience-ranked context.</td></tr>
					<tr><td>POST</td><td><code>/ezra/replay</code></td><td>Open a replay session.</td></tr>
					<tr><td>POST</td><td><code>/ezra/branch</code></td><td>Create a branch from a replay.</td></tr>
					<tr><td>POST</td><td><code>/ezra/branch/run-forward</code></td><td>Run a branch forward N steps.</td></tr>
					<tr><td>POST</td><td><code>/ezra/branch/diff</code></td><td>Diff two branch states.</td></tr>
					<tr><td>GET</td><td><code>/ezra/health</code></td><td>Health check. Returns 200 if nominal.</td></tr>
				</tbody>
			</table>

			<div class="ds-callout">
				<span class="ds-callout-label">// Auth</span>
				Send <code>Authorization: Bearer &lt;token&gt;</code> or configure OIDC via
				<code>EZRA_OIDC_ISSUER</code>. Service account tokens are accepted from GCP environments.
			</div>
		</section>

		<!-- ── LangGraph ── -->
		<section id="langgraph" data-section="langgraph">
			<h2>LangGraph Integration</h2>
			<p>
				Use the Python SDK with any LangGraph graph. Inject <code>ezra.recall()</code> at the
				start of each node and <code>ezra.complete()</code> to run the LLM call through the full
				Ezra router.
			</p>
			<div class="ds-callout teal">
				<span class="ds-callout-label">// Stub</span>
				Full LangGraph integration guide coming soon. Join the early access list at
				<a href="mailto:field@ezra.dev">field@ezra.dev</a>.
			</div>
		</section>

		<!-- ── LangChain ── -->
		<section id="langchain" data-section="langchain">
			<h2>LangChain Integration</h2>
			<p>
				Wrap any LangChain chain with <code>EzraChain</code> to inject memory, belief checking,
				and audit trail into your existing LangChain workflows.
			</p>
			<div class="ds-callout teal">
				<span class="ds-callout-label">// Stub</span>
				Full LangChain integration guide coming soon. <a href="mailto:field@ezra.dev">Contact us</a> for early access.
			</div>
		</section>
	</main>
</div>

<style>
	/* ── Layout ── */
	.docs-shell {
		display: grid;
		grid-template-columns: 260px 1fr;
		min-height: calc(100vh - var(--nav-h));
		position: relative;
	}

	/* ── Sidebar ── */
	.docs-sidebar {
		position: sticky;
		top: var(--nav-h);
		height: calc(100vh - var(--nav-h));
		overflow-y: auto;
		border-right: 1px solid var(--line);
		background: rgba(7, 23, 26, 0.5);
		flex-shrink: 0;
	}
	.docs-sidebar-inner {
		padding: 40px 24px;
		display: flex;
		flex-direction: column;
		gap: 32px;
	}

	.ds-group h6,
	.ds-group-title {
		font-family: var(--f-mono);
		font-size: 9.5px;
		letter-spacing: 0.22em;
		text-transform: uppercase;
		color: var(--fg-4);
		margin: 0 0 10px;
		padding-bottom: 8px;
		border-bottom: 1px solid var(--line-2);
	}
	.ds-group ul {
		list-style: none;
		padding: 0;
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: 2px;
	}
	.ds-group a {
		display: block;
		padding: 6px 10px;
		font-family: var(--f-mono);
		font-size: 12px;
		letter-spacing: 0.04em;
		color: var(--fg-3);
		text-decoration: none;
		border-radius: 2px;
		transition: color 0.15s, background 0.15s;
	}
	.ds-group a:hover { color: var(--fg); background: rgba(45, 199, 184, 0.06); }
	.ds-group a:global(.active) { color: var(--accent); background: rgba(45, 199, 184, 0.08); }

	/* ── Content ── */
	.docs-content {
		padding: 52px 80px 120px;
		max-width: 860px;
	}

	.docs-breadcrumb {
		display: flex;
		align-items: center;
		gap: 10px;
		font-family: var(--f-mono);
		font-size: 11px;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: var(--fg-4);
		margin-bottom: 48px;
	}
	.docs-breadcrumb a { color: var(--fg-4); text-decoration: none; }
	.docs-breadcrumb a:hover { color: var(--accent); }

	/* ── Typography ── */
	section { padding: 48px 0; border-top: 1px solid var(--line-2); }
	section:first-of-type { border-top: 0; padding-top: 0; }

	h1 {
		margin: 0 0 8px;
		font-family: var(--f-sans);
		font-size: clamp(28px, 3vw, 42px);
		font-weight: 500;
		letter-spacing: -0.02em;
		text-transform: uppercase;
		color: var(--fg);
	}
	h2 {
		margin: 0 0 16px;
		font-family: var(--f-sans);
		font-size: 22px;
		font-weight: 500;
		letter-spacing: -0.01em;
		text-transform: uppercase;
		color: var(--fg);
		scroll-margin-top: calc(var(--nav-h) + 24px);
	}
	h3 {
		margin: 28px 0 10px;
		font-family: var(--f-sans);
		font-size: 14px;
		font-weight: 500;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--fg-2);
	}

	.ds-intro {
		font-size: 15px;
		line-height: 1.7;
		color: var(--fg-2);
		margin-bottom: 40px;
		max-width: 60ch;
	}

	p { margin: 0 0 16px; color: var(--fg-3); font-size: 13.5px; line-height: 1.7; }
	a { color: var(--accent); text-decoration: none; }
	a:hover { text-decoration: underline; }
	code { font-family: var(--f-mono); font-size: 12px; color: var(--accent-2); background: rgba(45,199,184,0.08); padding: 2px 6px; border-radius: 2px; }

	/* ── Code blocks ── */
	.ds-code-wrap {
		border: 1px solid var(--line);
		margin: 16px 0 24px;
		background: rgba(0, 0, 0, 0.3);
	}
	.ds-code-bar {
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
	.ds-code-bar button {
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
	.ds-code-bar button:hover { border-color: var(--accent); color: var(--accent); }

	.ds-code {
		margin: 0;
		padding: 18px 16px;
		font-family: var(--f-mono);
		font-size: 12px;
		line-height: 1.7;
		color: var(--fg-2);
		overflow-x: auto;
		white-space: pre;
	}
	.ds-code :global(.kw)  { color: var(--accent); }
	.ds-code :global(.str) { color: var(--accent-2); }
	.ds-code :global(.cm)  { color: var(--fg-4); font-style: italic; }
	.ds-code :global(.fn)  { color: var(--fg); }
	.ds-code :global(.num) { color: var(--accent-2); }

	/* ── Callout ── */
	.ds-callout {
		border-left: 3px solid var(--line);
		padding: 14px 16px;
		margin: 16px 0;
		background: rgba(232, 220, 196, 0.03);
		font-family: var(--f-mono);
		font-size: 12px;
		line-height: 1.65;
		color: var(--fg-3);
	}
	.ds-callout.teal { border-left-color: var(--accent); background: rgba(45, 199, 184, 0.04); }
	.ds-callout-label {
		display: block;
		font-size: 9.5px;
		letter-spacing: 0.18em;
		text-transform: uppercase;
		color: var(--fg-4);
		margin-bottom: 6px;
	}
	.ds-callout.teal .ds-callout-label { color: var(--accent); }

	/* ── Memory tier cards ── */
	.ds-tier-grid {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 0;
		border: 1px solid var(--line);
		margin: 16px 0 24px;
	}
	.ds-tier {
		padding: 24px 20px;
		border-left: 1px solid var(--line);
	}
	.ds-tier:first-child { border-left: 0; }
	.ds-tier-name {
		font-family: var(--f-sans);
		font-weight: 500;
		font-size: 16px;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		margin-bottom: 2px;
	}
	.ds-tier.hot  .ds-tier-name { color: var(--hot); }
	.ds-tier.warm .ds-tier-name { color: var(--warm); }
	.ds-tier.cold .ds-tier-name { color: var(--cold); }
	.ds-tier-store { font-family: var(--f-mono); font-size: 10px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--fg-4); margin-bottom: 8px; }
	.ds-tier-lat { font-family: var(--f-display); font-style: italic; font-size: 20px; color: var(--fg-3); margin-bottom: 10px; }
	.ds-tier p { font-size: 12px; color: var(--fg-4); margin: 0; line-height: 1.6; }

	/* ── Table ── */
	.ds-table {
		width: 100%;
		border-collapse: collapse;
		border: 1px solid var(--line);
		font-family: var(--f-mono);
		font-size: 12px;
		margin: 16px 0 24px;
	}
	.ds-table th {
		padding: 10px 14px;
		text-align: left;
		font-size: 9.5px;
		letter-spacing: 0.16em;
		text-transform: uppercase;
		color: var(--fg-4);
		border-bottom: 1px solid var(--line);
		background: rgba(0, 0, 0, 0.2);
	}
	.ds-table td {
		padding: 10px 14px;
		border-bottom: 1px solid var(--line-2);
		color: var(--fg-3);
		vertical-align: top;
	}
	.ds-table tr:last-child td { border-bottom: 0; }
	.ds-table td:first-child { color: var(--accent); white-space: nowrap; }
	.ds-table td code { background: none; padding: 0; color: var(--accent-2); }

	/* ── List ── */
	.ds-list { padding-left: 20px; margin: 12px 0 20px; display: flex; flex-direction: column; gap: 6px; }
	.ds-list li { color: var(--fg-3); font-size: 13px; line-height: 1.6; }
	.ds-list strong { color: var(--fg); }

	/* ── Responsive ── */
	@media (max-width: 900px) {
		.docs-shell { grid-template-columns: 1fr; }
		.docs-sidebar { position: relative; top: 0; height: auto; border-right: 0; border-bottom: 1px solid var(--line); }
		.docs-sidebar-inner { flex-direction: row; flex-wrap: wrap; gap: 20px; padding: 24px 20px; }
		.docs-content { padding: 32px 24px 80px; max-width: 100%; }
		.ds-tier-grid { grid-template-columns: 1fr; }
		.ds-tier { border-left: 0; border-bottom: 1px solid var(--line); }
		.ds-tier:last-child { border-bottom: 0; }
	}
</style>
