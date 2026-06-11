// Guided walkthrough — an onboarding-style tour that auto-drives the fleet,
// switches the right-column tab per step, and narrates what Ezra is doing.
// A singleton like `demo`; the page sets the tab from `requestedTab` and renders
// the narration overlay from this state.
import { demo } from './state.svelte';
import { FLEET_AGENTS } from './agents';

const prefill = (id: string) => FLEET_AGENTS.find((a) => a.id === id)?.prefill ?? '';

interface Step {
	title: string;
	body: string;
	tab?: string; // right-column tab to reveal
	dwell?: number; // ms to linger before auto-advancing
	run?: () => Promise<void>; // optional action to perform on entry
}

const STEPS: Step[] = [
	{
		title: 'Ezra · live multi-agent fleet',
		body: 'Six specialist F1 agents share federated memory and a versioned audit trail over real Atlas, Snowflake & Vertex. Spawning the fleet…',
		tab: 'graph',
		dwell: 5500,
		run: async () => {
			if (!demo.graphId) await demo.start();
		}
	},
	{
		title: 'Federated, scoped data',
		body: 'The Race Strategist queries historical Monaco results from Snowflake — scoped to its permissions, with provenance. Watch the Data Access tab. (A live Vertex turn — give it a moment.)',
		tab: 'data',
		dwell: 4000,
		run: async () => {
			await demo.prompt('race_strategy', prefill('race_strategy'));
		}
	},
	{
		title: 'Shared belief store',
		body: 'Its call — "Final stint: softs." — is committed to the shared belief store. The graph shows the commit edge from the agent into the store.',
		tab: 'graph',
		dwell: 5500
	},
	{
		title: 'Cross-agent contradiction',
		body: 'Now the Tyre Engineer argues "hards". Two agents, one topic, opposite calls — Ezra detects the contradiction with a two-pass check (embedding cosine → NLI).',
		tab: 'graph',
		dwell: 4000,
		run: async () => {
			await demo.prompt('tyre_engineer', prefill('tyre_engineer'));
		}
	},
	{
		title: 'Detect → reconcile',
		body: 'The audit feed is the source of truth: contradiction_detected, then contradiction_reconciled — resolved by highest_trust (the higher-trust "hards" supersedes "softs").',
		tab: 'audit',
		dwell: 7000
	},
	{
		title: 'Three-tier federated memory',
		body: 'Commitments persist to the cold tier (Atlas, append-only); recent turns live in hot (Redis); scoped vector summaries in warm (Qdrant). Each agent only ever sees its scope.',
		tab: 'memory',
		dwell: 7000
	},
	{
		title: 'Branching replay',
		body: 'Fork the timeline into a counterfactual ("wets called at lap 43") and Ezra diffs the branches — a git-like history of every commitment.',
		tab: 'branch',
		dwell: 6500,
		run: async () => {
			await demo.branch();
		}
	},
	{
		title: 'Presenter controls',
		body: 'Every step is reversible and audited: revert a specific commitment or rewind to a turn — from the control strip, or the ⎌ / ↶ / ⑂ actions on each Audit row. Append-only; nothing is lost.',
		tab: 'audit',
		dwell: 7500
	},
	{
		title: 'That’s Ezra',
		body: 'Federated scoped memory · cross-agent belief reconciliation · branching replay · full replayable audit. The walkthrough is done — explore freely, or focus any agent chat with ⤢.',
		dwell: 6000
	}
];

class TourState {
	running = $state(false);
	index = $state(0);
	title = $state('');
	body = $state('');
	requestedTab = $state<string | null>(null);
	readonly total = STEPS.length;

	#aborted = false;
	#timer: ReturnType<typeof setTimeout> | null = null;
	#resolve: (() => void) | null = null;

	async start(): Promise<void> {
		if (this.running) return;
		this.running = true;
		this.#aborted = false;
		for (this.index = 0; this.index < STEPS.length; this.index++) {
			if (this.#aborted) break;
			const s = STEPS[this.index];
			this.title = s.title;
			this.body = s.body;
			if (s.tab) this.requestedTab = s.tab;
			if (s.run) {
				try {
					await s.run();
				} catch {
					/* a slow/failed live turn shouldn't break the tour */
				}
			}
			if (this.#aborted) break;
			await this.#delay(s.dwell ?? 5000);
		}
		this.running = false;
	}

	skip(): void {
		// resolve the current dwell early → jump to the next step
		if (this.#timer) clearTimeout(this.#timer);
		this.#timer = null;
		this.#resolve?.();
		this.#resolve = null;
	}

	stop(): void {
		this.#aborted = true;
		this.running = false;
		this.skip();
	}

	#delay(ms: number): Promise<void> {
		return new Promise<void>((resolve) => {
			this.#resolve = resolve;
			this.#timer = setTimeout(() => {
				this.#timer = null;
				this.#resolve = null;
				resolve();
			}, ms);
		});
	}
}

export const tour = new TourState();
