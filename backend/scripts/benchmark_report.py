"""
benchmark_report.py
===================
Runs retrieval metrics against the curated benchmark, compares them with baseline/v1
metrics, performs regression analysis, and generates benchmark_generation_report.md.
"""

from __future__ import annotations
import os
import sys
import json
import subprocess
from pathlib import Path
from collections import Counter

# Bootstrap paths
SCRIPTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPTS_DIR.parent
WORKSPACE_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT))

def run_metrics_pipeline(benchmark_path: Path) -> dict:
    """Run retrieval_metrics.py as a subprocess and load results."""
    metrics_script = PROJECT_ROOT / "tests" / "retrieval_metrics.py"
    print(f"\nRunning retrieval metrics on: {benchmark_path}...")
    
    cmd = [sys.executable, str(metrics_script), "--benchmark", str(benchmark_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("Error running retrieval_metrics.py:")
        print(result.stderr)
        sys.exit(1)
        
    # Load retrieval_metrics.json
    results_json_path = PROJECT_ROOT / "tests" / "retrieval_metrics.json"
    if not results_json_path.exists():
        print(f"Error: Expected results file not found at {results_json_path}")
        sys.exit(1)
        
    with open(results_json_path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_baseline_metrics() -> dict:
    """Load baseline metrics from data/baseline_metrics.json."""
    baseline_path = PROJECT_ROOT / "data" / "baseline_metrics.json"
    if not baseline_path.exists():
        return {
            "top_1": 0.8333,
            "top_3": 0.9333,
            "top_5": 0.9667,
            "mrr": 0.879
        }
    with open(baseline_path, "r", encoding="utf-8") as f:
        return json.load(f)["metrics"]

def generate_report(
    candidates_count: int,
    curated_questions: list[dict],
    metrics_results: dict,
    baseline: dict,
    output_path: Path
):
    """Generate the benchmark_generation_report.md report file."""
    # Count distributions
    categories = [q["category"] for q in curated_questions]
    repos = [q["repository"] for q in curated_questions]
    
    cat_counts = Counter(categories)
    repo_counts = Counter(repos)
    
    # Extract overall metrics
    overall_metrics = metrics_results["overall"]
    
    # Find failing questions
    failing_questions = []
    per_dataset = metrics_results.get("per_dataset", {})
    for dataset_name, dataset_data in per_dataset.items():
        for q in dataset_data.get("questions", []):
            if q.get("pass_fail") == "FAIL" or q.get("first_hit_rank") is None or q.get("first_hit_rank") > 5:
                failing_questions.append(q)

    # Format distributions
    cat_dist_md = "\n".join([f"- **{cat}**: {count} questions" for cat, count in sorted(cat_counts.items())])
    repo_dist_md = "\n".join([f"- **{repo}**: {count} questions" for repo, count in sorted(repo_counts.items())])

    # Format change columns
    def fmt_change(new_val, old_val, is_percentage=True):
        diff = new_val - old_val
        sign = "+" if diff > 0 else ""
        if is_percentage:
            return f"{new_val*100:.1f}% ({sign}{diff*100:.1f}%)"
        else:
            return f"{new_val:.3f} ({sign}{diff:.3f})"

    # Format failures md
    failures_md = ""
    if failing_questions:
        failures_md += "\n### Regressed / Failing Questions Analysis\n\n"
        failures_md += "The following questions failed to retrieve the expected symbol in the top 5 results:\n\n"
        for idx, q in enumerate(failing_questions, 1):
            failures_md += f"#### {idx}. {q['question']}\n"
            failures_md += f"- **Repository**: {q['repository']}\n"
            failures_md += f"- **Expected Symbol**: `{q['expected_symbols'][0] if q['expected_symbols'] else ''}`\n"
            failures_md += f"- **First Hit Rank**: {q['first_hit_rank'] or 'Not Found'}\n"
            failures_md += "- **Top Retrieved Symbols**:\n"
            for r_id in q.get("retrieved_ids", [])[:3]:
                failures_md += f"  - `{r_id}`\n"
            failures_md += "- **Analysis**: "
            # Automated analysis of the failure
            retrieved = q.get("retrieved_ids", [])
            expected = q['expected_symbols'][0] if q['expected_symbols'] else ''
            if not retrieved:
                failures_md += "No symbols retrieved. This is a query resolver or indexing failure.\n"
            elif expected not in retrieved:
                failures_md += "Expected symbol not in top 5 retrieval. The query wording might need to be refined to better match the symbol label, or the symbol holds low centrality/importance in the graph.\n"
            else:
                failures_md += "Symbol retrieved but ranked outside the top 5.\n"
            failures_md += "\n"
    else:
        failures_md = "\n### Regressed / Failing Questions Analysis\n\nNo questions failed retrieval. Perfect Top-5 accuracy!\n"

    report_content = f"""# RepoGraphAI — Benchmark Generation Report

This report summarizes the creation, curation, and validation of the new automated, graph-native benchmark version.

## Benchmark Summary

- **Total Candidate Question Templates**: {candidates_count} candidates
- **Total Curated / Accepted Questions**: {len(curated_questions)} questions
- **Benchmark Version**: `v2_curated`

### Repository Distribution
{repo_dist_md}

### Category Distribution
{cat_dist_md}

---

## Validation Metrics

The table below compares the retrieval metrics of the new curated benchmark (`v2_curated`) against the baseline manual benchmark (`v1_manual`).

| Metric | Baseline (`v1_manual`) | New Curated (`v2_curated`) | Status / Change |
| :--- | :--- | :--- | :--- |
| **Top-1 Accuracy** | {baseline['top_1']*100:.1f}% | {overall_metrics['top_1']*100:.1f}% | {fmt_change(overall_metrics['top_1'], baseline['top_1'])} |
| **Top-3 Accuracy** | {baseline['top_3']*100:.1f}% | {overall_metrics['top_3']*100:.1f}% | {fmt_change(overall_metrics['top_3'], baseline['top_3'])} |
| **Top-5 Accuracy** | {baseline['top_5']*100:.1f}% | {overall_metrics['top_5']*100:.1f}% | {fmt_change(overall_metrics['top_5'], baseline['top_5'])} |
| **Mean Reciprocal Rank (MRR)** | {baseline['mrr']:.3f} | {overall_metrics['mrr']:.3f} | {fmt_change(overall_metrics['mrr'], baseline['mrr'], False)} |

> [!NOTE]
> Lower retrieval metrics on a larger, more balanced dataset are expected if it exposes genuine architectural retrieval limits (e.g. broad coverage of 4 repositories rather than a small subset). This is part of the Quality-First validation philosophy.

---

{failures_md}

## Known Limitations & Dataset Evolution

1. **Static Templates**: Questions are generated using structured templates mapping verbs/nouns from public API symbols. Future iterations could integrate paraphrasing tools to enhance natural language variety.
2. **Deterministic matching**: Expected symbols are strictly verified via graph-native path IDs. Any refactoring of symbol names in subsequent repository updates requires regenerations.
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_content)
    print(f"Report successfully written to {output_path}")

def main():
    curated_path = PROJECT_ROOT / "tests" / "benchmarks" / "v2_curated.json"
    if not curated_path.exists():
        print(f"Error: Curated benchmark not found at {curated_path}")
        sys.exit(1)
        
    with open(curated_path, "r", encoding="utf-8") as f:
        curated_questions = json.load(f)
        
    # Run evaluation
    results = run_metrics_pipeline(curated_path)
    
    # Load baseline metrics
    baseline = load_baseline_metrics()
    
    # Load raw candidates count to show in report
    candidates_path = PROJECT_ROOT / "generated_candidates.json"
    candidates_count = 0
    if candidates_path.exists():
        with open(candidates_path, "r", encoding="utf-8") as f:
            candidates_count = len(json.load(f))
            
    # Output report paths
    report_paths = [
        PROJECT_ROOT / "benchmark_generation_report.md",
        WORKSPACE_ROOT / "benchmark_generation_report.md"
    ]
    
    for path in report_paths:
        generate_report(
            candidates_count=candidates_count,
            curated_questions=curated_questions,
            metrics_results=results,
            baseline=baseline,
            output_path=path
        )

if __name__ == "__main__":
    main()
