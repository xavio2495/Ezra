<script lang="ts">
	import { Badge } from '$lib/components/ui/badge/index.js';
	import { ScrollArea } from '$lib/components/ui/scroll-area/index.js';
	import { demo } from '$lib/demo/state.svelte';

	// The federated fetch/write ledger, derived purely from the audit feed.
	const accesses = $derived(
		demo.auditEvents.filter(
			(e) => e.event_type === 'federated_fetch' || e.event_type === 'fetch_denied'
		)
	);

	function str(detail: Record<string, unknown>, key: string): string {
		const v = detail[key];
		return v === undefined || v === null ? '' : String(v);
	}
</script>

<ScrollArea class="h-full">
	<div class="space-y-2 p-1">
		{#if accesses.length === 0}
			<p class="text-xs text-muted-foreground italic">
				No federated data access yet — events appear here as agents fetch.
			</p>
		{/if}
		{#each accesses as event (event.id)}
			<div class="rounded border p-2 text-xs {event.event_type === 'fetch_denied' ? 'border-destructive/60' : ''}">
				<div class="flex items-center gap-2">
					{#if event.event_type === 'fetch_denied'}
						<Badge variant="destructive" class="px-1.5 py-0 text-[10px]">denied</Badge>
					{:else}
						<Badge variant="secondary" class="px-1.5 py-0 text-[10px]">fetch</Badge>
					{/if}
					<span class="font-medium">{event.agent_id}</span>
					<span class="text-muted-foreground">→ {str(event.detail, 'source') || event.topic}</span>
					<span class="ml-auto text-muted-foreground">
						{new Date(event.created_at).toLocaleTimeString()}
					</span>
				</div>
				{#if event.event_type === 'federated_fetch'}
					<div class="mt-1 flex flex-wrap gap-1 text-muted-foreground">
						{#if str(event.detail, 'rows')}<span>{str(event.detail, 'rows')} rows</span>{/if}
						{#if str(event.detail, 'synced_at')}
							<Badge variant="outline" class="px-1 py-0 text-[10px]">
								synced {str(event.detail, 'synced_at')}
							</Badge>
						{/if}
						{#if event.detail['time_travel_available']}
							<Badge variant="outline" class="px-1 py-0 text-[10px]">time travel</Badge>
						{/if}
					</div>
				{:else}
					<p class="mt-1 text-muted-foreground">
						Refused at the source — {str(event.detail, 'reason') || 'outside permission scope'}
					</p>
				{/if}
			</div>
		{/each}
	</div>
</ScrollArea>
