import os
import re
import time
import itertools
import requests
from collections import Counter
from datetime import datetime

# Day-of-week analysis is done in US Eastern (your timezone, and the clock the
# two rotations are scheduled against). Try the DST-aware zone; fall back to a
# fixed EDT offset if the tz database isn't installed (some Windows setups
# lack it -- 'pip install tzdata' gives exact DST handling).
try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
except Exception:
    from datetime import timezone, timedelta
    ET = timezone(timedelta(hours=-4))  # EDT fallback

API_TOKEN = os.environ.get("BETSAPI_TOKEN", "your_api_key_here")
BASE_URL = "https://api.b365api.com/"

# League / sport constants in one place so updates are easy
SPORT_ID = 18
LEAGUE_ID = 23105

# This dict is now just a convenience cache. Run menu option 3 (Discover /
# Update Players) any time the league changes its roster, then paste the
# generated dict over this one.
player_ids = {
    "chiefkeef": 1101785,  # CHI Bulls (CHIEFKEEF)
    "lalkoff": 1290542,  # DET Pistons (Lalkoff)
    "lucker": 1241413,  # MIA Heat (lucker)
    "veljouni": 1305963,  # MIA Heat (veljouni)
    "barmaley_2": 1285377,  # MIN Timberwolves (Barmaley)
    "bazuka": 1158314,  # MIN Timberwolves (Bazuka)
    "barmaley": 1317853,  # NO Pelicans (Barmaley)
    "koja": 1290720,  # NO Pelicans (Koja)
    "yangrainmaker": 1271760,  # OKC Thunder (yangrainmaker)
    "panteraxball": 1119893,  # ORL Magic (panteraxball)
    "pakapaka": 1289438,  # PHI 76ers (Pakapaka)
    "dzojo": 1244111,  # PHX Suns (Dzojo)
    "falcon": 1306665,  # POR T Blazers (faLcOn)
    "jovke": 1272991,  # POR Trail Blazers (Jovke)
    "lucashin": 1263069,  # SAC Kings (Lucashin)
    "the_professor": 1268992,  # SAC Kings (The_Professor)
    "djoks": 1296843,  # TOR Raptors (Djoks)
    "kadzima": 1269263,  # TOR Raptors (Kadzima)
}


# Which players belong to each rotation (both play in the same 4x5 format but
# never against each other -- daytime and overnight are separate pools).
# Keyed "0" = daytime, "1" = overnight to match the menu prompt.
ROTATIONS = {
    "0": {
        "label": "Daytime (~8:30am-4:05pm ET)",
        "players": ["koja", "pakapaka", "lucashin", "dzojo",
                    "bazuka", "jovke", "djoks", "veljouni"],
    },
    "1": {
        "label": "Overnight (~12:40am-7:35am ET)",
        "players": ["lalkoff", "panteraxball", "lucker", "chiefkeef",
                    "the_professor", "kadzima", "yangrainmaker",
                    "barmaley", "barmaley_2", "falcon"],
    },
}


# Color codes for terminal
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'


def discover_players(max_pages=25, sleep=0.2):
    """
    Scan recent ended games in the league and collect every unique
    team (player) id + name that appears. Players still active show up in
    recent games; removed players naturally drop off over time.

    Prints a ready-to-paste player_ids dict. Run this whenever the league
    swaps its roster.
    """
    url = f"{BASE_URL}v3/events/ended"
    params = {"token": API_TOKEN, "sport_id": SPORT_ID, "league_id": LEAGUE_ID, "page": 1}
    found = {}  # id (str) -> name

    print(f"\n{Colors.CYAN}{Colors.BOLD}=== DISCOVER / UPDATE PLAYERS ==={Colors.END}")
    print(f"Scanning league {LEAGUE_ID} for active players...\n")

    for page in range(1, max_pages + 1):
        params["page"] = page
        try:
            resp = requests.get(url, params=params).json()
        except Exception as e:
            print(f"{Colors.RED}Request failed on page {page}: {e}{Colors.END}")
            break

        # success == 0 usually means a bad/expired token or bad params
        if resp.get("success") == 0:
            print(f"{Colors.RED}API error: {resp.get('error', resp)}{Colors.END}")
            print(f"{Colors.YELLOW}Check that BETSAPI_TOKEN is set to a valid token.{Colors.END}")
            break

        results = resp.get("results")
        if not results:
            print(f"No more results at page {page}. Stopping.")
            break

        for game in results:
            for side in ("home", "away"):
                team = game.get(side)
                if team and team.get("id"):
                    found[str(team["id"])] = (team.get("name") or "").strip()

        print(f"Page {page}: {len(found)} unique players so far...")
        time.sleep(sleep)  # stay under the rate limit

    if not found:
        print(f"{Colors.RED}No players found. Check your token / league_id.{Colors.END}")
        return {}

    # Build dict keys from the handle inside the parentheses, e.g.
    # "CHI Bulls (CHIEFKEEF)" -> "chiefkeef". Fall back to the full name.
    def handle(name):
        m = re.search(r"\(([^)]+)\)", name)
        base = (m.group(1) if m else name).strip().lower()
        return re.sub(r"[^a-z0-9_]", "", base.replace(" ", "_")) or "player"

    # Group IDs by handle in scan order (newest first), so the FIRST ID seen
    # for a handle is that player's most-recent identity.
    by_handle = {}  # handle -> list of (team_id, name), newest first
    for team_id, name in found.items():
        by_handle.setdefault(handle(name), []).append((team_id, name))

    # Most-recent ID gets the clean handle; older variants get _2, _3, ...
    key_for = {}   # team_id -> key
    dupes = []     # same handle, different team_id (player switched NBA team)
    for h, entries in by_handle.items():
        for i, (team_id, name) in enumerate(entries):
            key_for[team_id] = h if i == 0 else f"{h}_{i + 1}"
            if i > 0:
                dupes.append((h, team_id, name))

    # Display sorted by name for readability
    lines = []
    for team_id, name in sorted(found.items(), key=lambda kv: kv[1].lower()):
        lines.append(f'    "{key_for[team_id]}": {team_id},  # {name}')

    print(f"\n{Colors.GREEN}{Colors.BOLD}Found {len(found)} team IDs "
          f"({len(found) - len(dupes)} distinct players). "
          f"Paste this over your player_ids dict:{Colors.END}\n")
    print("player_ids = {")
    print("\n".join(lines))
    print("}")

    if dupes:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}Heads up -- these players appear under "
              f"more than one team ID (they switched NBA teams):{Colors.END}")
        for key, team_id, name in dupes:
            print(f"  {Colors.YELLOW}{key}{Colors.END}: extra ID {team_id}  ({name})")
        print(f"{Colors.YELLOW}Keep whichever ID is current (the one in the newest "
              f"games) unless you want their older history too.{Colors.END}")

    print(f"\n{Colors.YELLOW}Tip: eyeball the keys before pasting -- they come from "
          f"the handle in parentheses, e.g. 'CHI Bulls (CHIEFKEEF)' -> 'chiefkeef'.{Colors.END}")

    return found


def get_head_to_head_games(player1, player2, target_games, verbose=True):
    """
    Fetch games between two players in Ebasketball Battle from BetsAPI
    """
    url = f"{BASE_URL}v3/events/ended"
    params = {"token": API_TOKEN, "sport_id": SPORT_ID, "page": 1, "league_id": LEAGUE_ID, "team_id": player1}
    games = []

    while len(games) < target_games:
        response = requests.get(url, params=params).json()
        if "results" not in response or len(response["results"]) == 0:
            if verbose:
                print(f"No more results found. Found {len(games)} games total.")
            break

        for game in response["results"]:
            home = game.get('home')
            away = game.get('away')

            if not str(game["time_status"]) == "3":
                continue

            if str(player1) == str(home["id"]) and str(player2) == str(away["id"]):
                games.append({
                    "home": game["home"],
                    "away": game["away"],
                    "score": game.get("ss"),
                    "id": game["id"],
                    "time": game.get("time")
                })
                if len(games) >= target_games:
                    break
            elif str(player2) == str(home["id"]) and str(player1) == str(away["id"]):
                games.append({
                    "home": game["home"],
                    "away": game["away"],
                    "score": game.get("ss"),
                    "id": game["id"],
                    "time": game.get("time")
                })
                if len(games) >= target_games:
                    break

        if len(games) >= target_games:
            break

        params["page"] += 1
        if verbose:
            print(f"Page {params['page']} - Found {len(games)}/{target_games} games so far...")

    return games


def analyze_spreads(games, player1):
    """
    Compute score spreads and find lines with 80-100% hit rate
    """
    spreads = []
    for g in games:
        try:
            home_score, away_score = map(int, g["score"].split("-"))
            if str(g["home"]["id"]) == str(player1):
                spread = home_score - away_score
            else:
                spread = away_score - home_score
            spreads.append(spread)
        except:
            continue

    if not spreads:
        return []

    total = len(spreads)
    largest_loss = min(spreads)
    largest_win = max(spreads)

    results = []
    for line in range(largest_loss - 1, largest_win + 1):
        counter = 0
        for j in spreads:
            if j > line + 0.5:
                counter += 1
        hit_rate = counter / total
        if hit_rate >= 0.80:
            results.append({
                "spread": -(line + 0.5),
                "hit_rate": f"{hit_rate:.2%}",
                "hit_rate_raw": hit_rate,
                "hits": counter,
                "games": total
            })

    return sorted(results, key=lambda x: -x["hit_rate_raw"])


def analyze_spread_misses_by_day(games, player, threshold=0.90):
    """
    Find the most aggressive spread line that a player still COVERS at least
    `threshold` of the time, then return the games that did NOT cover it.
    Each row keeps the full datetime (ET) so misses can be split by weekday
    AND by time of day (e.g. morning vs afternoon within the day session).
    """
    rows = []  # (margin, dt, score)
    for g in games:
        try:
            hs, ascore = map(int, g["score"].split("-"))
        except (ValueError, AttributeError):
            continue
        if str(g["home"]["id"]) == str(player):
            margin = hs - ascore
        else:
            margin = ascore - hs
        ts = g.get("time")
        if not ts:
            continue
        dt = datetime.fromtimestamp(int(ts), ET)
        rows.append((margin, dt, g["score"]))

    if not rows:
        return None

    margins = [r[0] for r in rows]
    total = len(margins)
    lo, hi = min(margins), max(margins)

    # Highest line (tightest spread) whose cover rate is still >= threshold.
    # Scanning low->high means rate falls as the line rises, so the last line
    # that still qualifies is the tightest reliable one.
    best_line = None
    best_rate = 0.0
    for line in range(lo - 1, hi + 1):
        rate = sum(1 for m in margins if m > line + 0.5) / total
        if rate >= threshold:
            best_line = line
            best_rate = rate

    if best_line is None:
        return {"spread": None, "rate": None, "total": total,
                "hits": 0, "misses": [], "all_rows": rows}

    misses = [r for r in rows if r[0] <= best_line + 0.5]
    return {
        "spread": -(best_line + 0.5),
        "rate": best_rate,
        "total": total,
        "hits": total - len(misses),
        "misses": misses,
        "all_rows": rows,
    }


def print_miss_days(name, result, threshold=0.90, split_hour=12):
    """
    Print the miss breakdown for one player: which weekday the non-covers land
    on, and how they split by time of day (before vs after `split_hour`, ET).
    The all-games split is shown alongside so you can tell a real lean from
    plain volume -- if most games are afternoon, misses will be too.
    """
    pct = int(threshold * 100)
    if result is None:
        print(f"\n  {name}: no dated games to analyze.")
        return
    if result["spread"] is None:
        print(f"\n  {name}: no line reaches {pct}% cover in this sample.")
        return

    # --- header line for this player ---
    print(f"\n  {Colors.BOLD}{name}{Colors.END}   "
          f"{pct}%+ line {Colors.BOLD}{result['spread']:+.1f}{Colors.END}   "
          f"covered {result['hits']}/{result['total']} ({result['rate']:.0%})")

    if not result["misses"]:
        print(f"      {Colors.GREEN}no non-covers -- this line hit 100% here{Colors.END}")
        return

    misses = result["misses"]
    all_rows = result.get("all_rows", misses)
    n_miss = len(misses)
    n_all = len(all_rows)

    # --- weekday tally ---
    order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    tally = Counter(r[1].strftime("%a") for r in misses)
    wk = "   ".join(f"{d} x{tally[d]}" for d in order if tally[d])
    print(f"      {Colors.CYAN}by weekday{Colors.END}   {wk}")

    # --- session-half split, misses vs all games for base-rate context ---
    mb = sum(1 for r in misses if r[1].hour < split_hour)
    ma = n_miss - mb
    ab = sum(1 for r in all_rows if r[1].hour < split_hour)
    aa = n_all - ab
    cut = f"{split_hour}:00"
    print(f"      {Colors.CYAN}by half{Colors.END}      "
          f"before {cut}:  {mb}/{n_miss} misses   vs   {ab}/{n_all} games ({ab / n_all:.0%})")
    print(f"                   after  {cut}:  {ma}/{n_miss} misses   vs   {aa}/{n_all} games ({aa / n_all:.0%})")
    if ab == 0 or aa == 0:
        print(f"      {Colors.YELLOW}(all games on one side of {cut} -- likely the other "
              f"rotation; split not meaningful){Colors.END}")

    # --- aligned table of the individual misses ---
    print(f"      {Colors.CYAN}misses{Colors.END}")
    print(f"        {'date':<11}{'when':<11}{'score':>8}{'margin':>9}")
    for margin, dt, score in misses:
        print(f"        {dt.strftime('%Y-%m-%d'):<11}{dt.strftime('%a %H:%M'):<11}"
              f"{score:>8}{margin:>+9d}")


def get_head_to_head_stats(games, player1, player2):
    """
    Calculate wins/losses and average margins
    """
    p1_wins = 0
    p2_wins = 0
    p1_margins = []
    p2_margins = []

    for g in games:
        try:
            home_score, away_score = map(int, g["score"].split("-"))

            if str(g["home"]["id"]) == str(player1):
                margin = home_score - away_score
                if margin > 0:
                    p1_wins += 1
                else:
                    p2_wins += 1
                p1_margins.append(margin)
            else:
                margin = away_score - home_score
                if margin > 0:
                    p1_wins += 1
                else:
                    p2_wins += 1
                p1_margins.append(margin)
        except:
            continue

    p1_avg_margin = sum(p1_margins) / len(p1_margins) if p1_margins else 0

    return {
        "p1_wins": p1_wins,
        "p2_wins": p2_wins,
        "p1_avg_margin": p1_avg_margin,
        "p2_avg_margin": -p1_avg_margin
    }


def calculate_form(games, player1, last_n):
    """
    Calculate recent form (wins in last N games)
    """
    recent_games = games[:min(last_n, len(games))]
    wins = 0

    for g in recent_games:
        try:
            home_score, away_score = map(int, g["score"].split("-"))

            if str(g["home"]["id"]) == str(player1):
                if home_score > away_score:
                    wins += 1
            else:
                if away_score > home_score:
                    wins += 1
        except:
            continue

    return wins, len(recent_games)


def color_by_hit_rate(hit_rate_str):
    """
    Return colored text based on hit rate
    """
    rate = float(hit_rate_str.strip('%'))
    if rate == 100.0:
        return f"{Colors.GREEN}{Colors.BOLD}{hit_rate_str}{Colors.END}"
    elif rate >= 95.0:
        return f"{Colors.GREEN}{hit_rate_str}{Colors.END}"
    elif rate >= 90.0:
        return f"{Colors.YELLOW}{hit_rate_str}{Colors.END}"
    else:
        return hit_rate_str


def resolve_player(name):
    """
    Look up a player id by name, with a friendlier error if it's missing.
    """
    if name not in player_ids:
        print(f"{Colors.RED}'{name}' is not in player_ids.{Colors.END}")
        print(f"{Colors.YELLOW}Run option 3 (Discover / Update Players) to refresh the roster.{Colors.END}")
        return None
    return player_ids[name]


def analyze_matchup():
    """
    Analyze a specific matchup between two players
    """
    print(f"\n{Colors.CYAN}{Colors.BOLD}=== MATCHUP ANALYSIS ==={Colors.END}")
    name1 = input("Enter first player name: ")
    name2 = input("Enter second player name: ")
    num_games = int(input("How many games do you want to analyze? "))

    player1 = resolve_player(name1)
    player2 = resolve_player(name2)
    if player1 is None or player2 is None:
        return

    games = get_head_to_head_games(player1, player2, num_games)

    if not games:
        print("No games found between these players.")
        return

    print(f"\nFound {len(games)} games between {name1} and {name2}.")

    # Get head-to-head stats
    stats = get_head_to_head_stats(games, player1, player2)

    print(f"\n{Colors.BOLD}HEAD-TO-HEAD RECORD:{Colors.END}")
    print(f"{name1}: {Colors.GREEN}{stats['p1_wins']} wins{Colors.END}")
    print(f"{name2}: {Colors.GREEN}{stats['p2_wins']} wins{Colors.END}")
    print(f"\n{Colors.BOLD}AVERAGE MARGIN:{Colors.END}")
    print(f"{name1}: {stats['p1_avg_margin']:+.1f} points")
    print(f"{name2}: {stats['p2_avg_margin']:+.1f} points")

    # Analyze from player1's perspective
    results_p1 = analyze_spreads(games, player1)

    # Analyze from player2's perspective
    results_p2 = analyze_spreads(games, player2)

    print(f"\n{'=' * 60}")
    print(f"{Colors.BOLD}80-100% Hit Rate Lines for {name1.upper()}:{Colors.END}")
    print(f"{'=' * 60}")
    if results_p1:
        for r in results_p1:
            spread = r['spread']
            status = f" {Colors.GREEN}[100% GREEN]{Colors.END}" if r['hit_rate'] == "100.00%" else ""
            colored_rate = color_by_hit_rate(r['hit_rate'])
            print(f"Spread {spread:+.1f} | Hit Rate {colored_rate}{status} "
                  f"({r['hits']}/{r['games']})")
    else:
        print("No 80-100% reliable lines found.")

    print(f"\n{'=' * 60}")
    print(f"{Colors.BOLD}80-100% Hit Rate Lines for {name2.upper()}:{Colors.END}")
    print(f"{'=' * 60}")
    if results_p2:
        for r in results_p2:
            spread = r['spread']
            status = f" {Colors.GREEN}[100% GREEN]{Colors.END}" if r['hit_rate'] == "100.00%" else ""
            colored_rate = color_by_hit_rate(r['hit_rate'])
            print(f"Spread {spread:+.1f} | Hit Rate {colored_rate}{status} "
                  f"({r['hits']}/{r['games']})")
    else:
        print("No 80-100% reliable lines found.")

    # Which days / halves of the session break a reliable line, at two tiers
    for thr in (0.90, 0.95):
        pct = int(thr * 100)
        print(f"\n{'=' * 60}")
        print(f"{Colors.BOLD}{pct}%+ SPREAD MISS-DAY BREAKDOWN (Eastern time):{Colors.END}")
        print(f"{'=' * 60}")
        print_miss_days(name1, analyze_spread_misses_by_day(games, player1, threshold=thr), threshold=thr)
        print_miss_days(name2, analyze_spread_misses_by_day(games, player2, threshold=thr), threshold=thr)
    print(f"\n{Colors.YELLOW}Note: the 95%+ line is looser, so it has even fewer misses "
          f"(<=5%) than the 90%+ one -- treat both day/half splits as anecdotal until you "
          f"have a real pile of misses.{Colors.END}")


def analyze_form():
    """
    Analyze recent form for a matchup
    """
    print(f"\n{Colors.CYAN}{Colors.BOLD}=== FORM ANALYSIS ==={Colors.END}")
    name1 = input("Enter first player name: ")
    name2 = input("Enter second player name: ")
    num_games = int(input("How many total games to fetch? "))

    player1 = resolve_player(name1)
    player2 = resolve_player(name2)
    if player1 is None or player2 is None:
        return

    games = get_head_to_head_games(player1, player2, num_games)

    if not games:
        print("No games found between these players.")
        return

    print(f"\nFound {len(games)} games between {name1} and {name2}.")

    # Calculate form for different periods based on available games
    max_games = len(games)
    form_periods = []

    if max_games >= 5:
        form_periods.append(5)
    if max_games >= 10:
        form_periods.append(10)
    if max_games >= 15:
        form_periods.append(15)
    if max_games >= 20:
        form_periods.append(20)
    if max_games >= 30:
        form_periods.append(30)
    if max_games >= 50:
        form_periods.append(50)

    # Always include the total if not already in the list
    if max_games not in form_periods:
        form_periods.append(max_games)

    print(f"\n{Colors.BOLD}RECENT FORM:{Colors.END}")
    for period in form_periods:
        p1_wins, p1_games = calculate_form(games, player1, period)
        p2_wins = p1_games - p1_wins

        p1_rate = (p1_wins / p1_games * 100) if p1_games > 0 else 0
        p2_rate = (p2_wins / p1_games * 100) if p1_games > 0 else 0

        print(f"\n{Colors.CYAN}Last {period} games:{Colors.END}")
        print(f"  {name1}: {Colors.GREEN}{p1_wins}/{p1_games}{Colors.END} wins ({p1_rate:.1f}%)")
        print(f"  {name2}: {Colors.GREEN}{p2_wins}/{p1_games}{Colors.END} wins ({p2_rate:.1f}%)")


def print_rotation_pool(pct, misses, all_dts, split_hour=12):
    """
    Print pooled miss stats for one threshold across a whole rotation.
    Reports MISS RATE (misses / games) by weekday and by session half, which
    controls for volume automatically -- an elevated rate is the real signal,
    not a raw count.
    """
    n_all = len(all_dts)
    n_miss = len(misses)
    print(f"\n{'=' * 60}")
    print(f"{Colors.BOLD}{pct}%+ LINE MISSES (pooled across rotation){Colors.END}")
    print(f"{'=' * 60}")
    if n_all == 0:
        print("  no games.")
        return
    print(f"  {Colors.BOLD}{n_miss} misses over {n_all} games{Colors.END} "
          f"({n_miss / n_all:.1%} of games broke a {pct}%+ line)")
    if n_miss == 0:
        return

    # --- miss rate by weekday ---
    order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    games_by_day = Counter(dt.strftime("%a") for dt in all_dts)
    miss_by_day = Counter(r[1].strftime("%a") for r in misses)
    print(f"      {Colors.CYAN}miss rate by weekday{Colors.END}")
    for d in order:
        gd = games_by_day.get(d, 0)
        if not gd:
            continue
        md = miss_by_day.get(d, 0)
        print(f"        {d}   {md / gd:>4.0%}   ({md}/{gd})")

    # --- miss rate by session half ---
    gb = sum(1 for dt in all_dts if dt.hour < split_hour)
    ga = n_all - gb
    mb = sum(1 for r in misses if r[1].hour < split_hour)
    ma = n_miss - mb
    cut = f"{split_hour}:00"
    print(f"      {Colors.CYAN}miss rate by session half (noon ET){Colors.END}")
    if gb:
        print(f"        first half  (before {cut})   {mb / gb:>4.0%}   ({mb}/{gb})")
    if ga:
        print(f"        second half (after  {cut})   {ma / ga:>4.0%}   ({ma}/{ga})")
    if gb == 0 or ga == 0:
        print(f"        {Colors.YELLOW}(all games on one side of {cut} -- "
              f"split not meaningful for this rotation){Colors.END}")


def analyze_rotation():
    """
    Scan every player-vs-player matchup within one rotation, pool the games
    that break a 90%+ and 95%+ spread line, and report how those misses
    distribute by weekday and by time of day.
    """
    print(f"\n{Colors.CYAN}{Colors.BOLD}=== ROTATION-WIDE MISS SCAN ==={Colors.END}")
    print("Which rotation?")
    print("  0 = Daytime   (~8:30am-4:05pm ET)")
    print("  1 = Overnight (~12:40am-7:35am ET)")
    choice = input("Enter 0 or 1: ").strip()
    if choice not in ROTATIONS:
        print(f"{Colors.RED}Invalid choice -- type 0 for daytime or 1 for overnight.{Colors.END}")
        return
    rot = ROTATIONS[choice]

    raw = input("Games per matchup to scan (default 50): ").strip()
    try:
        per = int(raw) if raw else 50
        if per <= 0:
            per = 50
    except ValueError:
        per = 50

    # Only players that actually exist in the current dict
    keys = [k for k in rot["players"] if k in player_ids]
    missing = [k for k in rot["players"] if k not in player_ids]
    if len(keys) < 2:
        print(f"{Colors.RED}Need at least 2 known players in this rotation; found {len(keys)}.{Colors.END}")
        return

    print(f"\n{Colors.BOLD}{rot['label']}{Colors.END}")
    print(f"Players ({len(keys)}): {', '.join(keys)}")
    if missing:
        print(f"{Colors.YELLOW}Not in current dict, skipped: {', '.join(missing)}{Colors.END}")

    # Every unordered pair, skipping two IDs that are the same person
    def base(k):
        return re.sub(r"_\d+$", "", k)
    pairs = [(a, b) for a, b in itertools.combinations(keys, 2) if base(a) != base(b)]

    print(f"Scanning {len(pairs)} matchups (up to {per} games each). This can take a bit...\n")

    all_dts = []                    # datetime of every pooled game (each once)
    pools = {0.90: [], 0.95: []}    # threshold -> list of miss rows (margin, dt, score)
    scanned = 0

    for a, b in pairs:
        aid, bid = player_ids[a], player_ids[b]
        try:
            games = get_head_to_head_games(aid, bid, per, verbose=False)
        except Exception as e:
            print(f"  {a} vs {b}: {Colors.RED}fetch error ({e}){Colors.END}")
            continue

        n = len(games)
        if n == 0:
            print(f"  {a} vs {b}: {Colors.YELLOW}no games{Colors.END}")
            continue
        scanned += 1
        print(f"  {a} vs {b}: {n} games")

        for g in games:
            ts = g.get("time")
            if ts:
                all_dts.append(datetime.fromtimestamp(int(ts), ET))

        # Pool misses from BOTH sides at BOTH thresholds
        for thr in (0.90, 0.95):
            for pid in (aid, bid):
                res = analyze_spread_misses_by_day(games, pid, threshold=thr)
                if res and res.get("misses"):
                    pools[thr].extend(res["misses"])

        time.sleep(0.15)  # stay under the rate limit

    if not all_dts:
        print(f"\n{Colors.RED}No games found for this rotation.{Colors.END}")
        return

    print(f"\n{Colors.GREEN}Pooled {len(all_dts)} games across {scanned} matchups.{Colors.END}")
    for thr in (0.90, 0.95):
        print_rotation_pool(int(thr * 100), pools[thr], all_dts)

    print(f"\n{Colors.YELLOW}Read the RATES, not the counts: a weekday or half with a "
          f"higher miss rate than the others is the real lean -- volume is already "
          f"divided out.{Colors.END}")


def show_menu():
    """
    Display main menu
    """
    print(f"\n{Colors.BLUE}{Colors.BOLD}{'=' * 60}{Colors.END}")
    print(f"{Colors.BLUE}{Colors.BOLD}E-BASKETBALL SPREAD ANALYZER{Colors.END}")
    print(f"{Colors.BLUE}{Colors.BOLD}{'=' * 60}{Colors.END}")
    print("\n1. Analyze Matchup (Spreads & Stats)")
    print("2. Analyze Form (Recent Performance)")
    print("3. Discover / Update Players")
    print("4. Scan Rotation (pooled 90%/95% miss analysis)")
    print("5. Exit")
    print(f"\n{Colors.BLUE}{'=' * 60}{Colors.END}")


def main():
    """
    Main menu loop
    """
    if API_TOKEN == "PASTE_YOUR_NEW_TOKEN_HERE":
        print(f"{Colors.YELLOW}Warning: no token set. Set the BETSAPI_TOKEN environment "
              f"variable or edit API_TOKEN at the top of the file.{Colors.END}")

    while True:
        show_menu()
        choice = input("\nSelect an option (1-5): ")

        if choice == "1":
            analyze_matchup()
        elif choice == "2":
            analyze_form()
        elif choice == "3":
            discover_players()
        elif choice == "4":
            analyze_rotation()
        elif choice == "5":
            print(f"\n{Colors.GREEN}Thanks for using the analyzer! Goodbye.{Colors.END}")
            break
        else:
            print(f"{Colors.RED}Invalid option. Please choose 1-5.{Colors.END}")


if __name__ == "__main__":
    main()
