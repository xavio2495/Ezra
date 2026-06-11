<script lang="ts">
	import { onMount } from 'svelte';

	let currentSlide = $state(0);
	const TOTAL = 7;

	function goTo(n: number) {
		currentSlide = Math.max(0, Math.min(TOTAL - 1, n));
	}
	function next() {
		goTo(currentSlide + 1);
	}
	function prev() {
		goTo(currentSlide - 1);
	}

	// PowerPoint-style: click anywhere on the slide advances, unless the click
	// landed on a real control (link / button).
	function onDeckClick(e: MouseEvent) {
		if ((e.target as HTMLElement).closest('a, button')) return;
		next();
	}

	onMount(() => {
		// Presentation mode: no page scroll, no footer (restored on navigate-away).
		document.body.classList.add('pitch-mode');

		const onKey = (e: KeyboardEvent) => {
			if (['ArrowDown', 'ArrowRight', 'PageDown', ' ', 'Enter'].includes(e.key)) {
				e.preventDefault();
				next();
			} else if (['ArrowUp', 'ArrowLeft', 'PageUp'].includes(e.key)) {
				e.preventDefault();
				prev();
			} else if (e.key === 'Home') {
				goTo(0);
			} else if (e.key === 'End') {
				goTo(TOTAL - 1);
			}
		};
		window.addEventListener('keydown', onKey);
		return () => {
			document.body.classList.remove('pitch-mode');
			window.removeEventListener('keydown', onKey);
		};
	});
</script>

<svelte:head>
	<title>Pitch — Ezra</title>
</svelte:head>

<!-- Navigation dots -->
<nav class="slide-nav" aria-label="Slide navigation">
	{#each Array(TOTAL) as _, i}
		<button
			class="slide-dot"
			class:active={currentSlide === i}
			onclick={() => goTo(i)}
			aria-label={`Slide ${i + 1}`}
		></button>
	{/each}
</nav>

<!-- Prev / next controls + counter -->
<div class="slide-ctrl">
	<button class="ctrl-btn" onclick={prev} disabled={currentSlide === 0} aria-label="Previous slide"
		>‹</button
	>
	<span class="ctrl-count">{currentSlide + 1} / {TOTAL}</span>
	<button
		class="ctrl-btn"
		onclick={next}
		disabled={currentSlide === TOTAL - 1}
		aria-label="Next slide">›</button
	>
</div>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<!-- (click-to-advance; full keyboard navigation is handled on window) -->
<div class="pitch-deck" onclick={onDeckClick}>
	<!-- 0: Cover -->
	<section class="slide slide-cover" data-slide="0" class:active={currentSlide === 0}>
		<div class="slide-inner">
			<div class="slide-label">// Pre-Launch · June 2026</div>
			<img src="/ezra-logo.svg" alt="Ezra" class="pitch-logo" />
			<h1 class="slide-headline">The Multi-Agent<br /><em>Platform</em><br />for Enterprises.</h1>
			<p class="slide-sub">Federation · Memory · Belief · Replay</p>
			<div class="slide-meta-row">
				<span>Live on GKE</span>
				<span>·</span>
				<span>MIT License</span>
				<span>·</span>
				<span>v0.1.1 · PyPI / GHCR / Helm</span>
			</div>
		</div>
		<button class="slide-next" onclick={() => goTo(1)}>Next ↓</button>
	</section>

	<!-- 1: Problem -->
	<section class="slide" data-slide="1" class:active={currentSlide === 1}>
		<div class="slide-inner">
			<div class="slide-label">01 / Problem</div>
			<h2>Enterprise multi-agent AI<br />has a <em>coordination crisis.</em></h2>
			<div class="pitch-problems">
				<div class="pp">
					<div class="pp-n">01</div>
					<h4>No shared memory</h4>
					<p>
						Every agent starts blank. Valuable context from Agent A never reaches Agent B. The fleet
						rediscovers facts on every call.
					</p>
				</div>
				<div class="pp">
					<div class="pp-n">02</div>
					<h4>No audit trail</h4>
					<p>
						When something goes wrong, you cannot answer: what did the agent believe, from what
						source, at what time? Compliance teams are blocked.
					</p>
				</div>
				<div class="pp">
					<div class="pp-n">03</div>
					<h4>No reconciliation</h4>
					<p>
						Two agents commit conflicting facts about inventory, a customer, or a forecast. There is
						no resolution layer. The error propagates silently.
					</p>
				</div>
				<div class="pp">
					<div class="pp-n">04</div>
					<h4>Data access is unsafe</h4>
					<p>
						Agents query raw databases. Prompt injection attacks succeed because there is no policy
						layer between the model and the data.
					</p>
				</div>
			</div>
		</div>
	</section>

	<!-- 2: Solution -->
	<section class="slide slide-teal" data-slide="2" class:active={currentSlide === 2}>
		<div class="slide-inner">
			<div class="slide-label">02 / Solution</div>
			<h2>One runtime.<br /><em>Three layers.</em><br />Every agent.</h2>
			<div class="pitch-solution">
				<div class="ps-layer">
					<div class="ps-num">①</div>
					<div class="ps-name">Federation</div>
					<p>
						Pushdown execution to MongoDB, Snowflake, BigQuery, REST. Typed summaries with
						provenance. The model never touches raw rows.
					</p>
				</div>
				<div class="ps-layer">
					<div class="ps-num">②</div>
					<div class="ps-name">Memory</div>
					<p>
						Hot, warm, cold tiers. Automatic eviction, compaction, salience ranking. Shared across
						the fleet, scoped by permission.
					</p>
				</div>
				<div class="ps-layer">
					<div class="ps-num">③</div>
					<div class="ps-name">Belief & Audit</div>
					<p>
						Every fact attributed to an agent, a source, a timestamp. Queryable belief history.
						Branching replay for compliance and root-cause.
					</p>
				</div>
			</div>
		</div>
	</section>

	<!-- 3: Architecture -->
	<section class="slide" data-slide="3" class:active={currentSlide === 3}>
		<div class="slide-inner">
			<div class="slide-label">03 / Architecture</div>
			<h2>The 8-step router.<br />Per agent. <em>&lt;40ms.</em></h2>
			<div class="pitch-router">
				{#each [['01', 'Parse', 'Intent · entities'], ['02', 'Policy', 'Scope check'], ['03', 'Belief', 'Reconcile'], ['04', 'Hydrate', 'Memory pull'], ['05', 'Fetch', 'Mesh decision'], ['06', 'Assemble', 'Context build'], ['07', 'Call', 'LLM via litellm'], ['08', 'Write', 'Beliefs · trace']] as [n, label, desc]}
					<div class="pr-step">
						<div class="pr-n">{n}</div>
						<div class="pr-l">{label}</div>
						<div class="pr-d">{desc}</div>
					</div>
				{/each}
			</div>
			<p class="pitch-router-note">
				<strong>Most platforms only do steps 1, 7, and 8.</strong>
				Steps 2–6 — policy, belief, memory, federation, assembly — are where Ezra sits.
			</p>
		</div>
	</section>

	<!-- 4: Differentiators -->
	<section class="slide" data-slide="4" class:active={currentSlide === 4}>
		<div class="slide-inner">
			<div class="slide-label">04 / Why Ezra</div>
			<h2>Five things <em>no other</em><br />platform ships.</h2>
			<div class="pitch-diffs">
				{#each [['i.', 'Pushdown execution', 'The database does the math. The model gets typed summaries, never raw rows.'], ['ii.', 'Versioned belief audit', 'Every agent commitment, attributed by agent_id. Exportable at any timestamp.'], ['iii.', 'Branching replay', 'Reconstruct any agent state. Mutate it. Run forward. Diff. The compliance tool.'], ['iv.', 'Time-travel federation', 'Run any query as of any prior timestamp. Explicit provenance throughout.'], ['v.', 'Cross-agent reconciliation', 'Four strategies: last-write, highest-trust, escalate, or a custom resolver.']] as [n, title, desc]}
					<div class="pd-row">
						<div class="pd-n">{n}</div>
						<div>
							<strong>{title}</strong>
							<span>{desc}</span>
						</div>
					</div>
				{/each}
			</div>
		</div>
	</section>

	<!-- 5: Landscape -->
	<section class="slide slide-teal" data-slide="5" class:active={currentSlide === 5}>
		<div class="slide-inner">
			<div class="slide-label">05 / Landscape</div>
			<h2>The layer <em>under</em><br />the frameworks.</h2>
			<div class="pitch-land">
				<div class="pl-row pl-head">
					<span></span>
					<span>They do</span>
					<span>Ezra does</span>
				</div>
				<div class="pl-row">
					<strong>MemGPT · Letta</strong>
					<span>Self-editing memory for a single agent.</span>
					<span
						>Shared, permission-scoped memory and reconciled beliefs for the entire fleet — with a
						versioned audit trail.</span
					>
				</div>
				<div class="pl-row">
					<strong>Langflow</strong>
					<span>Visual builder for agent flows.</span>
					<span>The cloud runtime those flows need underneath — state, federated data, audit.</span>
				</div>
				<div class="pl-row">
					<strong>LangGraph · ADK</strong>
					<span>Orchestration and control flow.</span>
					<span>Plugs in as their state plane — a first-class Google ADK toolset ships today.</span>
				</div>
			</div>
			<p class="pitch-land-note">
				What MemGPT did for one agent's context window,
				<strong>Ezra does for a fleet's shared state.</strong> Complementary to your orchestrator — not
				another one.
			</p>
		</div>
	</section>

	<!-- 6: The Ask -->
	<section class="slide slide-cover slide-ask" data-slide="6" class:active={currentSlide === 6}>
		<div class="slide-inner slide-inner--center">
			<div class="slide-label">06 / The Ask</div>
			<h2>Join the<br /><em>early access</em><br />program.</h2>
			<p class="slide-ask-p">
				We are looking for two or three enterprise AI teams to co-build the production version. In
				exchange: direct influence on the roadmap, priority support, and pre-launch pricing.
			</p>
			<div class="slide-ship">
				<code>pip install ezra-client</code>
				<code>docker pull ghcr.io/xavio2495/ezra-api:0.1.1</code>
				<code>helm install ezra oci://ghcr.io/xavio2495/charts/ezra</code>
			</div>
			<div class="slide-ask-actions">
				<a class="cta-btn" href="mailto:2495.immanuel@gmail.com"
					>Book a Briefing <span class="arrow">→</span></a
				>
				<a class="cta-btn ghost" href="/docs">Read the Docs <span class="arrow">→</span></a>
				<a class="cta-btn ghost" href="/quickstart">Quick Start <span class="arrow">→</span></a>
			</div>
			<div class="slide-ask-meta">
				<span>2495.immanuel@gmail.com</span>
				<span>·</span>
				<span>github.com/xavio2495/Ezra</span>
				<span>·</span>
				<span>v0.1.1 · MIT</span>
			</div>
		</div>
	</section>
</div>

<style>
	/* ── Deck (presentation mode: one slide at a time, no scroll) ── */
	.pitch-deck {
		position: relative;
		height: calc(100vh - var(--nav-h));
		overflow: hidden;
	}

	.slide {
		position: absolute;
		inset: 0;
		display: flex;
		flex-direction: column;
		justify-content: center;
		align-items: center;
		overflow-y: auto;
		opacity: 0;
		visibility: hidden;
		transform: translateX(28px);
		pointer-events: none;
		transition:
			opacity 0.35s ease,
			transform 0.35s ease,
			visibility 0s linear 0.35s;
	}
	.slide.active {
		opacity: 1;
		visibility: visible;
		transform: none;
		pointer-events: auto;
		transition:
			opacity 0.35s ease,
			transform 0.35s ease,
			visibility 0s;
	}
	.slide-cover {
		background: radial-gradient(ellipse at 50% 40%, rgba(45, 199, 184, 0.07), transparent 60%);
	}
	.slide-teal {
		background: rgba(45, 199, 184, 0.02);
	}
	.slide-ask {
		background: radial-gradient(ellipse at 50% 50%, rgba(45, 199, 184, 0.1), transparent 65%);
	}

	.slide-inner {
		width: 100%;
		max-width: 1100px;
		padding: 60px var(--gutter);
	}
	.slide-inner--center {
		text-align: center;
	}

	.slide-label {
		font-family: var(--f-mono);
		font-size: 10px;
		letter-spacing: 0.22em;
		text-transform: uppercase;
		color: var(--accent);
		margin-bottom: 28px;
	}

	/* ── Headings ── */
	h1,
	h2 {
		margin: 0 0 24px;
		font-family: var(--f-sans);
		font-weight: 500;
		line-height: 0.95;
		text-transform: uppercase;
		letter-spacing: -0.025em;
		color: var(--fg);
	}
	h1 {
		font-size: clamp(44px, 6vw, 96px);
	}
	h2 {
		font-size: clamp(32px, 4.5vw, 72px);
	}
	h2 em,
	h1 em {
		font-family: var(--f-display);
		font-style: italic;
		font-weight: 400;
		text-transform: none;
		color: var(--accent);
	}

	.slide-headline {
		margin-bottom: 24px;
	}
	.slide-sub {
		font-family: var(--f-mono);
		font-size: 13px;
		letter-spacing: 0.18em;
		text-transform: uppercase;
		color: var(--fg-3);
		margin: 0 0 40px;
	}
	.slide-meta-row {
		font-family: var(--f-mono);
		font-size: 10px;
		letter-spacing: 0.16em;
		text-transform: uppercase;
		color: var(--fg-4);
		display: flex;
		gap: 12px;
	}

	.pitch-logo {
		height: 28px;
		display: block;
		margin-bottom: 48px;
	}

	.slide-next {
		position: absolute;
		bottom: 32px;
		left: 50%;
		transform: translateX(-50%);
		background: none;
		border: 1px solid var(--line);
		color: var(--fg-4);
		font-family: var(--f-mono);
		font-size: 10px;
		letter-spacing: 0.18em;
		text-transform: uppercase;
		padding: 8px 20px;
		cursor: pointer;
		transition: all 0.2s;
	}
	.slide-next:hover {
		border-color: var(--accent);
		color: var(--accent);
	}

	/* ── Nav dots ── */
	.slide-nav {
		position: fixed;
		right: 32px;
		top: 50%;
		transform: translateY(-50%);
		z-index: 8;
		display: flex;
		flex-direction: column;
		gap: 10px;
	}
	.slide-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		border: 1px solid var(--fg-4);
		background: transparent;
		cursor: pointer;
		transition: all 0.2s;
		padding: 0;
	}
	.slide-dot.active {
		background: var(--accent);
		border-color: var(--accent);
	}
	.slide-dot:hover {
		border-color: var(--accent);
	}

	/* ── Prev/next controls ── */
	.slide-ctrl {
		position: fixed;
		right: 28px;
		bottom: 24px;
		z-index: 8;
		display: flex;
		align-items: center;
		gap: 10px;
	}
	.ctrl-btn {
		width: 34px;
		height: 34px;
		display: grid;
		place-items: center;
		background: rgba(2, 6, 23, 0.5);
		border: 1px solid var(--line);
		color: var(--fg-3);
		font-size: 18px;
		line-height: 1;
		cursor: pointer;
		transition: all 0.2s;
		padding: 0;
	}
	.ctrl-btn:hover:not(:disabled) {
		border-color: var(--accent);
		color: var(--accent);
	}
	.ctrl-btn:disabled {
		opacity: 0.3;
		cursor: default;
	}
	.ctrl-count {
		font-family: var(--f-mono);
		font-size: 10px;
		letter-spacing: 0.16em;
		color: var(--fg-4);
		min-width: 38px;
		text-align: center;
	}

	/* ── Problem cards ── */
	.pitch-problems {
		display: grid;
		grid-template-columns: repeat(2, 1fr);
		gap: 0;
		border: 1px solid var(--line);
		margin-top: 8px;
	}
	.pp {
		padding: 32px;
		border-right: 1px solid var(--line);
		border-bottom: 1px solid var(--line);
	}
	.pp:nth-child(even) {
		border-right: 0;
	}
	.pp:nth-child(n + 3) {
		border-bottom: 0;
	}
	.pp-n {
		font-family: var(--f-mono);
		font-size: 10px;
		letter-spacing: 0.18em;
		color: var(--fg-4);
		margin-bottom: 10px;
	}
	.pp h4 {
		margin: 0 0 8px;
		font-family: var(--f-sans);
		font-weight: 500;
		font-size: 17px;
		text-transform: uppercase;
		letter-spacing: -0.01em;
		color: var(--fg);
	}
	.pp p {
		margin: 0;
		font-size: 12.5px;
		color: var(--fg-3);
		line-height: 1.65;
		max-width: 42ch;
	}

	/* ── Solution layers ── */
	.pitch-solution {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 0;
		border: 1px solid var(--line);
		margin-top: 8px;
	}
	.ps-layer {
		padding: 36px 28px;
		border-left: 1px solid var(--line);
	}
	.ps-layer:first-child {
		border-left: 0;
	}
	.ps-num {
		font-family: var(--f-display);
		font-style: italic;
		font-size: 40px;
		color: var(--accent);
		line-height: 1;
		margin-bottom: 12px;
	}
	.ps-name {
		font-family: var(--f-sans);
		font-weight: 500;
		font-size: 18px;
		text-transform: uppercase;
		letter-spacing: 0.01em;
		margin-bottom: 10px;
	}
	.ps-layer p {
		margin: 0;
		font-size: 12.5px;
		color: var(--fg-3);
		line-height: 1.65;
	}

	/* ── Router ── */
	.pitch-router {
		display: grid;
		grid-template-columns: repeat(8, 1fr);
		border: 1px solid var(--line);
		margin-top: 8px;
	}
	.pr-step {
		padding: 20px 10px;
		text-align: center;
		border-left: 1px solid var(--line);
		transition: background 0.2s;
	}
	.pr-step:first-child {
		border-left: 0;
	}
	.pr-step:hover {
		background: rgba(45, 199, 184, 0.05);
	}
	.pr-n {
		font-family: var(--f-display);
		font-style: italic;
		font-size: 28px;
		color: var(--fg-4);
		line-height: 1;
		margin-bottom: 6px;
	}
	.pr-l {
		font-family: var(--f-sans);
		font-weight: 500;
		font-size: 11px;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--fg);
	}
	.pr-d {
		font-family: var(--f-mono);
		font-size: 9px;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--fg-4);
		margin-top: 4px;
		line-height: 1.4;
	}
	.pitch-router-note {
		margin-top: 16px;
		font-family: var(--f-mono);
		font-size: 12px;
		color: var(--fg-3);
		line-height: 1.65;
		max-width: 70ch;
	}
	.pitch-router-note strong {
		color: var(--fg);
	}

	/* ── Diffs ── */
	.pitch-diffs {
		display: flex;
		flex-direction: column;
		border: 1px solid var(--line);
		margin-top: 8px;
	}
	.pd-row {
		display: grid;
		grid-template-columns: 56px 1fr;
		gap: 20px;
		padding: 20px 28px;
		border-bottom: 1px solid var(--line);
		align-items: baseline;
		transition: background 0.2s;
	}
	.pd-row:last-child {
		border-bottom: 0;
	}
	.pd-row:hover {
		background: rgba(45, 199, 184, 0.025);
	}
	.pd-n {
		font-family: var(--f-display);
		font-style: italic;
		font-size: 28px;
		color: var(--accent);
		line-height: 1;
	}
	.pd-row strong {
		font-family: var(--f-sans);
		font-weight: 500;
		font-size: 15px;
		text-transform: uppercase;
		color: var(--fg);
		display: block;
		margin-bottom: 3px;
		letter-spacing: 0.01em;
	}
	.pd-row span {
		font-family: var(--f-mono);
		font-size: 12px;
		color: var(--fg-3);
		line-height: 1.6;
	}

	/* ── Landscape ── */
	.pitch-land {
		display: flex;
		flex-direction: column;
		border: 1px solid var(--line);
		margin-top: 8px;
	}
	.pl-row {
		display: grid;
		grid-template-columns: 180px 1fr 1.3fr;
		gap: 24px;
		padding: 20px 28px;
		border-bottom: 1px solid var(--line);
		align-items: baseline;
		transition: background 0.2s;
	}
	.pl-row:last-child {
		border-bottom: 0;
	}
	.pl-row:hover {
		background: rgba(45, 199, 184, 0.025);
	}
	.pl-head {
		padding-top: 14px;
		padding-bottom: 14px;
	}
	.pl-head span {
		font-family: var(--f-mono);
		font-size: 10px;
		letter-spacing: 0.18em;
		text-transform: uppercase;
		color: var(--fg-4);
	}
	.pl-row strong {
		font-family: var(--f-sans);
		font-weight: 500;
		font-size: 15px;
		text-transform: uppercase;
		color: var(--fg);
		letter-spacing: 0.01em;
	}
	.pl-row span {
		font-family: var(--f-mono);
		font-size: 12px;
		color: var(--fg-3);
		line-height: 1.6;
	}
	.pl-row span:last-child {
		color: var(--fg-2);
	}
	.pitch-land-note {
		margin-top: 16px;
		font-family: var(--f-mono);
		font-size: 12px;
		color: var(--fg-3);
		line-height: 1.65;
		max-width: 70ch;
	}
	.pitch-land-note strong {
		color: var(--accent);
	}

	/* ── Ask ── */
	.slide-ship {
		display: flex;
		flex-direction: column;
		gap: 6px;
		align-items: center;
		margin: 0 auto 32px;
	}
	.slide-ship code {
		font-family: var(--f-mono);
		font-size: 12px;
		color: var(--accent);
		background: rgba(45, 199, 184, 0.06);
		border: 1px solid var(--line);
		padding: 7px 16px;
	}
	.slide-ask-p {
		font-size: 15px;
		line-height: 1.7;
		color: var(--fg-2);
		max-width: 52ch;
		margin: 0 auto 36px;
	}
	.slide-ask-actions {
		display: flex;
		gap: 14px;
		justify-content: center;
		flex-wrap: wrap;
		margin-bottom: 40px;
	}
	.slide-ask-meta {
		font-family: var(--f-mono);
		font-size: 10.5px;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: var(--fg-4);
		display: flex;
		gap: 12px;
		justify-content: center;
		flex-wrap: wrap;
	}

	/* ── CTA ── */
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
		.pitch-problems {
			grid-template-columns: 1fr;
		}
		.pp {
			border-right: 0;
			border-bottom: 1px solid var(--line);
		}
		.pp:last-child {
			border-bottom: 0;
		}
		.pitch-solution {
			grid-template-columns: 1fr;
		}
		.ps-layer {
			border-left: 0;
			border-bottom: 1px solid var(--line);
		}
		.ps-layer:last-child {
			border-bottom: 0;
		}
		.pitch-router {
			grid-template-columns: repeat(4, 1fr);
		}
		.pl-row {
			grid-template-columns: 1fr;
			gap: 8px;
		}
		.pl-head {
			display: none;
		}
		.slide-nav {
			display: none;
		}
	}
	@media (max-width: 600px) {
		.pitch-router {
			grid-template-columns: repeat(2, 1fr);
		}
		.pr-step {
			border-bottom: 1px solid var(--line);
		}
	}
</style>
