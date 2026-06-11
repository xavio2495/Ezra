<script lang="ts">
	import { Button } from '$lib/components/ui/button/index.js';
	import { tour } from '$lib/demo/tour.svelte';
</script>

{#if tour.running}
	<!-- Guided-walkthrough narration card (bottom-center coach mark). -->
	<div class="pointer-events-none fixed inset-x-0 bottom-3 z-50 flex justify-center px-3">
		<div class="pointer-events-auto w-full max-w-xl border border-primary/40 bg-card shadow-lg">
			<div class="h-0.5 bg-primary/30">
				<div
					class="h-full bg-primary transition-all duration-300"
					style="width: {((tour.index + 1) / tour.total) * 100}%"
				></div>
			</div>
			<div class="flex items-start gap-3 p-3">
				<div class="min-w-0 flex-1">
					<div class="flex items-center gap-2">
						<span class="font-heading text-[10px] font-semibold tracking-widest text-primary">
							GUIDED DEMO · {tour.index + 1}/{tour.total}
						</span>
					</div>
					<h3 class="mt-0.5 font-heading text-sm font-semibold">{tour.title}</h3>
					<p class="mt-1 text-[12px] leading-snug text-muted-foreground">{tour.body}</p>
				</div>
				<div class="flex shrink-0 flex-col gap-1">
					<Button size="sm" class="h-6 px-2 text-[10px]" onclick={() => tour.skip()}>Skip ▸</Button>
					<Button
						size="sm"
						variant="outline"
						class="h-6 px-2 text-[10px]"
						onclick={() => tour.stop()}>Stop</Button
					>
				</div>
			</div>
		</div>
	</div>
{/if}
