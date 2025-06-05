import socket
import threading
import json
import random
import time
from enum import Enum

class EventType(Enum):
    ILLNESS = "illness"
    WEATHER = "weather"
    TRADING = "trading"
    HUNTING = "hunting"
    WAGON_DAMAGE = "wagon_damage"

class Event:
    def __init__(self, type, description, choices=None, effects=None):
        self.type = type
        self.description = description
        self.choices = choices or {}
        self.effects = effects or {}
        self.timestamp = time.time()

    def to_dict(self):
        return {
            "type": self.type.value,
            "description": self.description,
            "choices": self.choices,
            "effects": self.effects,
            "timestamp": self.timestamp
        }

class Player:
    def __init__(self, name, position=0, food=100, ammo=20, money=50, health=100, wagon_condition=100):
        self.name = name
        self.position = position
        self.food = food
        self.ammo = ammo
        self.money = money
        self.health = health
        self.wagon_condition = wagon_condition
        self.effects = []  # List of active effects (illness, weather effects, etc.)
        self.event_log = []  # Recent events affecting this player

    def to_dict(self):
        return {
            "name": self.name,
            "position": self.position,
            "food": self.food,
            "ammo": self.ammo,
            "money": self.money,
            "health": self.health,
            "wagon_condition": self.wagon_condition,
            "effects": self.effects,
            "event_log": self.event_log[-5:]  # Keep only last 5 events
        }

    @staticmethod
    def from_dict(data):
        player = Player(
            data["name"],
            data.get("position", 0),
            data.get("food", 100),
            data.get("ammo", 20),
            data.get("money", 50),
            data.get("health", 100),
            data.get("wagon_condition", 100)
        )
        player.effects = data.get("effects", [])
        player.event_log = data.get("event_log", [])
        return player

    def add_event(self, event):
        self.event_log.append(event)
        if len(self.event_log) > 10:  # Keep only last 10 events
            self.event_log.pop(0)

    def add_effect(self, effect):
        self.effects.append(effect)

    def remove_effect(self, effect):
        if effect in self.effects:
            self.effects.remove(effect)

    def consume_food(self, amount):
        self.food = max(0, self.food - amount)
        if self.food == 0:
            self.health = max(0, self.health - 5)

    def add_food(self, amount):
        self.food += amount

    def use_ammo(self, amount):
        self.ammo = max(0, self.ammo - amount)

    def add_ammo(self, amount):
        self.ammo += amount

    def spend_money(self, amount):
        if self.money >= amount:
            self.money -= amount
            return True
        return False

    def earn_money(self, amount):
        self.money += amount

    def modify_health(self, amount):
        self.health = max(0, min(100, self.health + amount))

    def repair_wagon(self, amount):
        self.wagon_condition = min(100, self.wagon_condition + amount)

    def damage_wagon(self, amount):
        self.wagon_condition = max(0, self.wagon_condition - amount)

class GameState:
    def __init__(self):
        self.players = {}  # Dictionary of Player objects
        self.trail_length = 100
        self.landmarks = {
            10: "Independence",
            30: "Fort Kearney",
            50: "Chimney Rock",
            70: "Fort Laramie",
            90: "Oregon City"
        }
        self.current_weather = "clear"
        self.day = 1
        self.last_snapshot_time = time.time()
        self.snapshot_interval = 0.1  # Send snapshots every 100ms

    def update(self, actions):
        """Updates the game state based on player actions."""
        current_time = time.time()
        
        # Process player actions
        for player_name, action in actions.items():
            player = self.players.get(player_name)
            if not player:
                continue

            if action == "move":
                player.position = min(player.position + 1, self.trail_length)
                player.food = max(0, player.food - 5)
                self._check_landmark(player)
                self._apply_weather_effects(player)
                self._check_random_events(player)

            elif action == "hunt":
                if player.ammo >= 2:
                    player.use_ammo(2)
                    success = random.random() < 0.7  # 70% chance of successful hunt
                    if success:
                        food_gained = random.randint(15, 25)
                        player.add_food(food_gained)
                        player.add_event(f"Successfully hunted and gained {food_gained} food")
                    else:
                        player.add_event("Hunting attempt failed")

            elif action == "buy_food":
                if player.spend_money(10):
                    player.add_food(15)
                    player.add_event("Bought 15 food for 10 money")

            elif action == "repair_wagon":
                if player.spend_money(20):
                    player.wagon_condition = min(100, player.wagon_condition + 30)
                    player.add_event("Repaired wagon (+30 condition)")

        # Update weather periodically
        if current_time - self.last_snapshot_time >= 5:  # Change weather every 5 seconds
            self._update_weather()

    def _check_landmark(self, player):
        """Check if player has reached a landmark."""
        if player.position in self.landmarks:
            player.add_event(f"Reached {self.landmarks[player.position]}!")
            # Add special landmark effects here

    def _apply_weather_effects(self, player):
        """Apply effects based on current weather."""
        if self.current_weather == "storm":
            player.wagon_condition = max(0, player.wagon_condition - 5)
            player.add_event("Storm damaged wagon (-5 condition)")
        elif self.current_weather == "heat":
            player.food = max(0, player.food - 2)
            player.add_event("Hot weather spoiled some food (-2 food)")

    def _check_random_events(self, player):
        """Check for random events that might occur."""
        if random.random() < 0.1:  # 10% chance of random event
            event_type = random.choice(list(EventType))
            if event_type == EventType.ILLNESS:
                player.health = max(0, player.health - 20)
                player.add_effect("illness")
                player.add_event("Fell ill! Health -20")
            elif event_type == EventType.WAGON_DAMAGE:
                player.wagon_condition = max(0, player.wagon_condition - 15)
                player.add_event("Wagon damage! -15 condition")

    def _update_weather(self):
        """Update the weather state."""
        weathers = ["clear", "storm", "heat", "rain"]
        self.current_weather = random.choice(weathers)

    def to_dict(self):
        """Converts the game state to a dictionary for JSON serialization."""
        return {
            "players": [player.to_dict() for player in self.players.values()],
            "trail_length": self.trail_length,
            "landmarks": self.landmarks,
            "current_weather": self.current_weather,
            "day": self.day
        }

    @classmethod
    def from_dict(cls, data):
        """Creates a GameState object from a dictionary."""
        game_state = cls()
        game_state.players = {player["name"]: Player.from_dict(player) 
                            for player in data["players"]}
        game_state.trail_length = data["trail_length"]
        game_state.landmarks = data["landmarks"]
        game_state.current_weather = data["current_weather"]
        game_state.day = data["day"]
        return game_state

class GameServer:
    def __init__(self, host='127.0.0.1', port=50000):
        self.host = host
        self.port = port
        self.clients = []
        self.game_state = GameState()
        self.running = True

    def broadcast_game_state(self):
        """Broadcasts the current game state to all connected clients."""
        state_dict = self.game_state.to_dict()
        serialized = json.dumps(state_dict).encode()
        for client in self.clients:
            try:
                client.sendall(serialized)
            except Exception as e:
                print("Error sending to client:", e)

    def handle_client(self, client_socket):
        """Handles communication with a single client."""
        try:
            while self.running:
                data = client_socket.recv(4096)
                if not data:
                    break
                action = json.loads(data.decode())
                self.game_state.update({action["player"]: action["action"]})
                self.broadcast_game_state()
        except Exception as e:
            print("Client error:", e)
        finally:
            self.clients.remove(client_socket)
            client_socket.close()

    def start(self):
        """Starts the game server."""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind((self.host, self.port))
        server_socket.listen()
        print("Server listening on", self.port)

        try:
            while self.running:
                client_socket, addr = server_socket.accept()
                print("Connected to", addr)
                self.clients.append(client_socket)
                threading.Thread(target=self.handle_client, 
                               args=(client_socket,), 
                               daemon=True).start()
        except KeyboardInterrupt:
            print("Shutting down server...")
            self.running = False
            server_socket.close()

if __name__ == "__main__":
    GameServer().start() 