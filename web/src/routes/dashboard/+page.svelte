<script lang="ts">
	import { onMount } from 'svelte';

	// ---------------------------------------------------------------------------
	// This is an *illustrative* operations dashboard: a scripted simulation of the
	// runtime's live state (active agents, three-tier memory, belief
	// reconciliation, branching replay). It runs entirely client-side — no backend
	// — to show the shape of what Ezra's live state looks like during a session.
	// ---------------------------------------------------------------------------

	type Agent = {
		id: string;
		scope: string;
		born: number;
		dies: number | null;
	};

	// A race-weekend fleet that spawns and terminates as the weekend unfolds.
	const FLEET: Agent[] = [
		{ id: 'race_strategy', scope: 'strategy', born: 0, dies: null },
		{ id: 'tyre_engineer', scope: 'tyres', born: 0, dies: null },
		{ id: 'telemetry_analyst', scope: 'telemetry', born: 1, dies: 9 },
		{ id: 'weather_model', scope: 'weather', born: 2, dies: null },
		{ id: 'aero_rd', scope: 'aero', born: 3, dies: 8 },
		{ id: 'parts_shortage', scope: 'parts', born: 5, dies: 11 },
		{ id: 'logistics', scope: 'logistics', born: 4, dies: null },
		{ id: 'press_officer', scope: 'press', born: 8, dies: null }
	];
	const MAX_TICK = 12;
	const CONTRADICTION_TICK = 6;

	let tick = $state(0);
	let playing = $state(true);

	const activeAgents = $derived(
		FLEET.filter((a) => a.born <= tick && (a.dies === null || a.dies > tick))
	);
	const agentCount = $derived(activeAgents.length);
	const peakCount = $derived(
		Math.max(
			...Array.from(
				{ length: MAX_TICK + 1 },
				(_, t) => FLEET.filter((a) => a.born <= t && (a.dies === null || a.dies > t)).length
			)
		)
	);

	// Three-tier memory fills as the session runs.
	const hotTurns = $derived(Math.min(8, 1 + tick)); // capped ring buffer (max_turns)
	const warmSummaries = $derived(tick * 3);
	const coldCommitments = $derived(11 + tick * 4);

	const tiers = $derived([
		{
			key: 'hot',
			name: 'Hot tier',
			store: 'Redis',
			detail: 'Recent turns · pinned beliefs',
			value: hotTurns,
			cap: 8,
			unit: 'turns',
			color: 'var(--hot)'
		},
		{
			key: 'warm',
			name: 'Warm tier',
			store: 'Qdrant',
			detail: 'Compressed summaries · vectors',
			value: warmSummaries,
			cap: MAX_TICK * 3,
			unit: 'summaries',
			color: 'var(--warm)'
		},
		{
			key: 'cold',
			name: 'Cold tier',
			store: 'MongoDB Atlas',
			detail: 'Belief store · semantic memory',
			value: coldCommitments,
			cap: 11 + MAX_TICK * 4,
			unit: 'commitments',
			color: 'var(--cold)'
		}
	]);

	// Belief state on topic `tyres` — a contradiction fires mid-session and the
	// highest-trust reconciler resolves it (tyre_engineer 0.95 > race_strategy 0.80).
	type Belief = {
		agent: string;
		topic: string;
		claim: string;
		superseded?: boolean;
		winner?: boolean;
	};
	const fired = $derived(tick >= CONTRADICTION_TICK);
	const beliefs = $derived<Belief[]>([
		{ agent: 'weather_model', topic: 'weather', claim: 'Dry through lights-out; 8% rain risk.' },
		{ agent: 'logistics', topic: 'logistics', claim: 'Freight cleared customs at 14:02.' },
		{
			agent: 'race_strategy',
			topic: 'tyres',
			claim: 'Start on softs, one-stop.',
			superseded: fired
		},
		...(fired
			? [
					{
						agent: 'tyre_engineer',
						topic: 'tyres',
						claim: 'Start on mediums — softs overheat after lap 40.',
						winner: true
					}
				]
			: [])
	]);

	// Branching replay — branch from a prior turn, mutate, run forward, diff.
	type BranchScenario = {
		turn: number;
		label: string;
		mutation: string;
		diff: { topic: string; original: string; branch: string }[];
	};
	const SCENARIOS: BranchScenario[] = [
		{
			turn: 5,
			label: 'turn 5',
			mutation: 'parts_shortage spawned 3 turns earlier',
			diff: [
				{ topic: 'parts', original: 'FW-07 flagged at turn 8', branch: 'FW-07 flagged at turn 5' },
				{ topic: 'logistics', original: 'standard freight', branch: 'expedited freight booked' }
			]
		},
		{
			turn: 10,
			label: 'turn 10',
			mutation: 'tyre_engineer commits "wets" instead of "mediums"',
			diff: [
				{ topic: 'tyres', original: 'mediums, one-stop', branch: 'wets, two-stop' },
				{ topic: 'strategy', original: 'track position', branch: 'undercut on lap 18' }
			]
		},
		{
			turn: 15,
			label: 'turn 15',
			mutation: 'weather_model calls rain at lap 43',
			diff: [
				{ topic: 'weather', original: 'dry to flag', branch: 'rain from lap 43' },
				{ topic: 'tyres', original: 'stay out on hards', branch: 'box for inters, lap 43' },
				{ topic: 'strategy', original: 'P4 finish', branch: 'P2 finish (counterfactual)' }
			]
		}
	];
	let branchTurn = $state(15);
	const scenario = $derived(SCENARIOS.find((s) => s.turn === branchTurn) ?? SCENARIOS[2]);

	function togglePlay() {
		playing = !playing;
	}
	function step() {
		playing = false;
		tick = (tick + 1) % (MAX_TICK + 1);
	}
	function reset() {
		playing = false;
		tick = 0;
	}

	onMount(() => {
		const timer = setInterval(() => {
			if (playing) tick = tick >= MAX_TICK ? 0 : tick + 1;
		}, 1400);

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

		return () => {
			clearInterval(timer);
			io.disconnect();
		};
	});
</script>

<svelte:head>
	<title>Live Dashboard — Ezra Operations</title>
	<meta
		name="description"
		content="Ezra operations dashboard — live agent fleet, three-tier memory, belief reconciliation, and branching replay."
	/>
</svelte:head>

<main class="wrap">
	<!-- Header -->
	<section class="section db-head reveal">
		<div class="section-head">
			<div class="idx">// Operations</div>
			<h2>Live <em>operations</em> dashboard</h2>
			<p class="lede">
				A scripted simulation of a session graph mid-flight: agents spawning and terminating, the
				three memory tiers filling, beliefs reconciling under contradiction, and a counterfactual
				branch running forward. Illustrative — no backend attached.
			</p>
		</div>

		<div class="db-controls">
			<button class="db-btn" onclick={togglePlay} aria-pressed={playing}>
				<span class="db-dot" class:live={playing}></span>
				{playing ? 'Live' : 'Paused'}
			</button>
			<button class="db-btn ghost" onclick={step}>Step →</button>
			<button class="db-btn ghost" onclick={reset}>Reset</button>
			<div class="db-clock">
				turn <b>{tick}</b> / {MAX_TICK}
			</div>
		</div>
	</section>

	<!-- Top stat row -->
	<section class="db-stats reveal-stagger">
		<div class="db-stat">
			<div class="db-stat-n">{agentCount}</div>
			<div class="db-stat-l">Active agents</div>
			<div class="db-stat-s">peak {peakCount} this session</div>
		</div>
		<div class="db-stat">
			<div class="db-stat-n">{coldCommitments}</div>
			<div class="db-stat-l">Belief commitments</div>
			<div class="db-stat-s">append-only · replayable</div>
		</div>
		<div class="db-stat">
			<div class="db-stat-n">{fired ? 1 : 0}</div>
			<div class="db-stat-l">Contradictions resolved</div>
			<div class="db-stat-s">two-pass · highest-trust</div>
		</div>
		<div class="db-stat">
			<div class="db-stat-n">3</div>
			<div class="db-stat-l">Federated sources</div>
			<div class="db-stat-s">Atlas · Snowflake · BigQuery</div>
		</div>
	</section>

	<!-- Agents + tiers -->
	<section class="section db-grid-2">
		<!-- Live agent fleet -->
		<div class="db-panel reveal">
			<div class="db-panel-head">
				<h3>Agent fleet</h3>
				<span class="db-count">{agentCount} active</span>
			</div>
			<ul class="db-agents">
				{#each FLEET as agent (agent.id)}
					{@const isActive = activeAgents.includes(agent)}
					<li class="db-agent" class:inactive={!isActive}>
						<span class="db-agent-dot" class:on={isActive}></span>
						<span class="db-agent-id">{agent.id}</span>
						<span class="db-agent-scope">{agent.scope}</span>
						<span class="db-agent-state">
							{#if isActive}active{:else if agent.born > tick}pending{:else}terminated{/if}
						</span>
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
								style="width:{Math.min(100, (t.value / t.cap) * 100)}%; background:{t.color}"
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
				<span class="db-count" class:fired>
					{fired ? 'contradiction resolved' : 'coherent'}
				</span>
			</div>

			<ul class="db-beliefs">
				{#each beliefs as b (b.agent + b.topic)}
					<li class="db-belief" class:superseded={b.superseded} class:winner={b.winner}>
						<span class="db-belief-topic">{b.topic}</span>
						<span class="db-belief-claim">{b.claim}</span>
						<span class="db-belief-agent">{b.agent}</span>
						{#if b.superseded}<span class="db-tag dead">superseded</span>{/if}
						{#if b.winner}<span class="db-tag win">accepted</span>{/if}
					</li>
				{/each}
			</ul>

			{#if fired}
				<div class="db-recon">
					<div class="db-recon-row">
						<span class="db-recon-k">Detected</span>
						<span class="db-recon-v"
							>two-pass · embedding cosine 0.83 → NLI <b>contradiction</b> 0.97 on
							<b>tyres</b></span
						>
					</div>
					<div class="db-recon-row">
						<span class="db-recon-k">Strategy</span>
						<span class="db-recon-v">highest_trust</span>
					</div>
					<div class="db-recon-row">
						<span class="db-recon-k">Resolved</span>
						<span class="db-recon-v"
							>tyre_engineer <b>0.95</b> &gt; race_strategy <b>0.80</b> → accept_new; softs superseded</span
						>
					</div>
				</div>
			{:else}
				<p class="db-hint">
					No active contradictions. Let the session run to turn {CONTRADICTION_TICK} — race_strategy and
					tyre_engineer will disagree on <b>tyres</b>.
				</p>
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
				Branch from a prior turn, mutate state, and run forward. The diff shows where the branch
				diverges from reality.
			</p>

			<div class="db-branch-picker">
				{#each SCENARIOS as s (s.turn)}
					<button
						class="db-chip"
						class:active={branchTurn === s.turn}
						onclick={() => (branchTurn = s.turn)}
					>
						branch @ {s.label}
					</button>
				{/each}
			</div>

			<div class="db-mutation">
				<span class="db-recon-k">Mutation</span>
				<span class="db-recon-v">{scenario.mutation}</span>
			</div>

			<div class="db-diff">
				<div class="db-diff-head">
					<span>topic</span>
					<span>original</span>
					<span>branch</span>
				</div>
				{#each scenario.diff as d (d.topic)}
					<div class="db-diff-row">
						<span class="db-diff-topic">{d.topic}</span>
						<span class="db-diff-orig">{d.original}</span>
						<span class="db-diff-branch">{d.branch}</span>
					</div>
				{/each}
			</div>
		</div>
	</section>

	<section class="section db-foot reveal">
		<p class="muted">
			Illustrative simulation. The real dashboard reads live runtime state over the REST surface (<code
				>/ezra/health</code
			>, <code>/ezra/belief/snapshot</code>,
			<code>/ezra/branch/diff</code>). See the <a href="/docs#rest-api">REST API</a>.
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
		gap: 28px;
	}

	/* Controls */
	.db-controls {
		display: flex;
		align-items: center;
		gap: 12px;
		flex-wrap: wrap;
	}
	.db-btn {
		display: inline-flex;
		align-items: center;
		gap: 9px;
		padding: 9px 18px;
		background: rgba(45, 199, 184, 0.06);
		color: var(--fg);
		border: 1px solid var(--accent);
		font-family: var(--f-mono);
		font-size: 11px;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		cursor: pointer;
		transition: all 0.2s;
	}
	.db-btn:hover {
		background: var(--accent);
		color: var(--bg);
	}
	.db-btn.ghost {
		background: transparent;
		border-color: var(--line);
		color: var(--fg-2);
	}
	.db-btn.ghost:hover {
		border-color: var(--fg);
		background: transparent;
		color: var(--fg);
	}
	.db-dot {
		width: 7px;
		height: 7px;
		border-radius: 50%;
		background: var(--fg-4);
	}
	.db-dot.live {
		background: var(--accent);
		animation: pulse 1.4s infinite;
	}
	.db-clock {
		font-family: var(--f-mono);
		font-size: 12px;
		color: var(--fg-3);
		letter-spacing: 0.1em;
		margin-left: auto;
	}
	.db-clock b {
		color: var(--accent);
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
		transition: opacity 0.3s;
	}
	.db-agent:last-child {
		border-bottom: 0;
	}
	.db-agent.inactive {
		opacity: 0.38;
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
	}
	.db-tag.dead {
		color: var(--hot);
		border-color: rgba(232, 156, 94, 0.4);
	}
	.db-tag.win {
		color: var(--accent);
		border-color: rgba(45, 199, 184, 0.4);
	}

	/* Reconciliation trace */
	.db-recon {
		padding: 18px 20px;
		border-top: 1px solid var(--line);
		background: rgba(0, 0, 0, 0.22);
		display: flex;
		flex-direction: column;
		gap: 10px;
	}
	.db-recon-row {
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

	/* Branching */
	.db-branch-picker {
		display: flex;
		gap: 10px;
		flex-wrap: wrap;
		padding: 0 20px 16px;
	}
	.db-chip {
		padding: 8px 14px;
		background: transparent;
		border: 1px solid var(--line);
		color: var(--fg-2);
		font-family: var(--f-mono);
		font-size: 11px;
		letter-spacing: 0.08em;
		cursor: pointer;
		transition: all 0.2s;
	}
	.db-chip:hover {
		border-color: var(--fg);
		color: var(--fg);
	}
	.db-chip.active {
		border-color: var(--accent);
		color: var(--accent);
		background: rgba(45, 199, 184, 0.06);
	}
	.db-mutation {
		display: grid;
		grid-template-columns: 90px 1fr;
		gap: 14px;
		padding: 14px 20px;
		border-top: 1px solid var(--line-2);
		font-family: var(--f-mono);
		font-size: 11.5px;
	}
	.db-mutation .db-recon-v {
		color: var(--accent-2);
	}
	.db-diff {
		border-top: 1px solid var(--line);
	}
	.db-diff-head,
	.db-diff-row {
		display: grid;
		grid-template-columns: 110px 1fr 1fr;
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
	.db-diff-orig {
		color: var(--fg-4);
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
		.db-diff-head,
		.db-diff-row {
			grid-template-columns: 1fr;
			gap: 4px;
		}
	}
</style>
