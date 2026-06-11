<script lang="ts">
	import { Button } from '$lib/components/ui/button/index.js';
	import { Textarea } from '$lib/components/ui/textarea/index.js';
	import type { AgentInfo } from '$lib/demo/types';
	import { demo } from '$lib/demo/state.svelte';

	let {
		agent,
		focused = false,
		forceCollapsed = false,
		ontoggleFocus
	}: {
		agent: AgentInfo;
		focused?: boolean;
		forceCollapsed?: boolean;
		ontoggleFocus?: () => void;
	} = $props();

	let draft = $state('');
	let localCollapsed = $state(false);
	let scroller = $state<HTMLDivElement | null>(null);

	// Collapsed when the user collapsed this pane, OR another pane is focused.
	const collapsed = $derived(forceCollapsed || localCollapsed);
	const turns = $derived(demo.messagesFor(agent.id));
	const lastCommit = $derived([...turns].reverse().find((t) => t.committed)?.committed);
	const busy = $derived(demo.busyAgents[agent.id] ?? false);

	// Keep the conversation pinned to the newest turn.
	$effect(() => {
		void turns.length;
		if (scroller) scroller.scrollTop = scroller.scrollHeight;
	});

	async function send() {
		const text = draft.trim();
		if (!text || busy) return;
		draft = '';
		await demo.prompt(agent.id, text);
	}
	function loadTask() {
		draft = agent.prefill;
	}
</script>

<div
	class="flex min-h-0 flex-col border bg-card text-card-foreground {focused
		? 'col-span-full ring-1 ring-primary/40'
		: ''}"
>
	<!-- Header: role · scope · committed · collapse — all inline -->
	<div class="flex items-center gap-1.5 border-b px-2 py-1">
		<span
			class="size-1.5 shrink-0 rounded-full {agent.spawned
				? 'bg-emerald-400'
				: 'bg-muted-foreground/40'}"
			title={agent.spawned ? 'spawned' : 'not spawned'}
		></span>
		<span class="font-heading text-[11px] font-semibold tracking-wide whitespace-nowrap">
			{agent.role}
		</span>
		{#each agent.scope as t (t)}
			<span class="rounded-sm bg-secondary px-1 text-[9px] text-secondary-foreground">{t}</span>
		{/each}
		{#if busy}
			<span class="animate-pulse text-[10px] text-amber-400">▍thinking…</span>
		{/if}
		<span class="min-w-0 flex-1"></span>
		{#if lastCommit}
			<span class="truncate text-[10px] text-emerald-400" title={lastCommit.claim}>
				✓ {lastCommit.claim}
			</span>
		{/if}
		<button
			class="shrink-0 px-1 text-[10px] {focused ? 'text-primary' : 'text-muted-foreground'} hover:text-foreground"
			onclick={() => ontoggleFocus?.()}
			title={focused ? 'exit focus' : 'focus this chat'}
		>
			{focused ? '⤡' : '⤢'}
		</button>
		<button
			class="shrink-0 px-1 text-[10px] text-muted-foreground hover:text-foreground"
			onclick={() => (localCollapsed = !localCollapsed)}
			title={collapsed ? 'expand' : 'collapse'}
		>
			{collapsed ? '▸' : '▾'}
		</button>
	</div>

	{#if !collapsed}
		<!-- Conversation: user prompts (▸) and agent responses (◂) -->
		<div
			bind:this={scroller}
			class="min-h-0 space-y-1 overflow-y-auto px-2 py-1 text-[11px] leading-snug {focused
				? 'h-[55vh]'
				: 'h-40'}"
		>
			{#if turns.length === 0}
				<p class="text-muted-foreground italic">No turns yet — load the task or type a prompt.</p>
			{/if}
			{#each turns as turn, i (i)}
				<p class={turn.role === 'user' ? 'text-muted-foreground' : 'text-foreground'}>
					<span class="select-none opacity-60">{turn.role === 'user' ? '▸ ' : '◂ '}</span>{turn.text}
					{#if turn.committed}
						<span class="text-emerald-400">[committed: {turn.committed.claim}]</span>
					{/if}
				</p>
			{/each}
			{#if busy}
				<p class="text-amber-400"><span class="animate-pulse">◂ reasoning &amp; committing…</span></p>
			{/if}
		</div>

		<!-- Input: custom prompt + load-suggested-task + send -->
		<div class="flex items-end gap-1 border-t p-1">
			<Textarea
				bind:value={draft}
				rows={2}
				placeholder="Prompt {agent.role}… (⌘/Ctrl+Enter to send)"
				disabled={busy}
				class="max-h-16 min-h-0 flex-1 resize-none overflow-y-auto text-[11px] leading-snug"
				onkeydown={(e) => {
					if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
						e.preventDefault();
						send();
					}
				}}
			/>
			<div class="flex shrink-0 flex-col gap-1">
				<Button
					size="sm"
					variant="outline"
					class="h-6 px-2 text-[10px]"
					onclick={loadTask}
					disabled={busy}
					title="Load the suggested task into the prompt">Task</Button
				>
				<Button
					size="sm"
					class="h-6 px-2 text-[10px]"
					onclick={send}
					disabled={busy || !draft.trim()}>Send</Button
				>
			</div>
		</div>
	{/if}
</div>
