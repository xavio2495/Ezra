<script lang="ts">
	// Interactive session-graph diagram (xyflow). Shows a root session graph
	// spawning a dynamic agent fleet, all sharing one belief store + memory tiers.
	// Rendered browser-only (xyflow needs the DOM) to stay SSR/prerender-safe.
	import { onMount } from 'svelte';
	import { SvelteFlow, Background, Controls, type Node, type Edge } from '@xyflow/svelte';
	import '@xyflow/svelte/dist/style.css';

	let mounted = $state(false);
	onMount(() => {
		mounted = true;
	});

	const AGENTS = [
		{ id: 'race_strategy', label: 'race_strategy', x: -10 },
		{ id: 'tyre_engineer', label: 'tyre_engineer', x: 150 },
		{ id: 'telemetry', label: 'telemetry_analyst', x: 310 },
		{ id: 'weather', label: 'weather_model', x: 470 }
	];

	let nodes = $state.raw<Node[]>([
		{
			id: 'root',
			data: { label: 'Session graph · Monaco GP' },
			position: { x: 170, y: 0 },
			class: 'sg-root',
			draggable: false
		},
		...AGENTS.map(
			(a): Node => ({
				id: a.id,
				data: { label: a.label },
				position: { x: a.x, y: 120 },
				class: 'sg-agent'
			})
		),
		{
			id: 'belief',
			data: { label: 'Belief store + reconciler' },
			position: { x: 60, y: 250 },
			class: 'sg-shared'
		},
		{
			id: 'memory',
			data: { label: 'Three-tier memory' },
			position: { x: 360, y: 250 },
			class: 'sg-shared'
		}
	]);

	let edges = $state.raw<Edge[]>([
		...AGENTS.map(
			(a): Edge => ({
				id: `root-${a.id}`,
				source: 'root',
				target: a.id,
				animated: true,
				label: 'spawn'
			})
		),
		...AGENTS.flatMap((a): Edge[] => [
			{ id: `${a.id}-belief`, source: a.id, target: 'belief' },
			{ id: `${a.id}-memory`, source: a.id, target: 'memory' }
		])
	]);
</script>

<div class="sg-wrap">
	{#if mounted}
		<SvelteFlow
			bind:nodes
			bind:edges
			fitView
			nodesConnectable={false}
			elementsSelectable={false}
			minZoom={0.4}
			maxZoom={1.5}
		>
			<Background bgColor="transparent" patternColor="rgba(232,220,196,0.10)" gap={22} />
			<Controls showLock={false} />
		</SvelteFlow>
	{:else}
		<div class="sg-placeholder">Loading interactive diagram…</div>
	{/if}
</div>

<style>
	.sg-wrap {
		height: 440px;
		width: 100%;
		border: 1px solid var(--line);
		border-radius: 8px;
		background: rgba(0, 0, 0, 0.2);
		overflow: hidden;
	}
	.sg-placeholder {
		display: grid;
		place-items: center;
		height: 100%;
		font-family: var(--f-mono);
		font-size: 11px;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		color: var(--fg-4);
	}

	/* Teal Night theming of the xyflow surface (global — xyflow renders its own DOM) */
	.sg-wrap :global(.svelte-flow) {
		background: transparent;
	}
	.sg-wrap :global(.svelte-flow__node) {
		font-family: var(--f-mono);
		font-size: 11px;
		letter-spacing: 0.04em;
		color: var(--fg);
		border-radius: 6px;
		padding: 10px 14px;
		text-align: center;
		border: 1px solid var(--line);
		background: var(--bg-3);
		box-shadow: none;
		width: auto;
	}
	.sg-wrap :global(.sg-root) {
		border-color: var(--hot);
		color: var(--fg);
		background: rgba(232, 156, 94, 0.08);
		text-transform: uppercase;
		letter-spacing: 0.1em;
		font-size: 10.5px;
	}
	.sg-wrap :global(.sg-agent) {
		border-color: var(--accent);
		background: rgba(45, 199, 184, 0.07);
		color: var(--accent-2);
	}
	.sg-wrap :global(.sg-shared) {
		border-color: var(--line);
		background: var(--bg-2);
		color: var(--fg-2);
	}
	.sg-wrap :global(.svelte-flow__edge-path) {
		stroke: var(--fg-4);
		stroke-width: 1.5;
	}
	.sg-wrap :global(.svelte-flow__edge.animated .svelte-flow__edge-path) {
		stroke: var(--accent);
	}
	.sg-wrap :global(.svelte-flow__edge-text) {
		fill: var(--fg-3);
		font-family: var(--f-mono);
		font-size: 9px;
	}
	.sg-wrap :global(.svelte-flow__edge-textbg) {
		fill: var(--bg);
	}
	.sg-wrap :global(.svelte-flow__controls) {
		box-shadow: none;
		border: 1px solid var(--line);
	}
	.sg-wrap :global(.svelte-flow__controls-button) {
		background: var(--bg-3);
		border-bottom: 1px solid var(--line);
		color: var(--fg-2);
		fill: var(--fg-2);
	}
	.sg-wrap :global(.svelte-flow__controls-button:hover) {
		background: var(--bg-2);
	}
	.sg-wrap :global(.svelte-flow__attribution) {
		background: transparent;
		font-size: 9px;
	}
	.sg-wrap :global(.svelte-flow__attribution a) {
		color: var(--fg-4);
	}
</style>
