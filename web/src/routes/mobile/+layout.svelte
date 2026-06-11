<script lang="ts">
	import { page } from '$app/state';

	let { children } = $props();

	const path = $derived(page.url.pathname);

	function desktopSite() {
		document.cookie = 'ezra-view=desktop; path=/; max-age=2592000; samesite=lax';
		location.href = '/';
	}

	const TABS = [
		{ href: '/mobile', label: 'Home', icon: '◆' },
		{ href: '/mobile/pitch', label: 'Pitch', icon: '▤' },
		{ href: '/mobile/dashboard', label: 'Live', icon: '◉' },
		{ href: '/docs', label: 'Docs', icon: '✎' }
	];
</script>

<div class="m-shell">
	<header class="m-top">
		<a class="m-brand" href="/mobile">
			<img src="/ezra-logo.svg" alt="Ezra" />
		</a>
		<button class="m-desktop" onclick={desktopSite}>Desktop site</button>
	</header>

	<main class="m-main">
		{@render children()}
	</main>

	<nav class="m-tabs" aria-label="Mobile navigation">
		{#each TABS as tab (tab.href)}
			<a
				class="m-tab"
				class:active={tab.href === '/mobile' ? path === '/mobile' : path.startsWith(tab.href)}
				href={tab.href}
			>
				<span class="m-tab-icon" aria-hidden="true">{tab.icon}</span>
				<span class="m-tab-label">{tab.label}</span>
			</a>
		{/each}
	</nav>
</div>

<style>
	.m-shell {
		min-height: 100vh;
		min-height: 100dvh;
		display: flex;
		flex-direction: column;
		background: var(--bg);
	}

	/* ── Top bar ── */
	.m-top {
		position: sticky;
		top: 0;
		z-index: 10;
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 14px 18px;
		padding-top: calc(14px + env(safe-area-inset-top));
		background: color-mix(in srgb, var(--bg) 88%, transparent);
		backdrop-filter: blur(12px);
		border-bottom: 1px solid var(--line);
	}
	.m-brand img {
		height: 20px;
		display: block;
	}
	.m-desktop {
		background: none;
		border: 1px solid var(--line);
		color: var(--fg-3);
		font-family: var(--f-mono);
		font-size: 10px;
		letter-spacing: 0.14em;
		text-transform: uppercase;
		padding: 7px 12px;
		cursor: pointer;
	}

	/* ── Main ── */
	.m-main {
		flex: 1;
		padding-bottom: calc(76px + env(safe-area-inset-bottom));
	}

	/* ── Bottom tab bar ── */
	.m-tabs {
		position: fixed;
		left: 0;
		right: 0;
		bottom: 0;
		z-index: 10;
		display: grid;
		grid-template-columns: repeat(4, 1fr);
		background: color-mix(in srgb, var(--bg-2) 92%, transparent);
		backdrop-filter: blur(14px);
		border-top: 1px solid var(--line);
		padding-bottom: env(safe-area-inset-bottom);
	}
	.m-tab {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 3px;
		padding: 10px 4px 12px;
		min-height: 56px;
		text-decoration: none;
		color: var(--fg-4);
		transition: color 0.15s;
	}
	.m-tab.active {
		color: var(--accent);
	}
	.m-tab-icon {
		font-size: 16px;
		line-height: 1;
	}
	.m-tab-label {
		font-family: var(--f-mono);
		font-size: 9.5px;
		letter-spacing: 0.14em;
		text-transform: uppercase;
	}
</style>
