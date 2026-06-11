<script lang="ts">
	import { SvelteFlow, Background, Controls, type Node, type Edge } from '@xyflow/svelte';
	import '@xyflow/svelte/dist/style.css';
	import { demo } from '$lib/demo/state.svelte';
	import type { AgentInfo, AuditEvent } from '$lib/demo/types';

	// The marquee: a real-time context/commitment graph (plan §3 Tab 1). Every
	// node + edge is DERIVED from the persisted audit feed — nothing is invented.
	// Left → right pipeline: external sources → agents → Ezra router (+ memory
	// tiers) → belief store. Edges fire per audit event.
	let nodes = $state.raw<Node[]>([]);
	let edges = $state.raw<Edge[]>([]);

	$effect(() => {
		const built = build(demo.agents, demo.auditEvents);
		nodes = built.nodes;
		edges = built.edges;
	});

	const ROUTER = 'background:#0f766e;color:#d6f5ef;border:1px solid #2dd4bf;border-radius:8px;font-size:11px;font-weight:600;width:120px';
	const STORE = 'background:#1e293b;color:#e2e8f0;border:1px solid #64748b;border-radius:8px;font-size:11px;font-weight:600;width:120px';
	const TIER = 'background:#0b1220;color:#94a3b8;border:1px solid #334155;border-radius:6px;font-size:10px;width:120px';
	const SOURCE = 'background:#1e293b;color:#cbd5e1;border:1px dashed #64748b;border-radius:6px;font-size:10px;width:120px';
	const AGENT_ON = 'background:#134e4a;color:#ccfbf1;border:1px solid #2dd4bf;border-radius:8px;font-size:11px;font-weight:600;width:132px';
	const AGENT_OFF = 'background:#0b1220;color:#64748b;border:1px solid #1f2937;border-radius:8px;font-size:11px;font-weight:600;width:132px';
	const AGENT_DENIED = 'background:#3f1d1d;color:#fecaca;border:1px solid #f87171;border-radius:8px;font-size:11px;font-weight:600;width:132px';

	const E_BASE = 'stroke:#475569;stroke-width:1;opacity:.3';
	const E_COMMIT = 'stroke:#34d399;stroke-width:2';
	const E_FETCH = 'stroke:#38bdf8;stroke-width:2';
	const E_CONTRA = 'stroke:#f87171;stroke-width:2.5';
	const E_SUPER = 'stroke:#f87171;stroke-width:1.5;stroke-dasharray:4 3;opacity:.7';
	const E_DENIED = 'stroke:#f87171;stroke-width:2;stroke-dasharray:5 3';

	const TIERS: [string, string][] = [
		['hot', 'Hot · Redis'],
		['warm', 'Warm · Qdrant'],
		['cold', 'Cold · Atlas']
	];

	function shortSource(s: string): string {
		// "snowflake:results" / "bigquery:..." / "atlas-streams:proc" → first segment
		return s.split(':')[0] || s;
	}

	function build(agents: AgentInfo[], events: AuditEvent[]): { nodes: Node[]; edges: Edge[] } {
		const n = Math.max(agents.length, 1);
		const routerY = 40 + (n * 78) / 2 - 40;
		const ns: Node[] = [
			{ id: 'router', position: { x: 500, y: routerY }, data: { label: 'Ezra Router' }, style: ROUTER },
			{ id: 'belief-store', position: { x: 760, y: routerY }, data: { label: 'Belief Store' }, style: STORE }
		];
		TIERS.forEach(([id, label], k) =>
			ns.push({ id: `tier:${id}`, position: { x: 500, y: routerY + 96 + k * 52 }, data: { label }, style: TIER })
		);

		const denied = new Set(
			events.filter((e) => e.event_type === 'fetch_denied').map((e) => e.agent_id)
		);
		agents.forEach((a, i) =>
			ns.push({
				id: `agent:${a.id}`,
				position: { x: 240, y: 40 + i * 78 },
				data: { label: a.role },
				style: denied.has(a.id) ? AGENT_DENIED : a.spawned ? AGENT_ON : AGENT_OFF
			})
		);

		const sources = [
			...new Set(
				events
					.filter((e) => e.event_type === 'federated_fetch')
					.map((e) => String(e.detail.source ?? ''))
			)
		].filter(Boolean);
		sources.forEach((s, i) =>
			ns.push({ id: `src:${s}`, position: { x: 0, y: 40 + i * 64 }, data: { label: shortSource(s) }, style: SOURCE })
		);

		const es: Edge[] = [];
		const seen = new Set<string>();
		const add = (e: Edge) => {
			if (!seen.has(e.id)) {
				seen.add(e.id);
				es.push(e);
			}
		};

		// Faint base wiring for the formed fleet.
		agents
			.filter((a) => a.spawned)
			.forEach((a) => add({ id: `base:${a.id}`, source: `agent:${a.id}`, target: 'router', style: E_BASE }));
		add({ id: 'base:router-store', source: 'router', target: 'belief-store', style: E_BASE });
		TIERS.forEach(([id]) =>
			add({ id: `base:router-${id}`, source: 'router', target: `tier:${id}`, style: E_BASE })
		);

		// Event-driven edges (chronological; later events draw over earlier ones).
		for (const ev of events) {
			const a = ev.agent_id;
			if (ev.event_type === 'belief_committed' && a) {
				add({ id: `commit:${a}`, source: `agent:${a}`, target: 'belief-store', animated: true, style: E_COMMIT, label: 'commit' });
			} else if (ev.event_type === 'federated_fetch' && a) {
				const s = String(ev.detail.source ?? '');
				if (s)
					add({
						id: `fetch:${s}->${a}`,
						source: `src:${s}`,
						target: `agent:${a}`,
						animated: true,
						style: E_FETCH,
						label: ev.detail.rows != null ? `${ev.detail.rows} rows` : 'fetch'
					});
			} else if (ev.event_type === 'contradiction_detected' && a) {
				add({ id: `contra:${a}`, source: `agent:${a}`, target: 'belief-store', animated: true, style: E_CONTRA, label: '⚡ contradiction' });
				const w = ev.detail.with_agent as string | undefined;
				if (w) add({ id: `contra:${w}`, source: `agent:${w}`, target: 'belief-store', animated: true, style: E_CONTRA });
			} else if (ev.event_type === 'contradiction_reconciled') {
				const w = ev.detail.with_agent as string | undefined;
				if (w)
					add({
						id: `super:${w}`,
						source: `agent:${w}`,
						target: 'belief-store',
						style: E_SUPER,
						label: `superseded · ${String(ev.detail.decision ?? '')}`
					});
			} else if (ev.event_type === 'fetch_denied' && a) {
				add({ id: `denied:${a}`, source: `agent:${a}`, target: 'router', animated: true, style: E_DENIED, label: `⛔ ${ev.topic || 'denied'}` });
			}
		}

		return { nodes: ns, edges: es };
	}
</script>

<div style="height: 100%; width: 100%; position: relative;">
	<SvelteFlow bind:nodes bind:edges fitView minZoom={0.2} colorMode="dark">
		<Background />
		<Controls showLock={false} />
	</SvelteFlow>
	<div class="legend">
		<span><i style="background:#34d399"></i>commit</span>
		<span><i style="background:#38bdf8"></i>fetch</span>
		<span><i style="background:#f87171"></i>contradiction / denied</span>
	</div>
</div>

<style>
	.legend {
		position: absolute;
		bottom: 8px;
		right: 8px;
		display: flex;
		gap: 10px;
		padding: 4px 8px;
		border-radius: 6px;
		background: rgba(2, 6, 23, 0.7);
		font-size: 10px;
		color: #cbd5e1;
		pointer-events: none;
	}
	.legend span {
		display: flex;
		align-items: center;
		gap: 4px;
	}
	.legend i {
		width: 10px;
		height: 3px;
		border-radius: 2px;
		display: inline-block;
	}
</style>
