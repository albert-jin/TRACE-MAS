"""
Rank-aware context routing utilities for TRACE-MAS.

The original EvoMAS runtime passes the full Context.reports dictionary to
downstream agents. TRACE-MAS makes that exposure explicit: reports can be
restricted to direct graph parents and optionally ranked before they are shown
to a target agent.
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Tuple


VALID_ROUTING_POLICIES = {"all", "direct_parents", "topk_similarity"}


def tokenize(text: str) -> set:
    """Tokenize text for a lightweight lexical similarity score."""
    return set(re.findall(r"[A-Za-z0-9_]+", (text or "").lower()))


def lexical_similarity(query: str, report: str) -> float:
    """Compute a simple Jaccard score between the task query and a report."""
    query_tokens = tokenize(query)
    report_tokens = tokenize(report)
    if not query_tokens or not report_tokens:
        return 0.0
    return len(query_tokens & report_tokens) / len(query_tokens | report_tokens)


def rank_reports(
    task: str,
    reports: Dict[str, str],
    strategy: str = "topk_similarity",
) -> List[Tuple[str, str, float]]:
    """Rank candidate reports for exposure to a downstream agent.

    Args:
        task: Original task/query.
        reports: Candidate reports keyed by source agent ID.
        strategy: Ranking strategy. Currently supports 'topk_similarity',
            'direct_parents', and 'all'. Non-ranking strategies preserve the
            insertion order with neutral scores.

    Returns:
        Tuples of (agent_id, report, score), sorted descending when ranked.
    """
    if strategy not in VALID_ROUTING_POLICIES:
        raise ValueError(
            f"Unknown TRACE-MAS routing policy: {strategy}. "
            f"Expected one of {sorted(VALID_ROUTING_POLICIES)}"
        )

    if strategy == "topk_similarity":
        ranked = [
            (agent_id, report, lexical_similarity(task, report))
            for agent_id, report in reports.items()
        ]
        ranked.sort(key=lambda item: (-item[2], item[0]))
        return ranked

    return [(agent_id, report, 0.0) for agent_id, report in reports.items()]


def select_visible_reports(
    *,
    task: str,
    all_reports: Dict[str, str],
    dependency_ids: Iterable[str],
    policy: str = "all",
    top_k: Optional[int] = None,
) -> Tuple[Dict[str, str], Dict[str, object]]:
    """Select and rank reports visible to one target agent.

    Args:
        task: Original task/query.
        all_reports: All reports currently available in Context.
        dependency_ids: Direct topology dependencies for the target agent.
        policy: 'all', 'direct_parents', or 'topk_similarity'.
        top_k: Optional maximum number of reports to expose.

    Returns:
        (visible_reports, routing_metadata)
    """
    if policy not in VALID_ROUTING_POLICIES:
        raise ValueError(
            f"Unknown TRACE-MAS routing policy: {policy}. "
            f"Expected one of {sorted(VALID_ROUTING_POLICIES)}"
        )
    if top_k is not None and top_k < 0:
        raise ValueError("context_top_k must be a non-negative integer or None")

    dependency_set = set(dependency_ids)

    if policy == "all":
        candidates = dict(all_reports)
    elif policy in {"direct_parents", "topk_similarity"}:
        candidates = {
            agent_id: report
            for agent_id, report in all_reports.items()
            if agent_id in dependency_set
        }

    ranked = rank_reports(task, candidates, strategy=policy)
    if policy != "all" and top_k is not None:
        ranked = ranked[:top_k]

    visible = {agent_id: report for agent_id, report, _ in ranked}
    metadata = {
        "policy": policy,
        "top_k": top_k,
        "top_k_applied": policy != "all" and top_k is not None,
        "candidate_agents": list(candidates.keys()),
        "selected_agents": [agent_id for agent_id, _, _ in ranked],
        "scores": {agent_id: score for agent_id, _, score in ranked},
    }
    return visible, metadata

