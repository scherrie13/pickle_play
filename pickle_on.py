import streamlit as st
import random
import collections
import pandas as pd
from io import BytesIO

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
    Assigns players to courts, attempting to avoid repeat partners more effectively.
    Returns the assignments and any unassigned players.
    """
    court_assignments = []
    
    current_eligible = list(eligible_players) 
    random.shuffle(current_eligible)

    assigned_in_this_call = set()

    for _ in range(num_courts):
        court = []
        potential_court_players = [p for p in current_eligible if p not in assigned_in_this_call]
        
        if len(potential_court_players) < players_per_court:
            break 
        
        # Select Player 1
        potential_p1s = sorted(potential_court_players, key=lambda p: (len(p.partners), p.games_played, random.random()))
        if not potential_p1s: break
        p1 = potential_p1s.pop(0)
        court.append(p1)
        assigned_in_this_call.add(p1)

        # Select Player 2 (p1's partner)
        remaining_for_p2 = [p for p in potential_court_players if p not in assigned_in_this_call]
        # Prioritize players who have not partnered with p1
        potential_p2s_no_partner = [p for p in remaining_for_p2 if p not in p1.partners]
        potential_p2s_with_partner = [p for p in remaining_for_p2 if p in p1.partners]

        if potential_p2s_no_partner:
            potential_p2s_no_partner.sort(key=lambda p: len(p.partners))
            p2 = potential_p2s_no_partner[0]
        elif potential_p2s_with_partner:
            potential_p2s_with_partner.sort(key=lambda p: (len(p.partners & {p1}), random.random()))
            p2 = potential_p2s_with_partner[0]
        else:
            # If no partners are available, the court can't be formed
            assigned_in_this_call.remove(p1)
            continue
        
        court.append(p2)
        assigned_in_this_call.add(p2)

        # Select Player 3
        remaining_for_p3 = [p for p in potential_court_players if p not in assigned_in_this_call]
        if not remaining_for_p3:
            assigned_in_this_call.remove(p1)
            assigned_in_this_call.remove(p2)
            continue
        
        potential_p3s = sorted(remaining_for_p3, key=lambda p: len(p.partners))
        p3 = potential_p3s[0]
        court.append(p3)
        assigned_in_this_call.add(p3)

        # Select Player 4 (p3's partner)
        remaining_for_p4 = [p for p in potential_court_players if p not in assigned_in_this_call]
        # Prioritize players who have not partnered with p3
        potential_p4s_no_partner = [p for p in remaining_for_p4 if p not in p3.partners]
        potential_p4s_with_partner = [p for p in remaining_for_p4 if p in p3.partners]

        if potential_p4s_no_partner:
            potential_p4s_no_partner.sort(key=lambda p: len(p.partners))
            p4 = potential_p4s_no_partner[0]  # Corrected line
        elif potential_p4s_with_partner:
            potential_p4s_with_partner.sort(key=lambda p: (len(p.partners & {p3}), random.random()))
            p4 = potential_p4s_with_partner[0]
        else:
            assigned_in_this_call.remove(p1)
            assigned_in_this_call.remove(p2)
            assigned_in_this_call.remove(p3)
            continue
        
        court.append(p4)
        assigned_in_this_call.add(p4)
        
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
    """Resets all session state variables for a new game."""
    st.session_state.all_players = []
    st.session_state.num_courts = 0
    st.session_state.game_number = 0
    st.session_state.game_started = False
    st.session_state.court_assignments_display = "No game started yet."
    st.session_state.sitting_out_display = ""
    st.session_state.player_names_input_value = ""
    st.toast("Game reset!")
    # Removed st.experimental_rerun() - Streamlit will rerun naturally due to session state changes.


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
    court_text_lines = []
    if court_assignments:
        for i, court in enumerate(court_assignments):
            if len(court) == 4:
                court_text_lines.append(f"Court {i+1}: **{court[0].name} & {court[1].name}** vs. **{court[2].name} & {court[3].name}**")
            elif len(court) > 0:
                court_text_lines.append(f"Court {i+1}: {', '.join([p.name for p in court])} (incomplete)")
        st.session_state.court_assignments_display = "\n\n".join(court_text_lines)
    else:
        st.session_state.court_assignments_display = "No players assigned to courts."
        
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
            
    else:
        st.error(f"Player '{player_to_remove_name}' not found.")

def show_player_stats_logic():
    stats_text = "### Player Statistics\n"
    for player in sorted(st.session_state.all_players, key=lambda p: (p.games_played, p.games_sat_out, p.name)):
        stats_text += (f"- **{player.name}**: Played {player.games_played} games (Consecutive: {player.played_consecutive_games}), "
                       f"Sat out {player.games_sat_out} games\n")
        stats_text += f"  Partners: {', '.join(sorted([p.name for p in player.partners]))}\n"
    st.markdown(stats_text)


def export_to_excel_logic(num_games_to_export, num_courts_to_export):
    """
    Generates game data for a specified number of games and outputs it to an Excel file.
    """
    if not st.session_state.player_names_input_value:
        st.error("Please enter player names before exporting.")
        return

    player_names_raw = st.session_state.player_names_input_value.strip()
    players = [Player(name.strip()) for name in player_names_raw.split('\n') if name.strip()]
    
    if len(players) < 4:
        st.error("Not enough players for even one court (need at least 4).")
        return

    # Use a deepcopy of players to avoid modifying the current game state
    # A shallow copy (list(players)) is fine here since the class instances are new
    all_players_copy = [Player(p.name) for p in players]

    all_game_data = []

    # First game assignment
    court_assignments, players_sitting_out = assign_players_to_courts(all_players_copy, num_courts_to_export)
    
    game_data = {
        "Game": 1,
        "Courts": num_courts_to_export,
        "Assignments": court_assignments,
        "Sitting Out": players_sitting_out
    }
    all_game_data.append(game_data)
    
    for player in all_players_copy:
        if player in [p for court in court_assignments for p in court]:
            player.current_status = "playing"
        else:
            player.current_status = "sitting_out"
            player.games_sat_out += 1

    # Subsequent games
    for game_num in range(2, num_games_to_export + 1):
        court_assignments, players_sitting_out = rotate_players(all_players_copy, num_courts_to_export)
        
        game_data = {
            "Game": game_num,
            "Courts": num_courts_to_export,
            "Assignments": court_assignments,
            "Sitting Out": players_sitting_out
        }
        all_game_data.append(game_data)

    # Convert data to a list of lists for DataFrame
    df_rows = []
    for game in all_game_data:
        game_num = game['Game']
        
        # Flatten court assignments
        for i, court in enumerate(game['Assignments']):
            if len(court) == 4:
                df_rows.append([game_num, f"Court {i+1}", f"{court[0].name} & {court[1].name}", f"{court[2].name} & {court[3].name}", "", ""])
            elif len(court) > 0:
                df_rows.append([game_num, f"Court {i+1}", "Incomplete Court", ', '.join([p.name for p in court]), "", ""])
        
        # Add sitting out players
        sitting_out_names = ', '.join([p.name for p in game['Sitting Out']]) if game['Sitting Out'] else "None"
        df_rows.append([game_num, "Sitting Out", "", "", sitting_out_names, ""])
        df_rows.append([]) # Empty row for readability

    # The updated line with the new column name
    df = pd.DataFrame(df_rows, columns=["Game #", "Assignment Type", "Team 1", "Team 2", "Players Sitting Out", "Score"])
    
    # Use BytesIO to create an in-memory Excel file
    excel_buffer = BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Pickleball Games')
    excel_buffer.seek(0)
    
    return excel_buffer

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
    
    col_start, col_reset = st.columns(2)
    with col_start:
        st.button("Start Game", on_click=start_game_logic, disabled=st.session_state.game_started)
    with col_reset:
        st.button("Reset Game", on_click=reset_game_state)

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
    # New section for Excel export
    st.subheader("Export Games to Excel 📥")
    num_games_for_export = st.number_input(
        "Number of games to generate:",
        min_value=1,
        value=5,
        key='num_games_for_export'
    )
    num_courts_for_export = st.number_input(
        "Number of courts for export:",
        min_value=1,
        value=st.session_state.num_courts if st.session_state.num_courts > 0 else 2,
        key='num_courts_for_export'
    )

    if st.button("Generate Excel File"):
        # The export_to_excel_logic function is called to generate the file
        excel_buffer = export_to_excel_logic(num_games_for_export, num_courts_for_export)
        if excel_buffer:
            st.download_button(
                label="Download Excel File",
                data=excel_buffer,
                file_name="pickleball_games.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            st.success("Excel file generated! Click 'Download' to save it.")
    
# Main content area for game results
st.header(f"Game {st.session_state.game_number}")

st.subheader("Court Assignments:")
st.markdown(st.session_state.court_assignments_display)

st.subheader("Players Sitting Out:")
st.markdown(st.session_state.sitting_out_display if st.session_state.sitting_out_display else "No players sitting out this round.")