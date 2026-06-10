<script lang="ts">
	import { Button } from '$lib/components/ui/button/index.js';
	import { Badge } from '$lib/components/ui/badge/index.js';
	import { demo } from '$lib/demo/state.svelte';

	const started = $derived(demo.graphId !== null);
</script>

<div class="flex items-center gap-2">
	<Button size="sm" onclick={() => demo.start()} disabled={started}>▷ Start</Button>
	<Button size="sm" variant="outline" onclick={() => demo.rewind()} disabled={!started}>
		↶ Rewind
	</Button>
	<Button size="sm" variant="outline" onclick={() => demo.revert()} disabled={!started}>
		Revert
	</Button>
	<Button size="sm" variant="outline" onclick={() => demo.branch()} disabled={!started}>
		⑂ Branch
	</Button>
	<span class="flex-1"></span>
	<Badge variant={demo.connection === 'live' ? 'default' : 'secondary'}>
		{demo.connection}
	</Badge>
</div>
{#if demo.error}
	<p class="mt-1 text-xs text-destructive">{demo.error}</p>
{/if}
