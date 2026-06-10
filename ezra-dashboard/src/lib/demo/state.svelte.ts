import type { AgentInfo, AgentMessage, AuditEvent, ConnectionState } from './types';
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
	busyAgents = $state<Record<string, boolean>>({});
	error = $state<string | null>(null);

	#source: EventSource | null = null;

	messagesFor(agentId: string): AgentMessage[] {
		return this.messages.filter((m) => m.agent_id === agentId);
	}

	async start(): Promise<void> {
		this.error = null;
		const res = await this.#post('/demo/start');
		if (res) {
			this.graphId = (res as { graph_id: string }).graph_id;
			this.connect();
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
		}
	}

	async rewind(): Promise<void> {
		await this.#post('/demo/rewind');
	}

	async revert(): Promise<void> {
		await this.#post('/demo/revert');
	}

	async branch(): Promise<void> {
		await this.#post('/demo/branch');
	}

	#markSpawned(agentId: string): void {
		const known = this.agents.find((a) => a.id === agentId);
		if (known) {
			known.spawned = true;
		} else {
			// Emergent spawn mid-demo (e.g. parts_shortage) — grid grows.
			this.agents.push({
				id: agentId,
				role: agentId,
				scope: [],
				prefill: '',
				spawned: true
			});
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
}

export const demo = new DemoState();
