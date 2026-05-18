"""
Instagram message export parser for PersonalDB.

Parses an Instagram JSON data export into normalized message records.
Handles the latin-1/UTF-8 mojibake encoding bug in Instagram exports.

Usage (run from project root):
    # 1. List every sender name found, so you can spot your own:
    python src/ingest/instagram_parser.py --export-root "F:/path/to/export" --list-senders

    # 2. Parse and write normalized sent messages:
    python src/ingest/instagram_parser.py --export-root "F:/path/to/export" --me "Your Name"
"""

import argparse
import json
import os
from pathlib import Path
from collections import Counter

from personaldb.config import get_config


def fix_encoding(s):
    """Repair Instagram's double-encoded UTF-8 (mojibake)."""
    if not isinstance(s, str):
        return s
    try:
        return s.encode('latin-1').decode('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s  # already valid, or not repairable — leave as-is


def find_inbox(export_root):
    """Locate the messages/inbox directory anywhere inside the export."""
    root = Path(export_root)
    candidates = list(root.rglob('messages/inbox'))
    if not candidates:
        raise FileNotFoundError(
            f"No 'messages/inbox' folder found under {export_root}. "
            "Check the export extracted correctly."
        )
    return candidates[0]


def iter_conversations(inbox):
    """Yield (conversation_dir, parsed_json) for every message_*.json file."""
    for convo_dir in sorted(inbox.iterdir()):
        if not convo_dir.is_dir():
            continue
        for mf in sorted(convo_dir.glob('message_*.json')):
            with open(mf, encoding='utf-8') as f:
                yield convo_dir, json.load(f)


def list_senders(inbox):
    """Count messages per sender name across the whole export."""
    counter = Counter()
    for _, data in iter_conversations(inbox):
        for m in data.get('messages', []):
            counter[fix_encoding(m.get('sender_name', ''))] += 1
    return counter


SYSTEM_MSG_PATTERNS = (
    'sent an attachment',
    'liked a message',
    'reacted',
)


def _has_reply(messages, idx, me):
    """Return True if message at idx receives a real reply from another sender."""
    for j in range(idx + 1, min(idx + 5, len(messages))):
        nxt = messages[j]
        nxt_sender = fix_encoding(nxt.get('sender_name', ''))
        if nxt_sender == me:
            continue
        nxt_content = nxt.get('content', '') or ''
        if nxt_content and not any(p in nxt_content.lower() for p in SYSTEM_MSG_PATTERNS):
            return True
    return False


def parse(inbox, me):
    """Return normalized sent-message records authored by `me`.

    Each record includes the preceding message as `context` so the
    preprocessor can judge tone/meaning of short replies.

    Solo "attachment sent" messages are filtered out — only kept when
    another sender replied with real text (starting a conversation).
    """
    records = []
    for convo_dir, data in iter_conversations(inbox):
        participants = [fix_encoding(p.get('name', ''))
                        for p in data.get('participants', [])]
        is_group = len(participants) > 2
        title = fix_encoding(data.get('title', convo_dir.name))
        messages = data.get('messages', [])
        prev_msg = None  # track preceding message for context
        for i, m in enumerate(messages):
            sender = fix_encoding(m.get('sender_name', ''))
            content = m.get('content')
            if sender == me:
                if not content:          # photos, shares, calls — no text
                    prev_msg = None      # still advance; nothing to attach
                    continue
                text = fix_encoding(content)
                # Skip solo attachment-sent messages — only keep if replied to
                if 'sent an attachment' in text.lower():
                    if not _has_reply(messages, i, me):
                        prev_msg = None
                        continue
                record = {
                    'conversation_id': convo_dir.name,
                    'conversation_title': title,
                    'is_group': is_group,
                    'participants': participants,
                    'sender': sender,
                    'timestamp_ms': m.get('timestamp_ms'),
                    'text': text,
                }
                if prev_msg is not None:
                    record['context'] = prev_msg
                    prev_msg = None      # consumed — don't reuse for next
                records.append(record)
            else:
                # Remember this non-me message as potential context.
                # Keep only the fields we need (smaller output).
                if content:
                    prev_msg = {
                        'sender': sender,
                        'text': fix_encoding(content),
                        'timestamp_ms': m.get('timestamp_ms'),
                    }
                # If no content (photo / share / call), clear stale context.
                else:
                    prev_msg = None
    return records


def main():
    cfg = get_config()

    ap = argparse.ArgumentParser(description='Parse Instagram message export.')
    ap.add_argument('--export-root', required=True,
                    help='Path to the extracted Instagram export folder')
    ap.add_argument('--me', help='Your display name as it appears in sender_name')
    ap.add_argument('--list-senders', action='store_true',
                    help='List all sender names with counts, then exit')
    ap.add_argument('--out',
                    default=os.path.join(cfg['paths']['data_processed'], 'instagram_normalized.json'),
                    help='Output path for normalized records')
    args = ap.parse_args()

    inbox = find_inbox(args.export_root)
    print(f"Found inbox: {inbox}")

    if args.list_senders:
        for name, count in list_senders(inbox).most_common():
            print(f"  {count:>6}  {name}")
        return

    if not args.me:
        ap.error("--me is required unless using --list-senders")

    records = parse(inbox, args.me)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')

    print(f"Parsed {len(records)} sent messages -> {out_path}")


if __name__ == '__main__':
    main()


