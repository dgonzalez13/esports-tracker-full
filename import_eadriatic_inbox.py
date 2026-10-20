"""Import only saved result pages currently present in the GitHub inbox."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

from eadriatic_saved_results import import_saved_results

BASE = Path(__file__).resolve().parent
INBOX = BASE / 'eadriatic' / 'manual_imports'
HISTORY = BASE / 'eadriatic' / 'data' / 'match_history.jsonl'
LEDGER = BASE / 'eadriatic' / 'manual_import_log.json'
EXTENSIONS = {'.html', '.htm', '.mhtml', '.mht'}


def import_inbox(inbox=INBOX, history=HISTORY, ledger_path=LEDGER, *, apply=False, complete_days=()):
    inbox, history, ledger_path = map(Path, (inbox, history, ledger_path))
    if not inbox.is_dir():
        raise ValueError(f'Inbox does not exist: {inbox}')
    paths = sorted(p for p in inbox.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONS)
    ledger = json.loads(ledger_path.read_text(encoding='utf-8')) if ledger_path.exists() else {
        'schema_version': 1, 'processed_files': {}}
    if ledger.get('schema_version') != 1 or not isinstance(ledger.get('processed_files'), dict):
        raise ValueError('Invalid manual import log')
    hashes = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    # A renamed file or two equal files in the same batch is only processed once.
    pending = {}
    for path in paths:
        digest = hashes[path]
        if digest not in ledger['processed_files']:
            pending.setdefault(digest, path)
    report = dict(applied=apply, files_present=len(paths), files_pending=len(pending),
                  files_already_processed=len(paths) - len(pending), changed=False)
    if not pending and not complete_days:
        return report
    if complete_days and not paths:
        raise ValueError('Complete-day rebuilding requires the result pages in the inbox')
    selected = paths if complete_days else list(pending.values())
    summary = import_saved_results(selected, history, apply=apply, complete_days=complete_days)
    report['import'] = summary
    if apply:
        stamp = datetime.now(timezone.utc).isoformat()
        for digest, path in pending.items():
            ledger['processed_files'][digest] = {
                'file': path.name, 'imported_at': stamp,
                'input_matches_in_batch': summary['input_matches'],
                'added_matches_in_batch': summary['added_matches'],
                'affected_dates': summary['affected_dates'],
            }
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = ledger_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        temporary.replace(ledger_path)
        report['changed'] = bool(pending or complete_days)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inbox', type=Path, default=INBOX)
    parser.add_argument('--history', type=Path, default=HISTORY)
    parser.add_argument('--ledger', type=Path, default=LEDGER)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--complete-day', action='append', default=[])
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    # Workflow inputs stay in environment variables; never interpolate them as shell code.
    apply = args.apply or os.environ.get('APPLY_IMPORT', '').lower() == 'true'
    days = args.complete_day + [s.strip() for s in os.environ.get('COMPLETE_DAYS', '').split(',') if s.strip()]
    report = import_inbox(args.inbox, args.history, args.ledger, apply=apply, complete_days=days)
    output = json.dumps(report, ensure_ascii=True, indent=2) + '\n'
    print(output)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(output, encoding='utf-8')
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as handle:
            handle.write('changed=' + str(report['changed']).lower() + '\n')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as handle:
            handle.write('### Eadriatic manual import\n\n```json\n' + output + '```\n')


if __name__ == '__main__':
    main()
