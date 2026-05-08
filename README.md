# 🃏 Rıfkı (King) — Turkish Card Game

A real-time multiplayer Turkish trick-taking card game built with Flask + SocketIO.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![Flask](https://img.shields.io/badge/Flask-3.0-green)
![License](https://img.shields.io/badge/License-Private-red)

## 🎮 Features

- **Real-time multiplayer** via WebSockets (1-4 human players)
- **AI opponents** fill empty seats automatically
- **20-round game** with 7 contract types (Kız, Erkek, Kupa, Rıfkı, Son İki, El Almaz, Koz)
- **Manual Scoreboard** — Excel-style tracker for physical card games
- **Smart scoring** — type count of items, auto-calculates penalties
- **Validation** — enforces exact totals (4 queens, 8 boys, 13 hearts, etc.)
- **CSV Export** — download scoreboard to Excel
- **Persistent state** — scores survive page refresh

## 🚀 Quick Start (Local)

```bash
pip install -r requirements.txt
python server.py
```

Open `http://localhost:5000` in your browser.

## 📋 Game Rules

| Contract | Penalty | Total Items |
|----------|---------|-------------|
| Kız (Girls) | -100 per Queen | 4 Queens |
| Erkek (Boys) | -60 per J/K | 8 Boys |
| Kupa (Hearts) | -30 per ♥ card | 13 Hearts |
| Rıfkı | -320 for K♥ | 1 card |
| Son İki (Last Two) | -180 per trick | 2 tricks |
| El Almaz (No Tricks) | -50 per trick | 13 tricks |
| Koz (Trump) | +50 per trick | 13 tricks |

### Special Rules
- **First 4 rounds**: No trump (Koz) allowed
- **Rıfkı**: If you can't follow suit, you MUST play hearts
- **Misdeal**: If any player has only K♥, only A♥, or only K♥+A♥

## 🏗 Project Structure

```
king rifki/
├── server.py              # Flask + SocketIO server
├── game_engine.py         # Core game logic & rules
├── ai_player.py           # AI opponent logic
├── requirements.txt       # Python dependencies
├── Procfile              # Production deployment config
├── runtime.txt           # Python version for hosting
├── templates/
│   ├── index.html        # Lobby page
│   ├── game.html         # Game table
│   ├── scoreboard.html   # In-game scoreboard
│   └── manual_scoreboard.html  # Manual score tracker
├── static/
│   ├── css/style.css     # Game styles
│   └── js/game.js        # Client game logic
└── docs/
    └── AI_PLAN.md        # AI improvement roadmap
```

## 🌐 Deployment

### Render.com (Recommended — Free)
1. Push to GitHub
2. Go to [render.com](https://render.com) → New Web Service
3. Connect your GitHub repo
4. Settings: Build = `pip install -r requirements.txt`, Start = `gunicorn --worker-class geventwebsocket.gunicorn.workers.GeventWebSocketWorker -w 1 --bind 0.0.0.0:$PORT server:app`
5. Deploy!

### Custom Domain
After deploying on Render, go to Settings → Custom Domain → Add your domain.

## 🤖 AI Roadmap

See [docs/AI_PLAN.md](docs/AI_PLAN.md) for the full AI improvement plan with 4 difficulty levels.
