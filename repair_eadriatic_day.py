from playwright.sync_api import sync_playwright
from datetime import datetime, timedelta
import sys
import os

from eadriatic_leagues import (
    parse_matches,
    process,
    build_df
)


# -------------------------
# FECHA OBJETIVO
# -------------------------
def get_target_date():

    if len(sys.argv) > 1:
        return datetime.strptime(
            sys.argv[1],
            "%d%m%Y"
        )

    return datetime.now() - timedelta(days=1)


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

        browser = p.chromium.launch(
            headless=False
        )

        page = browser.new_page()

        page.goto(
            url,
            wait_until="networkidle"
        )


        print(f"Seleccionando {code}")

        page.wait_for_timeout(3000)

        button = page.locator(
            f'button[value="{code}"]'
        )

        button.wait_for(timeout=30000)

        button.click()

        page.wait_for_load_state("networkidle")

        html = page.content()

        browser.close()

    return html


# -------------------------
# GUARDAR TXT FECHA CONCRETA
# -------------------------
def save_txt_for_date(df, vs_text, date):

    output_dir = r"C:\apuestas\eadriatic\data"

    filename = (
        date.strftime("%Y%m%d")
        + "_eadriatic_player_stats.txt"
    )

    path = os.path.join(
        output_dir,
        filename
    )

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            f"ESTADÍSTICAS "
            f"{date.strftime('%Y-%m-%d')}\n\n"
        )

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

    print(
        f"\nReparando día "
        f"{date.strftime('%d/%m/%Y')}"
    )

    html = download_day(date)

    matches = parse_matches(html)

    print(
        f"Partidos encontrados: "
        f"{len(matches)}"
    )

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

    # OJO: aquí todavía generará el TXT con la fecha actual
    # porque save_txt() en eadriatic_leagues.py usa datetime.now()

    save_txt_for_date(
        df,
        vs_text,
        date
    )


if __name__ == "__main__":
    main()