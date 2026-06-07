<script lang="ts">
	import { hrefFor, type LoadedDoc } from '$lib/docs/nav';

	let { doc }: { doc: LoadedDoc } = $props();
	let prose = $state<HTMLDivElement>();

	// After the markdown HTML is committed (and on every SPA navigation — the effect
	// reads doc.slug, and the {#key} below recreates the prose subtree per page):
	//  1. inject a copy-to-clipboard button into each code block (not mermaid), and
	//  2. render any ```mermaid diagrams client-side, themed to Teal Night.
	$effect(() => {
		void doc.slug;
		const root = prose;
		if (!root) return;

		root.querySelectorAll<HTMLPreElement>('pre:not(.mermaid)').forEach((pre) => {
			if (pre.querySelector('.doc-copy')) return;
			pre.style.position = 'relative';
			// Capture the code text BEFORE the button is appended (so it's excluded).
			const code = (pre.querySelector('code')?.innerText ?? pre.innerText).replace(/\n$/, '');
			const btn = document.createElement('button');
			btn.type = 'button';
			btn.className = 'doc-copy';
			btn.textContent = 'Copy';
			btn.addEventListener('click', () => {
				navigator.clipboard.writeText(code).then(() => {
					btn.textContent = 'Copied';
					btn.classList.add('ok');
					setTimeout(() => {
						btn.textContent = 'Copy';
						btn.classList.remove('ok');
					}, 1600);
				});
			});
			pre.appendChild(btn);
		});

		const diagrams = root.querySelectorAll<HTMLElement>('pre.mermaid:not([data-processed])');
		if (diagrams.length === 0) return;
		let cancelled = false;
		import('mermaid').then(({ default: mermaid }) => {
			if (cancelled) return;
			mermaid.initialize({
				startOnLoad: false,
				securityLevel: 'strict',
				theme: 'base',
				fontFamily: "'JetBrains Mono', 'IBM Plex Mono', monospace",
				themeVariables: {
					background: '#0a1c1f',
					mainBkg: '#0e2327',
					primaryColor: '#0e2327',
					primaryBorderColor: '#2dc7b8',
					primaryTextColor: '#e8dcc4',
					secondaryColor: '#13322f',
					tertiaryColor: '#0a1c1f',
					lineColor: '#8a9695',
					textColor: '#e8dcc4',
					nodeBorder: '#2dc7b8',
					clusterBkg: 'rgba(45, 199, 184, 0.05)',
					clusterBorder: 'rgba(232, 220, 196, 0.18)',
					edgeLabelBackground: '#0a1c1f',
					titleColor: '#7de0d9'
				}
			});
			mermaid.run({ nodes: Array.from(diagrams) }).catch(() => {});
		});
		return () => {
			cancelled = true;
		};
	});
</script>

{#key doc.slug}
	<article class="doc-article">
		<!-- eslint-disable-next-line svelte/no-at-html-tags — content is our own trusted markdown -->
		<div class="doc-prose" bind:this={prose}>{@html doc.html}</div>

		<nav class="doc-pager">
			{#if doc.prev}
				<a class="doc-pager-link prev" href={hrefFor(doc.prev.slug)}>
					<span class="dp-dir">← Previous</span>
					<b>{doc.prev.title}</b>
				</a>
			{:else}
				<span></span>
			{/if}
			{#if doc.next}
				<a class="doc-pager-link next" href={hrefFor(doc.next.slug)}>
					<span class="dp-dir">Next →</span>
					<b>{doc.next.title}</b>
				</a>
			{/if}
		</nav>
	</article>
{/key}
