<script lang="ts">
	import './layout.css';
	import NavBar from '$lib/components/NavBar.svelte';
	import Footer from '$lib/components/Footer.svelte';

	let { children } = $props();
</script>

<div class="page-frame" aria-hidden="true"></div>
<div class="grain"></div>

<NavBar />
{@render children()}
<Footer />
