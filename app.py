import streamlit as st
import requests
import pandas as pd
import sqlite3
from datetime import datetime

# --- 1. ROBUST SQLITE PERSISTENCE LAYER ---
DB_FILE = "openodds_ledger.db"

def init_database():
    """Initializes the database schema safely using context managers."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS arbitrage_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                sport TEXT,
                matchup TEXT,
                athlete TEXT,
                market TEXT,
                line REAL,
                dk_execution TEXT,
                fd_execution TEXT,
                profit_margin TEXT,
                bankroll_used REAL
            )
        """)
        conn.commit()

def log_arbitrage_trade(sport, matchup, athlete, market, line, dk_play, fd_play, margin, bankroll):
    """Safely records discovered mathematical value parameters into local database tables."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO arbitrage_logs 
                (timestamp, sport, matchup, athlete, market, line, dk_execution, fd_execution, profit_margin, bankroll_used)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), str(sport), str(matchup), str(athlete), str(market), float(line), str(dk_play), str(fd_play), str(margin), float(bankroll)))
            conn.commit()
    except Exception as db_err:
        st.sidebar.error(f"Database write bypassed: {str(db_err)}")

def fetch_historical_records():
    """Extracts dataframe summaries using a clean connection environment wrapper."""
    try:
        with sqlite3.connect(DB_FILE) as conn:
            return pd.read_sql_query("SELECT * FROM arbitrage_logs ORDER BY timestamp DESC", conn)
    except Exception:
        return pd.DataFrame()

# --- 2. MASTER APPLICATION FUNCTION CONTAINER ---
def main():
    # Run structural database optimization checks first
    init_database()
    
    st.title("🛡️ OpenOdds Hardened Global Engine")
    st.caption("Error-isolated multi-sport scraping architecture targeting sportsbook data pools")

    # Hardened Configuration Registry
    SPORTS_REGISTRY = {
        "🏈 NFL Football": {"id": "88670846", "keywords": ["Player Props", "Passing", "Receiving", "Touchdown"]},
        "🏀 NBA Basketball": {"id": "1030", "keywords": ["Player Props", "Points", "Assists", "Rebounds", "Threes"]},
        "⚾ MLB Baseball": {"id": "84240", "keywords": ["Batter Props", "Pitcher Props", "Strikeouts", "Bases"]},
        "🏒 NHL Hockey": {"id": "4213", "keywords": ["Player Props", "Shots", "Points", "Goals"]},
        "🎓 NCAAF Football": {"id": "88670776", "keywords": ["Player Props", "Passing", "Rushing"]}
    }

    view_mode = st.sidebar.radio("🧭 Workspace Traversal Menu:", ["Live Scanner Interface", "Historical Profits Ledger"])
    selected_sport_label = st.sidebar.selectbox("🎯 Target Sport Module Selection:", list(SPORTS_REGISTRY.keys()))
    active_sport = SPORTS_REGISTRY[selected_sport_label]

    # PANEL A: LIVE SCANNER CORE INTERFACE
    if view_mode == "Live Scanner Interface":
        class ErrorIsolatedSportsEngine:
            def __init__(self):
                self.dk_base = "https://draftkings.com"
                self.fd_url = "https://fanduel.com"
                self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

            def get_active_games(self, sport_id):
                url = f"{self.dk_base}/v5/eventgroups/{sport_id}"
                try:
                    res = requests.get(url, headers=self.headers, params={"format": "json"}, timeout=8)
                    if res.status_code != 200: return {}
                    events = res.json().get("eventGroup", {}).get("events", [])
                    return {e.get("name"): e.get("eventId") for e in events if e.get("name") and e.get("eventId")}
                except Exception:
                    return {}

            def parse_dk_props(self, game_id, keywords):
                url = f"{self.dk_base}/v3/events/{game_id}"
                extracted = {}
                try:
                    res = requests.get(url, headers=self.headers, timeout=8)
                    if res.status_code != 200: return {}
                    res_json = res.json()
                    
                    for cat in res_json.get("eventCategories", []):
                        if any(x in cat.get("name", "") for x in keywords):
                            for sub in cat.get("componentizedOffers", []):
                                m_type = sub.get("categoryName")
                                for offer in sub.get("offers", []):
                                    for out in offer:
                                        p = out.get("participant")
                                        if p and m_type:
                                            if p not in extracted: extracted[p] = {}
                                            if m_type not in extracted[p]: extracted[p][m_type] = {}
                                            
                                            raw_lbl = str(out.get("label", "Over")).strip()
                                            lbl = "Under" if "Under" in raw_lbl else "Over"
                                            
                                            extracted[p][m_type][lbl] = {
                                                "line": float(out.get("line", 0.0)),
                                                "odds": int(out.get("oddsAmerican", 100))
                                            }
                    return extracted
                except Exception:
                    return {}

            def parse_fd_props(self, fd_id):
                params = {"page": "EVENT", "eventId": str(fd_id), "_ak": "Fh7gedByw96Sp7Xf", "tabs": "PLAYER_PROPS"}
                extracted = {}
                try:
                    res = requests.get(self.fd_url, headers=self.headers, params=params, timeout=8)
                    if res.status_code != 200: return {}
                    markets = res.json().get("attachments", {}).get("markets", {})
                    
                    for m in markets.values():
                        m_name = m.get("marketName", "").replace("Player ", "")
                        for run in m.get("runners", []):
                            p = run.get("runnerName")
                            win = run.get("winRunnerOdds", {})
                            odds = win.get("americanDisplayOdds", {}).get("americanOdds")
                            
                            if p and odds and m_name:
                                if p not in extracted: extracted[p] = {}
                                if m_name not in extracted[p]: extracted[p][m_name] = {}
                                
                                raw_lbl = str(run.get("result", {}).get("type", "Over")).strip()
                                lbl = "Under" if "Under" in raw_lbl else "Over"
                                
                                raw_handicap = float(win.get("handicap", 0.0))
                                extracted[p][m_name][lbl] = {
                                    "line": abs(raw_handicap), 
                                    "odds": int(odds)
                                }
                        return extracted
                except Exception:
                    return {}

        def american_to_implied(odds):
            try:
                return 100 / (odds + 100) if odds > 0 else abs(odds) / (abs(odds) + 100)
            except Exception:
                return 0.5

        engine = ErrorIsolatedSportsEngine()
        games_map = engine.get_active_games(active_sport["id"])

        if games_map:
            selected_game = st.selectbox(f"📋 Select an Active {selected_sport_label} Matchup:", list(games_map.keys()))
            dk_id = games_map[selected_game]
            
            col1, col2 = st.columns(2)
            with col1:
                st.info(f"DraftKings Event Code Token: `{dk_id}`")
            with col2:
                fd_input_id = st.text_input("FanDuel Matchup ID Token (From URL bar):", "33104928").strip()

            st.sidebar.markdown("---")
            st.sidebar.header("📊 Arbitrage Wallet Allocation")
            total_bankroll = st.sidebar.number_input("Max Allowable Stake Pool ($)", value=100.0, step=10.0, min_value=1.0)

            if st.button("🚀 Execute Zero-Error Multi-Book Scan", type="primary"):
                with st.spinner("Processing edge structures..."):
                    dk_data = engine.parse_dk_props(dk_id, active_sport["keywords"])
                    fd_data = engine.parse_fd_props(fd_input_id)
                    alerts = []

                    for player in list(dk_data.keys()):
                        if player in fd_data:
                            for market in list(dk_data[player].keys()):
                                if market in fd_data[player]:
                                    dk_sides = dk_data[player][market]
                                    fd_sides = fd_data[player][market]
                                    
                                    if "Over" in dk_sides and "Under" in fd_sides:
                                        do, fu = dk_sides["Over"], fd_sides["Under"]
                                        if do["line"] == fu["line"] and do["line"] > 0:
                                            p1 = american_to_implied(do["odds"])
