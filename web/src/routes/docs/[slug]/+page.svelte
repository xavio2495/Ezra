<script lang="ts">
	import DocContent from '$lib/components/DocContent.svelte';

	let { data } = $props();
</script>

<svelte:head>
	<title>{data.doc.title} — Ezra Docs</title>
	<meta name="description" content="Ezra documentation — {data.doc.title}." />
</svelte:head>

<DocContent doc={data.doc} />
