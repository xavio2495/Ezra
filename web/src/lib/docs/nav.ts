// Docs navigation + content loading. Markdown lives in ./content/<slug>.md and is
// bundled at build time via import.meta.glob. NAV defines the sidebar order/groups.

import { error } from '@sveltejs/kit';
import { renderMarkdown, type Heading } from './render';

export interface NavItem {
	slug: string;
	title: string;
}
export interface NavGroup {
	group: string;
	items: NavItem[];
}

export const NAV: NavGroup[] = [
	{
		group: 'Getting Started',
		items: [
			{ slug: 'overview', title: 'Overview' },
			{ slug: 'quickstart', title: 'Quickstart' },
			{ slug: 'architecture', title: 'Architecture' }
		]
	},
	{
		group: 'Core Concepts',
		items: [
			{ slug: 'router', title: 'The 8-Step Router' },
			{ slug: 'memory', title: 'Three-Tier Memory' },
			{ slug: 'beliefs', title: 'Beliefs & Reconciliation' },
			{ slug: 'branching', title: 'Branching Replay' },
			{ slug: 'federation', title: 'Federated Query' },
			{ slug: 'meta-agents', title: 'Meta-Agents & Observability' }
		]
	},
	{
		group: 'Reference',
		items: [
			{ slug: 'sdk', title: 'Python SDK' },
			{ slug: 'rest-api', title: 'REST API' },
			{ slug: 'deployment', title: 'Deployment' }
		]
	}
];

const FLAT: NavItem[] = NAV.flatMap((g) => g.items);

// Canonical href: the overview lives at /docs; everything else at /docs/<slug>.
export function hrefFor(slug: string): string {
	return slug === 'overview' ? '/docs' : `/docs/${slug}`;
}

const RAW = import.meta.glob('./content/*.md', {
	query: '?raw',
	import: 'default',
	eager: true
}) as Record<string, string>;

const BY_SLUG: Record<string, string> = {};
for (const [path, content] of Object.entries(RAW)) {
	const slug = path.split('/').pop()!.replace(/\.md$/, '');
	BY_SLUG[slug] = content;
}

export interface LoadedDoc {
	slug: string;
	title: string;
	html: string;
	headings: Heading[];
	prev: NavItem | null;
	next: NavItem | null;
}

export function loadDoc(slug: string): LoadedDoc {
	const raw = BY_SLUG[slug];
	if (raw === undefined) throw error(404, `No docs page "${slug}"`);
	const { html, headings } = renderMarkdown(raw);
	const idx = FLAT.findIndex((i) => i.slug === slug);
	const item = FLAT[idx];
	return {
		slug,
		title: item?.title ?? slug,
		html,
		headings,
		prev: idx > 0 ? FLAT[idx - 1] : null,
		next: idx >= 0 && idx < FLAT.length - 1 ? FLAT[idx + 1] : null
	};
}

export function allSlugs(): string[] {
	return FLAT.map((i) => i.slug);
}
