"""Two asynchronous, non-blocking meta-agents (both enabled by default).

``LearningMetaAgent`` runs after router step 8 every turn (memory write scoring,
core/archival promotion, damped trust updates). ``LifecycleMetaAgent`` runs on a
schedule (state transitions, archival compaction, belief-retention TTL, GDPR
tombstones). Both operate over the existing stores — no new persistence ports.
"""

from ezra_core.meta_agent.learning import LearningMetaAgent, LearningReport
from ezra_core.meta_agent.lifecycle import LifecycleMetaAgent, LifecycleReport

__all__ = [
    "LearningMetaAgent",
    "LearningReport",
    "LifecycleMetaAgent",
    "LifecycleReport",
]
