import streamlit as st
import random
import collections

# --- Core Logic Classes and Functions (No Change Needed Here) ---

class Player:
    def __init__(self, name):
        self.name = name
        self.games_played = 0
        self.games_sat_out = 0
        self.current_status = "available" # "available", "playing", "sitting_out"
        self.partners = set() # Set to store players this player has partnered with
        self.played_consecutive_games = 0 # Track consecutive games played

    def __repr__(self):
        return (f"Player(name='{self.name}', played={self.games_played}, "
                f"sat_out={self.games_sat_out}, cons={self.played_consecutive_games})")

    def __eq__(self, other):
        return self.name == other.name if isinstance(other, Player) else False

    def __hash__(self):
        return hash(self.name)

def assign_players_to_courts(eligible_players, num_courts, players_per_court=4):
    """
    Assigns players to courts, attempting to avoid repeat partners.
    Returns the assignments and any unassigned players.
    """
    court_assignments = []
    unassigned_players = []
    
    current_eligible = list(eligible_players) 
    random.shuffle(current_eligible) # Shuffle to add randomness when choices are equal

    # Keep track of players already assigned in this call to prevent double assignment
    assigned_in_this_call = set()

    for _ in range(num_courts):
        court = []
        # Need 4 unique players for a full court
        potential_court_players = [p for p in current_eligible if p not in assigned_in_this_call]
        
        if len(potential_court_players) < players_per_court:
            # Not enough players left for a full court
            break 
        
        p1 = None
        potential_p1s = sorted(potential_court_players, key=lambda p: (len(p.partners), p.games_played, random.random()))
        
        if potential_p1s:
            p1 = potential_p1s.pop(0)
            court_candidates = [p1]
            assigned_in_this_call.add(p1)
        else:
            break

        remaining_for_p2 = [p for p in potential_court_players if p not in assigned_in_this_call]
        potential_p2s = [p for p in remaining_for_p2 if p not in p1.partners]
        
        if not potential_p2s:
            potential_p2s = remaining_for_p2
            if not potential_p2s:
                unassigned_players.append(p1)
                assigned_in_this_call.remove(p1)
                break
            potential_p2s.sort(key=lambda p: (len(p.partners & {p1}), random.random()))
            p2 = potential_p2s[0]
        else:
            potential_p2s.sort(key=lambda p: len(p.partners)) 
            p2 = potential_p2s[0]
        
        court_candidates.append(p2)
        assigned_in_this_call.add(p2)

        remaining_for_p3 = [p for p in potential_court_players if p not in assigned_in_this_call]
        potential_p3s = sorted(remaining_for_p3, key=lambda p: len(p.partners))
        if not potential_p3s:
            unassigned_players.extend([p for p in court_candidates if p not in unassigned_players])
            break
        p3 = potential_p3s[0]
        court_candidates.append(p3)
        assigned_in_this_call.add(p3)

        remaining_for_p4 = [p for p in potential_court_players if p not in assigned_in_this_call]
        potential_p4s = [p for p in remaining_for_p4 if p not in p3.partners]

        if not potential_p4s:
            potential_p4s = remaining_for_p4
            if not potential_p4s:
                unassigned_players.extend([p for p in court_candidates if p not in unassigned_players])
                break
            potential_p4s.sort(key=lambda p: (len(p.partners & {p3}), random.random()))
            p4 = potential_p4s[0]
        else:
            potential_p4s.sort(key=lambda p: len(p.partners))
            p4 = potential_p4s[0]
        
        court_candidates.append(p4)
        assigned_in_this_call.add(p4)
        
        court = court_candidates

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
    """
    Manages player rotation for multiple games, ensuring different players sit out.
    """
    players_per_court = 4
    num_players = len(all_players)
    total_playing_spots = num_courts * players_per_court
    
    # 1. Update stats from previous round and prepare for new round
    for player in all_players:
        if player.current_status == "playing":
            player.games_played += 1
            # played_consecutive_games is updated in assign_players_to_courts
        elif player.current_status == "sitting_out":
            player.games_sat_out += 1
            player.played_consecutive_games = 0 # Reset if they sat out
        player.current_status = "available" # All become available for next selection

    # Determine how many players need to sit out
    num_to_sit_out = max(0, num_players - total_playing_spots)

    sit_out_for_this_round = []
    players_for_next_game = []

    if num_to_sit_out == 0:
        players_for_next_game = list(all_players)
    else:
        # Candidate pool for sitting out: players who are currently available.
        # Prioritize those who have played more consecutive games, then played more overall, then sat out less.
        sit_out_candidates = sorted(
            [p for p in all_players if p.current_status == "available"],
            key=lambda p: (-p.played_consecutive_games, -p.games_played, p.games_sat_out, random.random())
        )
        
        sit_out_for_this_round = sit_out_candidates[:num_to_sit_out]
        
        players_for_next_game = [p for p in all_players if p not in sit_out_for_this_round]

    random.shuffle(players_for_next_game) # Shuffle eligible players for varied court assignment attempts

    court_assignments, actual_unassigned_by_assign_func = assign_players_to_courts(players_for_next_game, num_courts, players_per_court)

    for p in actual_unassigned_by_assign_func:
        if p not in sit_out_for_this_round:
            sit_out_for_this_round.append(p)
            p.current_status = "sitting_out"
            p.games_sat_out += 1
            p.played_consecutive_games = 0

    for p in sit_out_for_this_round:
        p.current_status = "sitting_out"
        p.played_consecutive_games = 0

    return court_assignments, sit_out_for_this_round

# --- Streamlit Application UI ---

st.set_page_config(
    page_title="Pickleball Court Picker",
    page_icon="🎾",
    layout="centered"
)

st.title("🎾 Pickleball Court Picker")

# Initialize session state variables if they don't exist
if 'all_players' not in st.session_state:
    st.session_state.all_players = []
if 'num_courts' not in st.session_state:
    st.session_state.num_courts = 0
if 'game_number' not in st.session_state:
    st.session_state.game_number = 0
if 'game_started' not in st.session_state:
    st.session_state.game_started = False
if 'court_assignments_display' not in st.session_state:
    st.session_state.court_assignments_display = "No game started yet."
if 'sitting_out_display' not in st.session_state:
    st.session_state.sitting_out_display = ""
if 'player_names_input_value' not in st.session_state:
    st.session_state.player_names_input_value = ""

def reset_game_state():
    st.session_state.all_players = []
    st.session_state.num_courts = 0
    st.session_state.game_number = 0
    st.session_state.game_started = False
    st.session_state.court_assignments_display = "No game started yet."
    st.session_state.sitting_out_display = ""
    st.session_state.player_names_input_value = ""
    st.toast("Game reset!")
    st.experimental_rerun()


def start_game_logic():
    player_names_raw = st.session_state.player_names_input_value.strip()
    num_courts_input = st.session_state.num_courts_input

    if not player_names_raw:
        st.error("Please enter player names.")
        return

    try:
        num_courts = int(num_courts_input)
        if num_courts <= 0:
            st.error("Number of courts must be positive.")
            return
    except ValueError:
        st.error("Please enter a valid number for courts.")
        return

    players = []
    for name in player_names_raw.split('\n'):
        name = name.strip()
        if name:
            players.append(Player(name))
    
    if len(players) < 4:
        st.error("Not enough players for even one court (need at least 4).")
        return
    
    st.session_state.all_players = players
    st.session_state.num_courts = num_courts
    st.session_state.game_number = 1
    st.session_state.game_started = True

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

    update_display(court_assignments, players_sitting_out)
    st.success("Game started!")


def next_game_logic():
    if not st.session_state.game_started:
        st.warning("Please start a game first.")
        return

    if len(st.session_state.all_players) < st.session_state.num_courts * 4:
        if len(st.session_state.all_players) < 4:
            st.error("Not enough players to form any courts. Consider adding players or reducing courts.")
            return
        else:
            st.warning(f"Only {len(st.session_state.all_players)} players for {st.session_state.num_courts} courts. Will form as many as possible.")
    
    st.session_state.game_number += 1
    
    court_assignments, players_sitting_out = rotate_players(st.session_state.all_players, st.session_state.num_courts)
    update_display(court_assignments, players_sitting_out)
    st.toast(f"Game {st.session_state.game_number} generated!")

def update_display(court_assignments, players_sitting_out):
    court_text = ""
    if court_assignments:
        for i, court in enumerate(court_assignments):
            if len(court) == 4:
                court_text += f"Court {i+1}: **{court[0].name} & {court[1].name}** vs. **{court[2].name} & {court[3].name}**\n"
            elif len(court) > 0:
                court_text += f"Court {i+1}: {', '.join([p.name for p in court])} (incomplete)\n"
    else:
        court_text = "No players assigned to courts."
        
    st.session_state.court_assignments_display = court_text

    sitting_out_text = ""
    if players_sitting_out:
        sitting_out_text = f"**{', '.join([p.name for p in players_sitting_out])}**"
    else:
        sitting_out_text = "No players are sitting out this round."
    st.session_state.sitting_out_display = sitting_out_text

def remove_player_logic(player_to_remove_name):
    player_found = None
    for player in st.session_state.all_players:
        if player.name == player_to_remove_name:
            player_found = player
            break
    
    if player_found:
        st.session_state.all_players.remove(player_found)
        for player in st.session_state.all_players:
            if player_found in player.partners:
                player.partners.remove(player_found)
        
        st.toast(f"{player_found.name} removed.")
        
        if st.session_state.game_started:
            st.warning("Player removed. Click 'Next Game' to re-assign players based on the updated list.")
            
        # Streamlit will rerun automatically when session state changes, no explicit rerun needed.
    else:
        st.error(f"Player '{player_to_remove_name}' not found.")

def show_player_stats_logic():
    stats_text = "### Player Statistics\n"
    for player in sorted(st.session_state.all_players, key=lambda p: (p.games_played, p.games_sat_out, p.name)):
        stats_text += (f"- **{player.name}**: Played {player.games_played} games (Consecutive: {player.played_consecutive_games}), "
                       f"Sat out {player.games_sat_out} games\n")
        stats_text += f"  Partners: {', '.join(sorted([p.name for p in player.partners]))}\n"
    st.markdown(stats_text)


# --- Streamlit UI Layout ---

# Sidebar for initial setup and controls
with st.sidebar:
    st.header("Game Setup & Controls")
    
    st.text_area(
        "Enter player names (one per line):", 
        value='\n'.join([p.name for p in st.session_state.all_players]) if st.session_state.player_names_input_value == "" else st.session_state.player_names_input_value,
        key='player_names_input_value',
        height=180
    )
    
    st.number_input(
        "Number of Courts:", 
        min_value=1, 
        value=st.session_state.num_courts if st.session_state.num_courts > 0 else 2,
        key='num_courts_input'
    )
    
    # --- Buttons moved here ---
    col_start, col_reset = st.columns(2)
    with col_start:
        st.button("Start Game", on_click=start_game_logic, disabled=st.session_state.game_started)
    with col_reset:
        st.button("Reset Game", on_click=reset_game_state)

    # Next Game and Show Stats buttons
    st.button("Next Game", on_click=next_game_logic, disabled=not st.session_state.game_started)
    st.button("Show Player Stats", on_click=show_player_stats_logic, disabled=not st.session_state.game_started)

    st.markdown("---")
    st.subheader("Manage Active Players")
    st.info("Players will appear here after 'Start Game'.")
    
    if st.session_state.all_players:
        players_copy = list(st.session_state.all_players)
        for player in players_copy:
            col_player_name, col_remove_btn = st.columns([0.7, 0.3])
            with col_player_name:
                st.write(player.name)
            with col_remove_btn:
                st.button("Remove", key=f"remove_{player.name}", on_click=remove_player_logic, args=(player.name,))
    
    st.markdown("---")


# Main content area for game results
st.header(f"Game {st.session_state.game_number}")

st.subheader("Court Assignments:")
st.markdown(st.session_state.court_assignments_display)

st.subheader("Players Sitting Out:")
st.markdown(st.session_state.sitting_out_display if st.session_state.sitting_out_display else "No players sitting out this round.")