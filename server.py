"""
Rıfkı (King) - Flask + SocketIO Server
========================================
Manages game rooms, player connections, AI auto-play,
and real-time communication via WebSockets.
"""

import uuid
import time
import threading
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room

from game_engine import GameEngine, ContractType, CONTRACT_DISPLAY
from ai_player import AIPlayer

app = Flask(__name__)
app.config['SECRET_KEY'] = 'rifki-king-secret-key-2026'
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')

# ─── Game Room Storage ────────────────────────────────────────
games = {}       # room_id -> GameRoom
player_rooms = {}  # sid -> room_id

AI_PLAY_DELAY = 1.0  # seconds between AI moves


class GameRoom:
    """Holds all state for one game room."""

    def __init__(self, room_id, num_humans=1, creator_name='Player 1'):
        self.room_id = room_id
        self.num_humans = num_humans
        self.num_ai = 4 - num_humans
        self.engine = None
        self.ai = AIPlayer(difficulty='hard')
        self.players = {}       # sid -> seat index
        self.seat_names = {}    # seat -> name
        self.seats_taken = 0
        self.started = False
        self.ai_timer = None

        # Reserve seat 0 for the creator
        self.seat_names[0] = creator_name

    @property
    def needed_humans(self):
        return self.num_humans - self.seats_taken

    def add_player(self, sid, name):
        """Add a human player, returns seat index or None."""
        if self.seats_taken >= self.num_humans:
            return None
        seat = self.seats_taken
        self.players[sid] = seat
        self.seat_names[seat] = name
        self.seats_taken += 1
        return seat

    def get_seat(self, sid):
        return self.players.get(sid)

    def init_game(self):
        """Create engine with player names and start."""
        names = []
        human_indices = list(range(self.num_humans))
        for i in range(4):
            if i < self.num_humans:
                names.append(self.seat_names.get(i, f'Player {i+1}'))
            else:
                ai_names = ['Bot Ahmet', 'Bot Mehmet', 'Bot Ayşe', 'Bot Fatma']
                names.append(ai_names[i - self.num_humans])
        self.engine = GameEngine(names, human_indices)
        self.started = True


# ─── Routes ───────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/game/<room_id>')
def game_page(room_id):
    return render_template('game.html')


@app.route('/manual-scoreboard')
def manual_scoreboard():
    return render_template('manual_scoreboard.html')


@app.route('/scoreboard/<room_id>')
def scoreboard_page(room_id):
    return render_template('scoreboard.html')


# ─── Socket Events ───────────────────────────────────────────

@socketio.on('create_game')
def handle_create_game(data):
    name = data.get('name', 'Player 1').strip() or 'Player 1'
    num_humans = int(data.get('num_humans', 1))
    num_humans = max(1, min(4, num_humans))

    room_id = uuid.uuid4().hex[:6].upper()
    room = GameRoom(room_id, num_humans, name)
    games[room_id] = room

    sid = request.sid
    seat = room.add_player(sid, name)
    player_rooms[sid] = room_id
    join_room(room_id)

    if room.needed_humans > 0:
        # Multiplayer: wait for others
        emit('game_created', {
            'room_id': room_id,
            'waiting_for': room.needed_humans
        })
    else:
        # Solo or all seats filled: start immediately
        room.init_game()
        emit('game_created', {
            'room_id': room_id,
            'waiting_for': 0
        })
        start_first_round(room)


@socketio.on('join_game')
def handle_join_game(data):
    sid = request.sid
    room_id = data.get('room_id', '').strip().upper()
    name = data.get('name', 'Player').strip() or 'Player'

    # If joining a game page (already in room)
    if room_id in games:
        room = games[room_id]

        # Check if this sid is already in the room
        if sid in room.players:
            join_room(room_id)
            emit('joined_game', {
                'room_id': room_id,
                'seat': room.players[sid]
            })
            if room.started:
                send_game_state(room, sid)
            return

        # New player joining
        if room.started:
            # Try to reconnect by matching name to an existing seat
            reconnected = False
            for old_sid, seat_idx in list(room.players.items()):
                if room.seat_names.get(seat_idx) == name and old_sid != sid:
                    # Reconnect: replace old SID with new one
                    del room.players[old_sid]
                    room.players[sid] = seat_idx
                    player_rooms[sid] = room_id
                    join_room(room_id)
                    emit('joined_game', {
                        'room_id': room_id,
                        'seat': seat_idx
                    })
                    send_game_state(room, sid)
                    reconnected = True
                    break
            if not reconnected:
                # Also allow joining if there's an empty human seat
                if room.seats_taken < room.num_humans:
                    seat = room.add_player(sid, name)
                    if seat is not None:
                        player_rooms[sid] = room_id
                        join_room(room_id)
                        emit('joined_game', {
                            'room_id': room_id,
                            'seat': seat
                        })
                        send_game_state(room, sid)
                        reconnected = True
                if not reconnected:
                    emit('error', {'message': 'Game already in progress'})
            return

        seat = room.add_player(sid, name)
        if seat is None:
            emit('error', {'message': 'Room is full'})
            return

        player_rooms[sid] = room_id
        join_room(room_id)

        emit('joined_game', {
            'room_id': room_id,
            'seat': seat
        })

        # Notify others
        socketio.emit('player_joined', {
            'players': room.seats_taken,
            'needed': room.num_humans
        }, room=room_id)

        # Check if all humans joined
        if room.needed_humans <= 0:
            room.init_game()
            socketio.emit('game_started', {}, room=room_id)
            start_first_round(room)
    else:
        emit('error', {'message': f'Room {room_id} not found'})


@socketio.on('get_state')
def handle_get_state(data):
    sid = request.sid
    room_id = data.get('room_id', '')
    room = games.get(room_id)
    if not room or not room.engine:
        return
    send_game_state(room, sid)


@socketio.on('select_contract')
def handle_select_contract(data):
    sid = request.sid
    room_id = data.get('room_id', '')
    room = games.get(room_id)
    if not room or not room.engine:
        return

    seat = room.get_seat(sid)
    if seat is None or seat != room.engine.declarer_index:
        emit('error', {'message': 'Not your turn to declare'})
        return

    contract = data.get('contract', '')
    result = room.engine.set_contract(contract)

    if not result.get('success'):
        if result.get('misdeal'):
            socketio.emit('misdeal', {'reason': result['reason']}, room=room_id)
            # Re-deal and re-prompt
            room.engine.deal()
            for p in room.engine.players:
                p.sort_hand()
            prompt_contract_selection(room)
            return
        if result.get('need_trump_suit'):
            emit('need_trump_suit', {})
            return
        emit('error', {'message': result.get('error', 'Invalid contract')})
        return

    announce_contract(room)
    broadcast_state(room)
    schedule_ai_if_needed(room)


@socketio.on('set_trump_suit')
def handle_set_trump_suit(data):
    sid = request.sid
    room_id = data.get('room_id', '')
    room = games.get(room_id)
    if not room or not room.engine:
        return

    seat = room.get_seat(sid)
    if seat is None or seat != room.engine.declarer_index:
        emit('error', {'message': 'Not your turn'})
        return

    suit = data.get('suit', '')
    result = room.engine.set_trump_suit(suit)

    if not result.get('success'):
        emit('error', {'message': result.get('error', 'Invalid suit')})
        return

    announce_contract(room)
    broadcast_state(room)
    schedule_ai_if_needed(room)


@socketio.on('play_card')
def handle_play_card(data):
    sid = request.sid
    room_id = data.get('room_id', '')
    room = games.get(room_id)
    if not room or not room.engine:
        return

    seat = room.get_seat(sid)
    if seat is None:
        emit('error', {'message': 'Not in this game'})
        return

    card_data = data.get('card', {})
    result = room.engine.play_card(seat, card_data)

    if not result.get('success'):
        emit('error', {'message': result.get('error', 'Invalid play')})
        return

    socketio.emit('card_played', {}, room=room_id)

    if result.get('trick_complete'):
        trick = result.get('trick', {})
        winner = trick.get('winner', 0)
        winner_name = room.engine.players[winner].name

        if result.get('round_over'):
            # Check girls misdeal
            if result.get('girls_misdeal'):
                socketio.emit('misdeal', {
                    'reason': result.get('reason', 'Misdeal!')
                }, room=room_id)
                prompt_contract_selection(room)
                return

            socketio.emit('trick_complete', {
                'trick': trick,
                'trick_number': trick.get('trick_number', 0),
                'winner_name': winner_name
            }, room=room_id)

            socketio.emit('round_ended', {
                'round_scores': result.get('round_scores', {}),
                'total_scores': result.get('total_scores', {}),
                'game_over': result.get('game_over', False),
                'scoreboard': room.engine.scoreboard
            }, room=room_id)
            return

        socketio.emit('trick_complete', {
            'trick': trick,
            'trick_number': trick.get('trick_number', 0),
            'winner_name': winner_name
        }, room=room_id)

        # Schedule AI play after trick display pause
        schedule_ai_if_needed(room, delay=3.5)
    else:
        # Trick not complete, next player
        schedule_ai_if_needed(room)


@socketio.on('next_round')
def handle_next_round(data):
    room_id = data.get('room_id', '')
    room = games.get(room_id)
    if not room or not room.engine:
        return

    if room.engine.game_over:
        return

    start_round(room)


@socketio.on('get_scoreboard')
def handle_get_scoreboard(data):
    room_id = data.get('room_id', '')
    room = games.get(room_id)
    if not room or not room.engine:
        emit('scoreboard_data', {'scoreboard': [], 'players': []})
        return

    emit('scoreboard_data', {
        'scoreboard': room.engine.scoreboard,
        'players': [p.to_dict(hide_hand=True) for p in room.engine.players]
    })


@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    room_id = player_rooms.pop(sid, None)
    if room_id and room_id in games:
        room = games[room_id]
        if sid in room.players:
            leave_room(room_id)


# ─── Game Flow Helpers ────────────────────────────────────────

def start_first_round(room):
    """Start round 1 after a short delay to let clients connect."""
    def _delayed_start():
        time.sleep(1.5)
        start_round(room)

    t = threading.Thread(target=_delayed_start, daemon=True)
    t.start()


def start_round(room):
    """Start a new round: deal, announce, prompt contract."""
    result = room.engine.start_new_round()
    socketio.emit('round_started', {
        'round': result['round'],
        'declarer': result['declarer'],
        'declarer_name': result['declarer_name']
    }, room=room.room_id)

    # Short delay then prompt for contract
    def _prompt():
        time.sleep(0.8)
        prompt_contract_selection(room)

    t = threading.Thread(target=_prompt, daemon=True)
    t.start()


def prompt_contract_selection(room):
    """Prompt the declarer (human or AI) to pick a contract."""
    engine = room.engine
    declarer = engine.declarer_index
    available = engine.get_available_contracts()

    if engine.players[declarer].is_human:
        # Send to human declarer
        for sid, seat in room.players.items():
            if seat == declarer:
                socketio.emit('choose_contract', {
                    'available': available
                }, room=sid)
            else:
                socketio.emit('waiting_for_contract', {
                    'declarer_name': engine.players[declarer].name
                }, room=sid)
        # Also broadcast state so hands are visible
        broadcast_state(room)
    else:
        # AI picks contract
        def _ai_contract():
            time.sleep(AI_PLAY_DELAY)
            choice = room.ai.choose_contract(engine)
            if not choice:
                return

            contract = choice['contract']
            trump_suit = choice.get('trump_suit')

            result = engine.set_contract(contract, trump_suit)

            if not result.get('success'):
                if result.get('misdeal'):
                    socketio.emit('misdeal', {
                        'reason': result['reason']
                    }, room=room.room_id)
                    engine.deal()
                    for p in engine.players:
                        p.sort_hand()
                    prompt_contract_selection(room)
                    return
                if result.get('need_trump_suit'):
                    # Set trump suit separately
                    ts = choice.get('trump_suit', 'spades')
                    engine.set_trump_suit(ts)

            announce_contract(room)
            broadcast_state(room)
            schedule_ai_if_needed(room)

        t = threading.Thread(target=_ai_contract, daemon=True)
        t.start()


def announce_contract(room):
    """Broadcast the selected contract to all players."""
    engine = room.engine
    contract = engine.current_contract
    if not contract:
        return

    info = {
        'contract': contract.value,
        'declarer_name': engine.players[engine.declarer_index].name,
        'trump_suit': engine.trump_suit.value if engine.trump_suit else None
    }
    socketio.emit('contract_selected', info, room=room.room_id)


def broadcast_state(room):
    """Send game state to all players in room."""
    for sid, seat in room.players.items():
        send_game_state(room, sid)


def send_game_state(room, sid):
    """Send personalized game state to a specific player."""
    seat = room.players.get(sid)
    if seat is None:
        return

    engine = room.engine
    state = engine.get_state(for_player=seat)
    state['your_seat'] = seat

    # Include valid cards for the current player if it's their turn
    if engine.state == 'playing' and engine.current_player_index == seat:
        valid = engine.get_valid_cards(seat)
        state['valid_cards'] = [c.to_dict() for c in valid]
    else:
        state['valid_cards'] = []

    socketio.emit('game_state', state, room=sid)


def schedule_ai_if_needed(room, delay=None):
    """If the current player is AI, schedule their move."""
    engine = room.engine
    if not engine or engine.state != 'playing':
        return

    current = engine.current_player_index
    if engine.players[current].is_human:
        # Human's turn — just broadcast state
        broadcast_state(room)
        return

    actual_delay = delay if delay is not None else AI_PLAY_DELAY

    def _ai_play():
        time.sleep(actual_delay)
        ai_play_card(room)

    t = threading.Thread(target=_ai_play, daemon=True)
    t.start()


def ai_play_card(room):
    """Have the AI play a card and handle the result."""
    engine = room.engine
    if not engine or engine.state != 'playing':
        return

    current = engine.current_player_index
    if engine.players[current].is_human:
        broadcast_state(room)
        return

    card = room.ai.choose_card(engine, current)
    if not card:
        return

    result = engine.play_card(current, card.to_dict())
    if not result.get('success'):
        return

    socketio.emit('card_played', {}, room=room.room_id)

    if result.get('trick_complete'):
        trick = result.get('trick', {})
        winner = trick.get('winner', 0)
        winner_name = engine.players[winner].name

        if result.get('round_over'):
            if result.get('girls_misdeal'):
                socketio.emit('misdeal', {
                    'reason': result.get('reason', 'Misdeal!')
                }, room=room.room_id)
                prompt_contract_selection(room)
                return

            socketio.emit('trick_complete', {
                'trick': trick,
                'trick_number': trick.get('trick_number', 0),
                'winner_name': winner_name
            }, room=room.room_id)

            socketio.emit('round_ended', {
                'round_scores': result.get('round_scores', {}),
                'total_scores': result.get('total_scores', {}),
                'game_over': result.get('game_over', False),
                'scoreboard': engine.scoreboard
            }, room=room.room_id)
            return

        socketio.emit('trick_complete', {
            'trick': trick,
            'trick_number': trick.get('trick_number', 0),
            'winner_name': winner_name
        }, room=room.room_id)

        # After trick display, continue if next player is also AI
        schedule_ai_if_needed(room, delay=3.5)
    else:
        # Trick not complete — continue
        schedule_ai_if_needed(room)


# ─── Main ─────────────────────────────────────────────────────

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    print('=' * 50)
    print('  Rifki (King) Card Game Server')
    print(f'  http://localhost:{port}')
    print('=' * 50)
    socketio.run(app, host='0.0.0.0', port=port, debug=True, allow_unsafe_werkzeug=True)