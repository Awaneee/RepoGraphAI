"""
template_engine.py
==================
Generates natural-sounding candidate questions for public symbols using
predefined template families based on verb/noun extraction and category mapping.
"""

from __future__ import annotations
import re
from typing import Optional
from app.models.pydantic_models import GraphNode, NodeType

# Mapping of categories and their keyword associations
CATEGORY_KEYWORDS = {
    "Parsing": ["parse", "parser", "extract", "ast", "lexer", "token"],
    "Graph Construction": ["graph", "builder", "node", "edge", "relationship", "link", "construct", "build"],
    "Retrieval": ["retrieve", "retriever", "fetch", "collect", "query", "find", "search"],
    "Context Building": ["context", "builder", "prompt", "llm", "package"],
    "Routing": ["route", "router", "register", "endpoint", "dispatch"],
    "Authentication": ["auth", "login", "authenticate", "session", "token", "sign"],
    "Configuration": ["config", "settings", "setup", "env"],
    "HTTP": ["http", "request", "response", "client", "server", "middleware"],
    "CLI": ["cli", "command", "parser", "args", "argparse", "typer", "click"],
    "Visualization": ["visualize", "visualization", "plot", "render", "draw", "png"],
    "Utilities": ["util", "utils", "helper", "common", "format", "clean"]
}

def split_snake_case(text: str) -> list[str]:
    """Split snake_case string into list of words."""
    return [w for w in text.split("_") if w]

def split_camel_case(text: str) -> list[str]:
    """Split CamelCase string into list of words."""
    return re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\b)', text)

def get_word_parts(node: GraphNode) -> list[str]:
    """Extract individual word parts from a node label or ID."""
    label = node.label
    # If it's a method (e.g. Class.method), use the method part
    if "." in label:
        parts = label.split(".")
        label = parts[-1]
    
    # Check if camelCase or snake_case
    if "_" in label:
        return split_snake_case(label)
    else:
        return split_camel_case(label)

def infer_category(node: GraphNode) -> str:
    """Infer the category of a node based on its name, parent class, and file path."""
    text_to_check = f"{node.id} {node.label} {node.file_path or ''}".lower()
    
    # Check each category's keywords
    best_category = "Utilities"
    max_matches = 0
    
    for category, keywords in CATEGORY_KEYWORDS.items():
        matches = sum(1 for kw in keywords if kw in text_to_check)
        if matches > max_matches:
            max_matches = matches
            best_category = category
            
    return best_category

def extract_verb_noun(node: GraphNode) -> tuple[Optional[str], Optional[str]]:
    """
    Extract a verb and noun from the symbol name.
    E.g. parse_file -> verb="parse", noun="file"
    E.g. generate_statistics -> verb="generate", noun="statistics"
    E.g. QueryResolver (Class) -> verb=None, noun="query resolver"
    """
    label = node.label
    if node.type == NodeType.CLASS:
        # For classes, we don't have a verb, just a noun phrase
        words = split_camel_case(label)
        noun = " ".join(words).lower()
        return None, noun

    # For functions/methods, split qualified name
    if "." in label:
        label = label.split(".")[-1]
        
    words = split_snake_case(label) if "_" in label else split_camel_case(label)
    if not words:
        return None, None
        
    verb = words[0].lower()
    
    # If the first word isn't a common verb, or there's only 1 word, handle it
    common_verbs = {
        "parse", "extract", "build", "construct", "generate", "create", 
        "resolve", "get", "retrieve", "fetch", "collect", "register", 
        "add", "calculate", "compute", "analyze", "scan", "clone", 
        "validate", "check", "format", "render", "visualize", "run"
    }
    
    if verb in common_verbs and len(words) > 1:
        noun = " ".join(words[1:]).lower()
        return verb, noun
    else:
        # If it doesn't start with a known verb, treat the whole thing as a noun phrase
        noun = " ".join(words).lower()
        return None, noun

def generate_questions_for_symbol(node: GraphNode) -> list[dict]:
    """
    Generate candidate questions for a given node using template families.
    Each candidate is a dict with fields:
      - question: the generated question text
      - category: the template family category
      - template_family: name of the template used
    """
    category = infer_category(node)
    verb, noun = extract_verb_noun(node)
    
    candidates = []
    
    # Define templates based on category and verb/noun structure
    if node.type == NodeType.CLASS:
        # Class-specific templates
        class_noun = noun or node.label.lower()
        candidates.append({
            "question": f"How does the {class_noun} work?",
            "template_family": "class_generic_work",
        })
        candidates.append({
            "question": f"What is the purpose of the {class_noun}?",
            "template_family": "class_generic_purpose",
        })
        # If class matches specific categories
        if category == "Retrieval":
            candidates.append({
                "question": f"How is retrieval performed using {node.label}?",
                "template_family": "class_retrieval",
            })
        elif category == "Parsing":
            candidates.append({
                "question": f"How is code parsed by the {node.label}?",
                "template_family": "class_parsing",
            })
    else:
        # Function/Method templates
        if verb and noun:
            # We have both verb and noun (e.g. parse_file -> parse, file)
            if verb == "parse":
                candidates.append({
                    "question": f"How are {noun}s parsed?",
                    "template_family": "verb_parse_plural",
                })
                candidates.append({
                    "question": f"How is {noun} parsing implemented?",
                    "template_family": "verb_parse_implemented",
                })
            elif verb == "extract":
                candidates.append({
                    "question": f"How are {noun}s extracted?",
                    "template_family": "verb_extract_plural",
                })
                candidates.append({
                    "question": f"How is {noun} extraction implemented?",
                    "template_family": "verb_extract_implemented",
                })
            elif verb in ("build", "construct"):
                candidates.append({
                    "question": f"How is the {noun} constructed?",
                    "template_family": "verb_build_constructed",
                })
                candidates.append({
                    "question": f"How is the {noun} built?",
                    "template_family": "verb_build_built",
                })
            elif verb in ("generate", "create"):
                candidates.append({
                    "question": f"How are {noun}s generated?",
                    "template_family": "verb_generate_plural",
                })
                candidates.append({
                    "question": f"How is the {noun} created?",
                    "template_family": "verb_generate_created",
                })
            elif verb == "resolve":
                candidates.append({
                    "question": f"How are {noun}s resolved?",
                    "template_family": "verb_resolve_plural",
                })
                candidates.append({
                    "question": f"How does {noun} resolution work?",
                    "template_family": "verb_resolve_work",
                })
            elif verb in ("get", "retrieve", "fetch", "collect"):
                candidates.append({
                    "question": f"How is a {noun} retrieved?",
                    "template_family": "verb_retrieve_singular",
                })
                candidates.append({
                    "question": f"How are {noun}s fetched?",
                    "template_family": "verb_retrieve_plural_fetched",
                })
                candidates.append({
                    "question": f"How are {noun}s collected?",
                    "template_family": "verb_retrieve_plural_collected",
                })
            elif verb in ("register", "add"):
                candidates.append({
                    "question": f"How are {noun}s registered?",
                    "template_family": "verb_register_plural",
                })
                candidates.append({
                    "question": f"How is a {noun} registered?",
                    "template_family": "verb_register_singular",
                })
            elif verb in ("calculate", "compute"):
                candidates.append({
                    "question": f"How are {noun}s calculated?",
                    "template_family": "verb_compute_calculated",
                })
                candidates.append({
                    "question": f"How is {noun} computation implemented?",
                    "template_family": "verb_compute_implemented",
                })
            elif verb in ("visualize", "render", "plot"):
                candidates.append({
                    "question": f"How are {noun}s visualized?",
                    "template_family": "verb_visualize_plural",
                })
                candidates.append({
                    "question": f"How is the {noun} rendered?",
                    "template_family": "verb_visualize_rendered",
                })
            else:
                # Default verb-noun template
                candidates.append({
                    "question": f"How is {noun} {verb}ed?",
                    "template_family": "verb_noun_default",
                })
                candidates.append({
                    "question": f"How does the {verb}_{noun} process work?",
                    "template_family": "verb_noun_process",
                })
        else:
            # Only noun phrase (no explicit verb found)
            noun_phrase = noun or node.label.lower()
            
            # Use category-specific default templates
            if category == "Parsing":
                candidates.append({
                    "question": f"How is the parsing of {noun_phrase} handled?",
                    "template_family": "noun_parsing",
                })
            elif category == "Graph Construction":
                candidates.append({
                    "question": f"How is {noun_phrase} represented in the graph?",
                    "template_family": "noun_graph_represented",
                })
                candidates.append({
                    "question": f"How are {noun_phrase} relationships created?",
                    "template_family": "noun_graph_relationships",
                })
            elif category == "Retrieval":
                candidates.append({
                    "question": f"How is {noun_phrase} retrieved?",
                    "template_family": "noun_retrieval",
                })
            elif category == "Routing":
                candidates.append({
                    "question": f"How are routes registered for {noun_phrase}?",
                    "template_family": "noun_routing",
                })
            elif category == "CLI":
                candidates.append({
                    "question": f"How are {noun_phrase} commands parsed?",
                    "template_family": "noun_cli",
                })
            else:
                candidates.append({
                    "question": f"How is {noun_phrase} handled?",
                    "template_family": "noun_generic_handled",
                })
                candidates.append({
                    "question": f"How is {noun_phrase} implemented?",
                    "template_family": "noun_generic_implemented",
                })
                
    # Normalize and return candidates
    results = []
    for c in candidates:
        # Clean up double spaces or trailing punctuation inside words
        cleaned_question = re.sub(r'\s+', ' ', c["question"]).strip()
        results.append({
            "question": cleaned_question,
            "category": category,
            "template_family": c["template_family"]
        })
        
    return results
