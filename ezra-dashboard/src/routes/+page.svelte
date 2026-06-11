<script lang="ts">
	import * as Tabs from '$lib/components/ui/tabs/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import AgentPane from '$lib/components/AgentPane.svelte';
	import ControlStrip from '$lib/components/ControlStrip.svelte';
	import ContextFlow from '$lib/components/ContextFlow.svelte';
	import MemoryTiersTab from '$lib/components/MemoryTiersTab.svelte';
	import BranchGraphTab from '$lib/components/BranchGraphTab.svelte';
	import DataAccessTab from '$lib/components/DataAccessTab.svelte';
	import AuditLogTab from '$lib/components/AuditLogTab.svelte';
	import TourOverlay from '$lib/components/TourOverlay.svelte';
	import { demo } from '$lib/demo/state.svelte';
	import { tour } from '$lib/demo/tour.svelte';

	let vizOpen = $state(true);
	// Focus one chat: the focused pane spans full-width/tall, the rest auto-collapse
	// so the presenter can drill into a single agent.
	let focused = $state<string | null>(null);
	// Active right-column tab — controlled so the guided demo can switch it.
	let activeTab = $state('graph');
	$effect(() => {
		if (tour.requestedTab) activeTab = tour.requestedTab;
	});

	const spawned = $derived(demo.agents.filter((a) => a.spawned).length);
	const activeBeliefs = $derived(demo.beliefs.filter((b) => b.active).length);
	const dot = $derived(
		demo.connection === 'live'
			? 'bg-emerald-400'
			: demo.connection === 'connecting'
				? 'bg-amber-400'
				: 'bg-muted-foreground/50'
	);
</script>

<svelte:head>
	<title>Ezra — Live Demo Conductor</title>
</svelte:head>

<div class="flex h-screen flex-col bg-background">
	<!-- Status strip -->
	<header class="flex items-center gap-3 border-b px-3 py-1 font-mono text-[11px]">
		<span class="font-heading text-[12px] font-semibold tracking-widest">EZRA · LIVE FLEET</span>
		<span class="flex items-center gap-1 text-muted-foreground">
			<span class="size-1.5 rounded-full {dot}"></span>{demo.connection}
		</span>
		<span class="text-muted-foreground">{demo.graphId ?? 'not started'}</span>
		<span class="min-w-0 flex-1"></span>
		<span class="text-muted-foreground">agents <span class="text-foreground">{spawned}/{demo.agents.length}</span></span>
		<span class="text-muted-foreground">beliefs <span class="text-emerald-400">{activeBeliefs}</span></span>
		<span class="text-muted-foreground">branches <span class="text-amber-400">{demo.branches.length}</span></span>
		<span class="text-muted-foreground">events <span class="text-foreground">{demo.auditEvents.length}</span></span>
		<Button
			size="sm"
			class="h-6 px-2 text-[10px]"
			onclick={() => (tour.running ? tour.stop() : tour.start())}
		>
			{tour.running ? '■ Stop demo' : '▶ Run demo'}
		</Button>
		<Button size="sm" variant="ghost" class="h-6 px-2 text-[10px]" onclick={() => (vizOpen = !vizOpen)}>
			{vizOpen ? 'viz ▸' : '◂ viz'}
		</Button>
	</header>

	<div class="flex min-h-0 flex-1">
		<main
			class="grid min-h-0 flex-1 content-start gap-1 overflow-y-auto p-1"
			style="grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); grid-auto-rows: min-content;"
		>
			{#each demo.agents as agent (agent.id)}
				<AgentPane
					{agent}
					focused={focused === agent.id}
					forceCollapsed={focused !== null && focused !== agent.id}
					ontoggleFocus={() => (focused = focused === agent.id ? null : agent.id)}
				/>
			{/each}
		</main>

		{#if vizOpen}
			<aside class="flex w-[44%] min-w-[400px] flex-col gap-1 border-l p-1">
				<ControlStrip />
				<Tabs.Root bind:value={activeTab} class="flex min-h-0 flex-1 flex-col">
					<Tabs.List class="h-7 w-full">
						<Tabs.Trigger value="graph" class="text-[11px]">Context</Tabs.Trigger>
						<Tabs.Trigger value="memory" class="text-[11px]">Memory</Tabs.Trigger>
						<Tabs.Trigger value="branch" class="text-[11px]">Branch</Tabs.Trigger>
						<Tabs.Trigger value="data" class="text-[11px]">Data</Tabs.Trigger>
						<Tabs.Trigger value="audit" class="text-[11px]">Audit</Tabs.Trigger>
					</Tabs.List>
					<Tabs.Content value="graph" class="mt-1 min-h-0 flex-1 border">
						<ContextFlow />
					</Tabs.Content>
					<Tabs.Content value="memory" class="mt-1 min-h-0 flex-1 border">
						<MemoryTiersTab />
					</Tabs.Content>
					<Tabs.Content value="branch" class="mt-1 min-h-0 flex-1 border">
						<BranchGraphTab />
					</Tabs.Content>
					<Tabs.Content value="data" class="mt-1 min-h-0 flex-1 border">
						<DataAccessTab />
					</Tabs.Content>
					<Tabs.Content value="audit" class="mt-1 min-h-0 flex-1 border">
						<AuditLogTab />
					</Tabs.Content>
				</Tabs.Root>
			</aside>
		{/if}
	</div>

	<TourOverlay />
</div>
