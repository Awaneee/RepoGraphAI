"""
quality_scoring.py
==================
Deterministic quality scoring system for generated questions and symbols
based on graph importance and question-level ambiguity/uniqueness checks.
"""

from __future__ import annotations
import re
from typing import Optional
from app.models.pydantic_models import GraphNode, NodeType

# Stop words to filter out when checking keyword matches
STOP_WORDS = {
    "how", "what", "why", "when", "where", "which", "who", "whom", "is", "are", 
    "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", 
    "did", "a", "an", "the", "and", "but", "or", "in", "on", "at", "by", "for", 
    "with", "about", "to", "from", "of", "process", "implementation", "implemented", 
    "work", "generic", "handler", "helper", "class", "function", "method"
}

def levenshtein_distance(s1: str, s2: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
        
    return previous_row[-1]

def is_nearly_identical(name1: str, name2: str) -> bool:
    """Check if two symbol names are nearly identical (singular/plural or off by 1 char)."""
    name1 = name1.lower()
    name2 = name2.lower()
    if name1 == name2:
        return True
    if name1 + "s" == name2 or name2 + "s" == name1:
        return True
    if name1 + "es" == name2 or name2 + "es" == name1:
        return True
    if levenshtein_distance(name1, name2) <= 1:
        return True
    return False

def compute_importance_score(
    node_id: str,
    all_metrics: dict[str, dict[str, float]]
) -> float:
    """
    Compute normalized symbol-level importance score from graph metrics.
    Signals used:
      - node degree (weighted 0.3)
      - incoming reference count (weighted 0.4)
      - PageRank (weighted 0.3)
    """
    if not all_metrics or node_id not in all_metrics:
        return 0.0

    node_metric = all_metrics[node_id]
    
    # Extract max values across all nodes for normalization
    max_degree = max((m["degree"] for m in all_metrics.values()), default=1.0)
    max_ref = max((m["reference_count"] for m in all_metrics.values()), default=1.0)
    max_pr = max((m["pagerank"] for m in all_metrics.values()), default=1.0)

    # Avoid division by zero
    norm_degree = node_metric["degree"] / max_degree if max_degree > 0 else 0.0
    norm_ref = node_metric["reference_count"] / max_ref if max_ref > 0 else 0.0
    norm_pr = node_metric["pagerank"] / max_pr if max_pr > 0 else 0.0

    importance = 0.3 * norm_degree + 0.4 * norm_ref + 0.3 * norm_pr
    return float(round(importance, 4))

def extract_query_keywords(question: str) -> list[str]:
    """Tokenize and extract meaningful keywords from the question."""
    # Remove punctuation and lowercase
    cleaned = re.sub(r'[^\w\s]', '', question.lower())
    words = cleaned.split()
    return [w for w in words if w not in STOP_WORDS and len(w) > 1]

def get_matching_nodes_count(
    keywords: list[str],
    all_public_nodes: list[GraphNode]
) -> list[str]:
    """Find all public nodes whose label or ID matches all given keywords."""
    matching_ids = []
    for node in all_public_nodes:
        # Check both label and ID
        text = f"{node.id} {node.label}".lower()
        if all(kw in text for kw in keywords):
            matching_ids.append(node.id)
    return matching_ids

def score_question(
    question: str,
    expected_node_id: str,
    all_public_nodes: list[GraphNode],
    all_metrics: dict[str, dict[str, float]],
    importance_score: float
) -> tuple[float, str]:
    """
    Evaluate the quality of a question candidate.
    Returns:
      - quality_score: score between 0.0 and 1.0 (0.0 means rejected)
      - reason: string explanation of the score or rejection reason
    """
    # 1. Basic Syntactic/Clarity Checks
    if not (question.startswith("How ") or question.startswith("What ")):
        return 0.0, "Rejection: Question must start with 'How' or 'What'"
    if not question.endswith("?"):
        return 0.0, "Rejection: Question must end with '?'"
    if "  " in question:
        return 0.0, "Rejection: Question contains double spaces"

    # Extract clean label parts to check for nearly identical symbols
    expected_node = next((n for n in all_public_nodes if n.id == expected_node_id), None)
    if not expected_node:
        return 0.0, f"Rejection: Expected node '{expected_node_id}' not found in public nodes"

    expected_label = expected_node.label
    if "." in expected_label:
        expected_label = expected_label.split(".")[-1]

    # 2. Check for nearly identical public symbol names in the graph (Ambiguity check)
    for node in all_public_nodes:
        if node.id == expected_node_id:
            continue
        other_label = node.label
        if "." in other_label:
            other_label = other_label.split(".")[-1]
            
        if is_nearly_identical(expected_label, other_label):
            # If they have nearly identical names, reject the question to avoid ambiguity
            return 0.0, f"Rejection: Ambiguous symbol naming (nearly identical to {node.id})"

    # 3. Check for Keyword Ambiguity (does the question match multiple symbols?)
    keywords = extract_query_keywords(question)
    if not keywords:
        return 0.0, "Rejection: Question has no meaningful keywords"

    matching_nodes = get_matching_nodes_count(keywords, all_public_nodes)
    
    # If the question matches other symbols besides the expected one, reject it
    if len(matching_nodes) > 1:
        # Check if they are actually different (not just subcomponents)
        other_matches = [nid for nid in matching_nodes if nid != expected_node_id]
        return 0.0, f"Rejection: Ambiguous wording (matches other public symbols: {', '.join(other_matches[:3])})"

    # 4. Generic Verb / Wording Check
    generic_verbs = {"build", "process", "handle", "execute", "run"}
    question_words = question.lower().split()
    question_verb = question_words[1] if len(question_words) > 1 else ""
    if question_verb in generic_verbs:
        # Check if there are other nodes with the same noun category
        # E.g. "How is graph built?" vs other built things.
        # If we have multiple candidates containing the noun phrase, reject it
        noun_keywords = [kw for kw in keywords if kw != question_verb]
        if noun_keywords:
            similar_nouns = [n.id for n in all_public_nodes if any(kw in n.id.lower() for kw in noun_keywords)]
            if len(similar_nouns) > 1:
                return 0.0, f"Rejection: Uses generic verb '{question_verb}' with ambiguous noun context"

    # 5. Compute Clarity/Clarity Score
    # Give points for clean structure
    clarity_score = 1.0
    
    # Penalize overly generic names in the question
    if any(gw in question.lower() for gw in ["helper", "util", "temp", "tmp", "dummy"]):
        clarity_score -= 0.3
        
    # Reward specific length (not too short, not too long)
    words_count = len(question.split())
    if words_count < 4 or words_count > 10:
        clarity_score -= 0.2

    # 6. Combined Final Quality Score
    # 60% importance score (structural value) + 40% clarity score
    final_score = 0.6 * importance_score + 0.4 * clarity_score
    final_score = max(0.0, min(1.0, final_score))
    
    reason = f"Accepted: Importance={importance_score:.2f}, Clarity={clarity_score:.2f}"
    return float(round(final_score, 4)), reason
