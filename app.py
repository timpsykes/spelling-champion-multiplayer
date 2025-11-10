from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room, rooms
import random
import eventlet

eventlet.monkey_patch()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'spelling-champion-secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

# 50 WORDS – EASY → IMPOSSIBLE
WORDS = [
    ("cat", 12), ("dog", 12), ("sun", 12), ("book", 12), ("fish", 12),
    ("apple", 12), ("house", 12), ("tree", 12), ("bird", 12), ("cake", 12),
    ("water", 12), ("happy", 12), ("school", 12), ("friend", 12), ("play", 12),
    ("light", 12), ("night", 12), ("table", 12), ("chair", 12), ("window", 12),
    ("beautiful", 13), ("dangerous", 13), ("elephant", 13), ("giraffe", 13), ("kangaroo", 13),
    ("necessary", 14), ("embarrass", 14), ("rhythm", 14), ("xylophone", 15), ("pneumonia", 15),
    ("queue", 15), ("handkerchief", 15), ("colonel", 15), ("lieutenant", 15), ("onomatopoeia", 16),
    ("supercalifragilisticexpialidocious", 18),
    ("antidisestablishmentarianism", 18),
    ("floccinaucinihilipilification", 18),
    ("pneumonoultramicroscopicsilicovolcanoconiosis", 20),
    ("hippopotomonstrosesquipedaliophobia", 20),
    ("pseudopseudohypoparathyroidism", 20),
    ("Llanfairpwllgwyngyllgogerychwyrndrobwllllantysiliogogogoch", 22),
    ("taumatawhakatangihangakoauauotamateaturipukakapikimaungahoronukupokaiwhenuakitanatahu", 24),
    ("aequeosalinocalcalinoceraceoaluminosocupreovitriolic", 24),
    ("bababadalgharaghtakamminarronnkonnbronntonnerronntuonnthunntrovarrhounawnskawntoohoohoordenenthurnuk", 26),
]

# Room storage
rooms_data = {}  # room_code: {players: [], game_state: {...}}

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('create_room')
def create_room(data):
    name = data['name'].strip() or "Player"
    room_code = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=6))
    while room_code in rooms_data:
        room_code = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=6))
    
    rooms_data[room_code] = {
        'players': [{'id': request.sid, 'name': name, 'score': 0, 'correct': 0, 'chars': 0, 'errors': 0}],
        'current_q': 0,
        'current_player': 0,
        'game_started': False,
        'timer_start': 0,
        'result_msg': '',
        'words': WORDS.copy()
    }
    random.shuffle(rooms_data[room_code]['words'])
    join_room(room_code)
    emit('room_created', {'room_code': room_code, 'players': rooms_data[room_code]['players']})

@socketio.on('join_room')
def join_room_event(data):
    name = data['name'].strip() or "Player"
    room_code = data['room_code'].upper()
    if room_code not in rooms_data:
        emit('error', {'msg': 'Room not found!'})
        return
    if len(rooms_data[room_code]['players']) >= 5:
        emit('error', {'msg': 'Room full!'})
        return
    
    rooms_data[room_code]['players'].append({
        'id': request.sid, 'name': name, 'score': 0, 'correct': 0, 'chars': 0, 'errors': 0
    })
    join_room(room_code)
    emit('joined_room', {
        'room_code': room_code,
        'players': rooms_data[room_code]['players']
    }, room=room_code)

    if len(rooms_data[room_code]['players']) >= 2 and not rooms_data[room_code]['game_started']:
        start_game(room_code)

def start_game(room_code):
    rooms_data[room_code]['game_started'] = True
    rooms_data[room_code]['timer_start'] = time.time()
    socketio.emit('game_start', {'players': rooms_data[room_code]['players']}, room=room_code)
    ask_next_question(room_code)

def ask_next_question(room_code):
    data = rooms_data[room_code]
    if data['current_q'] >= len(data['words']):
        socketio.emit('game_over', {'final_scores': [p['score'] for p in data['players']]}, room=room_code)
        return
    
    word, time_limit = data['words'][data['current_q']]
    player = data['players'][data['current_player']]['name']
    data['timer_start'] = time.time()
    data['time_limit'] = time_limit
    socketio.emit('new_question', {
        'player_name': player,
        'word': word,
        'time_limit': time_limit,
        'level': data['current_q'] + 1
    }, room=room_code)

@socketio.on('submit_answer')
def submit_answer(data):
    room_code = list(rooms(request.sid))[0]
    room = rooms_data[room_code]
    answer = data['answer'].strip().lower()
    word = room['words'][room['current_q']][0].lower()
    
    player = room['players'][room['current_player']]
    player['chars'] += len(data['answer'])
    
    if answer == word:
        player['correct'] += 1
        pts = 100 * (2 ** (player['correct'] - 1))
        player['score'] += pts
        result = f"CORRECT! +{pts} points"
    else:
        player['errors'] += 1
        result = f"WRONG! Correct: {room['words'][room['current_q']][0].upper()}"
    
    room['result_msg'] = result
    socketio.emit('result', {
        'result': result,
        'scores': [p['score'] for p in room['players']],
        'correct_count': [p['correct'] for p in room['players']]
    }, room=room_code)
    
    room['current_q'] += 1
    room['current_player'] = (room['current_player'] + 1) % len(room['players'])
    
    if room['current_q'] >= len(words):
        socketio.emit('game_over', {'final_scores': [p['score'] for p in room['players']]}, room=room_code)
    else:
        ask_next_question(room_code)

@socketio.on('time_up')
def time_up():
    room_code = list(rooms(request.sid))[0]
    room = rooms_data[room_code]
    word = room['words'][room['current_q']][0]
    room['result_msg'] = f"TIME UP! Correct: {word.upper()}"
    socketio.emit('result', {'result': room['result_msg']}, room=room_code)
    
    room['current_q'] += 1
    room['current_player'] = (room['current_player'] + 1) % len(room['players'])
    if room['current_q'] >= len(words):
        socketio.emit('game_over', {}, room=room_code)
    else:
        ask_next_question(room_code)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
