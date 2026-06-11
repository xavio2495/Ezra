// Client-rendered SPA: the conductor serves the built static bundle and the app
// talks to it over fetch/SSE at runtime. No prerender / no SSR.
export const ssr = false;
export const prerender = false;
