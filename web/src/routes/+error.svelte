<script lang="ts">
	import { page } from '$app/stores';
</script>

<svelte:head>
	<title>{$page.status} — Ezra</title>
</svelte:head>

<div class="error-shell">
	<div class="error-inner">
		<div class="error-code">{$page.status}</div>
		<div class="error-sep"></div>
		<h1 class="error-title">
			{#if $page.status === 404}
				Page not found.
			{:else if $page.status === 500}
				Server error.
			{:else}
				Something went wrong.
			{/if}
		</h1>
		<p class="error-desc">
			{#if $page.status === 404}
				The page you're looking for doesn't exist or has been moved.
			{:else}
				{$page.error?.message ?? 'An unexpected error occurred.'}
			{/if}
		</p>
		<div class="error-actions">
			<a class="err-btn" href="/">← Back to Ezra</a>
			<a class="err-btn ghost" href="/docs">Docs</a>
			<a class="err-btn ghost" href="/quickstart">Quick Start</a>
		</div>
		<div class="error-meta">
			<span>// EZRA</span>
			<span>·</span>
			<span>STATUS {$page.status}</span>
			<span>·</span>
			<span>PRE-LAUNCH v0.1.0</span>
		</div>
	</div>
</div>

<style>
	.error-shell {
		min-height: calc(100vh - var(--nav-h));
		display: flex;
		align-items: center;
		justify-content: center;
		padding: var(--gutter);
	}

	.error-inner {
		text-align: center;
		max-width: 560px;
	}

	.error-code {
		font-family: var(--f-display);
		font-style: italic;
		font-size: clamp(80px, 14vw, 180px);
		line-height: 0.9;
		color: var(--accent);
		letter-spacing: -0.04em;
		margin-bottom: 24px;
	}

	.error-sep {
		width: 60px;
		height: 1px;
		background: var(--accent);
		margin: 0 auto 24px;
		opacity: 0.5;
	}

	h1.error-title {
		margin: 0 0 12px;
		font-family: var(--f-sans);
		font-size: clamp(20px, 2.5vw, 32px);
		font-weight: 500;
		text-transform: uppercase;
		letter-spacing: -0.01em;
		color: var(--fg);
	}

	.error-desc {
		margin: 0 0 40px;
		font-family: var(--f-mono);
		font-size: 13px;
		color: var(--fg-3);
		line-height: 1.65;
	}

	.error-actions {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 12px;
		flex-wrap: wrap;
		margin-bottom: 48px;
	}

	.err-btn {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		padding: 10px 22px;
		font-family: var(--f-mono);
		font-size: 11px;
		letter-spacing: 0.16em;
		text-transform: uppercase;
		font-weight: 600;
		text-decoration: none;
		border: 1px solid var(--fg);
		color: var(--fg);
		background: transparent;
		transition: all 0.2s;
	}
	.err-btn:hover { background: var(--fg); color: var(--bg); }
	.err-btn.ghost { border-color: var(--line); color: var(--fg-3); }
	.err-btn.ghost:hover { border-color: var(--fg); color: var(--fg); background: transparent; }

	.error-meta {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 10px;
		font-family: var(--f-mono);
		font-size: 9.5px;
		letter-spacing: 0.2em;
		text-transform: uppercase;
		color: var(--fg-4);
	}
</style>
