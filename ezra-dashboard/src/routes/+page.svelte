<script lang="ts">
	import * as Tabs from '$lib/components/ui/tabs/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import AgentPane from '$lib/components/AgentPane.svelte';
	import ControlStrip from '$lib/components/ControlStrip.svelte';
	import ContextFlow from '$lib/components/ContextFlow.svelte';
	import DataAccessTab from '$lib/components/DataAccessTab.svelte';
	import AuditLogTab from '$lib/components/AuditLogTab.svelte';
	import { demo } from '$lib/demo/state.svelte';

	// Collapsible right column: the chat grid grows past 3×2 when the fleet
	// spawns mid-demo; the presenter expands the column for the Ezra beats.
	let vizOpen = $state(true);
</script>

<svelte:head>
	<title>Ezra — Live Demo Conductor</title>
</svelte:head>

<div class="flex h-screen flex-col">
	<header class="flex items-center gap-3 border-b px-4 py-2">
		<h1 class="font-heading text-sm font-semibold tracking-wide">EZRA · LIVE FLEET</h1>
		<span class="text-xs text-muted-foreground">
			{demo.graphId ?? 'fleet not started'}
		</span>
		<span class="flex-1"></span>
		<Button size="sm" variant="ghost" onclick={() => (vizOpen = !vizOpen)}>
			{vizOpen ? 'Collapse viz ▸' : '◂ Expand viz'}
		</Button>
	</header>

	<div class="flex min-h-0 flex-1">
		<main
			class="grid min-h-0 flex-1 auto-rows-fr gap-2 overflow-y-auto p-2"
			style="grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));"
		>
			{#each demo.agents as agent (agent.id)}
				<AgentPane {agent} />
			{/each}
		</main>

		{#if vizOpen}
			<aside class="flex w-[42%] min-w-[380px] flex-col gap-2 border-l p-2">
				<ControlStrip />
				<Tabs.Root value="graph" class="flex min-h-0 flex-1 flex-col">
					<Tabs.List class="w-full">
						<Tabs.Trigger value="graph">Context</Tabs.Trigger>
						<Tabs.Trigger value="data">Data Access</Tabs.Trigger>
						<Tabs.Trigger value="audit">Audit Log</Tabs.Trigger>
					</Tabs.List>
					<Tabs.Content value="graph" class="min-h-0 flex-1">
						<ContextFlow />
					</Tabs.Content>
					<Tabs.Content value="data" class="min-h-0 flex-1">
						<DataAccessTab />
					</Tabs.Content>
					<Tabs.Content value="audit" class="min-h-0 flex-1">
						<AuditLogTab />
					</Tabs.Content>
				</Tabs.Root>
			</aside>
		{/if}
	</div>
</div>
