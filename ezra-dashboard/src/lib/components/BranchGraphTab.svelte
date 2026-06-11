<script lang="ts">
	import { ScrollArea } from '$lib/components/ui/scroll-area/index.js';
	import { demo } from '$lib/demo/state.svelte';

	// git-like commit graph: the belief commitment log on the main line, with the
	// presenter's counterfactual branches diverging off it. Derived from
	// /demo/beliefs (commits) + /demo/branches (divergences).
	const commits = $derived(
		demo.beliefs
			.filter((b) => !b.is_marker)
			.sort((a, b) => a.turn_index - b.turn_index || a.created_at.localeCompare(b.created_at))
	);
</script>

<ScrollArea class="h-full">
	<div class="p-2 font-mono text-[11px]">
		<div class="mb-1 flex items-center gap-2 font-sans text-[10px] text-muted-foreground">
			<span class="size-2 rounded-full bg-primary"></span>
			main · {demo.graphId ?? '—'}
		</div>

		{#if commits.length === 0}
			<p class="font-sans text-muted-foreground italic">No commits yet — drive an agent turn.</p>
		{/if}

		{#each commits as c (c.id)}
			<div class="grid grid-cols-[16px_1fr] gap-1.5">
				<div class="relative flex justify-center">
					<div class="absolute inset-y-0 w-px bg-border/60"></div>
					<span
						class="relative z-10 mt-1.5 size-2 rounded-full {c.active
							? 'bg-emerald-400'
							: 'bg-muted-foreground/50'}"
					></span>
				</div>
				<div class="py-0.5 {c.active ? '' : 'text-muted-foreground line-through'}">
					<span class="text-muted-foreground">T{c.turn_index}</span>
					<span class="font-semibold">{c.agent_id}</span>
					<span class="text-cyan-400">{c.topic}</span>
					· {c.claim}
					{#if c.active}
						<span class="text-emerald-400">● active</span>
					{:else if c.superseded_by}
						<span class="not-italic text-amber-400">⟶ superseded</span>
					{/if}
					<span class="text-muted-foreground">trust {c.trust_score.toFixed(2)}</span>
				</div>
			</div>
		{/each}

		{#each demo.branches as br (br.branch_id)}
			<div class="mt-1 grid grid-cols-[16px_1fr] gap-1.5">
				<div class="flex justify-center pt-1 text-amber-400">⑂</div>
				<div class="border border-amber-400/30 bg-amber-400/5 p-1.5">
					<div class="font-semibold text-amber-400">
						{br.branch_id} <span class="font-normal text-muted-foreground">· from T{br.from_turn}</span>
					</div>
					<div class="text-muted-foreground">
						counterfactual: {br.counterfactual.agent_id}/{br.counterfactual.topic}: "{br.counterfactual.claim}"
					</div>
					{#each br.diverged as d (d.topic)}
						<div class="mt-0.5 text-cyan-400">{d.topic}</div>
						{#each d.only_in_branch as c (c)}<div class="text-emerald-400">+ {c} <span class="text-muted-foreground">(branch)</span></div>{/each}
						{#each d.only_in_original as c (c)}<div class="text-muted-foreground line-through">− {c} (original)</div>{/each}
					{/each}
				</div>
			</div>
		{/each}
	</div>
</ScrollArea>
