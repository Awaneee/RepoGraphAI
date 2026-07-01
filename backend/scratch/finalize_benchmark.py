import json
from pathlib import Path

p = Path('tests/benchmarks/v2_curated.json')
with open(p, 'r') as f:
    data = json.load(f)

# Apply rewrites
for item in data:
    if item['question'] == 'How are routes registered for for include?':
        item['question'] = 'How is the router inclusion context constructed for_include?'
        item['review_notes'] = 'Rewritten to remove double preposition and improve phrasing'
    elif item['question'] == 'How are routes registered for combine?':
        item['question'] = 'How does _RouterIncludeContext combine routing configurations?'
        item['review_notes'] = 'Rewritten to improve phrasing and target combine method naturally'
    elif item['question'] == 'How are routes registered for route?':
        item['question'] = 'How does the route decorator register a route in APIRouter?'
        item['review_notes'] = 'Rewritten to specify route decorator context'
    elif item['question'] == 'How are routes registered for path for?':
        item['question'] = 'How is a route path resolved in _RouterIncludeContext?'
        item['review_notes'] = 'Rewritten to specify path resolution context'

# Remove invalid/duplicate questions
final_data = [
    item for item in data 
    if item['question'] not in (
        'How does the request exception work?',
        'How is code parsed by the BaseModelWithConfig?'
    )
]

# Write to v2_curated.json
with open(p, 'w', encoding='utf-8') as f:
    json.dump(final_data, f, indent=2)

# Write to tests/generated_benchmark.json
legacy_path = Path('tests/generated_benchmark.json')
with open(legacy_path, 'w', encoding='utf-8') as f:
    json.dump(final_data, f, indent=2)

print(f"Successfully finalized curation benchmark with {len(final_data)} questions.")
