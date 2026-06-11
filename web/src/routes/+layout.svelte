<script lang="ts">
	import './layout.css';
	import { page } from '$app/state';
	import NavBar from '$lib/components/NavBar.svelte';
	import Footer from '$lib/components/Footer.svelte';

	let { children } = $props();

	// The /mobile experience ships its own chrome (top bar + bottom tab nav).
	const isMobileRoute = $derived(page.url.pathname.startsWith('/mobile'));
</script>

<div class="page-frame" aria-hidden="true"></div>
<div class="grain"></div>

{#if !isMobileRoute}
	<NavBar />
{/if}
{@render children()}
{#if !isMobileRoute}
	<Footer />
{/if}
