<script lang="ts">
	import { page } from '$app/state';
	import { NAV, hrefFor } from '$lib/docs/nav';
	import type { Heading } from '$lib/docs/render';

	let { children } = $props();

	const currentSlug = $derived(
		page.url.pathname === '/docs'
			? 'overview'
			: page.url.pathname.replace(/^\/docs\//, '').replace(/\/$/, '')
	);
	const headings = $derived(
		((page.data as { doc?: { headings: Heading[] } })?.doc?.headings ?? []) as Heading[]
	);

	let activeId = $state('');
	let navOpen = $state(false);

	// Scroll-spy: highlight the heading currently in view in the on-this-page TOC.
	// Re-armed on each navigation (the effect reads `headings`).
	$effect(() => {
		void headings;
		let io: IntersectionObserver | undefined;
		const raf = requestAnimationFrame(() => {
			const els = Array.from(
				document.querySelectorAll<HTMLElement>('.doc-prose h2[id], .doc-prose h3[id]')
			);
			if (!els.length) return;
			io = new IntersectionObserver(
				(entries) => {
					const visible = entries
						.filter((e) => e.isIntersecting)
						.sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
					if (visible[0]) activeId = (visible[0].target as HTMLElement).id;
				},
				{ rootMargin: '-80px 0px -68% 0px', threshold: [0, 1] }
			);
			els.forEach((el) => io!.observe(el));
		});
		return () => {
			cancelAnimationFrame(raf);
			io?.disconnect();
		};
	});
</script>

<div class="doc-shell">
	<!-- Left: page navigation -->
	<aside class="doc-nav" class:open={navOpen}>
		<div class="doc-nav-bar">
			<a class="doc-nav-home" href="/docs">Documentation</a>
			<button
				class="doc-nav-toggle"
				type="button"
				aria-expanded={navOpen}
				onclick={() => (navOpen = !navOpen)}
			>
				{navOpen ? 'Close' : 'Menu'}
			</button>
		</div>
		<div class="doc-nav-inner">
			{#each NAV as group (group.group)}
				<div class="doc-nav-group">
					<h6 class="doc-nav-title">{group.group}</h6>
					<ul>
						{#each group.items as item (item.slug)}
							<li>
								<a
									href={hrefFor(item.slug)}
									class:active={currentSlug === item.slug}
									onclick={() => (navOpen = false)}
								>
									{item.title}
								</a>
							</li>
						{/each}
					</ul>
				</div>
			{/each}
		</div>
	</aside>

	<!-- Center: rendered markdown -->
	<main class="doc-main">
		{@render children()}
	</main>

	<!-- Right: on this page -->
	<aside class="doc-toc">
		{#if headings.length}
			<div class="doc-toc-inner">
				<h6 class="doc-toc-title">On this page</h6>
				<ul>
					{#each headings as h (h.id)}
						<li class:sub={h.level === 3}>
							<a href={`#${h.id}`} class:active={activeId === h.id}>{h.text}</a>
						</li>
					{/each}
				</ul>
			</div>
		{/if}
	</aside>
</div>
