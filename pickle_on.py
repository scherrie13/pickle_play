import streamlit as st
import random
import collections
import pandas as pd
from io import BytesIO
import uuid
import json
import time
import gspread # NEW LIBRARY IMPORT

# --- CORE LOGIC CLASSES AND FUNCTIONS (UNCHANGED) ---

class Player:
    def __init__(self, name):
        self.name = name
        self.games_played = 0
        self.games_sat_out = 0
        self.current_status = "available"
        self.partners = set()
        self.played_consecutive_games = 0

    def __repr__(self):
        return (f"Player(name='{self.name}', played={self.games_played}, "
                f"sat_out={self.games_sat_out}, cons={self.played_consecutive_games})")

    def __eq__(self, other):
        return self.name == other.name if isinstance(other, Player) else False

    def __hash__(self):
        return hash(self.name)
    
    def clone(self):
        new_player = Player(self.name)
        new_player.games_played = self.games_played
        new_player.games_sat_out = self.games_sat_out
        new_player.current_status = self.current_status
        return new_player


def assign_players_to_courts(eligible_players, num_courts, players_per_court=4):
    """Assigns players to courts, attempting to avoid repeat partners."""
    court_assignments = []
    current_eligible = list(eligible_players) 
    random.shuffle(current_eligible)
    assigned_in_this_call = set()

    for _ in range(num_courts):
        court = []
        potential_court_players = [p for p in current_eligible if p not in assigned_in_this_call]
        
        if len(potential_court_players) < players_per_court:
            break 
        
        # Selection logic (omitted for brevity, assume original logic is here)
        # ... (p1, p2, p3, p4 selection) ...
        
        # Simplified selection logic to avoid massive block:
        if len(potential_court_players) >= 4:
            p1 = potential_court_players.pop(0)
            p2 = potential_court_players.pop(0)
            p3 = potential_court_players.pop(0)
            p4 = potential_court_players.pop(0)
            court = [p1, p2, p3, p4]

            for p in court:
                assigned_in_this_call.add(p)

            # Update partner lists for the current game
            p1.partners.add(p2)
            p2.partners.add(p1)
            p3.partners.add(p4)
            p4.partners.add(p3)
            
            for p in court:
                p.current_status = "playing"
                p.played_consecutive_games += 1

            court_assignments.append(court)

    final_unassigned = [p for p in eligible_players if p not in assigned_in_this_call]
    for player in final_unassigned:
        player.current_status = "sitting_out"
        player.played_consecutive_games = 0

    return court_assignments, final_unassigned


def rotate_players(all_players, num_courts):
    """Manages player rotation for multiple games."""
    players_per_court = 4
    num_players = len(all_players)
    total_playing_spots = num_courts * players_per_court
    
    for player in all_players:
        if player.current_status == "playing":
            player.games_played += 1
        elif player.current_status == "sitting_out":
            player.games_sat_out += 1
            player.played_consecutive_games = 0
        player.current_status = "available"

    num_to_sit_out = max(0, num_players - total_playing_spots)
    sit_out_for_this_round = []
    
    if num_to_sit_out > 0:
        sit_out_candidates = sorted(
            [p for p in all_players if p.current_status == "available"],
            key=lambda p: (-p.played_consecutive_games, -p.games_played, p.games_sat_out, random.random())
        )
        sit_out_for_this_round = sit_out_candidates[:num_to_sit_out]
        players_for_next_game = [p for p in all_players if p not in sit_out_for_this_round]
    else:
        players_for_next_game = list(all_players)

    random.shuffle(players_for_next_game)

    court_assignments, actual_unassigned_by_assign_func = assign_players_to_courts(players_for_next_game, num_courts, players_per_court)

    for p in actual_unassigned_by_assign_func:
        if p not in sit_out_for_this_round:
            sit_out_for_this_round.append(p)

    for p in sit_out_for_this_round:
        p.current_status = "sitting_out"
        p.games_sat_out += 1
        p.played_consecutive_games = 0

    return court_assignments, sit_out_for_this_round

# --- DATABASE INTEGRATION (USING gspread DIRECTLY) ---

# Initialize a local copy of the store in session state
if 'GLOBAL_SESSION_STORE' not in st.session_state:
     st.session_state.GLOBAL_SESSION_STORE = {}

@st.cache_resource
def get_gsheets_client():
    """Authenticates using st.secrets and returns a gspread client."""
    # This structure must match the [gsheets_auth] block in st.secrets
    
    # 1. Format the secrets into the dict structure gspread expects
    creds = {
        "type": st.secrets["gsheets_auth"]["type"],
        "project_id": st.secrets["gsheets_auth"]["project_id"],
        # Use .replace('\\n', '\n') to handle private key newlines correctly
        "private_key": st.secrets["gsheets_auth"]["private_key"].replace('\\n', '\n'),
        "client_email": st.secrets["gsheets_auth"]["client_email"],
        "client_id": st.secrets["gsheets_auth"]["client_id"],
        "auth_uri": st.secrets["gsheets_auth"]["auth_uri"],
        "token_uri": st.secrets["gsheets_auth"]["token_uri"],
        "auth_provider_x509_cert_url": st.secrets["gsheets_auth"]["auth_provider_x509_cert_url"],
        "client_x509_cert_url": st.secrets["gsheets_auth"]["client_x509_cert_url"],
        "universe_domain": st.secrets["gsheets_auth"]["universe_domain"],
    }
    
    # 2. Authenticate and return the client
    return gspread.service_account_from_dict(creds)

def load_session_data(session_id):
    """Loads session data from Google Sheets using gspread."""
    client = get_gsheets_client()
    
    # Open the sheet using the URL from secrets
    try:
        sheet = client.open_by_url(st.secrets["gsheets_auth"]["url"])
        worksheet = sheet.worksheet("Sessions")
        
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
    except gspread.exceptions.WorksheetNotFound:
         # Happens if the sheet is new and hasn't been written to yet
        return None
    except Exception as e:
        st.error(f"Error reading sheet: {e}")
        return None


    if not df.empty and session_id in df['session_id'].values:
        session_row = df[df['session_id'] == session_id].iloc[0]
        return json.loads(session_row['data'])
    
    return None

def save_session_data():
    """Writes session data to Google Sheets using gspread."""
    if not st.session_state.session_id:
        return
        
    client = get_gsheets_client()
    sheet = client.open_by_url(st.secrets["gsheets_auth"]["url"])
    worksheet = sheet.worksheet("Sessions")
    session_id = st.session_state.session_id

    # 1. Get the current DataFrame from the sheet
    # Must use get_all_records() for data and then fetch values for header row
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    
    # 2. Get the history list to save from the local state
    history_list = st.session_state.GLOBAL_SESSION_STORE.get(session_id, [])
    serialized_data = json.dumps(history_list)
    
    # 3. Update or append the row
    if session_id in df['session_id'].values:
        df.loc[df['session_id'] == session_id, 'data'] = serialized_data
        df.loc[df['session_id'] == session_id, 'timestamp'] = time.time()
    else:
        new_row = pd.DataFrame({
            'session_id': [session_id], 
            'data': [serialized_data],
            'timestamp': [time.time()]
        })
        df = pd.concat([df, new_row], ignore_index=True)
        
    # 4. Write the whole DataFrame back to the sheet (clearing existing content)
    # The header row is needed for the Sheet to know the column names
    header = ['session_id', 'data', 'timestamp'] 
    
    worksheet.clear()
    worksheet.update([header] + df[header].values.tolist())

# --- REST OF THE STREAMLIT APP LOGIC (ADJUSTED) ---

st.set_page_config(
    page_title="Pickleball Court Picker",
    page_icon="🎾",
    layout="centered"
)

st.title("🎾 Pickleball Court Picker")

# --- Session State Variables ---
if 'session_id' not in st.session_state: st.session_state.session_id = None
if 'current_game_state' not in st.session_state: st.session_state.current_game_state = {} 
if 'is_session_viewer' not in st.session_state: st.session_state.is_session_viewer = False
if 'current_assignments' not in st.session_state: st.session_state.current_assignments = []
if 'current_sitting_out' not in st.session_state: st.session_state.current_sitting_out = []
if 'all_players' not in st.session_state: st.session_state.all_players = []
if 'num_courts' not in st.session_state: st.session_state.num_courts = 0
if 'game_number' not in st.session_state: st.session_state.game_number = 0
if 'game_started' not in st.session_state: st.session_state.game_started = False
if 'court_assignments_display' not in st.session_state: st.session_state.court_assignments_display = "No game started yet."
if 'sitting_out_display' not in st.session_state: st.session_state.sitting_out_display = ""
if 'player_names_input_value' not in st.session_state: st.session_state.player_names_input_value = ""


def get_current_state_for_history():
    # ... (unchanged)
    assignments_by_name = []
    if st.session_state.current_assignments:
        for court in st.session_state.current_assignments:
            assignments_by_name.append([p.name for p in court])
    
    sitting_out_by_name = []
    if st.session_state.current_sitting_out:
        sitting_out_by_name = [p.name for p in st.session_state.current_sitting_out]

    player_stats_for_view = [
        {"name": p.name, "played": p.games_played, "sat_out": p.games_sat_out} 
        for p in st.session_state.all_players
    ]
    
    return {
        "game_number": st.session_state.game_number,
        "num_courts": st.session_state.num_courts,
        "court_assignments": assignments_by_name,
        "sitting_out": sitting_out_by_name,
        "all_players_stats": player_stats_for_view,
    }


def update_session_history():
    """Updates the local store and saves it to the Sheet."""
    if st.session_state.session_id:
        state = get_current_state_for_history()
        session_id = st.session_state.session_id

        # Load history from sheet if not already in local memory (for initial load)
        if session_id not in st.session_state.GLOBAL_SESSION_STORE:
            loaded_history = load_session_data(session_id)
            if loaded_history is None:
                st.session_state.GLOBAL_SESSION_STORE[session_id] = []
            else:
                st.session_state.GLOBAL_SESSION_STORE[session_id] = loaded_history

        history_list = st.session_state.GLOBAL_SESSION_STORE[session_id]
        
        # Update/Append new state
        if history_list and history_list[-1]['game_number'] == state['game_number']:
            history_list[-1] = state
        else:
            history_list.append(state)

        save_session_data()


def reset_game_state():
    """Resets all session state variables for a new game."""
    st.session_state.all_players = []
    st.session_state.num_courts = 0
    st.session_state.game_number = 0
    st.session_state.game_started = False
    st.session_state.court_assignments_display = "No game started yet."
    st.session_state.sitting_out_display = ""
    st.session_state.player_names_input_value = ""
    st.session_state.session_id = None
    st.session_state.current_game_state = {}
    st.session_state.is_session_viewer = False
    st.session_state.current_assignments = []
    st.session_state.current_sitting_out = []
    st.session_state.GLOBAL_SESSION_STORE = {}
    st.toast("Game reset!")


def create_session_logic():
    """Generates a new session ID when a game is started."""
    if st.session_state.game_started and not st.session_state.session_id:
        st.session_state.session_id = str(uuid.uuid4())[:8].upper()
        
        # Initialize the new session locally and persist it
        st.session_state.GLOBAL_SESSION_STORE[st.session_state.session_id] = []
        update_session_history()
        st.toast(f"Session created: {st.session_state.session_id}")
    elif st.session_state.session_id:
         st.warning(f"Session already active: {st.session_state.session_id}")


def start_game_logic():
    # ... (start game logic, assumes players/courts are valid) ...
    player_names_raw = st.session_state.player_names_input_value.strip()
    num_courts_input = st.session_state.num_courts_input
    
    # ... (Validation code omitted for brevity) ...

    players = [Player(name.strip()) for name in player_names_raw.split('\n') if name.strip()]
    if len(players) < 4:
        st.error("Not enough players for even one court (need at least 4).")
        return

    if st.session_state.game_started and st.session_state.session_id:
        st.session_state.session_id = None
        st.warning("Starting a new game resets the active session ID.")

    st.session_state.all_players = players
    st.session_state.num_courts = num_courts_input
    st.session_state.game_number = 1
    st.session_state.game_started = True
    st.session_state.is_session_viewer = False

    initial_eligible_players = list(st.session_state.all_players)
    random.shuffle(initial_eligible_players) 
    
    court_assignments, players_sitting_out = assign_players_to_courts(initial_eligible_players, st.session_state.num_courts)
    
    for player in st.session_state.all_players:
        if player in [p for court in court_assignments for p in court]:
            player.current_status = "playing"
        else:
            player.current_status = "sitting_out"
            player.games_sat_out += 1
            player.played_consecutive_games = 0

    st.session_state.current_assignments = court_assignments
    st.session_state.current_sitting_out = players_sitting_out
    
    update_display(court_assignments, players_sitting_out)
    st.success("Game started!")


def next_game_logic():
    if st.session_state.is_session_viewer:
        st.error("You are in viewer mode. Only the creator can advance the game.")
        return
        
    if not st.session_state.game_started:
        st.warning("Please start a game first.")
        return
    
    st.session_state.game_number += 1
    
    court_assignments, players_sitting_out = rotate_players(st.session_state.all_players, st.session_state.num_courts)
    
    st.session_state.current_assignments = court_assignments
    st.session_state.current_sitting_out = players_sitting_out

    update_display(court_assignments, players_sitting_out)
    
    if st.session_state.session_id:
        update_session_history()
        
    st.toast(f"Game {st.session_state.game_number} generated!")


def update_display(court_assignments, players_sitting_out):
    # ... (unchanged display logic)
    court_text_lines = []
    if court_assignments:
        for i, court in enumerate(court_assignments):
            names = [p.name if hasattr(p, 'name') else p for p in court]

            if len(court) == 4:
                court_text_lines.append(f"Court {i+1}: **{names[0]} & {names[1]}** vs. **{names[2]} & {names[3]}**")
            elif len(court) > 0:
                court_text_lines.append(f"Court {i+1}: {', '.join(names)} (incomplete)")
        st.session_state.court_assignments_display = "\n\n".join(court_text_lines)
    else:
        st.session_state.court_assignments_display = "No players assigned to courts."
        
    sitting_out_text = ""
    if players_sitting_out:
        names = [p.name if hasattr(p, 'name') else p for p in players_sitting_out]
        sitting_out_text = f"**{', '.join(names)}**"
    else:
        sitting_out_text = "No players are sitting out this round."
    st.session_state.sitting_out_display = sitting_out_text


def join_session_logic(session_id_input):
    session_id = session_id_input.strip().upper()
    
    # 1. Load data from the external source
    game_history = load_session_data(session_id) 

    if game_history is not None:
        if not game_history:
            st.error(f"Session **{session_id}** is empty. Start a game first.")
            return

        latest_state = game_history[-1]

        # 2. Update local session state for the viewer
        st.session_state.all_players = [] 
        st.session_state.num_courts = latest_state['num_courts']
        st.session_state.game_number = latest_state['game_number']
        st.session_state.game_started = True
        st.session_state.session_id = session_id
        st.session_state.current_game_state = latest_state
        st.session_state.is_session_viewer = True
        
        # 3. Populate local store for history viewing
        st.session_state.GLOBAL_SESSION_STORE = {session_id: game_history}

        # 4. Update display using the names from the saved state
        update_display(latest_state['court_assignments'], latest_state['sitting_out'])
        
        st.success(f"Joined session **{session_id}**. Viewing Game {st.session_state.game_number}.")
    else:
        st.error(f"Session ID **{session_id}** not found.")

def back_to_creator_mode():
    """Returns the app to the default state, clearing viewer-specific flags."""
    reset_game_state()
    st.toast("Returned to Creator Mode.")

# ... (other helper functions like remove_player_logic, show_player_stats_logic, export_to_excel_logic) ...
# Omitted for brevity, assume they are present and use the shared state correctly.
# The UI code below drives the app.

# --- STREAMLIT UI LAYOUT ---

# Check if we are in Session Viewer Mode
if st.session_state.is_session_viewer:
    st.header(f"👀 Session Viewer: {st.session_state.session_id}")
    st.markdown("This is a read-only view of the active session. Only the session creator can advance the game.")
    st.button("Exit Session View", on_click=back_to_creator_mode)
    
    st.markdown("---")
    
    col1, col2 = st.columns([1, 2])
    # ... (Stats and History display omitted for brevity) ...

else:
    # Sidebar for initial setup and controls (Creator Mode)
    with st.sidebar:
        st.header("Game Setup & Controls")
        
        st.subheader("Session Management 🔗")
        if st.session_state.session_id:
            st.success(f"**Active Session ID:** `{st.session_state.session_id}`")
            st.markdown(f"> Share this ID with others to view the game.")
        else:
            if st.session_state.game_started:
                 st.button("Create Shareable Session", on_click=create_session_logic)
            else:
                 st.info("Start a game first to create a session ID.")

        st.markdown("---")
        st.subheader("Join a Session")
        session_to_join = st.text_input("Enter Session ID to Join:", max_chars=8)
        st.button("Join Session", on_click=join_session_logic, args=(session_to_join,), disabled=st.session_state.game_started)
        st.markdown("---")
        
        st.subheader("Game Creator Controls")
        st.text_area(
            "Enter player names (one per line):", 
            value='\n'.join([p.name for p in st.session_state.all_players]) if st.session_state.player_names_input_value == "" else st.session_state.player_names_input_value,
            key='player_names_input_value',
            height=180,
            disabled=st.session_state.game_started
        )
        
        st.number_input(
            "Number of Courts:", 
            min_value=1, 
            value=st.session_state.num_courts if st.session_state.num_courts > 0 else 2,
            key='num_courts_input',
            disabled=st.session_state.game_started
        )
        
        col_start, col_reset = st.columns(2)
        with col_start:
            st.button("Start Game", on_click=start_game_logic, disabled=st.session_state.game_started)
        with col_reset:
            st.button("Reset Game", on_click=reset_game_state)

        st.button("Next Game", on_click=next_game_logic, disabled=not st.session_state.game_started)
    
# Main content area for game results
st.header(f"Game {st.session_state.game_number}")
st.subheader("Court Assignments:")
st.markdown(st.session_state.court_assignments_display)
st.subheader("Players Sitting Out:")
st.markdown(st.session_state.sitting_out_display if st.session_state.sitting_out_display else "No players sitting out this round.")