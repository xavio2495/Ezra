<script lang="ts">
	import { Badge } from '$lib/components/ui/badge/index.js';
	import { ScrollArea } from '$lib/components/ui/scroll-area/index.js';
	import { demo } from '$lib/demo/state.svelte';
	import type { AuditEventType } from '$lib/demo/types';

	const VARIANT: Partial<Record<AuditEventType, 'default' | 'secondary' | 'destructive' | 'outline'>> = {
		fetch_denied: 'destructive',
		contradiction_detected: 'destructive',
		contradiction_reconciled: 'default',
		belief_committed: 'default'
	};
</script>

<ScrollArea class="h-full">
	<div class="space-y-1 p-1 font-mono text-[11px]">
		{#if demo.auditEvents.length === 0}
			<p class="font-sans text-xs text-muted-foreground italic">
				The raw chronological AuditEvent feed — every other tab derives from this.
			</p>
		{/if}
		{#each demo.auditEvents as event (event.id)}
			<div class="flex items-start gap-2">
				<span class="shrink-0 text-muted-foreground">
					{new Date(event.created_at).toLocaleTimeString()}
				</span>
				<Badge variant={VARIANT[event.event_type] ?? 'secondary'} class="px-1 py-0 text-[10px]">
					{event.event_type}
				</Badge>
				<span class="min-w-0 break-all">
					{event.agent_id ?? '—'}{event.topic ? ` · ${event.topic}` : ''}
				</span>
			</div>
		{/each}
	</div>
</ScrollArea>
