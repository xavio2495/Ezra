import type { AgentInfo } from './types';

// Mirrors demo/f1_race_weekend/agents/roles.py (ids, roles, permission scopes)
// and the climax-tuned briefings in demo/f1_race_weekend/adk_runtime/fleet.py
// (FLEET_PROMPTS). The presenter clicks through these pre-fills; the two tyres
// contestants MUST be prompted in order (race_strategy first, tyre_engineer
// second) so the lower-trust commit lands first and highest_trust → accept_new.
export const FLEET_AGENTS: AgentInfo[] = [
	{
		id: 'race_strategy',
		role: 'Race Strategist',
		scope: ['strategy', 'tyres'],
		prefill:
			"Lap 45 at Monaco. Call fetch_federated once for historical Monaco results " +
			"(topic 'strategy') to ground your call. Track position is critical and the " +
			"softs are the fastest compound. You MUST then call commit_belief on topic " +
			"'tyres' with EXACTLY this claim and nothing else: 'Final stint: softs.' Do " +
			'not end your turn until you have called commit_belief once. Commit now.',
		spawned: false
	},
	{
		id: 'tyre_engineer',
		role: 'Tyre Engineer',
		scope: ['tyres'],
		prefill:
			'Lap 45 at Monaco. Rear surface temps are 52°C and the softs are graining and ' +
			'will not last — you must protect tyre life with the hard compound. You MUST ' +
			"call commit_belief on topic 'tyres' with EXACTLY this claim and nothing else: " +
			"'Final stint: hards.' Do not end your turn until you have called commit_belief " +
			'once. Commit now.',
		spawned: false
	},
	{
		id: 'aero_rd',
		role: 'Aero R&D Engineer',
		scope: ['aero'],
		prefill:
			'Monaco final stint. First call fetch_federated for historical results (topic ' +
			"'aero') for context, then commit one short downforce recommendation as a " +
			"belief on topic 'aero'. Call commit_belief exactly once, then stop.",
		spawned: false
	},
	{
		id: 'logistics',
		role: 'Logistics Coordinator',
		scope: ['parts', 'supplier', 'calendar'],
		prefill:
			'Confirm the parts and logistics posture for the final stint. Commit one short ' +
			"belief on topic 'parts'. Call commit_belief exactly once, then stop.",
		spawned: false
	},
	{
		id: 'telemetry_analyst',
		role: 'Telemetry Analyst',
		scope: ['telemetry'],
		prefill:
			"Summarise the car's current telemetry posture and commit one short belief on " +
			"topic 'telemetry'. Call commit_belief exactly once, then stop.",
		spawned: false
	},
	{
		id: 'weather_model',
		role: 'Weather Modeller',
		scope: ['weather'],
		prefill:
			'Radar shows a 30% chance of light rain in ~15 minutes. Commit your forecast as ' +
			"a belief on topic 'weather' in one short sentence. Call commit_belief exactly " +
			'once, then stop.',
		spawned: false
	}
];
