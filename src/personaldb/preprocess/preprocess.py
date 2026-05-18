#!/usr/bin/env python3
"""
Preprocessing script for PersonalDB.
Filters, tags, and chunks normalized messages.
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Any

from personaldb.config import get_config


def is_emoji_only(text: str) -> bool:
    """
    Check if text consists only of emojis and whitespace.
    Simple heuristic: remove all emoji characters (non-ASCII) and see if anything remains.
    """
    # Remove emojis (non-ASCII characters) and whitespace
    stripped = re.sub(r'[\s\U00010000-\U0010ffff]', '', text, flags=re.UNICODE)
    return len(stripped) == 0


def is_pure_acknowledgement(text: str, cfg=None) -> bool:
    """
    Check if text is a pure acknowledgement like 'ok', 'lol', 'haha yeah'.
    """
    if cfg is None:
        cfg = get_config()
    acknowledgements = set(cfg['preprocess']['acknowledgements'])
    # Normalize: lower case, remove punctuation, extra spaces
    normalized = re.sub(r'[^\w\s]', '', text.lower()).strip()
    # Collapse multiple spaces
    normalized = re.sub(r'\s+', ' ', normalized)
    return normalized in acknowledgements


def should_keep(message: Dict[str, Any]) -> bool:
    """
    Keep all messages with text content.
    Only drop truly empty messages (photos, shares, calls — already stripped by parser).
    """
    text = message.get('text', '').strip()
    return bool(text)


def enrich_message(message: Dict[str, Any], cfg=None) -> Dict[str, Any]:
    """
    Enrich short, emoji-only, or acknowledgement messages with context
    from the preceding message so tone/meaning is preserved.
    """
    if cfg is None:
        cfg = get_config()
    min_words = cfg['preprocess']['min_words']
    min_content_length = cfg['preprocess']['min_content_length']

    text = message.get('text', '').strip()
    context = message.get('context', {})
    if context and context.get('text'):
        ctx_sender = context.get('sender', '')
        ctx_text = context.get('text', '')
        if is_emoji_only(text):
            message['enriched_text'] = f'[{ctx_sender}: "{ctx_text}"] [reacted: {text}]'
            message['condensed'] = True
        elif is_pure_acknowledgement(text, cfg):
            message['enriched_text'] = f'[{ctx_sender}: "{ctx_text}"] [replied: {text}]'
            message['condensed'] = True
        elif len(text.split()) < min_words:
            message['enriched_text'] = f'[{ctx_sender}: "{ctx_text}"] {text}'
            message['condensed'] = True
        else:
            message['enriched_text'] = text
            message['condensed'] = False
    else:
        message['enriched_text'] = text
        message['condensed'] = len(text.split()) < min_words
    return message


def tag_chunk(chunk: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Create a tagged chunk from a list of messages.
    Returns a dict representing the chunk.
    """
    if not chunk:
        return {}
    # Use the first message to get conversation info
    first = chunk[0]
    # Determine participants (other than the user)
    participants = first.get('participants', [])
    # Assuming the user's name is not in participants? In our normalized data, participants includes everyone.
    # We'll set person as the first participant that is not the user? But we don't have the user name here.
    # For simplicity, we'll store the list of participants.
    # Platform is instagram (hardcoded for now)
    # Relationship type: group if len(participants) > 2 else direct
    # Inferred context: placeholder (could be derived from conversation title or keywords)
    is_group = len(participants) > 2
    # Build chunk record
    tagged = {
        'chunk_id': f"{first.get('conversation_id')}_{chunk[0].get('timestamp_ms')}_{len(chunk)}",
        'conversation_id': first.get('conversation_id'),
        'conversation_title': first.get('conversation_title', ''),
        'is_group': is_group,
        'participants': participants,
        'platform': 'instagram',
        'relationship_type': 'group' if is_group else 'direct',
        'inferred_context': '',  # TODO: implement context inference
        'message_count': len(chunk),
        'messages': [
            {
                'text': msg.get('enriched_text', msg['text']),
                'timestamp': msg.get('timestamp_ms'),
                'sender_name': msg.get('sender_name', msg.get('sender', '')),
            }
            for msg in chunk
        ],
        # Combined text uses enriched text when available
        'combined_text': ' '.join([msg.get('enriched_text', msg.get('text', '')) for msg in chunk])
    }
    return tagged


def chunk_messages(messages: List[Dict[str, Any]], cfg=None) -> List[List[Dict[str, Any]]]:
    """
    Group consecutive messages per conversation into chunks.
    We'll split by conversation_id and then by a simple max chunk size.
    """
    if cfg is None:
        cfg = get_config()
    max_chunk_size = cfg['preprocess']['max_chunk_size']

    # Sort by conversation_id and timestamp
    sorted_msgs = sorted(messages, key=lambda m: (m.get('conversation_id', ''), m.get('timestamp_ms', 0)))

    chunks = []
    current_convo = None
    current_chunk = []

    for msg in sorted_msgs:
        convo_id = msg.get('conversation_id')
        if convo_id != current_convo:
            # Finish previous chunk
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = []
            current_convo = convo_id

        # Start new chunk if current chunk reaches max size
        if len(current_chunk) >= max_chunk_size:
            chunks.append(current_chunk)
            current_chunk = []

        current_chunk.append(msg)

    # Append last chunk
    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def main():
    import argparse
    cfg = get_config()

    parser = argparse.ArgumentParser(description='Preprocess normalized messages for PersonalDB')
    parser.add_argument('--input', type=str, required=True, help='Input JSONL or JSON file of normalized messages')
    parser.add_argument('--output', type=str, required=True, help='Output JSON file for tagged chunks')
    args = parser.parse_args()

    # Load messages
    input_path = Path(args.input)
    messages = []
    if input_path.suffix == '.jsonl':
        with open(input_path, 'r', encoding='utf-8') as f:
            for line in f:
                messages.append(json.loads(line.strip()))
    else:  # assume json
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                messages = data
            else:
                # If the JSON is an object with a list under a key, adjust accordingly
                # For now, assume it's a list
                messages = data.get('messages', [])

    # Enrich and filter
    enriched = [enrich_message(msg, cfg) for msg in messages if should_keep(msg)]
    print(f"Kept {len(enriched)} / {len(messages)} messages after filtering (dropped {len(messages) - len(enriched)})")

    # Chunk
    chunked = chunk_messages(enriched, cfg)
    print(f"Created {len(chunked)} chunks")

    # Tag each chunk
    tagged_chunks = [tag_chunk(chunk) for chunk in chunked]

    # Save
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(tagged_chunks, f, ensure_ascii=False, indent=2)

    print(f"Saved tagged chunks to {output_path}")


if __name__ == '__main__':
    main()