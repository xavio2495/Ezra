<script lang="ts">
	import { onMount } from 'svelte';
	import snapshot from '$lib/dashboard-snapshot.json';

	// ---------------------------------------------------------------------------
	// This dashboard renders a REAL recorded run — not a simulation. The data in
	// $lib/dashboard-snapshot.json is captured verbatim from a live google.adk
	// fleet executed on GKE (Vertex Gemini agents over Atlas + Snowflake +
	// BigQuery) by demo/f1_race_weekend/adk_runtime/fleet.py::capture_snapshot.
	// ---------------------------------------------------------------------------

	type Agent = {
		id: string;
		role: string;
		scope: string[];
		committed: boolean;
		trust_tyres: number | null;
	};
	type Belief = {
		agent: string;
		topic: string;
		claim: string;
		turn: number;
		trust: number;
		active: boolean;
		superseded: boolean;
	};
	type Recon = {
		topic: string;
		similarity: number | null;
		nli_confidence: number | null;
		strategy: string;
		decision: string;
		winner: string;
		loser: string;
		winner_trust: number | null;
		loser_trust: number | null;
	} | null;
	type Fetch = {
		agent: string;
		source: string;
		time_travel_available: boolean;
		rows: number;
	};
	type Denial = { agent: string; denied_topic: string; scope: string[] } | null;
	type DivergedTopic = { topic: string; only_in_original: string[]; only_in_branch: string[] };
	type Branch = { diverged?: DivergedTopic[]; error?: string } | null;
	type Snapshot = {
		meta: {
			recorded_at: string;
			graph_id: string;
			inherited_from: string;
			llm_model: string;
			sources: string[];
		};
		agents: Agent[];
		tiers: {
			hot_turns: number;
			warm_summaries: number;
			cold_commitments: number;
			active_beliefs: number;
			superseded_beliefs: number;
		};
		beliefs: Belief[];
		reconciliation: Recon;
		federated_fetches: Fetch[];
		denial: Denial;
		branch: Branch;
	};

	const snap = snapshot as Snapshot;

	const committedCount = snap.agents.filter((a) => a.committed).length;
	const recon = snap.reconciliation;

	const recordedAt = (() => {
		const d = new Date(snap.meta.recorded_at);
		return isNaN(d.getTime())
			? snap.meta.recorded_at
			: d.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
	})();

	// Three-tier counts, scaled to the largest tier so the bars stay honest.
	const tierMax = Math.max(
		1,
		snap.tiers.hot_turns,
		snap.tiers.warm_summaries,
		snap.tiers.cold_commitments
	);
	const tiers = [
		{
			key: 'hot',
			name: 'Hot tier',
			store: 'Redis',
			detail: 'Recent turns',
			value: snap.tiers.hot_turns,
			unit: 'turns',
			color: 'var(--hot)'
		},
		{
			key: 'warm',
			name: 'Warm tier',
			store: 'Qdrant',
			detail: 'Compressed summaries · vectors',
			value: snap.tiers.warm_summaries,
			unit: 'summaries',
			color: 'var(--warm)'
		},
		{
			key: 'cold',
			name: 'Cold tier',
			store: 'MongoDB Atlas',
			detail: `${snap.tiers.active_beliefs} active · ${snap.tiers.superseded_beliefs} superseded`,
			value: snap.tiers.cold_commitments,
			unit: 'commitments',
			color: 'var(--cold)'
		}
	];

	const fmt = (n: number | null) => (n === null || n === undefined ? '—' : n.toFixed(2));

	onMount(() => {
		const io = new IntersectionObserver(
			(entries) => {
				entries.forEach((e) => {
					if (e.isIntersecting) {
						e.target.classList.add('in');
						io.unobserve(e.target);
					}
				});
			},
			{ threshold: 0.12, rootMargin: '0px 0px -8% 0px' }
		);
		document.querySelectorAll('.reveal, .reveal-stagger').forEach((el) => io.observe(el));
		return () => io.disconnect();
	});
</script>

<svelte:head>
	<title>Live Dashboard — Ezra Operations</title>
	<meta
		name="description"
		content="Ezra operations dashboard — a real recorded multi-agent run: agent fleet, three-tier memory, belief reconciliation, federation, and a counterfactual branch."
	/>
</svelte:head>

<main class="wrap">
	<!-- Header -->
	<section class="section db-head reveal">
		<div class="section-head">
			<div class="idx">// Operations</div>
			<h2>Recorded <em>operations</em> dashboard</h2>
			<p class="lede">
				A real session graph, captured end-to-end from a live <b>google.adk</b> fleet run on GKE — Vertex
				Gemini agents reasoning over MongoDB Atlas, Snowflake, and BigQuery. Every number below is read
				back from the runtime: the agents and their scopes, the append-only belief log, the contradiction
				that genuinely fired and how trust resolved it, the federated fetches, and a counterfactual branch.
				Nothing here is staged.
			</p>
		</div>

		<div class="db-meta">
			<span class="db-meta-dot"></span>
			<span>recorded <b>{recordedAt}</b></span>
			<span class="db-meta-sep">·</span>
			<span>{snap.meta.llm_model}</span>
			<span class="db-meta-sep">·</span>
			<span>graph <code>{snap.meta.graph_id}</code></span>
		</div>

		<div class="db-live">
			<span class="db-live-pulse"></span>
			<div class="db-live-copy">
				<strong>Drive it live.</strong>
				<span
					>The interactive demo conductor is running on GKE — prompt the six-agent fleet yourself
					and watch the context graph, data access, and audit feed react in real time.</span
				>
			</div>
			<a class="db-live-btn" href="http://34.24.243.248/" target="_blank" rel="noopener">
				Open the live dashboard <span class="db-live-arrow">→</span>
			</a>
		</div>
	</section>

	<!-- Top stat row -->
	<section class="db-stats reveal-stagger">
		<div class="db-stat">
			<div class="db-stat-n">{snap.agents.length}</div>
			<div class="db-stat-l">Agents spawned</div>
			<div class="db-stat-s">{committedCount} committed a belief</div>
		</div>
		<div class="db-stat">
			<div class="db-stat-n">{snap.tiers.cold_commitments}</div>
			<div class="db-stat-l">Belief commitments</div>
			<div class="db-stat-s">append-only · replayable</div>
		</div>
		<div class="db-stat">
			<div class="db-stat-n">{recon ? 1 : 0}</div>
			<div class="db-stat-l">Contradictions resolved</div>
			<div class="db-stat-s">two-pass · {recon ? recon.strategy : 'none fired'}</div>
		</div>
		<div class="db-stat">
			<div class="db-stat-n">{snap.federated_fetches.length}</div>
			<div class="db-stat-l">Federated fetches</div>
			<div class="db-stat-s">{snap.meta.sources.join(' · ')}</div>
		</div>
	</section>

	<!-- Agents + tiers -->
	<section class="section db-grid-2">
		<!-- Agent fleet -->
		<div class="db-panel reveal">
			<div class="db-panel-head">
				<h3>Agent fleet</h3>
				<span class="db-count">{snap.agents.length} spawned</span>
			</div>
			<ul class="db-agents">
				{#each snap.agents as agent (agent.id)}
					<li class="db-agent" class:inactive={!agent.committed}>
						<span class="db-agent-dot" class:on={agent.committed}></span>
						<span class="db-agent-id">{agent.id}</span>
						<span class="db-agent-scope">{agent.scope.join(', ')}</span>
						<span class="db-agent-state">{agent.committed ? 'committed' : 'no commit'}</span>
					</li>
				{/each}
			</ul>
		</div>

		<!-- Tier-state visualiser -->
		<div class="db-panel reveal">
			<div class="db-panel-head">
				<h3>Three-tier memory</h3>
				<span class="db-count">hot · warm · cold</span>
			</div>
			<div class="db-tiers">
				{#each tiers as t (t.key)}
					<div class="db-tier">
						<div class="db-tier-top">
							<span class="db-tier-name" style="color:{t.color}">{t.name}</span>
							<span class="db-tier-store">{t.store}</span>
						</div>
						<div class="db-tier-bar">
							<div
								class="db-tier-fill"
								style="width:{Math.min(100, (t.value / tierMax) * 100)}%; background:{t.color}"
							></div>
						</div>
						<div class="db-tier-foot">
							<span class="db-tier-detail">{t.detail}</span>
							<span class="db-tier-val">{t.value} {t.unit}</span>
						</div>
					</div>
				{/each}
			</div>
		</div>
	</section>

	<!-- Belief-diff viewer -->
	<section class="section reveal">
		<div class="db-panel">
			<div class="db-panel-head">
				<h3>Belief state &amp; reconciliation</h3>
				<span class="db-count" class:fired={recon}>
					{recon ? 'contradiction resolved' : 'coherent'}
				</span>
			</div>

			<ul class="db-beliefs">
				{#each snap.beliefs as b (b.agent + b.topic + b.turn)}
					<li
						class="db-belief"
						class:superseded={b.superseded}
						class:winner={recon && b.agent === recon.winner && b.topic === recon.topic}
					>
						<span class="db-belief-topic">{b.topic}</span>
						<span class="db-belief-claim">{b.claim}</span>
						<span class="db-belief-agent">{b.agent}</span>
						{#if b.superseded}<span class="db-tag dead">superseded</span>
						{:else if recon && b.agent === recon.winner && b.topic === recon.topic}<span
								class="db-tag win">accepted</span
							>{/if}
					</li>
				{/each}
			</ul>

			{#if recon}
				<div class="db-recon">
					<div class="db-recon-row">
						<span class="db-recon-k">Detected</span>
						<span class="db-recon-v"
							>two-pass · embedding cosine <b>{fmt(recon.similarity)}</b> → NLI
							<b>contradiction</b>
							{fmt(recon.nli_confidence)} on <b>{recon.topic}</b></span
						>
					</div>
					<div class="db-recon-row">
						<span class="db-recon-k">Strategy</span>
						<span class="db-recon-v">{recon.strategy}</span>
					</div>
					<div class="db-recon-row">
						<span class="db-recon-k">Resolved</span>
						<span class="db-recon-v"
							>{recon.winner} <b>{fmt(recon.winner_trust)}</b> &gt; {recon.loser}
							<b>{fmt(recon.loser_trust)}</b> → {recon.decision}; {recon.decision === 'accept_new'
								? `${recon.loser}'s claim superseded`
								: `${recon.winner}'s claim kept`}</span
						>
					</div>
				</div>
			{:else}
				<p class="db-hint">
					No contradiction fired on this run — every agent stayed coherent within its scope.
				</p>
			{/if}
		</div>
	</section>

	<!-- Federation + permission scoping -->
	<section class="section db-grid-2">
		<div class="db-panel reveal">
			<div class="db-panel-head">
				<h3>Federated fetches</h3>
				<span class="db-count">live · provenance</span>
			</div>
			{#if snap.federated_fetches.length}
				<ul class="db-fetches">
					{#each snap.federated_fetches as f (f.agent + f.source)}
						<li class="db-fetch">
							<span class="db-fetch-agent">{f.agent}</span>
							<span class="db-fetch-src">{f.source}</span>
							<span class="db-fetch-rows">{f.rows} rows</span>
							<span class="db-tag" class:tt={f.time_travel_available}>
								{f.time_travel_available ? 'time-travel' : 'no time-travel'}
							</span>
						</li>
					{/each}
				</ul>
			{:else}
				<p class="db-hint">No federated fetch landed on this run.</p>
			{/if}
		</div>

		<div class="db-panel reveal">
			<div class="db-panel-head">
				<h3>Permission scoping</h3>
				<span class="db-count">policy engine</span>
			</div>
			{#if snap.denial}
				<div class="db-denial">
					<div class="db-denial-row">
						<span class="db-recon-k">Denied</span>
						<span class="db-recon-v"
							><b>{snap.denial.agent}</b> requested <b>{snap.denial.denied_topic}</b> — outside its remit</span
						>
					</div>
					<div class="db-denial-row">
						<span class="db-recon-k">Scope</span>
						<span class="db-recon-v">{snap.denial.scope.join(', ')}</span>
					</div>
					<p class="db-hint">
						The policy engine refused the out-of-scope fetch before any data left the source —
						scoping is enforced by Ezra, not the agent.
					</p>
				</div>
			{:else}
				<p class="db-hint">No out-of-scope request was attempted on this run.</p>
			{/if}
		</div>
	</section>

	<!-- Branching replay -->
	<section class="section reveal">
		<div class="db-panel">
			<div class="db-panel-head">
				<h3>Branching replay</h3>
				<span class="db-count">counterfactual</span>
			</div>

			<p class="db-hint">
				A real counterfactual branched from turn 1 of the live graph and run forward — mutating
				<b>race_strategy</b>'s call to "wets at lap 43". The diff shows where the branch diverges
				from what actually happened.
			</p>

			{#if snap.branch && snap.branch.diverged && snap.branch.diverged.length}
				<div class="db-diff">
					<div class="db-diff-head">
						<span>topic</span>
						<span>commitment present only in the branch</span>
					</div>
					{#each snap.branch.diverged as d (d.topic)}
						{#each d.only_in_branch as claim (claim)}
							<div class="db-diff-row">
								<span class="db-diff-topic">{d.topic}</span>
								<span class="db-diff-branch">{claim}</span>
							</div>
						{/each}
					{/each}
				</div>
			{:else if snap.branch && snap.branch.error}
				<p class="db-hint">Branch run reported: {snap.branch.error}</p>
			{:else}
				<p class="db-hint">The branch produced no divergence on this run.</p>
			{/if}
		</div>
	</section>

	<section class="section db-foot reveal">
		<p class="muted">
			Recorded from a live GKE run, inherited from <code>{snap.meta.inherited_from}</code>. The same
			state is available live over the REST surface (<code>/ezra/health</code>,
			<code>/ezra/belief/snapshot</code>, <code>/ezra/branch/diff</code>). See the
			<a href="/docs/rest-api">REST API</a>.
		</p>
	</section>
</main>

<style>
	main.wrap {
		padding-top: 40px;
		padding-bottom: 80px;
	}

	.db-head {
		padding-bottom: 40px;
		display: flex;
		flex-direction: column;
		gap: 24px;
	}

	/* Recorded-run meta line */
	.db-meta {
		display: flex;
		align-items: center;
		gap: 12px;
		flex-wrap: wrap;
		font-family: var(--f-mono);
		font-size: 11.5px;
		letter-spacing: 0.06em;
		color: var(--fg-3);
	}
	.db-meta b {
		color: var(--fg);
	}
	.db-meta code {
		color: var(--accent);
		font-size: 11px;
	}
	.db-meta-sep {
		color: var(--fg-4);
	}
	.db-meta-dot {
		width: 7px;
		height: 7px;
		border-radius: 50%;
		background: var(--accent);
		box-shadow: 0 0 8px rgba(45, 199, 184, 0.6);
	}

	/* Live GKE demo banner */
	.db-live {
		display: flex;
		align-items: center;
		gap: 16px;
		flex-wrap: wrap;
		margin-top: 22px;
		padding: 18px 22px;
		border: 1px solid rgba(45, 199, 184, 0.35);
		background: rgba(45, 199, 184, 0.05);
	}
	.db-live-pulse {
		flex: 0 0 auto;
		width: 9px;
		height: 9px;
		border-radius: 50%;
		background: var(--accent);
		box-shadow: 0 0 0 0 rgba(45, 199, 184, 0.5);
		animation: db-live-pulse 2s ease-out infinite;
	}
	@keyframes db-live-pulse {
		0% {
			box-shadow: 0 0 0 0 rgba(45, 199, 184, 0.5);
		}
		70% {
			box-shadow: 0 0 0 10px rgba(45, 199, 184, 0);
		}
		100% {
			box-shadow: 0 0 0 0 rgba(45, 199, 184, 0);
		}
	}
	.db-live-copy {
		flex: 1 1 320px;
	}
	.db-live-copy strong {
		display: block;
		font-family: var(--f-sans);
		font-weight: 500;
		font-size: 15px;
		text-transform: uppercase;
		letter-spacing: 0.02em;
		color: var(--fg);
		margin-bottom: 3px;
	}
	.db-live-copy span {
		font-family: var(--f-mono);
		font-size: 11.5px;
		line-height: 1.6;
		color: var(--fg-3);
	}
	.db-live-btn {
		flex: 0 0 auto;
		display: inline-flex;
		align-items: center;
		gap: 10px;
		padding: 11px 20px;
		border: 1px solid var(--accent);
		color: var(--accent);
		text-decoration: none;
		font-family: var(--f-mono);
		font-size: 11.5px;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		font-weight: 600;
		transition: all 0.2s;
	}
	.db-live-btn:hover {
		background: var(--accent);
		color: var(--bg);
	}
	.db-live-arrow {
		font-size: 14px;
	}

	/* Stat row */
	.db-stats {
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		border: 1px solid var(--line);
		border-bottom: 0;
	}
	.db-stat {
		padding: 28px 24px;
		border-right: 1px solid var(--line);
		border-bottom: 1px solid var(--line);
	}
	.db-stat:last-child {
		border-right: 0;
	}
	.db-stat-n {
		font-family: var(--f-sans);
		font-size: 44px;
		font-weight: 500;
		line-height: 1;
		color: var(--accent);
	}
	.db-stat-l {
		margin-top: 10px;
		font-family: var(--f-mono);
		font-size: 11px;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: var(--fg-2);
	}
	.db-stat-s {
		margin-top: 4px;
		font-family: var(--f-mono);
		font-size: 10.5px;
		color: var(--fg-4);
	}

	/* Panels */
	.db-panel {
		border: 1px solid var(--line);
		background: rgba(0, 0, 0, 0.18);
	}
	.db-panel-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 16px 20px;
		border-bottom: 1px solid var(--line);
	}
	.db-panel-head h3 {
		margin: 0;
		font-family: var(--f-mono);
		font-size: 12px;
		letter-spacing: 0.16em;
		text-transform: uppercase;
		color: var(--fg);
	}
	.db-count {
		font-family: var(--f-mono);
		font-size: 10.5px;
		letter-spacing: 0.12em;
		text-transform: uppercase;
		color: var(--fg-3);
	}
	.db-count.fired {
		color: var(--hot);
	}

	.db-grid-2 {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 28px;
		padding-top: 0;
		border-top: 0;
	}

	/* Agents */
	.db-agents {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.db-agent {
		display: grid;
		grid-template-columns: 14px 1.4fr 1fr auto;
		align-items: center;
		gap: 12px;
		padding: 12px 20px;
		border-bottom: 1px solid var(--line-2);
		font-family: var(--f-mono);
		font-size: 12px;
	}
	.db-agent:last-child {
		border-bottom: 0;
	}
	.db-agent.inactive {
		opacity: 0.5;
	}
	.db-agent-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--fg-4);
	}
	.db-agent-dot.on {
		background: var(--accent);
		box-shadow: 0 0 8px rgba(45, 199, 184, 0.6);
	}
	.db-agent-id {
		color: var(--fg);
	}
	.db-agent-scope {
		color: var(--fg-3);
	}
	.db-agent-state {
		text-align: right;
		font-size: 10px;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: var(--fg-4);
	}

	/* Tiers */
	.db-tiers {
		padding: 20px;
		display: flex;
		flex-direction: column;
		gap: 22px;
	}
	.db-tier-top {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		margin-bottom: 8px;
	}
	.db-tier-name {
		font-family: var(--f-mono);
		font-size: 12px;
		letter-spacing: 0.1em;
		text-transform: uppercase;
	}
	.db-tier-store {
		font-family: var(--f-mono);
		font-size: 10.5px;
		color: var(--fg-3);
	}
	.db-tier-bar {
		height: 8px;
		background: rgba(255, 255, 255, 0.05);
		border: 1px solid var(--line-2);
		overflow: hidden;
	}
	.db-tier-fill {
		height: 100%;
		transition: width 0.6s cubic-bezier(0.2, 0.6, 0.2, 1);
		opacity: 0.85;
	}
	.db-tier-foot {
		display: flex;
		justify-content: space-between;
		margin-top: 8px;
		font-family: var(--f-mono);
		font-size: 10.5px;
	}
	.db-tier-detail {
		color: var(--fg-4);
	}
	.db-tier-val {
		color: var(--fg-2);
	}

	/* Beliefs */
	.db-beliefs {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.db-belief {
		display: grid;
		grid-template-columns: 100px 1fr auto auto;
		align-items: center;
		gap: 14px;
		padding: 13px 20px;
		border-bottom: 1px solid var(--line-2);
		font-family: var(--f-mono);
		font-size: 12px;
	}
	.db-belief:last-child {
		border-bottom: 0;
	}
	.db-belief.superseded .db-belief-claim {
		text-decoration: line-through;
		color: var(--fg-4);
	}
	.db-belief.winner {
		background: rgba(45, 199, 184, 0.05);
	}
	.db-belief-topic {
		color: var(--accent);
		text-transform: uppercase;
		font-size: 10px;
		letter-spacing: 0.12em;
	}
	.db-belief-claim {
		color: var(--fg);
	}
	.db-belief-agent {
		color: var(--fg-3);
		font-size: 11px;
	}
	.db-tag {
		font-size: 9.5px;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		padding: 3px 8px;
		border: 1px solid var(--line);
		color: var(--fg-3);
	}
	.db-tag.dead {
		color: var(--hot);
		border-color: rgba(232, 156, 94, 0.4);
	}
	.db-tag.win {
		color: var(--accent);
		border-color: rgba(45, 199, 184, 0.4);
	}
	.db-tag.tt {
		color: var(--accent-2);
		border-color: rgba(125, 224, 217, 0.4);
	}

	/* Reconciliation / denial trace */
	.db-recon,
	.db-denial {
		padding: 18px 20px;
		border-top: 1px solid var(--line);
		background: rgba(0, 0, 0, 0.22);
		display: flex;
		flex-direction: column;
		gap: 10px;
	}
	.db-recon-row,
	.db-denial-row {
		display: grid;
		grid-template-columns: 90px 1fr;
		gap: 14px;
		font-family: var(--f-mono);
		font-size: 11.5px;
	}
	.db-recon-k {
		color: var(--fg-3);
		text-transform: uppercase;
		font-size: 10px;
		letter-spacing: 0.12em;
	}
	.db-recon-v {
		color: var(--fg-2);
	}
	.db-recon-v b {
		color: var(--accent);
		font-weight: 600;
	}

	.db-hint {
		padding: 16px 20px;
		margin: 0;
		font-family: var(--f-mono);
		font-size: 11.5px;
		color: var(--fg-3);
		line-height: 1.6;
	}
	.db-hint b {
		color: var(--accent);
	}
	.db-denial .db-hint {
		padding: 4px 0 0;
	}

	/* Federated fetches */
	.db-fetches {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.db-fetch {
		display: grid;
		grid-template-columns: 1.1fr 1.8fr auto auto;
		align-items: center;
		gap: 12px;
		padding: 13px 20px;
		border-bottom: 1px solid var(--line-2);
		font-family: var(--f-mono);
		font-size: 11.5px;
	}
	.db-fetch:last-child {
		border-bottom: 0;
	}
	.db-fetch-agent {
		color: var(--fg-3);
	}
	.db-fetch-src {
		color: var(--fg);
		overflow-wrap: anywhere;
	}
	.db-fetch-rows {
		color: var(--accent-2);
	}

	/* Branching diff */
	.db-diff {
		border-top: 1px solid var(--line);
	}
	.db-diff-head,
	.db-diff-row {
		display: grid;
		grid-template-columns: 110px 1fr;
		gap: 14px;
		padding: 12px 20px;
		font-family: var(--f-mono);
		font-size: 11.5px;
	}
	.db-diff-head {
		color: var(--fg-4);
		text-transform: uppercase;
		font-size: 10px;
		letter-spacing: 0.12em;
		border-bottom: 1px solid var(--line);
	}
	.db-diff-row {
		border-bottom: 1px solid var(--line-2);
	}
	.db-diff-row:last-child {
		border-bottom: 0;
	}
	.db-diff-topic {
		color: var(--accent);
		text-transform: uppercase;
		font-size: 10px;
		letter-spacing: 0.1em;
	}
	.db-diff-branch {
		color: var(--fg);
	}

	.db-foot code {
		font-family: var(--f-mono);
		color: var(--accent);
		font-size: 11px;
	}
	.db-foot a {
		color: var(--fg);
		border-bottom: 1px solid var(--line);
	}
	.db-foot a:hover {
		color: var(--accent);
		border-color: var(--accent);
	}

	@media (max-width: 1100px) {
		.db-grid-2 {
			grid-template-columns: 1fr;
		}
		.db-stats {
			grid-template-columns: repeat(2, 1fr);
		}
	}
	@media (max-width: 640px) {
		.db-stats {
			grid-template-columns: 1fr;
		}
		.db-belief,
		.db-fetch,
		.db-diff-head,
		.db-diff-row {
			grid-template-columns: 1fr;
			gap: 4px;
		}
	}
</style>
