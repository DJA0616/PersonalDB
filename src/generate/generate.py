#!/usr/bin/env python3
"""
Generation script for PersonalDB.
Uses Ollama LLM (llama3.1:8b or mistral) to draft a reply based on retrieved context.
"""

import json
import requests
from pathlib import Path
import sys
from typing import Dict, Any, List

# Ensure UTF-8 output for console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


OLLAMA_API_URL = "http://localhost:11434/api/generate"
# Default model; can be overriden by environment or argument
DEFAULT_MODEL = "qwen3:14b"


def build_prompt(context: Dict[str, Any], user_prompt: str) -> str:
    """
    Build the prompt for the LLM.
    We'll include static style examples and dynamic results as guidance.
    """
    static_examples = context.get('static_examples', [])
    dynamic_results = context.get('dynamic_results', [])

    # Start with instruction
    prompt_parts = [
        "You are a helpful assistant that drafts message replies in the user's personal style.",
        "Use the provided examples and context to generate a natural, appropriate reply.",
        "",
        "=== STATIC STYLE EXAMPLES ===",
    ]
    # Add static examples (limit to first 5 to avoid too long prompt)
    for i, example in enumerate(static_examples[:5]):
        prompt_parts.append(f"Example {i+1}: {example}")
    prompt_parts.append("")
    prompt_parts.append("=== DYNAMIC CONTEXT (similar past conversations) ===")
    for i, res in enumerate(dynamic_results[:5]):  # top 5
        prompt_parts.append(f"Context {i+1}: {res.get('text', '')}")
    prompt_parts.append("")
    prompt_parts.append("=== CURRENT SITUATION ===")
    prompt_parts.append(user_prompt)
    prompt_parts.append("")
    prompt_parts.append("Instructions: Draft a reply that fits the user's style and the context. Only output the draft reply, nothing else.")

    return "\n".join(prompt_parts)


def generate_draft(prompt: str, model: str = DEFAULT_MODEL) -> str:
    """
    Call Ollama's generate API to get a draft.
    """
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False  # we want the full response at once
    }
    response = requests.post(OLLAMA_API_URL, json=payload)
    response.raise_for_status()
    result = response.json()
    return result.get("response", "")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Generate a draft reply using retrieved context')
    parser.add_argument('--context', type=str, help='Path to JSON file containing context (output from retrieve.py)')
    parser.add_argument('--prompt', type=str, required=True, help='The prompt/situation for which to generate a reply')
    parser.add_argument('--model', type=str, default=DEFAULT_MODEL, help='Ollama model to use')
    parser.add_argument('--context-stdin', action='store_true', help='Read context from stdin instead of file')
    args = parser.parse_args()

    # Load context
    if args.context_stdin:
        context_data = json.load(sys.stdin)
    elif args.context:
        with open(args.context, 'r', encoding='utf-8') as f:
            context_data = json.load(f)
    else:
        # If no context provided, we'll use empty context
        context_data = {'static_examples': [], 'dynamic_results': []}

    # Build the full prompt
    full_prompt = build_prompt(context_data, args.prompt)

    # Generate draft
    try:
        draft = generate_draft(full_prompt, model=args.model)
        print(draft)
    except Exception as e:
        print(f"Error generating draft: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()