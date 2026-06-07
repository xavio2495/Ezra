<script lang="ts">
	import { onMount } from 'svelte';
	import SessionGraphFlow from '$lib/components/SessionGraphFlow.svelte';

	function copyText(text: string, btn: HTMLButtonElement) {
		navigator.clipboard.writeText(text).then(() => {
			const orig = btn.textContent ?? '';
			btn.textContent = 'Copied';
			btn.style.borderColor = 'var(--accent)';
			btn.style.color = 'var(--accent)';
			setTimeout(() => {
				btn.textContent = orig;
				btn.style.borderColor = '';
				btn.style.color = '';
			}, 1500);
		});
	}

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
	<title>Ezra — Multi-agent platform for enterprises</title>
</svelte:head>

<main id="top">
	<!-- ============================================================
	     HERO — centered, Hermes-style v2
	     ============================================================ -->
	<section class="hero-v2 reveal">
		<h1 class="hero-title">
			<span class="ht-line">
				<em>Runtime Substrate</em>
			</span>
			<span class="ht-line ht-conn">
				<span class="ht-for">for</span>
			</span>
			<span class="ht-line">
				<span class="ht-roman">Multi-Agent</span>
				<span class="stroke">Fleets.</span>
			</span>
		</h1>

		<p class="hero-desc">
			Replayable federated context for multi-agent runtime, managing what each agent in the fleet
			sees, believes, and remembers — with complete provenance.
		</p>

		<div class="hero-install">
			<code><span class="kw">curl</span> -fsSL https://ezra128.vercel.app/install.sh | bash</code>
			<button
				class="hi-copy"
				onclick={(e) =>
					copyText(
						'curl -fsSL https://ezra128.vercel.app/install.sh | bash',
						e.currentTarget as HTMLButtonElement
					)}>Copy</button
			>
		</div>

		<div class="hero-actions-v2">
			<a class="cta-btn" href="/quickstart">Quick Start <span class="arrow">→</span></a>
			<a class="cta-btn ghost" href="/pitch">Read the Pitch <span class="arrow">→</span></a>
		</div>

		<a href="#stats" class="hero-scroll-hint">See it in action ↓</a>
	</section>

	<!-- ============================================================
	     STATS STRIP
	     ============================================================ -->
	<section class="wrap reveal-stagger" id="stats">
		<div class="stats-v2">
			<div class="stat-v2">
				<div class="n">&lt;40<sup>MS</sup></div>
				<div class="l">Per-Agent Overhead</div>
			</div>
			<div class="stat-v2">
				<div class="n">N<sup>AGENTS</sup></div>
				<div class="l">Dynamic Fleet Scaling</div>
			</div>
			<div class="stat-v2">
				<div class="n">3<sup>TIER</sup></div>
				<div class="l">Memory Topology</div>
			</div>
			<div class="stat-v2">
				<div class="n">∞<sup>REPLAY</sup></div>
				<div class="l">Branching Belief History</div>
			</div>
		</div>
	</section>

	<!-- ============================================================
	     QUICKSTART PREVIEW — terminal-style numbered steps
	     ============================================================ -->
	<section class="section wrap" id="quickstart">
		<div class="sh-center reveal">
			<div class="section-label">Quickstart</div>
			<h2>Three steps.<br /><em>Running</em> in minutes.</h2>
		</div>

		<div class="terminal-block reveal">
			<div class="terminal-bar">
				<div class="td"></div>
				<div class="td"></div>
				<div class="td"></div>
				<span class="tl">ezra / quickstart</span>
			</div>

			<div class="terminal-step">
				<div class="ts-n">1</div>
				<div>
					<div class="ts-label">Install</div>
					<div class="ts-code">
						<span class="kw">curl</span> -fsSL https://ezra128.vercel.app/install.sh | bash
					</div>
				</div>
				<button
					class="cp-btn"
					onclick={(e) =>
						copyText(
							'curl -fsSL https://ezra128.vercel.app/install.sh | bash',
							e.currentTarget as HTMLButtonElement
						)}>Copy</button
				>
			</div>

			<div class="terminal-step">
				<div class="ts-n">2</div>
				<div>
					<div class="ts-label">Spawn an agent</div>
					<div class="ts-code">
						<span class="kw">from</span> ezra_core.runtime <span class="kw">import</span> Ezra ezra
						= Ezra.from_env() graph = <span class="kw">await</span>
						ezra.create_session_graph(session_graph_id=<span class="str">"race-weekend"</span>) svc
						= <span class="kw">await</span> ezra.spawn_agent(graph, agent_id=<span class="str"
							>"strategist"</span
						>, permission_scope=[<span class="str">"tyres"</span>])
					</div>
				</div>
				<button
					class="cp-btn"
					onclick={(e) =>
						copyText(
							`from ezra_core.runtime import Ezra\nezra = Ezra.from_env()\ngraph = await ezra.create_session_graph(session_graph_id="race-weekend")\nsvc = await ezra.spawn_agent(graph, agent_id="strategist", permission_scope=["tyres"])`,
							e.currentTarget as HTMLButtonElement
						)}>Copy</button
				>
			</div>

			<div class="terminal-step">
				<div class="ts-n">3</div>
				<div>
					<div class="ts-label">Run a turn</div>
					<div class="ts-code">
						result = <span class="kw">await</span> svc.complete(<span class="str"
							>"What tyre for the final stint?"</span
						>) <span class="kw">print</span>(result.response)
					</div>
				</div>
				<button
					class="cp-btn"
					onclick={(e) =>
						copyText(
							`result = await svc.complete("What tyre for the final stint?")\nprint(result.response)`,
							e.currentTarget as HTMLButtonElement
						)}>Copy</button
				>
			</div>
		</div>

		<div style="text-align: center; margin-top: 40px;">
			<a class="cta-btn teal" href="/quickstart"
				>Full Setup Guide — Google Cloud ADK <span class="arrow">→</span></a
			>
		</div>
	</section>

	<!-- ============================================================
	     FEATURES — 2×3 grid
	     ============================================================ -->
	<section class="section wrap" id="features">
		<div class="sh-center reveal">
			<div class="section-label">Capabilities</div>
			<h2>Six things <em>one</em><br />platform handles.</h2>
			<p class="lede">
				Most tools solve federation or memory — for a single agent. Ezra does both, for any number
				of agents, as one runtime.
			</p>
		</div>

		<div class="fg-grid reveal-stagger">
			<div class="fg-card">
				<div class="fc-tag">// Federation</div>
				<h3>Pushdown <em>Data</em> Access</h3>
				<p>
					Connect to MongoDB, Snowflake, BigQuery, REST. The database does the math — the model gets
					typed summaries with provenance, never raw dumps.
				</p>
			</div>
			<div class="fg-card">
				<div class="fc-tag">// Memory</div>
				<h3>Three-Tier <em>Recall</em></h3>
				<p>
					Hot, warm, cold. Automatic eviction, compaction, and salience-ranked hydration. Each agent
					gets the most relevant slice of what the fleet has ever known.
				</p>
			</div>
			<div class="fg-card">
				<div class="fc-tag">// Beliefs</div>
				<h3><em>Four-Strategy</em> Reconciliation</h3>
				<p>
					When agents disagree, four strategies resolve it before the model sees it: last-write,
					highest-trust, manual escalation, or your own custom resolver.
				</p>
			</div>
			<div class="fg-card">
				<div class="fc-tag">// Replay</div>
				<h3>Branching <em>Replay</em></h3>
				<p>
					Reconstruct what any agent knew at any prior moment. Mutate state. Run forward. Diff
					against reality. The compliance and counterfactual artifact.
				</p>
			</div>
			<div class="fg-card">
				<div class="fc-tag">// Security</div>
				<h3>Per-Agent <em>Scopes</em></h3>
				<p>
					Every agent sees only what its permission scope allows. Enforced at the platform layer on
					every memory query and data fetch — not in the prompt.
				</p>
			</div>
			<div class="fg-card">
				<div class="fc-tag">// Scale</div>
				<h3>Flat <em>Latency</em> at N</h3>
				<p>
					Adding agents doesn't slow per-agent decisions. O(1) hot tier, scope-filtered shared
					tiers, independent mesh fetches. Constant latency, linear throughput.
				</p>
			</div>
		</div>
	</section>

	<!-- ============================================================
	     ARCHITECTURE — 8-step router
	     ============================================================ -->
	<section class="section wrap" id="architecture">
		<div class="sh-center reveal">
			<div class="section-label">Architecture</div>
			<h2>The 8-step <em>router.</em><br />Per agent. &lt;40ms.</h2>
			<p class="lede">
				Every agent call runs through eight steps in the same order. Each agent gets its own
				pipeline instance. The output of every step is observable, replayable, and pinned to the
				belief store.
			</p>
		</div>

		<div class="router-v2 reveal">
			<div class="router-v2-header">
				<span>// Pipeline &nbsp; <b>EZRA.RUNTIME / ROUTER</b></span>
				<span>P50 Target · &lt;40ms</span>
			</div>
			<div class="router-v2-steps">
				<div class="rv2-step">
					<div class="rn">01</div>
					<div class="rl">Parse</div>
					<div class="rd">Intent · entities</div>
				</div>
				<div class="rv2-step">
					<div class="rn">02</div>
					<div class="rl">Policy</div>
					<div class="rd">Scope check</div>
				</div>
				<div class="rv2-step">
					<div class="rn">03</div>
					<div class="rl">Belief</div>
					<div class="rd">Reconcile</div>
				</div>
				<div class="rv2-step">
					<div class="rn">04</div>
					<div class="rl">Hydrate</div>
					<div class="rd">Memory pull</div>
				</div>
				<div class="rv2-step">
					<div class="rn">05</div>
					<div class="rl">Fetch</div>
					<div class="rd">Mesh decision</div>
				</div>
				<div class="rv2-step">
					<div class="rn">06</div>
					<div class="rl">Assemble</div>
					<div class="rd">Context build</div>
				</div>
				<div class="rv2-step">
					<div class="rn">07</div>
					<div class="rl">Call</div>
					<div class="rd">LLM via litellm</div>
				</div>
				<div class="rv2-step">
					<div class="rn">08</div>
					<div class="rl">Write</div>
					<div class="rd">Beliefs · trace</div>
				</div>
			</div>
			<div class="router-note">
				<strong>Most agent platforms only do steps 1, 7, and 8.</strong>
				Steps 2–6 are where Ezra differs —
				<em
					>policy enforcement, belief reconciliation, scope-filtered memory, pushdown federation,
					and salience-ranked assembly</em
				> all happen before the model is called.
			</div>
		</div>

		<!-- Interactive session graph -->
		<div class="sh-center reveal" style="margin-top: 100px;">
			<div class="section-label">Session graph</div>
			<h2>A fleet that <em>spawns</em><br />and shares.</h2>
			<p class="lede">
				One session graph binds N agents — spawned and terminated as the operation needs. Each has
				its own scoped view, but they share one belief store and one tiered memory. Drag, pan, and
				zoom the graph below.
			</p>
		</div>
		<div class="reveal" style="margin-top: 40px;">
			<SessionGraphFlow />
		</div>

		<!-- Memory tiers -->
		<div class="sh-center reveal" style="margin-top: 100px;">
			<h2>Hot, warm,<br />and <em>cold.</em></h2>
			<p class="lede">
				Memory is not flat. The runtime evicts, compacts, and hydrates across three tiers — so each
				agent always sees the most relevant slice, filtered by its permission scope.
			</p>
		</div>

		<div class="mem-bands reveal-stagger">
			<div class="mem-band hot">
				<div class="mb-left">
					<div class="mb-sw"></div>
					<div>
						<div class="mb-name">Hot</div>
						<span class="mb-store">Redis · per-agent hash</span>
					</div>
				</div>
				<div class="mb-desc">
					Active turn, pinned beliefs, and current mesh result — isolated per agent in the session
					graph.
				</div>
				<div class="mb-lat">~0ms</div>
			</div>
			<div class="mem-band warm">
				<div class="mb-left">
					<div class="mb-sw"></div>
					<div>
						<div class="mb-name">Warm</div>
						<span class="mb-store">Qdrant · vector filtered</span>
					</div>
				</div>
				<div class="mb-desc">
					Compressed prior turns, topic summaries, recent tool results. Searchable by salience,
					evicted on decay.
				</div>
				<div class="mb-lat">5–15ms</div>
			</div>
			<div class="mem-band cold">
				<div class="mb-left">
					<div class="mb-sw"></div>
					<div>
						<div class="mb-name">Cold</div>
						<span class="mb-store">MongoDB Atlas · durable</span>
					</div>
				</div>
				<div class="mb-desc">
					Episodic, semantic core, archival, procedural rules, and the full versioned belief
					history. Never evicted.
				</div>
				<div class="mb-lat">20–50ms</div>
			</div>
		</div>
	</section>

	<!-- ============================================================
	     FIVE DIFFERENTIATORS
	     ============================================================ -->
	<section class="section wrap" id="differentiators">
		<div class="sh-center reveal">
			<div class="section-label">Whitespace</div>
			<h2>Five things <em>no other</em><br />platform ships.</h2>
			<p class="lede">
				Persistent memory is table-stakes. The wedge is what sits one layer above it: provenance,
				audit, per-agent replay, time-travel, and cross-agent reconciliation.
			</p>
		</div>

		<div class="diff-v2 reveal-stagger">
			<div class="diff-row">
				<div class="dn">i.</div>
				<div>
					<h4 class="dt">Pushdown execution</h4>
					<span class="dd"
						>The database does the math. Typed queries to MongoDB, Snowflake, BigQuery — the model
						never touches raw rows.</span
					>
				</div>
			</div>
			<div class="diff-row">
				<div class="dn">ii.</div>
				<div>
					<h4 class="dt">Versioned belief audit</h4>
					<span class="dd"
						>Every commitment any agent made, every fact it relied on, attributed by agent_id.
						Queryable and exportable at any timestamp.</span
					>
				</div>
			</div>
			<div class="diff-row">
				<div class="dn">iii.</div>
				<div>
					<h4 class="dt">Branching replay</h4>
					<span class="dd"
						>Reconstruct any agent's view. Mutate state. Run forward with a new model or policy.
						Diff branches. The compliance and eval surface.</span
					>
				</div>
			</div>
			<div class="diff-row">
				<div class="dn">iv.</div>
				<div>
					<h4 class="dt">Time-travel federated query</h4>
					<span class="dd"
						>Run any query as of any prior timestamp. Source-native where it exists. Best-effort
						with explicit provenance where it does not.</span
					>
				</div>
			</div>
			<div class="diff-row">
				<div class="dn">v.</div>
				<div>
					<h4 class="dt">Cross-agent reconciliation</h4>
					<span class="dd"
						>When agents commit conflicting beliefs, four strategies resolve it: last-write,
						highest-trust, manual escalation, or a custom application-defined resolver.</span
					>
				</div>
			</div>
		</div>
	</section>

	<!-- ============================================================
	     INTEGRATION PATHS
	     ============================================================ -->
	<section class="section wrap" id="integrate">
		<div class="sh-center reveal">
			<div class="section-label">Integration</div>
			<h2>Three ways in.<br /><em>Pick</em> one.</h2>
			<p class="lede">
				Ezra is framework-agnostic. ADK is the primary path. The Python SDK covers LangGraph and
				LangChain. REST covers everything else.
			</p>
		</div>

		<div class="int-grid reveal-stagger">
			<div class="int-card">
				<div class="it-tag">// Path 01</div>
				<div class="it-name">ADK <em>Service</em></div>
				<p class="it-desc">
					Direct Python integration for agents built with Google ADK. No MCP indirection. Best for
					production fleets on Google Cloud.
				</p>
				<div class="code-block">
					<span class="c-key">from</span> ezra.adk_service <span class="c-key">import</span>
					EzraService svc = EzraService( session_graph_id=<span class="c-str">"race-weekend"</span>
					) ctx = svc.<span class="c-fn">recall</span>(agent_id=<span class="c-str">"tyre_eng"</span
					>) svc.<span class="c-fn">belief_check</span>(claim=<span class="c-str"
						>"soft optimal"</span
					>)
				</div>
			</div>

			<div class="int-card">
				<div class="it-tag">// Path 02</div>
				<div class="it-name">Python <em>SDK</em></div>
				<p class="it-desc">
					Six methods for LangGraph, LangChain, or any custom framework. Adopt belief audit alone,
					or memory, or replay.
				</p>
				<div class="code-block">
					<span class="c-key">from</span> ezra_core <span class="c-key">import</span> Ezra ezra =
					Ezra.from_env( session_graph_id=<span class="c-str">"incident-triage"</span>
					)
					<span class="c-key">await</span> ezra.complete( agent_id=<span class="c-str"
						>"triage"</span
					>, messages=[...], )
				</div>
			</div>

			<div class="int-card">
				<div class="it-tag">// Path 03</div>
				<div class="it-name">REST <em>API</em></div>
				<p class="it-desc">
					Thirteen endpoints. Bearer or OIDC auth. Use from any language or external system.
				</p>
				<div class="code-block">
					<span class="c-com"># Thirteen endpoints</span>
					POST /ezra/belief/<span class="c-key">check</span>
					POST /ezra/belief/<span class="c-key">snapshot</span>
					POST /ezra/mesh/<span class="c-key">query</span>
					POST /ezra/<span class="c-key">commit</span>
					POST /ezra/<span class="c-key">recall</span>
					POST /ezra/<span class="c-key">rewind</span>
					POST /ezra/<span class="c-key">revert</span>
					POST /ezra/<span class="c-key">replay</span>
					POST /ezra/<span class="c-key">branch</span>
					POST /ezra/branch/<span class="c-key">diff</span>
					GET /ezra/<span class="c-key">health</span>
				</div>
			</div>
		</div>

		<div style="text-align: center; margin-top: 40px;">
			<a class="cta-btn ghost" href="/docs">Full API Reference <span class="arrow">→</span></a>
		</div>
	</section>

	<!-- ============================================================
	     BUYERS
	     ============================================================ -->
	<section class="section wrap" id="buyers">
		<div class="sh-center reveal">
			<div class="section-label">Audience</div>
			<h2>Four rooms <em>it</em><br />belongs in.</h2>
		</div>

		<div class="buyers-v2 reveal-stagger">
			<div class="bv2">
				<div class="bv2-who">// AI Platform Engineer</div>
				<div class="bv2-q">"One platform. One audit trail. Any number of agents."</div>
				<p>
					Wins back weeks of glue code per agent. Federation, memory, and belief tracking for the
					entire fleet.
				</p>
			</div>
			<div class="bv2">
				<div class="bv2-who">// Enterprise Security</div>
				<div class="bv2-q">
					"Agents inherit user identity. The wrong agent never sees wrong data."
				</div>
				<p>
					Per-agent permission scopes enforced on every query and fetch. The security chokepoint for
					the fleet.
				</p>
			</div>
			<div class="bv2">
				<div class="bv2-who">// Compliance Officer</div>
				<div class="bv2-q">
					"Every fact, every source, every permission — queryable and replayable."
				</div>
				<p>
					The belief history is the SOC2, GDPR, and financial-audit artifact. Branching replay is
					the root-cause tool.
				</p>
			</div>
			<div class="bv2">
				<div class="bv2-who">// CTO</div>
				<div class="bv2-q">
					"Smallest context per call. Lower tokens, lower latency, at 100+ agents."
				</div>
				<p>
					Performance stays flat as the fleet scales. Constant per-agent latency, linear total
					throughput. Provable.
				</p>
			</div>
		</div>
	</section>

	<!-- ============================================================
	     CTA
	     ============================================================ -->
	<section class="section wrap" id="cta">
		<blockquote class="bigquote-v2 reveal">
			<span class="quiet">Ezra is the</span><br />
			<em>multi-agent platform</em><br />
			<span class="quiet">for</span> enterprises.
		</blockquote>

		<div class="final-cta reveal" style="justify-content: center; margin-top: 48px;">
			<a class="cta-btn" href="/docs">Explore Docs <span class="arrow">→</span></a>
			<a class="cta-btn ghost" href="/pitch">Read the Pitch <span class="arrow">→</span></a>
			<a class="cta-btn ghost" href="mailto:2495.immanuel@gmail.com">Book a Briefing</a>
		</div>

		<div class="final-meta reveal-stagger" style="margin-top: 80px;">
			<div class="fm">
				<h5>// Repo</h5>
				<p>
					<a href="https://github.com/xavio2495/ezra" target="_blank" rel="noopener"
						>github.com/xavio2495/ezra</a
					>
				</p>
			</div>
			<div class="fm">
				<h5>// Docs</h5>
				<p><a href="/docs">ezra128.vercel.app/docs</a></p>
			</div>
			<div class="fm">
				<h5>// Status</h5>
				<p><span class="status-dot"></span>All systems nominal</p>
			</div>
			<div class="fm">
				<h5>// Contact</h5>
				<p><a href="mailto:2495.immanuel@gmail.com">2495.immanuel@gmail.com</a></p>
			</div>
		</div>
	</section>
</main>
