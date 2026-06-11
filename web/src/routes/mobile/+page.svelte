<script lang="ts">
	let copied = $state(false);
	const INSTALL = 'pip install ezra-client';

	async function copyInstall() {
		try {
			await navigator.clipboard.writeText(INSTALL);
			copied = true;
			setTimeout(() => (copied = false), 1600);
		} catch {
			/* clipboard unavailable — the text is visible to copy by hand */
		}
	}

	const PROBLEMS = [
		['No shared memory', 'Context from Agent A never reaches Agent B.'],
		['No audit trail', 'What did the agent believe, from what source, when? Unanswerable.'],
		['No reconciliation', 'Two agents commit conflicting facts. The error propagates silently.'],
		['Unsafe data access', 'Raw database access, one prompt injection away.']
	];

	const DIFFS = [
		[
			'Federated pushdown',
			'Snowflake · BigQuery · MongoDB do the work. The model sees typed summaries with provenance — never raw rows.'
		],
		[
			'Shared scoped memory',
			'Three tiers — Redis, Qdrant, Atlas — shared fleet-wide, permission-scoped per agent at the source.'
		],
		[
			'Belief reconciliation',
			'Two-pass contradiction detection (embedding → NLI), resolved by trust. Losers are superseded, never erased.'
		],
		[
			'Git for agent state',
			'Rewind any turn. Revert any decision. Branch reality and diff the counterfactual.'
		],
		[
			'One audit feed',
			'Every spawn, fetch, denial, commit, and contradiction — one chronological, replayable stream.'
		]
	];
</script>

<svelte:head>
	<title>Ezra — Agentic infrastructure for cloud runtimes</title>
	<meta
		name="description"
		content="Shared federated memory, versioned beliefs, cross-agent reconciliation, and branching replay for agent fleets."
	/>
</svelte:head>

<!-- Hero -->
<section class="mh-hero">
	<div class="mh-label">// Agentic Infrastructure</div>
	<h1>The state layer your <em>agent fleet</em> is missing.</h1>
	<p class="mh-sub">
		Shared federated memory · versioned beliefs · cross-agent reconciliation · branching replay.
		Live on GKE, MIT-licensed.
	</p>
	<button class="mh-install" onclick={copyInstall}>
		<code>$ {INSTALL}</code>
		<span class="mh-copy">{copied ? '✓ copied' : 'copy'}</span>
	</button>
	<div class="mh-ctas">
		<a class="mh-btn solid" href="http://34.24.243.248/" target="_blank" rel="noopener">
			Drive the live demo →
		</a>
		<a class="mh-btn" href="https://github.com/xavio2495/Ezra" target="_blank" rel="noopener">
			GitHub
		</a>
	</div>
	<div class="mh-meta">v0.1.1 · PyPI / GHCR / Helm · 274 tests green</div>
</section>

<!-- Problem -->
<section class="mh-section">
	<div class="mh-label">01 / The fleet problem</div>
	<h2>One agent is easy.<br />Fifty is chaos.</h2>
	<div class="mh-cards">
		{#each PROBLEMS as [title, body] (title)}
			<div class="mh-card">
				<h4>{title}</h4>
				<p>{body}</p>
			</div>
		{/each}
	</div>
</section>

<!-- Differentiators -->
<section class="mh-section">
	<div class="mh-label">02 / What Ezra ships</div>
	<h2>Five things <em>no other</em> platform has.</h2>
	<ul class="mh-diffs">
		{#each DIFFS as [title, body], i (title)}
			<li>
				<span class="mh-diff-n">{i + 1}</span>
				<div>
					<strong>{title}</strong>
					<p>{body}</p>
				</div>
			</li>
		{/each}
	</ul>
</section>

<!-- Landscape -->
<section class="mh-section mh-land">
	<div class="mh-label">03 / Landscape</div>
	<p class="mh-land-line">
		What MemGPT did for one agent's context window, <strong
			>Ezra does for an entire fleet's shared state.</strong
		> Complementary to your orchestrator — a first-class Google ADK toolset ships today.
	</p>
</section>

<!-- Links -->
<section class="mh-section mh-links">
	<a href="/mobile/pitch">View the pitch <span>→</span></a>
	<a href="/mobile/dashboard">See a real recorded run <span>→</span></a>
	<a href="/docs">Read the docs <span>→</span></a>
	<a href="/quickstart">Build your first agent <span>→</span></a>
</section>

<style>
	.mh-hero {
		padding: 48px 20px 36px;
		background: radial-gradient(ellipse at 50% 0%, rgba(45, 199, 184, 0.09), transparent 65%);
	}
	.mh-label {
		font-family: var(--f-mono);
		font-size: 10px;
		letter-spacing: 0.2em;
		text-transform: uppercase;
		color: var(--accent);
		margin-bottom: 16px;
	}
	h1 {
		margin: 0 0 14px;
		font-family: var(--f-sans);
		font-weight: 500;
		font-size: clamp(30px, 9vw, 40px);
		line-height: 1.02;
		text-transform: uppercase;
		letter-spacing: -0.02em;
		color: var(--fg);
	}
	h1 em,
	h2 em {
		font-family: var(--f-display);
		font-style: italic;
		font-weight: 400;
		text-transform: none;
		color: var(--accent);
	}
	.mh-sub {
		margin: 0 0 22px;
		font-size: 13.5px;
		line-height: 1.65;
		color: var(--fg-3);
	}
	.mh-install {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
		width: 100%;
		padding: 13px 16px;
		background: var(--bg-2);
		border: 1px solid var(--line);
		cursor: pointer;
		margin-bottom: 14px;
	}
	.mh-install code {
		font-family: var(--f-mono);
		font-size: 12.5px;
		color: var(--fg-2);
	}
	.mh-copy {
		font-family: var(--f-mono);
		font-size: 10px;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: var(--accent);
	}
	.mh-ctas {
		display: flex;
		flex-direction: column;
		gap: 10px;
		margin-bottom: 18px;
	}
	.mh-btn {
		display: block;
		text-align: center;
		padding: 14px 18px;
		border: 1px solid var(--line);
		color: var(--fg);
		text-decoration: none;
		font-family: var(--f-mono);
		font-size: 12px;
		letter-spacing: 0.16em;
		text-transform: uppercase;
		font-weight: 600;
	}
	.mh-btn.solid {
		border-color: var(--accent);
		color: var(--accent);
		background: rgba(45, 199, 184, 0.06);
	}
	.mh-meta {
		font-family: var(--f-mono);
		font-size: 10px;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: var(--fg-4);
	}

	.mh-section {
		padding: 36px 20px;
		border-top: 1px solid var(--line);
	}
	h2 {
		margin: 0 0 20px;
		font-family: var(--f-sans);
		font-weight: 500;
		font-size: 24px;
		line-height: 1.05;
		text-transform: uppercase;
		letter-spacing: -0.015em;
		color: var(--fg);
	}

	.mh-cards {
		display: grid;
		gap: 10px;
	}
	.mh-card {
		border: 1px solid var(--line);
		padding: 16px;
	}
	.mh-card h4 {
		margin: 0 0 6px;
		font-family: var(--f-sans);
		font-weight: 500;
		font-size: 14px;
		text-transform: uppercase;
		color: var(--fg);
	}
	.mh-card p {
		margin: 0;
		font-size: 12px;
		line-height: 1.6;
		color: var(--fg-3);
	}

	.mh-diffs {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 0;
		border: 1px solid var(--line);
	}
	.mh-diffs li {
		display: grid;
		grid-template-columns: 40px 1fr;
		gap: 12px;
		padding: 16px;
		border-bottom: 1px solid var(--line);
	}
	.mh-diffs li:last-child {
		border-bottom: 0;
	}
	.mh-diff-n {
		font-family: var(--f-display);
		font-style: italic;
		font-size: 24px;
		color: var(--accent);
		line-height: 1;
	}
	.mh-diffs strong {
		display: block;
		font-family: var(--f-sans);
		font-weight: 500;
		font-size: 13.5px;
		text-transform: uppercase;
		color: var(--fg);
		margin-bottom: 4px;
	}
	.mh-diffs p {
		margin: 0;
		font-family: var(--f-mono);
		font-size: 11.5px;
		line-height: 1.6;
		color: var(--fg-3);
	}

	.mh-land {
		background: rgba(45, 199, 184, 0.03);
	}
	.mh-land-line {
		margin: 0;
		font-size: 14.5px;
		line-height: 1.7;
		color: var(--fg-2);
	}
	.mh-land-line strong {
		color: var(--accent);
	}

	.mh-links {
		display: grid;
		gap: 0;
		padding: 0 20px 36px;
		border-top: 0;
	}
	.mh-links a {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 16px 2px;
		border-bottom: 1px solid var(--line);
		text-decoration: none;
		font-family: var(--f-mono);
		font-size: 12.5px;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: var(--fg-2);
	}
	.mh-links a span {
		color: var(--accent);
	}
</style>
