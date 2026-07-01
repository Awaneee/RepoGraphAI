"""
generate_candidates.py
======================
Scans all repositories (RepoGraphAI and cloned dependencies), extracts public APIs,
scores them, generates candidate questions, and outputs generated_candidates.json.
"""

from __future__ import annotations
import os
import sys
import json
import uuid
import math
from pathlib import Path

# Bootstrap paths
SCRIPTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPTS_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.parsers.code_parser import CodeParser
from app.graph.graph_builder import GraphBuilder
from app.evaluation.graph_interface import is_stable_public_symbol, analyze_graph_importance
from app.evaluation.template_engine import generate_questions_for_symbol
from app.evaluation.quality_scoring import compute_importance_score, score_question

# Repository configurations
REPOS_DIR = PROJECT_ROOT / "repos"
REPOSITORIES = {
    "RepoGraphAI": PROJECT_ROOT / "app",
    "FastAPI": REPOS_DIR / "fastapi",
    "Typer": REPOS_DIR / "typer",
    "Requests": REPOS_DIR / "requests"
}

def main():
    print("=" * 60)
    print("  REPO GRAPH AI — BENCHMARK CANDIDATE GENERATION")
    print("=" * 60)
    
    all_candidates = []
    
    # Track statistics
    stats = {
        "repositories": {},
        "total_public_symbols": 0,
        "total_raw_candidates": 0,
        "total_accepted_candidates": 0
    }

    # 1. Generate candidates for each repository
    for repo_name, repo_path in REPOSITORIES.items():
        if not repo_path.exists():
            print(f"[WARN] Repository {repo_name} not found at {repo_path}. Skipping.")
            continue
            
        print(f"\nProcessing repository: {repo_name}...")
        
        # Parse repository
        print("  Parsing AST...")
        parsed_repo = CodeParser().parse_repository(str(repo_path))
        
        # Build graph using existing pipeline
        print("  Building RepositoryGraph...")
        graph = GraphBuilder().build_graph(parsed_repo)
        
        # Find public API symbols
        public_nodes = [node for node in graph.nodes if is_stable_public_symbol(node)]
        stats["total_public_symbols"] += len(public_nodes)
        print(f"  Found {len(public_nodes)} public stable API symbols (out of {len(graph.nodes)} total nodes).")
        
        # Compute graph importance metrics
        print("  Computing graph-derived importance metrics...")
        importance_metrics = analyze_graph_importance(graph)
        
        repo_candidates = []
        
        for node in public_nodes:
            importance_score = compute_importance_score(node.id, importance_metrics)
            
            # Generate candidate questions
            question_templates = generate_questions_for_symbol(node)
            stats["total_raw_candidates"] += len(question_templates)
            
            # Score each candidate question
            for qt in question_templates:
                question = qt["question"]
                category = qt["category"]
                temp_family = qt["template_family"]
                
                q_score, reason = score_question(
                    question=question,
                    expected_node_id=node.id,
                    all_public_nodes=public_nodes,
                    all_metrics=importance_metrics,
                    importance_score=importance_score
                )
                
                # Create candidate record
                deterministic_id = str(uuid.uuid5(
                    uuid.NAMESPACE_DNS, 
                    f"{repo_name}:{node.id}:{question}"
                ))
                
                candidate = {
                    "id": deterministic_id,
                    "question": question,
                    "expected_symbol": node.id,
                    "repository": repo_name,
                    "category": category,
                    "quality_score": q_score,
                    "generation_reason": reason,
                    "template_family": temp_family,
                    "review_status": "candidate",
                    "review_notes": "",
                    "benchmark_version": "v2_candidates"
                }
                
                if q_score > 0.0:
                    repo_candidates.append(candidate)
                    
        print(f"  Generated {len(repo_candidates)} valid (non-ambiguous) candidate questions.")
        stats["repositories"][repo_name] = {
            "public_symbols": len(public_nodes),
            "valid_candidates": len(repo_candidates)
        }
        all_candidates.extend(repo_candidates)

    stats["total_accepted_candidates"] = len(all_candidates)
    print("\n" + "-" * 60)
    print(f"Total accepted valid candidates across all repos: {len(all_candidates)}")
    print("-" * 60)

    # 2. Balancing Strategy: Category-based round-robin selection
    print("\nApplying balancing strategy (category-based round-robin)...")
    
    # Group candidates by category
    categories = {}
    for c in all_candidates:
        categories.setdefault(c["category"], []).append(c)
        
    balanced_selection = []
    
    # We want around 100 questions total, which is roughly 9-10 per category
    target_total = 100
    num_categories = len(categories)
    target_per_category = max(1, math.ceil(target_total / num_categories))
    
    for cat_name, cat_candidates in categories.items():
        # Group by repository within category
        repo_groups = {}
        for c in cat_candidates:
            repo_groups.setdefault(c["repository"], []).append(c)
            
        # Sort each repository's candidates by quality score descending
        for repo_name in repo_groups:
            # Sort by quality score, then break ties deterministically by symbol/question
            repo_groups[repo_name].sort(
                key=lambda x: (x["quality_score"], x["expected_symbol"], x["question"]), 
                reverse=True
            )
            
        # Select round-robin
        cat_selected = []
        repos_list = sorted(list(repo_groups.keys()))
        repo_indices = {r: 0 for r in repos_list}
        
        while len(cat_selected) < target_per_category:
            added_any = False
            for repo_name in repos_list:
                idx = repo_indices[repo_name]
                group = repo_groups[repo_name]
                if idx < len(group):
                    cat_selected.append(group[idx])
                    repo_indices[repo_name] += 1
                    added_any = True
                    if len(cat_selected) >= target_per_category:
                        break
            if not added_any:
                break
                
        balanced_selection.extend(cat_selected)

    print(f"Balanced selection contains {len(balanced_selection)} questions.")
    
    # 3. Write candidates to file
    output_path = PROJECT_ROOT / "generated_candidates.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(balanced_selection, f, indent=2)
        
    print(f"Candidates successfully written to {output_path}")

    # Write stats summary
    print("\nGeneration Statistics Summary:")
    for r, r_stats in stats["repositories"].items():
        print(f"  {r:<15}: {r_stats['public_symbols']:>4} public symbols, {r_stats['valid_candidates']:>4} valid candidates")
    print(f"Total raw candidate templates generated: {stats['total_raw_candidates']}")

if __name__ == "__main__":
    main()
