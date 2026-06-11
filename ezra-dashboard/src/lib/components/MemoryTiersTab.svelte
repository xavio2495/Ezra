<script lang="ts">
	import { ScrollArea } from '$lib/components/ui/scroll-area/index.js';
	import { Badge } from '$lib/components/ui/badge/index.js';
	import { demo } from '$lib/demo/state.svelte';

	const hotAgents = $derived(Object.entries(demo.tiers.hot));
	const warm = $derived(demo.tiers.warm);
	const cold = $derived(demo.beliefs.filter((b) => !b.is_marker));

	function preview(o: unknown, n = 90): string {
		if (o == null) return '';
		if (typeof o === 'string') return o.slice(0, n);
		const r = o as Record<string, unknown>;
		const t = r.response ?? r.content ?? r.user_input ?? r.claim ?? r.text;
		return (typeof t === 'string' ? t : JSON.stringify(o)).slice(0, n);
	}
</script>

<ScrollArea class="h-full">
	<div class="space-y-2 p-2 text-[11px]">
		<!-- HOT (Redis): recent per-agent turns + pinned beliefs -->
		<section>
			<div class="mb-1 flex items-center gap-2 border-b pb-0.5">
				<span class="size-2 rounded-full bg-rose-400"></span>
				<span class="font-heading text-[10px] font-semibold tracking-wide">HOT · Redis</span>
				<span class="text-[10px] text-muted-foreground">recent turns / pinned beliefs</span>
			</div>
			{#if hotAgents.length === 0}
				<p class="text-muted-foreground italic">empty</p>
			{/if}
			{#each hotAgents as [agent, data] (agent)}
				<div class="mb-0.5">
					<span class="font-mono font-semibold">{agent}</span>
					<Badge variant="secondary" class="px-1 py-0 text-[9px]">{data.turns.length} turns</Badge>
					{#if data.pinned.length}<Badge variant="outline" class="px-1 py-0 text-[9px]">{data.pinned.length} pinned</Badge>{/if}
					{#if data.turns.length}
						<span class="text-muted-foreground">— {preview(data.turns.at(-1))}</span>
					{/if}
				</div>
			{/each}
		</section>

		<!-- WARM (Qdrant): scoped archival summaries (vectors) -->
		<section>
			<div class="mb-1 flex items-center gap-2 border-b pb-0.5">
				<span class="size-2 rounded-full bg-amber-400"></span>
				<span class="font-heading text-[10px] font-semibold tracking-wide">WARM · Qdrant</span>
				<span class="text-[10px] text-muted-foreground">vector summaries</span>
			</div>
			{#if warm.length === 0}
				<p class="text-muted-foreground italic">empty</p>
			{/if}
			{#each warm as w, i (i)}
				<div class="font-mono text-muted-foreground">
					{#if Array.isArray(w.topics)}{(w.topics as string[]).join(',')} · {/if}{preview(w)}
				</div>
			{/each}
		</section>

		<!-- COLD (Atlas): the append-only belief commitment log -->
		<section>
			<div class="mb-1 flex items-center gap-2 border-b pb-0.5">
				<span class="size-2 rounded-full bg-sky-400"></span>
				<span class="font-heading text-[10px] font-semibold tracking-wide">COLD · Atlas</span>
				<span class="text-[10px] text-muted-foreground">{demo.tiers.cold.belief_count} commitments (append-only)</span>
			</div>
			{#if cold.length === 0}
				<p class="text-muted-foreground italic">empty</p>
			{/if}
			{#each cold as b (b.id)}
				<div class="font-mono {b.active ? '' : 'text-muted-foreground line-through'}">
					<span class="text-muted-foreground">T{b.turn_index}</span>
					<span class="font-semibold">{b.agent_id}</span>
					<span class="text-cyan-400">{b.topic}</span> · {b.claim}
				</div>
			{/each}
		</section>
	</div>
</ScrollArea>
