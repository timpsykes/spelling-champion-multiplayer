const socket = io();

let roomCode = '';
let myName = '';
let timerInterval;
let timeLeft = 0;

document.getElementById('playerName').value = 'Player' + Math.floor(Math.random()*999);

function createRoom() {
    myName = document.getElementById('playerName').value || 'Player';
    socket.emit('create_room', {name: myName});
}

function joinRoom() {
    myName = document.getElementById('playerName').value || 'Player';
    roomCode = document.getElementById('roomCode').value.toUpperCase();
    socket.emit('join_room', {name: myName, room_code: roomCode});
}

socket.on('room_created', (data) => {
    roomCode = data.room_code;
    showGame();
    document.getElementById('code').innerText = roomCode;
});

socket.on('joined_room', (data) => {
    roomCode = data.room_code;
    showGame();
    document.getElementById('code').innerText = roomCode;
    updatePlayers(data.players);
});

socket.on('game_start', (data) => {
    updatePlayers(data.players);
});

socket.on('new_question', (data) => {
    document.getElementById('question').innerHTML = `<h2>${data.player_name}'s turn!</h2><p>Spell the word you hear...</p>`;
    document.getElementById('level').innerText = `Level ${data.level}/50`;
    document.getElementById('answerInput').disabled = false;
    document.getElementById('answerInput').focus();
    document.getElementById('answerInput').value = '';
    document.getElementById('result').innerHTML = '';
    
    // Browser voice
    const utter = new SpeechSynthesisUtterance(`${data.player_name}, spell ${data.word}. Go!`);
    utter.rate = 0.9;
    speechSynthesis.speak(utter);
    
    timeLeft = data.time_limit;
    clearInterval(timerInterval);
    timerInterval = setInterval(() => {
        timeLeft--;
        document.getElementById('timer').innerText = timeLeft;
        if (timeLeft <= 0) {
            clearInterval(timerInterval);
            socket.emit('time_up');
        }
    }, 1000);
});

socket.on('result', (data) => {
    document.getElementById('result').innerHTML = `<div class="result-box">${data.result}</div>`;
    document.getElementById('answerInput').disabled = true;
    clearInterval(timerInterval);
    updateWPM(data.wpm || {gross: 0, net: 0});
});

socket.on('game_over', () => {
    document.getElementById('question').innerHTML = '<h1>GAME OVER!</h1><p>Press F5 to play again</p>';
    document.getElementById('answerInput').disabled = true;
    clearInterval(timerInterval);
});

function showGame() {
    document.getElementById('menu').classList.add('hidden');
    document.getElementById('game').classList.remove('hidden');
}

function updatePlayers(players) {
    let html = '<h3>Players:</h3>';
    players.forEach(p => {
        html += `<p>${p.name} - Score: ${p.score}</p>`;
    });
    document.getElementById('playerCount').innerText = players.length;
    // playersList.innerHTML = html;  // optional
}

document.getElementById('answerInput').addEventListener('keyup', (e) => {
    if (e.key === 'Enter') {
        socket.emit('submit_answer', {answer: e.target.value});
    }
});

socket.on('error', (data) => {
    alert(data.msg);
});
