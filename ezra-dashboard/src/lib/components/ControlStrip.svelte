<script lang="ts">
	import { Button } from '$lib/components/ui/button/index.js';
	import { Badge } from '$lib/components/ui/badge/index.js';
	import { demo } from '$lib/demo/state.svelte';

	const started = $derived(demo.graphId !== null);
	const active = $derived(demo.beliefs.filter((b) => b.active));
	const turns = $derived([...new Set(demo.beliefs.map((b) => b.turn_index))].sort((a, b) => a - b));

	let revertId = $state('');
	let rewindTurn = $state('');

	const sel =
		'border bg-secondary text-secondary-foreground px-1 py-0.5 text-[10px] max-w-[160px] truncate';
</script>

<div class="flex flex-wrap items-center gap-1.5 border bg-card px-2 py-1.5">
	<Button size="sm" class="h-6 px-2 text-[10px]" onclick={() => demo.start()} disabled={started}>
		▷ Start
	</Button>

	<span class="mx-0.5 h-4 w-px bg-border"></span>

	<!-- Rewind: pick the turn to roll back to -->
	<select class={sel} bind:value={rewindTurn} disabled={!started || turns.length === 0} title="Rewind target turn">
		<option value="">latest</option>
		{#each turns as t (t)}<option value={String(t)}>turn {t}</option>{/each}
	</select>
	<Button
		size="sm"
		variant="outline"
		class="h-6 px-2 text-[10px]"
		disabled={!started}
		onclick={() => demo.rewind(rewindTurn === '' ? (turns.at(-1) ?? 1) : Number(rewindTurn))}>↶ Rewind</Button
	>

	<span class="mx-0.5 h-4 w-px bg-border"></span>

	<!-- Revert: pick the active commitment to undo -->
	<select class={sel} bind:value={revertId} disabled={!started || active.length === 0} title="Commitment to revert">
		<option value="">latest commit</option>
		{#each active as b (b.id)}
			<option value={b.id}>T{b.turn_index} {b.agent_id}: {b.claim}</option>
		{/each}
	</select>
	<Button
		size="sm"
		variant="outline"
		class="h-6 px-2 text-[10px]"
		disabled={!started || active.length === 0}
		onclick={() => demo.revert(revertId || null)}>⎌ Revert</Button
	>

	<span class="mx-0.5 h-4 w-px bg-border"></span>

	<Button
		size="sm"
		variant="outline"
		class="h-6 px-2 text-[10px]"
		disabled={!started}
		onclick={() => demo.branch()}
		title="Counterfactual branch (configure in the Branch tab)">⑂ Branch</Button
	>

	<span class="min-w-0 flex-1"></span>
	<Badge variant={demo.connection === 'live' ? 'default' : 'secondary'} class="text-[10px]">
		{demo.connection}
	</Badge>
</div>
{#if demo.error}
	<p class="border border-destructive/40 bg-destructive/10 px-2 py-0.5 text-[10px] text-destructive">
		{demo.error}
	</p>
{/if}
