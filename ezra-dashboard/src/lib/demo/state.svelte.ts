import type {
	AgentInfo,
	AgentMessage,
	AuditEvent,
	Belief,
	BranchRecord,
	ConnectionState,
	Tiers
} from './types';
import { FLEET_AGENTS } from './agents';

// Conductor API base. Same-origin in production (the conductor serves this UI);
// override via VITE_CONDUCTOR_URL for local dev against a remote conductor.
const BASE = import.meta.env.VITE_CONDUCTOR_URL ?? '';

class DemoState {
	connection = $state<ConnectionState>('disconnected');
	graphId = $state<string | null>(null);
	agents = $state<AgentInfo[]>(FLEET_AGENTS.map((a) => ({ ...a })));
	messages = $state<AgentMessage[]>([]);
	// The honest source of truth: right-column tabs derive purely from this feed.
	auditEvents = $state<AuditEvent[]>([]);
	// Readback state (GET endpoints), refreshed as the feed advances.
	beliefs = $state<Belief[]>([]);
	tiers = $state<Tiers>({ hot: {}, warm: [], cold: { belief_count: 0 } });
	branches = $state<BranchRecord[]>([]);
	busyAgents = $state<Record<string, boolean>>({});
	error = $state<string | null>(null);

	#source: EventSource | null = null;
	#refreshTimer: ReturnType<typeof setTimeout> | null = null;

	messagesFor(agentId: string): AgentMessage[] {
		return this.messages.filter((m) => m.agent_id === agentId);
	}

	get activeBeliefs(): Belief[] {
		return this.beliefs.filter((b) => b.active);
	}

	async start(): Promise<void> {
		this.error = null;
		const res = await this.#post('/demo/start');
		if (res) {
			this.graphId = (res as { graph_id: string }).graph_id;
			this.connect();
			this.refreshState();
		}
	}

	connect(): void {
		if (this.#source) this.#source.close();
		this.connection = 'connecting';
		const source = new EventSource(`${BASE}/demo/stream`);
		this.#source = source;
		source.onopen = () => (this.connection = 'live');
		source.onerror = () => (this.connection = 'disconnected');
		source.addEventListener('message_event', (e) => {
			this.messages.push(JSON.parse(e.data) as AgentMessage);
		});
		source.addEventListener('audit', (e) => {
			const event = JSON.parse(e.data) as AuditEvent;
			this.auditEvents.push(event);
			if (event.event_type === 'agent_spawned' && event.agent_id) {
				this.#markSpawned(event.agent_id);
			}
			// The feed advanced → beliefs/tiers likely changed; refresh (debounced).
			this.#scheduleRefresh();
		});
	}

	disconnect(): void {
		this.#source?.close();
		this.#source = null;
		this.connection = 'disconnected';
	}

	async prompt(agentId: string, text: string): Promise<void> {
		this.busyAgents[agentId] = true;
		this.messages.push({
			agent_id: agentId,
			role: 'user',
			text,
			created_at: new Date().toISOString()
		});
		try {
			await this.#post(`/demo/agent/${agentId}/prompt`, { text });
		} finally {
			this.busyAgents[agentId] = false;
			this.refreshState();
		}
	}

	// Presenter ops — now targeted (a specific turn / commitment / counterfactual).
	async rewind(turn: number, reason = 'presenter rewind'): Promise<void> {
		await this.#post('/demo/rewind', { turn, reason });
		this.refreshState();
	}

	async revert(commitmentId: string | null = null, reason = 'presenter revert'): Promise<void> {
		await this.#post('/demo/revert', { commitment_id: commitmentId, reason });
		this.refreshState();
	}

	async branch(opts: Partial<BranchRecord['counterfactual']> & { from_turn?: number } = {}): Promise<void> {
		await this.#post('/demo/branch', {
			from_turn: opts.from_turn ?? 1,
			agent_id: opts.agent_id ?? 'race_strategy',
			topic: opts.topic ?? 'tyres',
			new_claim: opts.claim ?? 'wets called at lap 43'
		});
		this.refreshState();
	}

	async refreshState(): Promise<void> {
		const [beliefs, tiers, branches] = await Promise.all([
			this.#get('/demo/beliefs'),
			this.#get('/demo/tiers'),
			this.#get('/demo/branches')
		]);
		if (beliefs) this.beliefs = beliefs as Belief[];
		if (tiers) this.tiers = tiers as Tiers;
		if (branches) this.branches = branches as BranchRecord[];
	}

	#scheduleRefresh(): void {
		if (this.#refreshTimer) clearTimeout(this.#refreshTimer);
		this.#refreshTimer = setTimeout(() => this.refreshState(), 400);
	}

	#markSpawned(agentId: string): void {
		const known = this.agents.find((a) => a.id === agentId);
		if (known) {
			known.spawned = true;
		} else {
			// Emergent spawn mid-demo (e.g. parts_shortage) — grid grows.
			this.agents.push({ id: agentId, role: agentId, scope: [], prefill: '', spawned: true });
		}
	}

	async #post(path: string, body?: unknown): Promise<unknown | null> {
		try {
			const res = await fetch(`${BASE}${path}`, {
				method: 'POST',
				headers: { 'content-type': 'application/json' },
				body: body === undefined ? undefined : JSON.stringify(body)
			});
			if (!res.ok) {
				this.error = `${path} → ${res.status}`;
				return null;
			}
			return await res.json();
		} catch (err) {
			this.error = `${path} failed: ${err}`;
			return null;
		}
	}

	async #get(path: string): Promise<unknown | null> {
		try {
			const res = await fetch(`${BASE}${path}`);
			if (!res.ok) return null;
			return await res.json();
		} catch {
			return null;
		}
	}
}

export const demo = new DemoState();
