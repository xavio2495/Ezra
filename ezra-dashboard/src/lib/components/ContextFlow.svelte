<script lang="ts">
	import { SvelteFlow, Background, type Node, type Edge } from '@xyflow/svelte';
	import '@xyflow/svelte/dist/style.css';

	let nodes = $state.raw<Node[]>([
		{ id: 'router', position: { x: 0, y: 0 }, data: { label: 'Ezra Router' } },
		{ id: 'belief-store', position: { x: 220, y: 0 }, data: { label: 'Belief Store' } }
	]);
	let edges = $state.raw<Edge[]>([
		{ id: 'router->belief-store', source: 'router', target: 'belief-store', animated: true }
	]);
</script>

<div style="height: 100%; width: 100%;">
	<SvelteFlow bind:nodes bind:edges fitView>
		<Background />
	</SvelteFlow>
</div>
