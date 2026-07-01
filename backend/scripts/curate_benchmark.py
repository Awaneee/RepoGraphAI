"""
curate_benchmark.py
===================
Interactive CLI script to review, rename, categorize, merge, and curate candidate questions
into a final versioned benchmark.
"""

from __future__ import annotations
import os
import sys
import json
import argparse
from pathlib import Path

# Bootstrap paths
SCRIPTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPTS_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

def load_candidates(path: Path) -> list[dict]:
    if not path.exists():
        print(f"Error: Candidates file not found at {path}")
        print("Please run scripts/generate_candidates.py first.")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_curated_benchmark(questions: list[dict], version: str, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    versioned_path = output_dir / f"{version}.json"
    
    # Save versioned file
    with open(versioned_path, "w", encoding="utf-8") as f:
        json.dump(questions, f, indent=2)
    print(f"\nSaved {len(questions)} curated questions to {versioned_path}")

    # Also save to tests/generated_benchmark.json for downstream compatibility
    legacy_path = PROJECT_ROOT / "tests" / "generated_benchmark.json"
    legacy_path.parent.mkdir(parents=True, exist_ok=True)
    with open(legacy_path, "w", encoding="utf-8") as f:
        json.dump(questions, f, indent=2)
    print(f"Copied curated benchmark to {legacy_path}")

def migrate_v1_manual():
    """Migrate original 30 manual questions from retrieval_metrics.py to v1_manual.json."""
    from tests.retrieval_metrics import INTERNAL_QUESTIONS, CROSS_REPO_QUESTIONS
    import uuid

    v1_questions = []
    
    # Process internal questions
    for q in INTERNAL_QUESTIONS:
        det_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"RepoGraphAI:{q['expected_symbols'][0]}:{q['question']}"))
        v1_questions.append({
            "id": det_id,
            "question": q["question"],
            "expected_symbol": q["expected_symbols"][0],
            "repository": "RepoGraphAI",
            "category": q.get("category", "Uncategorized"),
            "quality_score": 1.0,
            "generation_reason": "Manually curated baseline",
            "template_family": "manual",
            "review_status": "accepted",
            "review_notes": "",
            "benchmark_version": "v1_manual"
        })

    # Process cross-repo questions
    for repo_name, questions in CROSS_REPO_QUESTIONS.items():
        for q in questions:
            det_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{repo_name}:{q['expected_symbols'][0]}:{q['question']}"))
            v1_questions.append({
                "id": det_id,
                "question": q["question"],
                "expected_symbol": q["expected_symbols"][0],
                "repository": repo_name,
                "category": q.get("category", "Uncategorized"),
                "quality_score": 1.0,
                "generation_reason": "Manually curated baseline",
                "template_family": "manual",
                "review_status": "accepted",
                "review_notes": "",
                "benchmark_version": "v1_manual"
            })

    output_dir = PROJECT_ROOT / "tests" / "benchmarks"
    output_dir.mkdir(parents=True, exist_ok=True)
    v1_path = output_dir / "v1_manual.json"
    with open(v1_path, "w", encoding="utf-8") as f:
        json.dump(v1_questions, f, indent=2)
    print(f"Migrated {len(v1_questions)} manual questions to {v1_path}")

def main():
    parser = argparse.ArgumentParser(description="Curate generated benchmark questions.")
    parser.add_argument("--candidates", type=str, default="generated_candidates.json",
                        help="Path to candidates JSON file")
    parser.add_argument("--version", type=str, default="v2_curated",
                        help="Curated benchmark version name (e.g. v2_curated)")
    parser.add_argument("--auto-accept", action="store_true",
                        help="Automatically accept candidates with quality score above threshold")
    parser.add_argument("--threshold", type=float, default=0.4,
                        help="Score threshold for auto-accept")
    parser.add_argument("--migrate-v1", action="store_true",
                        help="Migrate manual benchmark to v1_manual.json and exit")
    args = parser.parse_args()

    # Create tests/benchmarks directory
    output_dir = PROJECT_ROOT / "tests" / "benchmarks"
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.migrate_v1:
        migrate_v1_manual()
        return

    candidates_path = PROJECT_ROOT / args.candidates
    candidates = load_candidates(candidates_path)
    
    print(f"Loaded {len(candidates)} candidate questions from {candidates_path}.")

    accepted_questions = []
    
    if args.auto_accept:
        print(f"Auto-accept mode enabled. Accepting all candidates with score >= {args.threshold}...")
        for c in candidates:
            if c["quality_score"] >= args.threshold:
                c["review_status"] = "accepted"
                c["benchmark_version"] = args.version
                accepted_questions.append(c)
        print(f"Auto-accepted {len(accepted_questions)} questions.")
        save_curated_benchmark(accepted_questions, args.version, output_dir)
        return

    # Interactive Curation Mode
    print("\nStarting Interactive Curation CLI. Enter options to curate each question:")
    print("[A]ccept (default) | [R]eject | [S]kip | [E]dit question | [C]hange category | [M]erge duplicates | [Q]uit & Save")
    print("-" * 80)
    
    for i, c in enumerate(candidates):
        print(f"\n[{i+1}/{len(candidates)}] Candidate Details:")
        print(f"  Question   : {c['question']}")
        print(f"  Symbol     : {c['expected_symbol']}")
        print(f"  Repository : {c['repository']}")
        print(f"  Category   : {c['category']}")
        print(f"  Score      : {c['quality_score']:.3f}")
        print(f"  Reason     : {c['generation_reason']}")
        
        while True:
            choice = input("Your choice [A/R/S/E/C/M/Q] (default Accept): ").strip().upper()
            if not choice:
                choice = "A"
                
            if choice == "A":
                c["review_status"] = "accepted"
                c["benchmark_version"] = args.version
                accepted_questions.append(c)
                print("Accepted.")
                break
            elif choice == "R":
                c["review_status"] = "rejected"
                print("Rejected.")
                break
            elif choice == "S":
                c["review_status"] = "skipped"
                print("Skipped.")
                break
            elif choice == "E":
                new_q = input("Enter new question text: ").strip()
                if new_q:
                    c["question"] = new_q
                    c["review_notes"] = "Renamed during curation"
                c["review_status"] = "accepted"
                c["benchmark_version"] = args.version
                accepted_questions.append(c)
                print("Question renamed and accepted.")
                break
            elif choice == "C":
                new_cat = input("Enter new category name: ").strip()
                if new_cat:
                    c["category"] = new_cat
                    c["review_notes"] = f"Category changed from {c['category']}"
                c["review_status"] = "accepted"
                c["benchmark_version"] = args.version
                accepted_questions.append(c)
                print("Category changed and accepted.")
                break
            elif choice == "M":
                c["review_status"] = "merged"
                print("Marked as merged duplicate.")
                break
            elif choice == "Q":
                print("Quitting curation process...")
                save_curated_benchmark(accepted_questions, args.version, output_dir)
                return
            else:
                print("Invalid choice. Please select from A, R, S, E, C, M, or Q.")

    save_curated_benchmark(accepted_questions, args.version, output_dir)

if __name__ == "__main__":
    main()
