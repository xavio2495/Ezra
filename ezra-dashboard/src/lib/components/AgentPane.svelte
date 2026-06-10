<script lang="ts">
	import * as Card from '$lib/components/ui/card/index.js';
	import { Badge } from '$lib/components/ui/badge/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Textarea } from '$lib/components/ui/textarea/index.js';
	import type { AgentInfo } from '$lib/demo/types';
	import { demo } from '$lib/demo/state.svelte';

	let { agent }: { agent: AgentInfo } = $props();

	// svelte-ignore state_referenced_locally -- the pre-filled task seeds the
	// draft once; the presenter edits it freely afterwards.
	let draft = $state(agent.prefill);
	let expanded = $state(false);

	const turns = $derived(demo.messagesFor(agent.id));
	const latest = $derived(turns.at(-1));
	const lastCommit = $derived([...turns].reverse().find((t) => t.committed)?.committed);
	const busy = $derived(demo.busyAgents[agent.id] ?? false);

	async function send() {
		const text = draft.trim();
		if (!text || busy) return;
		await demo.prompt(agent.id, text);
	}
</script>

<Card.Root class="flex h-full flex-col gap-2 py-3">
	<Card.Header class="px-3">
		<Card.Title class="flex items-center gap-2 text-sm">
			<span
				class="size-2 rounded-full {agent.spawned ? 'bg-emerald-400' : 'bg-muted-foreground/40'}"
				title={agent.spawned ? 'spawned' : 'not spawned'}
			></span>
			{agent.role}
		</Card.Title>
		<Card.Description class="flex flex-wrap gap-1">
			{#each agent.scope as topic (topic)}
				<Badge variant="secondary" class="px-1.5 py-0 text-[10px]">{topic}</Badge>
			{/each}
		</Card.Description>
	</Card.Header>

	<Card.Content class="min-h-0 flex-1 px-3">
		{#if latest}
			<button
				class="w-full cursor-pointer text-left"
				onclick={() => (expanded = !expanded)}
				title="Click to {expanded ? 'collapse' : 'expand'} scrollback"
			>
				{#if expanded}
					<div class="max-h-40 space-y-1 overflow-y-auto">
						{#each turns as turn, i (i)}
							<p class="text-xs {turn.role === 'user' ? 'text-muted-foreground' : ''}">
								<span class="font-medium">{turn.role === 'user' ? '▸' : '◂'}</span>
								{turn.text}
							</p>
						{/each}
					</div>
				{:else}
					<p class="line-clamp-3 text-xs">{latest.text}</p>
				{/if}
			</button>
		{:else}
			<p class="text-xs text-muted-foreground italic">No turns yet.</p>
		{/if}
		{#if lastCommit}
			<Badge class="mt-1 max-w-full px-1.5 py-0 text-[10px]" title={lastCommit.claim}>
				<span class="truncate">committed: {lastCommit.claim}</span>
			</Badge>
		{/if}
	</Card.Content>

	<Card.Footer class="flex items-end gap-2 px-3">
		<Textarea
			bind:value={draft}
			rows={2}
			class="min-h-0 flex-1 resize-none text-xs"
			placeholder="Task for {agent.role}…"
			disabled={busy}
		/>
		<Button size="sm" onclick={send} disabled={busy || !draft.trim()}>
			{busy ? '…' : 'Send'}
		</Button>
	</Card.Footer>
</Card.Root>
