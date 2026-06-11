import tailwindcss from '@tailwindcss/vite';
import adapter from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [
		tailwindcss(),
		sveltekit({
			compilerOptions: {
				// Force runes mode for the project, except for libraries. Can be removed in svelte 6.
				runes: ({ filename }) => filename.split(/[/\\]/).includes('node_modules') ? undefined : true
			},

			// Static SPA: the conductor (FastAPI) serves the built UI single-origin
			// on GKE. `fallback` makes it a client-rendered SPA (see +layout.ts).
			adapter: adapter({ fallback: 'index.html' })
		})
	]
});
