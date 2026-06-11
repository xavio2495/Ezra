<script lang="ts">
	import { Badge } from '$lib/components/ui/badge/index.js';
	import { ScrollArea } from '$lib/components/ui/scroll-area/index.js';
	import { demo } from '$lib/demo/state.svelte';
	import type { AuditEvent, AuditEventType } from '$lib/demo/types';

	const VARIANT: Partial<Record<AuditEventType, 'default' | 'secondary' | 'destructive' | 'outline'>> = {
		fetch_denied: 'destructive',
		contradiction_detected: 'destructive',
		contradiction_reconciled: 'default',
		belief_committed: 'default',
		belief_reverted: 'outline',
		belief_rewound: 'outline'
	};

	function num(e: AuditEvent, k: string): number | null {
		const v = e.detail[k];
		return typeof v === 'number' ? v : null;
	}
	function str(e: AuditEvent, k: string): string | null {
		const v = e.detail[k];
		return typeof v === 'string' ? v : null;
	}
</script>

<ScrollArea class="h-full">
	<div class="space-y-px p-1 font-mono text-[10px]">
		{#if demo.auditEvents.length === 0}
			<p class="p-1 font-sans text-muted-foreground italic">
				The raw chronological AuditEvent feed — act on any commit row directly.
			</p>
		{/if}
		{#each demo.auditEvents as event (event.id)}
			{@const commitId = str(event, 'commitment_id')}
			{@const turn = num(event, 'turn_index')}
			<div class="flex items-center gap-1.5 border-b border-border/40 px-1 py-0.5">
				<span class="shrink-0 text-muted-foreground">
					{new Date(event.created_at).toLocaleTimeString()}
				</span>
				<Badge variant={VARIANT[event.event_type] ?? 'secondary'} class="shrink-0 px-1 py-0 text-[9px]">
					{event.event_type}
				</Badge>
				<span class="min-w-0 flex-1 truncate">
					{event.agent_id ?? '—'}{event.topic ? ` · ${event.topic}` : ''}{str(event, 'claim')
						? ` · ${str(event, 'claim')}`
						: ''}
				</span>
				{#if event.event_type === 'belief_committed' && commitId}
					<div class="flex shrink-0 gap-0.5">
						<button
							class="border px-1 text-[9px] text-muted-foreground hover:bg-secondary hover:text-foreground"
							title="Revert this commitment"
							onclick={() => demo.revert(commitId)}>⎌</button
						>
						{#if turn != null}
							<button
								class="border px-1 text-[9px] text-muted-foreground hover:bg-secondary hover:text-foreground"
								title="Rewind to turn {turn}"
								onclick={() => demo.rewind(turn)}>↶T{turn}</button
							>
							<button
								class="border px-1 text-[9px] text-muted-foreground hover:bg-secondary hover:text-foreground"
								title="Branch from turn {turn}"
								onclick={() => demo.branch({ from_turn: turn })}>⑂</button
							>
						{/if}
					</div>
				{/if}
			</div>
		{/each}
	</div>
</ScrollArea>
