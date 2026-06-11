<script lang="ts">
	let current = $state(0);

	type Slide = {
		label: string;
		title: string;
		em?: string;
		rows: [string, string][];
		note?: string;
	};

	const SLIDES: Slide[] = [
		{
			label: '// Pre-Launch · June 2026',
			title: 'The Multi-Agent Platform for',
			em: 'Enterprises.',
			rows: [
				['Federation · Memory · Belief · Replay', ''],
				['Live on GKE', 'v0.1.1 · MIT · PyPI / GHCR / Helm']
			]
		},
		{
			label: '01 / Problem',
			title: 'Multi-agent AI has a',
			em: 'coordination crisis.',
			rows: [
				['No shared memory', 'Context from Agent A never reaches Agent B.'],
				['No audit trail', 'What did the agent believe, when, from what source?'],
				['No reconciliation', 'Conflicting facts propagate silently.'],
				['Unsafe data access', 'Raw queries, one prompt injection away.']
			]
		},
		{
			label: '02 / Solution',
			title: 'One runtime.',
			em: 'Three layers.',
			rows: [
				[
					'① Federation',
					'Pushdown to MongoDB, Snowflake, BigQuery, REST. The model never touches raw rows.'
				],
				['② Memory', 'Hot, warm, cold tiers — shared across the fleet, scoped by permission.'],
				['③ Belief & Audit', 'Every fact attributed. Queryable history. Branching replay.']
			]
		},
		{
			label: '03 / Architecture',
			title: 'The 8-step router.',
			em: '<40ms per agent.',
			rows: [
				['1–2', 'Parse · Policy'],
				['3–4', 'Belief check · Hydrate memory'],
				['5–6', 'Federated fetch · Assemble context'],
				['7–8', 'LLM call · Write-back']
			],
			note: 'Most platforms only do steps 1, 7, and 8. Steps 2–6 are where Ezra sits.'
		},
		{
			label: '04 / Why Ezra',
			title: 'Five things',
			em: 'no other platform ships.',
			rows: [
				['Pushdown execution', 'Typed summaries, never raw rows.'],
				['Versioned belief audit', 'Every commitment, attributed, exportable.'],
				['Branching replay', 'Reconstruct · mutate · run forward · diff.'],
				['Time-travel federation', 'Any query, as of any prior timestamp.'],
				['Cross-agent reconciliation', 'Four strategies, trust-aware.']
			]
		},
		{
			label: '05 / Landscape',
			title: 'The layer',
			em: 'under the frameworks.',
			rows: [
				['MemGPT · Letta', 'Memory for one agent → Ezra: reconciled state for the fleet.'],
				['Langflow', 'Visual builder → Ezra: the runtime underneath.'],
				['LangGraph · ADK', 'Orchestration → Ezra plugs in as the state plane.']
			],
			note: "What MemGPT did for one agent's context window, Ezra does for a fleet's shared state."
		},
		{
			label: '06 / The Ask',
			title: 'Join the',
			em: 'early access program.',
			rows: [
				['pip install ezra-client', ''],
				['docker pull ghcr.io/xavio2495/ezra-api:0.1.1', ''],
				['helm install ezra oci://ghcr.io/xavio2495/charts/ezra', '']
			],
			note: 'Two or three enterprise AI teams to co-build the production version. 2495.immanuel@gmail.com'
		}
	];

	const TOTAL = SLIDES.length;

	function goTo(n: number) {
		current = Math.max(0, Math.min(TOTAL - 1, n));
	}

	let touchX = 0;
	function onTouchStart(e: TouchEvent) {
		touchX = e.touches[0].clientX;
	}
	function onTouchEnd(e: TouchEvent) {
		const dx = e.changedTouches[0].clientX - touchX;
		if (Math.abs(dx) > 48) goTo(current + (dx < 0 ? 1 : -1));
	}
</script>

<svelte:head>
	<title>Pitch — Ezra</title>
</svelte:head>

<div
	class="mp-deck"
	role="group"
	aria-roledescription="carousel"
	aria-label="Pitch slides"
	ontouchstart={onTouchStart}
	ontouchend={onTouchEnd}
>
	{#each SLIDES as slide, i (slide.label)}
		<section class="mp-slide" class:active={current === i} aria-hidden={current !== i}>
			<div class="mp-label">{slide.label}</div>
			<h2>
				{slide.title}
				{#if slide.em}<em>{slide.em}</em>{/if}
			</h2>
			<div class="mp-rows">
				{#each slide.rows as [head, body] (head)}
					<div class="mp-row">
						<strong>{head}</strong>
						{#if body}<span>{body}</span>{/if}
					</div>
				{/each}
			</div>
			{#if slide.note}
				<p class="mp-note">{slide.note}</p>
			{/if}
		</section>
	{/each}

	<div class="mp-ctrl">
		<button onclick={() => goTo(current - 1)} disabled={current === 0} aria-label="Previous">
			‹
		</button>
		<div class="mp-dots">
			{#each SLIDES as slide, i (slide.label)}
				<button
					class="mp-dot"
					class:on={current === i}
					onclick={() => goTo(i)}
					aria-label={`Slide ${i + 1}`}
				></button>
			{/each}
		</div>
		<button onclick={() => goTo(current + 1)} disabled={current === TOTAL - 1} aria-label="Next">
			›
		</button>
	</div>
	<div class="mp-hint">swipe or tap arrows · {current + 1} / {TOTAL}</div>
</div>

<style>
	.mp-deck {
		position: relative;
		display: flex;
		flex-direction: column;
		min-height: calc(100dvh - 180px);
		padding: 28px 20px 8px;
	}
	.mp-slide {
		display: none;
		flex: 1;
	}
	.mp-slide.active {
		display: block;
		animation: mp-in 0.3s ease;
	}
	@keyframes mp-in {
		from {
			opacity: 0;
			transform: translateX(16px);
		}
		to {
			opacity: 1;
			transform: none;
		}
	}

	.mp-label {
		font-family: var(--f-mono);
		font-size: 10px;
		letter-spacing: 0.2em;
		text-transform: uppercase;
		color: var(--accent);
		margin-bottom: 14px;
	}
	h2 {
		margin: 0 0 20px;
		font-family: var(--f-sans);
		font-weight: 500;
		font-size: 27px;
		line-height: 1.02;
		text-transform: uppercase;
		letter-spacing: -0.02em;
		color: var(--fg);
	}
	h2 em {
		display: block;
		font-family: var(--f-display);
		font-style: italic;
		font-weight: 400;
		text-transform: none;
		color: var(--accent);
	}

	.mp-rows {
		border: 1px solid var(--line);
	}
	.mp-row {
		padding: 13px 16px;
		border-bottom: 1px solid var(--line);
	}
	.mp-row:last-child {
		border-bottom: 0;
	}
	.mp-row strong {
		display: block;
		font-family: var(--f-mono);
		font-weight: 600;
		font-size: 12px;
		letter-spacing: 0.04em;
		color: var(--fg);
		overflow-wrap: anywhere;
	}
	.mp-row span {
		display: block;
		margin-top: 3px;
		font-family: var(--f-mono);
		font-size: 11px;
		line-height: 1.55;
		color: var(--fg-3);
	}
	.mp-note {
		margin: 14px 0 0;
		font-family: var(--f-mono);
		font-size: 11.5px;
		line-height: 1.6;
		color: var(--fg-2);
	}

	.mp-ctrl {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
		margin-top: 22px;
	}
	.mp-ctrl > button {
		width: 44px;
		height: 44px;
		background: var(--bg-2);
		border: 1px solid var(--line);
		color: var(--fg-2);
		font-size: 20px;
		cursor: pointer;
	}
	.mp-ctrl > button:disabled {
		opacity: 0.3;
	}
	.mp-dots {
		display: flex;
		gap: 8px;
	}
	.mp-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		border: 1px solid var(--fg-4);
		background: transparent;
		padding: 0;
	}
	.mp-dot.on {
		background: var(--accent);
		border-color: var(--accent);
	}
	.mp-hint {
		margin-top: 10px;
		text-align: center;
		font-family: var(--f-mono);
		font-size: 9.5px;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: var(--fg-4);
	}
</style>
