// Markdown → HTML rendering for the docs hub. `marked` parses; `highlight.js`
// colours code blocks; ```mermaid fences are emitted as <pre class="mermaid">
// (raw, HTML-escaped source) for client-side rendering in DocContent. Heading ids
// are injected by post-processing so anchors + the on-this-page TOC stay in sync.

import { marked } from 'marked';
import hljs from 'highlight.js';

function escapeHtml(s: string): string {
	return s
		.replace(/&/g, '&amp;')
		.replace(/</g, '&lt;')
		.replace(/>/g, '&gt;')
		.replace(/"/g, '&quot;');
}

marked.use({
	gfm: true,
	renderer: {
		code({ text, lang }: { text: string; lang?: string }): string {
			const language = (lang ?? '').trim().split(/\s+/)[0];
			if (language === 'mermaid') {
				// Raw source for mermaid.run() — the browser decodes entities via textContent.
				return `<pre class="mermaid">${escapeHtml(text)}</pre>`;
			}
			const valid = language && hljs.getLanguage(language) ? language : 'plaintext';
			const html = hljs.highlight(text, { language: valid }).value;
			return `<pre><code class="hljs language-${valid}">${html}</code></pre>`;
		}
	}
});

export interface Heading {
	id: string;
	text: string;
	level: number;
}

function slugify(text: string): string {
	return text
		.toLowerCase()
		.replace(/<[^>]+>/g, '')
		.replace(/[^\w\s-]/g, '')
		.trim()
		.replace(/\s+/g, '-');
}

export function renderMarkdown(md: string): { html: string; headings: Heading[] } {
	const headings: Heading[] = [];
	const used = new Set<string>();
	let html = marked.parse(md, { async: false }) as string;

	// Inject stable ids into headings and collect h2/h3 for the page TOC.
	html = html.replace(/<h([1-4])>([\s\S]*?)<\/h\1>/g, (_match, level: string, inner: string) => {
		const text = inner.replace(/<[^>]+>/g, '').trim();
		let id = slugify(text) || 'section';
		let n = 2;
		const base = id;
		while (used.has(id)) id = `${base}-${n++}`;
		used.add(id);
		const depth = Number(level);
		if (depth === 2 || depth === 3) headings.push({ id, text, level: depth });
		return `<h${level} id="${id}">${inner}</h${level}>`;
	});

	return { html, headings };
}
