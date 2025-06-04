# Multiplayer Oregon Trail

A multiplayer version of the classic Oregon Trail game where multiple players can travel together, share resources, and compete to reach Oregon first.

## Features

- Real-time multiplayer gameplay
- Resource management (food, ammo, money)
- Player status dashboard
- Multiple actions (move, hunt, buy food)
- Simple and intuitive controls

## Requirements

- Python 3.8 or higher
- Pygame 2.5.2

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/multiplayer-oregon-trail.git
cd multiplayer-oregon-trail
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the Game

1. Start the server:
```bash
python server.py
```

2. Start one or more clients (in separate terminals):
```bash
python client.py
```

## Controls

- M - Move forward
- H - Hunt for food
- B - Buy food
- Q - Quit game

## Game Rules

- Each player starts with 100 food, 20 ammo, and 50 money
- Moving consumes 5 food
- Hunting requires 2 ammo and provides 20 food
- Buying food costs 10 money and provides 15 food
- Players can see each other's status in real-time

## Contributing

Feel free to submit issues and enhancement requests! 