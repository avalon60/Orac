"""Package the versioned original strategy overlay as an immutable catalogue release."""
# Author: Clive Bostock
# Date: 12-Nov-2026
# Description: Validate strategy coverage and preserve every historical catalogue field.
# Purpose: Produce a deterministic additive strategy release through the private sync API.
# Usage: python3 plugins/orac_chess/tools/generate_strategy_catalogue.py --check

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

# Support the established plugin-local tools package for direct CLI execution.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.generate_catalogue_sync import generate, normalise  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
HISTORICAL = ROOT / 'seed/catalogue/2026_11_10_comprehensive_catalogue/catalogue.json'
OVERLAY = ROOT / 'seed/strategy/2026_11_12/strategies.json'
RELEASE = ROOT / 'seed/catalogue/2026_11_12_strategy_catalogue'


def build_release(source: dict, overlay: dict, *, editorial: bool = False) -> dict:
    """Attach complete strategy by stable source key without changing historical fields.

    Args:
        source: Complete prior immutable catalogue.
        overlay: Versioned original narrative records and provenance.
        editorial: Package the later bounded editorial revision without a word floor.

    Returns:
        A complete release preserving source identities and non-strategy fields.

    Raises:
        ValueError: If coverage, reference positions or narrative bounds differ.
    """
    result = copy.deepcopy(source)
    entries = overlay['entries']
    owners = result['openings'] + result['gambits']
    if set(entries) != {row['source_key'] for row in owners}:
        raise ValueError('Strategy overlay must cover exactly all opening and gambit keys')
    for row in owners:
        narrative = entries[row['source_key']]
        if narrative['reference_pgn'] != row['mainline_pgn'] or narrative['name'] != row['name']:
            raise ValueError('Strategy reference position or name differs from its source')
        strategy = narrative['strategy']
        if not isinstance(strategy, str) or (not editorial and not 80 <= len(strategy.split()) <= 130):
            raise ValueError('Each strategy must contain 80–130 words')
        if editorial and (not strategy.strip() or '\n\n' not in strategy):
            raise ValueError('Editorial strategy must contain nonempty topical paragraphs')
        row['strategy'] = strategy
    result['batch_key'] = '2026_11_13_editorial_catalogue' if editorial else '2026_11_12_strategy_catalogue'
    result['source_revision'] = source['source_revision'] + ('+editorial-2026-11-13-v1' if editorial else '+strategy-2026-11-12-v1')
    result['provenance']['strategy'] = copy.deepcopy(overlay['provenance'])
    return result


def main() -> None:
    """Write or verify the release, bounded source payload and once-only SQL batch."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    source = json.loads(HISTORICAL.read_text(encoding='utf-8'))
    overlay = json.loads(OVERLAY.read_text(encoding='utf-8'))
    if overlay['provenance']['position_source_sha256'] != hashlib.sha256(HISTORICAL.read_bytes()).hexdigest():
        raise ValueError('Strategy overlay provenance does not match the immutable source')
    release = build_release(source, overlay)
    artifacts = {
        RELEASE / 'catalogue.json': json.dumps(release, ensure_ascii=False, sort_keys=True, indent=2) + '\n',
        RELEASE / 'sync_payload.json': json.dumps(normalise(release), ensure_ascii=False, sort_keys=True, indent=2) + '\n',
        ROOT / 'db/schema/seed_data/chess_batch_2026_11_12_strategy_catalogue.sql': generate(
            release, '2026_11_12_strategy_catalogue', '12-Nov-2026'),
    }
    editorial_path = ROOT / 'seed/strategy/2026_11_13/strategies.json'
    editorial_overlay = json.loads(editorial_path.read_text(encoding='utf-8'))
    if editorial_overlay['provenance']['previous_strategy_sha256'] != hashlib.sha256(OVERLAY.read_bytes()).hexdigest():
        raise ValueError('Editorial provenance does not match the original strategy overlay')
    if editorial_overlay['provenance']['position_source_sha256'] != hashlib.sha256(HISTORICAL.read_bytes()).hexdigest():
        raise ValueError('Editorial position provenance does not match the immutable source')
    editorial_release = build_release(release, editorial_overlay, editorial=True)
    editorial_root = ROOT / 'seed/catalogue/2026_11_13_editorial_catalogue'
    artifacts.update({
        editorial_root / 'catalogue.json': json.dumps(editorial_release, ensure_ascii=False, sort_keys=True, indent=2) + '\n',
        editorial_root / 'sync_payload.json': json.dumps(normalise(editorial_release), ensure_ascii=False, sort_keys=True, indent=2) + '\n',
        ROOT / 'db/schema/seed_data/chess_batch_2026_11_13_editorial_catalogue.sql': generate(
            editorial_release, '2026_11_13_editorial_catalogue', '13-Nov-2026'),
    })
    for path, text in artifacts.items():
        if args.check:
            if not path.exists() or path.read_text(encoding='utf-8') != text:
                raise SystemExit(f'Stale strategy release artifact: {path}')
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding='utf-8')


if __name__ == '__main__':
    main()
