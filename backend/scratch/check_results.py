import json
from pathlib import Path

p = Path('tests/retrieval_metrics.json')
with open(p, 'r') as f:
    data = json.load(f)

rewritten_questions = [
    'How is the router inclusion context constructed for_include?',
    'How does _RouterIncludeContext combine routing configurations?',
    'How does the route decorator register a route in APIRouter?',
    'How is a route path resolved in _RouterIncludeContext?'
]

for repo, repo_data in data['per_dataset'].items():
    for q in repo_data['questions']:
        if q['question'] in rewritten_questions:
            print(f"\nQuestion: {q['question']}")
            print(f"Expected: {q['expected_symbols']}")
            print(f"Rank: {q['first_hit_rank']}")
            print("Retrieved Top 5:")
            for idx, (rid, score) in enumerate(zip(q['retrieved_ids'], q['retrieved_scores'])):
                print(f"  {idx+1}. {rid} (Score: {score})")
