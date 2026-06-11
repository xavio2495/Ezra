// Mirrors ezra_core/schemas/audit.py — the honest source of truth the right
// column derives from. Keep in sync with the platform schema.
export type AuditEventType =
	| 'agent_spawned'
	| 'federated_fetch'
	| 'fetch_denied'
	| 'belief_committed'
	| 'contradiction_detected'
	| 'contradiction_reconciled'
	| 'belief_reverted'
	| 'belief_rewound';

export interface AuditEvent {
	id: string;
	session_graph_id: string;
	agent_id: string | null;
	event_type: AuditEventType;
	topic: string | null;
	detail: Record<string, unknown>;
	created_at: string;
}

// The `message` SSE channel — one agent turn's output for a chat pane.
export interface AgentMessage {
	agent_id: string;
	role: 'user' | 'agent';
	text: string;
	committed?: { topic: string; claim: string } | null;
	created_at: string;
}

export interface AgentInfo {
	id: string;
	role: string;
	scope: string[];
	prefill: string;
	// Set once the conductor reports the agent spawned (agent_spawned event).
	spawned: boolean;
}

export type ConnectionState = 'disconnected' | 'connecting' | 'live';

// GET /demo/beliefs — the append-only commitment log (cold tier). Drives the
// branch graph, the revert-target picker, and the cold-tier view.
export interface Belief {
	id: string;
	agent_id: string;
	topic: string;
	claim: string;
	type: string;
	turn_index: number;
	trust_score: number;
	superseded_by: string | null;
	redacted: boolean;
	is_marker: boolean;
	active: boolean;
	created_at: string;
}

// GET /demo/tiers — snapshot of the three memory tiers.
export interface Tiers {
	hot: Record<string, { turns: unknown[]; pinned: unknown[] }>;
	warm: Record<string, unknown>[];
	cold: { belief_count: number };
}

// GET /demo/branches — counterfactual branches the presenter created.
export interface BranchRecord {
	branch_id: string;
	from_turn: number;
	counterfactual: { agent_id: string; topic: string; claim: string };
	diverged: { topic: string; only_in_original: string[]; only_in_branch: string[] }[];
}
