import { redirect, type Handle } from '@sveltejs/kit';

// Phones get the purpose-built /mobile experience for the marketing surfaces;
// docs + quickstart stay on the responsive desktop pages. A visitor who picks
// "Desktop site" on mobile gets a cookie and is never redirected again.
// (Modern iPads report a desktop UA — they get the desktop site, which is fine.)
const MOBILE_UA = /Android|iPhone|iPod|Windows Phone|webOS|BlackBerry|Opera Mini|IEMobile/i;

const MOBILE_MIRRORS: Record<string, string> = {
	'/': '/mobile',
	'/pitch': '/mobile/pitch',
	'/dashboard': '/mobile/dashboard'
};

export const handle: Handle = async ({ event, resolve }) => {
	const target = MOBILE_MIRRORS[event.url.pathname];
	// UA test FIRST: prerender requests are never mobile, and touching
	// event.cookies during prerendering throws (build-time 500).
	const ua = event.request.headers.get('user-agent') ?? '';
	if (
		target &&
		MOBILE_UA.test(ua) &&
		!event.url.searchParams.has('desktop') && // one-off override, e.g. /dashboard?desktop=1
		event.cookies.get('ezra-view') !== 'desktop'
	) {
		redirect(307, target + event.url.search);
	}
	return resolve(event);
};
