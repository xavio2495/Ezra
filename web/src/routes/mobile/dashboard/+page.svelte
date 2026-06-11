<script lang="ts">
	import snapshot from '$lib/dashboard-snapshot.json';

	// Same honest source as the desktop /dashboard: the verbatim capture of a
	// real google.adk fleet run on GKE (fleet.py::capture_snapshot).
	type Agent = { id: string; role: string; scope: string[]; committed: boolean };
	type Recon = {
		topic: string;
		similarity: number | null;
		nli_confidence: number | null;
		strategy: string;
		decision: string;
		winner: string;
		loser: string;
	} | null;
	type Snap = {
		meta: { recorded_at: string; llm_model: string; graph_id: string; sources: string[] };
		agents: Agent[];
		tiers: { cold_commitments: number; active_beliefs: number; superseded_beliefs: number };
		reconciliation: Recon;
		federated_fetches: { agent: string; source: string; rows: number }[];
		denial: { agent: string; denied_topic: string } | null;
	};

	const snap = snapshot as Snap;
	const recon = snap.reconciliation;
	const fmt = (n: number | null) => (n === null || n === undefined ? '—' : n.toFixed(2));
</script>

<svelte:head>
	<title>Live Dashboard — Ezra</title>
</svelte:head>

<div class="md-wrap">
	<div class="md-label">// Operations</div>
	<h2>A <em>real</em> fleet run.</h2>

	<!-- Live demo first -->
	<a class="md-live" href="http://34.24.243.248/" target="_blank" rel="noopener">
		<span class="md-live-pulse"></span>
		<span class="md-live-text">
			<strong>Drive it live on GKE</strong>
			<span>Prompt the six-agent fleet yourself — graph, data access, audit feed in real time.</span
			>
		</span>
		<span class="md-live-arrow">→</span>
	</a>

	<!-- Stats -->
	<div class="md-stats">
		<div class="md-stat">
			<b>{snap.agents.length}</b>
			<span>agents spawned</span>
		</div>
		<div class="md-stat">
			<b>{snap.tiers.cold_commitments}</b>
			<span>belief commitments</span>
		</div>
		<div class="md-stat">
			<b>{recon ? 1 : 0}</b>
			<span>contradictions resolved</span>
		</div>
		<div class="md-stat">
			<b>{snap.federated_fetches.length}</b>
			<span>federated fetches</span>
		</div>
	</div>

	<!-- Reconciliation -->
	{#if recon}
		<div class="md-panel">
			<h3>The contradiction</h3>
			<p class="md-recon">
				<b>{recon.loser}</b> vs <b>{recon.winner}</b> on <b>{recon.topic}</b> — cosine
				{fmt(recon.similarity)} → NLI {fmt(recon.nli_confidence)} → <b>{recon.strategy}</b> →
				<b>{recon.decision}</b>. The losing belief was superseded, not erased.
			</p>
		</div>
	{/if}

	<!-- Fleet -->
	<div class="md-panel">
		<h3>The fleet</h3>
		<ul class="md-agents">
			{#each snap.agents as agent (agent.id)}
				<li>
					<span class="md-dot" class:on={agent.committed}></span>
					<span class="md-agent-id">{agent.id}</span>
					<span class="md-agent-scope">{agent.scope.join(' · ')}</span>
				</li>
			{/each}
		</ul>
		{#if snap.denial}
			<p class="md-denial">
				⛔ <b>{snap.denial.agent}</b> was refused <b>{snap.denial.denied_topic}</b> — outside its permission
				scope, denied at the source.
			</p>
		{/if}
	</div>

	<div class="md-meta">
		{snap.meta.llm_model} · {snap.meta.sources.join(' · ')} · graph
		<code>{snap.meta.graph_id}</code>
	</div>

	<a class="md-full" href="/dashboard?desktop=1">Full recorded dashboard (desktop view) →</a>
</div>

<style>
	.md-wrap {
		padding: 28px 20px 36px;
	}
	.md-label {
		font-family: var(--f-mono);
		font-size: 10px;
		letter-spacing: 0.2em;
		text-transform: uppercase;
		color: var(--accent);
		margin-bottom: 14px;
	}
	h2 {
		margin: 0 0 18px;
		font-family: var(--f-sans);
		font-weight: 500;
		font-size: 27px;
		line-height: 1.02;
		text-transform: uppercase;
		color: var(--fg);
	}
	h2 em {
		font-family: var(--f-display);
		font-style: italic;
		font-weight: 400;
		text-transform: none;
		color: var(--accent);
	}

	.md-live {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 16px;
		border: 1px solid rgba(45, 199, 184, 0.4);
		background: rgba(45, 199, 184, 0.06);
		text-decoration: none;
		margin-bottom: 18px;
	}
	.md-live-pulse {
		flex: 0 0 auto;
		width: 9px;
		height: 9px;
		border-radius: 50%;
		background: var(--accent);
		animation: md-pulse 2s ease-out infinite;
	}
	@keyframes md-pulse {
		0% {
			box-shadow: 0 0 0 0 rgba(45, 199, 184, 0.5);
		}
		70% {
			box-shadow: 0 0 0 9px rgba(45, 199, 184, 0);
		}
		100% {
			box-shadow: 0 0 0 0 rgba(45, 199, 184, 0);
		}
	}
	.md-live-text strong {
		display: block;
		font-family: var(--f-sans);
		font-weight: 500;
		font-size: 14px;
		text-transform: uppercase;
		color: var(--fg);
	}
	.md-live-text span {
		font-family: var(--f-mono);
		font-size: 10.5px;
		line-height: 1.5;
		color: var(--fg-3);
	}
	.md-live-arrow {
		margin-left: auto;
		color: var(--accent);
		font-size: 18px;
	}

	.md-stats {
		display: grid;
		grid-template-columns: 1fr 1fr;
		border: 1px solid var(--line);
		margin-bottom: 18px;
	}
	.md-stat {
		padding: 16px;
		border-right: 1px solid var(--line);
		border-bottom: 1px solid var(--line);
	}
	.md-stat:nth-child(even) {
		border-right: 0;
	}
	.md-stat:nth-child(n + 3) {
		border-bottom: 0;
	}
	.md-stat b {
		display: block;
		font-family: var(--f-display);
		font-style: italic;
		font-weight: 400;
		font-size: 30px;
		color: var(--accent);
		line-height: 1;
		margin-bottom: 4px;
	}
	.md-stat span {
		font-family: var(--f-mono);
		font-size: 10px;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: var(--fg-3);
	}

	.md-panel {
		border: 1px solid var(--line);
		padding: 16px;
		margin-bottom: 18px;
	}
	.md-panel h3 {
		margin: 0 0 10px;
		font-family: var(--f-sans);
		font-weight: 500;
		font-size: 13px;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--fg);
	}
	.md-recon {
		margin: 0;
		font-family: var(--f-mono);
		font-size: 11.5px;
		line-height: 1.7;
		color: var(--fg-3);
	}
	.md-recon b {
		color: var(--fg);
	}

	.md-agents {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.md-agents li {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 9px 0;
		border-bottom: 1px solid var(--line-2);
		font-family: var(--f-mono);
		font-size: 11.5px;
	}
	.md-agents li:last-child {
		border-bottom: 0;
	}
	.md-dot {
		flex: 0 0 auto;
		width: 7px;
		height: 7px;
		border-radius: 50%;
		background: var(--fg-4);
	}
	.md-dot.on {
		background: var(--accent);
	}
	.md-agent-id {
		color: var(--fg);
	}
	.md-agent-scope {
		margin-left: auto;
		color: var(--fg-4);
		font-size: 10px;
		text-align: right;
	}
	.md-denial {
		margin: 12px 0 0;
		font-family: var(--f-mono);
		font-size: 11px;
		line-height: 1.6;
		color: var(--fg-3);
	}
	.md-denial b {
		color: var(--fg);
	}

	.md-meta {
		font-family: var(--f-mono);
		font-size: 10px;
		letter-spacing: 0.08em;
		color: var(--fg-4);
		line-height: 1.7;
		margin-bottom: 16px;
	}
	.md-meta code {
		color: var(--accent);
	}
	.md-full {
		display: block;
		text-align: center;
		padding: 13px;
		border: 1px solid var(--line);
		font-family: var(--f-mono);
		font-size: 11px;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: var(--fg-2);
		text-decoration: none;
	}
</style>
