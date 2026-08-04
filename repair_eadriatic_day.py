from __future__ import annotations

from datetime import date as date_type, datetime, timedelta
import os
from pathlib import Path
import shutil
import sys
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright

from eadriatic_leagues import (
    MATCH_HISTORY_FILE,
    build_df,
    parse_history_records,
    parse_matches,
    process,
)
from match_history import load_records, write_records_atomic


BASE = Path(__file__).resolve().parent
OUTPUT_DIR = BASE / "eadriatic" / "data"


# -------------------------
# FECHA OBJETIVO
# -------------------------
def parse_target_date(value=None, *, now=None):
    """Resolve YYYYMMDD (canonical) or legacy DDMMYYYY repair dates."""
    if value:
        value = str(value).strip()
        if len(value) == 8 and value.isdigit():
            for date_format in ("%Y%m%d", "%d%m%Y"):
                try:
                    parsed = datetime.strptime(value, date_format)
                except ValueError:
                    continue
                if parsed.strftime(date_format) == value:
                    return parsed
        raise ValueError(
            "repair date must use a valid YYYYMMDD or DDMMYYYY date"
        )
    return (now or datetime.now()) - timedelta(days=1)


def get_target_date():
    if len(sys.argv) > 1:
        return parse_target_date(sys.argv[1])
    return parse_target_date()


# -------------------------
# RECONCILIACIÓN JSONL
# -------------------------
def _compatible_perspective(existing: dict, candidate: dict) -> bool:
    """Return whether two rows represent the same finalized match perspective."""
    fields = (
        "league",
        "match_id",
        "perspective_id",
        "player_key",
        "rival_key",
        "home_score",
        "away_score",
        "home_away",
    )
    return all(existing.get(field) == candidate.get(field) for field in fields)


def _repair_relevant_dates(target: date_type) -> set[date_type]:
    """Include the selected day and its possible post-midnight continuation."""
    return {target, target + timedelta(days=1)}


def _local_record_date(record: dict) -> date_type | None:
    value = record.get("timestamp")
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        return date_type.fromisoformat(value[:10])
    except ValueError:
        return None


def update_repaired_history(
    html,
    target_date,
    *,
    history_path=MATCH_HISTORY_FILE,
    collected_at=None,
    source_file=None,
):
    """
    Reconcile repaired perspectives with the normalized history.

    In addition to adding missing perspectives, this updates already stored rows
    whose timestamp/group metadata was previously inferred with the wrong day.
    This integrates the former one-off midnight-rollover migration into the
    normal repair flow.
    """
    target = target_date.date() if isinstance(target_date, datetime) else target_date
    if not isinstance(target, date_type):
        raise ValueError("target_date must be a date or datetime")

    history_path = Path(history_path)
    collected = collected_at or datetime.now(ZoneInfo("Europe/Madrid")).isoformat(
        timespec="seconds"
    )
    source = source_file or f"repair_eadriatic:{target.strftime('%Y%m%d')}"

    parsed = parse_history_records(
        html,
        source_file=source,
        collected_at=collected,
    )

    relevant_dates = _repair_relevant_dates(target)
    candidates = [
        row for row in parsed
        if _local_record_date(row) in relevant_dates
    ]
    candidate_by_id = {row["perspective_id"]: row for row in candidates}

    existing = load_records(history_path)
    repaired = []
    seen = set()
    updated = 0
    added = 0
    unchanged = 0
    conflicts = 0

    for row in existing:
        perspective = row["perspective_id"]
        candidate = candidate_by_id.get(perspective)
        if candidate is None:
            repaired.append(row)
            continue

        seen.add(perspective)
        if not _compatible_perspective(row, candidate):
            conflicts += 1
            repaired.append(row)
            continue

        repair_fields = (
            "timestamp",
            "timestamp_utc",
            "round",
            "competition",
            "group_key",
            "source_block_order",
            "source_row_order",
        )
        changed = any(row.get(field) != candidate.get(field) for field in repair_fields)

        if changed:
            replacement = dict(row)
            for field in repair_fields:
                if field in candidate:
                    replacement[field] = candidate[field]
                else:
                    replacement.pop(field, None)
            # Preserve the latest provenance for rows that were actually repaired.
            replacement["source_file"] = candidate["source_file"]
            if "collected_at" in candidate:
                replacement["collected_at"] = candidate["collected_at"]
            repaired.append(replacement)
            updated += 1
        else:
            repaired.append(row)
            unchanged += 1

    for perspective, candidate in candidate_by_id.items():
        if perspective not in seen:
            repaired.append(candidate)
            added += 1

    changed_total = updated + added
    backup_path = None
    if changed_total:
        history_path.parent.mkdir(parents=True, exist_ok=True)
        if history_path.exists():
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = history_path.with_name(
                f"{history_path.stem}.before_repair_{target.strftime('%Y%m%d')}_{stamp}"
                f"{history_path.suffix}"
            )
            shutil.copy2(history_path, backup_path)
        write_records_atomic(history_path, repaired)

    repaired_matches = len(parse_matches(html))
    normalized_matches = len({row["match_id"] for row in candidates})
    return {
        "txt_matches": repaired_matches,
        "parsed_perspectives": len(parsed),
        "generated_perspectives": len(candidates),
        "added_perspectives": added,
        "updated_perspectives": updated,
        "unchanged_perspectives": unchanged,
        "conflicts": conflicts,
        "duplicate_perspectives": len(candidates) - added - updated,
        "omitted_matches": max(0, repaired_matches - normalized_matches),
        "backup_path": str(backup_path) if backup_path else None,
    }


# -------------------------
# DESCARGA HTML DE UNA FECHA
# -------------------------
def download_day(date):
    code = (
        f"year{date.year}_"
        f"month{date.month:02d}_"
        f"day{date.day:02d}"
    )

    url = "https://eadriaticleague2.leaguerepublic.com/index.html"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")

        print(f"Seleccionando {code}")
        page.wait_for_timeout(3000)

        button = page.locator(f'button[value="{code}"]')
        button.wait_for(timeout=30000)
        button.click()
        page.wait_for_load_state("networkidle")

        html = page.content()
        browser.close()

    return html


def save_repair_html(html: str, target_date: datetime) -> Path:
    """Keep the exact source used by the repair for later auditing."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / (
        target_date.strftime("%Y%m%d") + "_eadriatic_repair_downloaded.html"
    )
    path.write_text(html, encoding="utf-8")
    return path


# -------------------------
# GUARDAR TXT FECHA CONCRETA
# -------------------------
def save_txt_for_date(df, vs_text, date):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / (
        date.strftime("%Y%m%d") + "_eadriatic_player_stats.txt"
    )

    with path.open("w", encoding="utf-8") as f:
        f.write(f"ESTADÍSTICAS {date.strftime('%Y-%m-%d')}\n\n")
        f.write(
            f"{'player':<12} "
            f"{'W':>3} "
            f"{'D':>3} "
            f"{'L':>3} "
            f"{'played':>6} "
            f"{'stk':>4} "
            f"seq\n"
        )

        for _, row in df.iterrows():
            f.write(
                f"{row['player']:<12} "
                f"{row['W']:>3} "
                f"{row['D']:>3} "
                f"{row['L']:>3} "
                f"{row['played']:>6} "
                f"{row['current_streak']:>4} "
                f"{row['seq']}\n"
            )

        f.write("\n\nVS RIVALES\n")
        for player in df["player"]:
            f.write(f"\n{player}\n")
            f.write(vs_text[player] + "\n")

    print(f"\n✔ Guardado en {path}")


# -------------------------
# MAIN
# -------------------------
def main():
    date = get_target_date()

    print(f"\nReparando día {date.strftime('%d/%m/%Y')}")

    html = download_day(date)
    html_path = save_repair_html(html, date)
    print(f"HTML de reparación guardado: {html_path}")

    matches = parse_matches(html)
    print(f"Partidos encontrados: {len(matches)}")

    stats = process(matches)
    df, vs_text = build_df(stats)

    print("\n🏆 RESULTADOS\n")
    for _, row in df.iterrows():
        print(
            f"{row['player']:<12} "
            f"{row['W']:>3} "
            f"{row['D']:>3} "
            f"{row['L']:>3} "
            f"{row['played']:>6} "
            f"{row['current_streak']:>3} "
            f"{row['seq']}"
        )

    save_txt_for_date(df, vs_text, date)

    summary = update_repaired_history(
        html,
        date,
        source_file=html_path.name,
    )
    print(f"TXT reparado: {summary['txt_matches']} partidos")
    print(f"Perspectivas parseadas: {summary['parsed_perspectives']}")
    print(f"Perspectivas relevantes: {summary['generated_perspectives']}")
    print(f"Perspectivas nuevas añadidas: {summary['added_perspectives']}")
    print(f"Perspectivas existentes corregidas: {summary['updated_perspectives']}")
    print(f"Perspectivas sin cambios: {summary['unchanged_perspectives']}")
    print(f"Conflictos no modificados: {summary['conflicts']}")
    print(f"Partidos omitidos: {summary['omitted_matches']}")
    if summary["backup_path"]:
        print(f"Copia de seguridad JSONL: {summary['backup_path']}")
    else:
        print("JSONL sin cambios; no fue necesario crear copia de seguridad")


if __name__ == "__main__":
    main()
