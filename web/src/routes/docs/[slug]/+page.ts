import { redirect } from '@sveltejs/kit';
import { allSlugs, loadDoc } from '$lib/docs/nav';

export const load = ({ params }: { params: { slug: string } }) => {
	// The overview is canonical at /docs.
	if (params.slug === 'overview') redirect(308, '/docs');
	return { doc: loadDoc(params.slug) };
};

// Enumerate slugs so every page is prerendered even if the crawler misses a link.
export const entries = () =>
	allSlugs()
		.filter((s) => s !== 'overview')
		.map((slug) => ({ slug }));
