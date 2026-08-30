# scripts/run_ablation_v2.py
import json
import sys
from pathlib import Path
from typing import Optional

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.retrieval_metrics import (
    run_internal_benchmark,
    run_cross_repo_benchmark,
    aggregate_metrics,
)

def main():
    benchmark_path = PROJECT_ROOT / "tests" / "benchmarks" / "v2_curated.json"
    if not benchmark_path.exists():
        print(f"Error: Curated benchmark not found at {benchmark_path}")
        sys.exit(1)
        
    with open(benchmark_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    print(f"Loaded {len(data)} questions from custom benchmark {benchmark_path}")
    
    custom_internal = []
    custom_cross = {}
    for item in data:
        q_mapped = {
            "question": item["question"],
            "expected_symbols": [item["expected_symbol"]],
            "category": item["category"]
        }
        repo = item["repository"]
        if repo in ("RepoGraphAI", "internal"):
            custom_internal.append(q_mapped)
        else:
            custom_cross.setdefault(repo, []).append(q_mapped)

    # 4 Configurations to compare
    base_toggles = {
        "dto_fixes": False,
        "private_penalties": True,
        "dunder_penalties": True,
        "generate_build": False,
        "resolution_resolve": True,
        "retrieval_synonyms": True,
        "symbol_candidate": True,
        "file_module_penalty": True,
        "visualization_penalty": True,
        "verb_lexicon_cleanup": True,
    }

    configs = [
        ("Current Ranking", base_toggles.copy()),
        ("No DTO Penalty", {**base_toggles, "no_dto_penalty": True, "adaptive_dto_penalty": False, "entity_aware_ranking": False, "exception_inheritance_check": False}),
        ("Adaptive DTO Penalty", {**base_toggles, "no_dto_penalty": False, "adaptive_dto_penalty": True, "entity_aware_ranking": False, "exception_inheritance_check": True}),
        ("Adaptive DTO Penalty + Entity-Aware", {**base_toggles, "no_dto_penalty": False, "adaptive_dto_penalty": True, "entity_aware_ranking": True, "exception_inheritance_check": True}),
    ]

    results = []
    for label, toggles in configs:
        print(f"\nRunning evaluation for configuration: {label}...")
        metrics_internal = run_internal_benchmark(ablation_toggles=toggles, custom_questions=custom_internal)
        metrics_cross_dict = run_cross_repo_benchmark(ablation_toggles=toggles, custom_questions=custom_cross)
        
        # Flatten cross-repo results
        metrics_cross = []
        for lst in metrics_cross_dict.values():
            metrics_cross.extend(lst)
            
        all_qm = metrics_internal + metrics_cross
        valid = [qm for qm in all_qm if not qm.error]
        
        all_metrics = [
            {k: getattr(qm, k) for k in ["top_1", "top_3", "top_5", "mrr"]}
            for qm in valid
        ]
        agg = aggregate_metrics(all_metrics)
        results.append((label, agg))

    # Print markdown table
    print("\n" + "=" * 60)
    print("  ABLATION STUDY ON V2 CURATED BENCHMARK")
    print("=" * 60)
    print("| Configuration | Top-1 | Top-3 | Top-5 | MRR |")
    print("|---|---|---|---|---|")
    for label, agg in results:
        print(f"| {label:<35} | {agg.get('top_1', 0)*100:>5.1f}% | {agg.get('top_3', 0)*100:>5.1f}% | {agg.get('top_5', 0)*100:>5.1f}% | {agg.get('mrr', 0):>5.3f} |")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()
