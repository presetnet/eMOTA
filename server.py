import socket
import threading
import json
import random
import time
from enum import Enum

class EventType(Enum):
    ILLNESS = "illness"
    WEATHER = "weather"
    BANDITS = "bandits"
    TRADING_POST = "trading_post"
    HUNTING = "hunting"

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
        self.active_effects = []
        self.events = []

    def to_dict(self):
        return {
            "name": self.name,
            "position": self.position,
            "food": self.food,
            "ammo": self.ammo,
            "money": self.money,
            "health": self.health,
            "wagon_condition": self.wagon_condition,
            "active_effects": self.active_effects,
            "events": [event.to_dict() for event in self.events[-5:]]  # Keep last 5 events
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
        player.active_effects = data.get("active_effects", [])
        return player

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
        self.players = []
        self.day = 1
        self.trail_length = 100
        self.landmarks = {
            10: "Independence",
            30: "Fort Kearney",
            50: "Fort Laramie",
            70: "Fort Bridger",
            90: "Fort Hall"
        }
        self.weather_conditions = ["Clear", "Rain", "Storm", "Heat Wave"]
        self.current_weather = "Clear"

    def to_dict(self):
        return {
            "players": [p.to_dict() for p in self.players],
            "day": self.day,
            "trail_length": self.trail_length,
            "landmarks": self.landmarks,
            "current_weather": self.current_weather
        }

    @staticmethod
    def from_dict(data):
        game_state = GameState()
        game_state.players = [Player.from_dict(p) for p in data["players"]]
        game_state.day = data["day"]
        game_state.trail_length = data["trail_length"]
        game_state.landmarks = data["landmarks"]
        game_state.current_weather = data["current_weather"]
        return game_state

    def generate_event(self, player):
        if random.random() < 0.3:  # 30% chance of event
            event_type = random.choice(list(EventType))
            if event_type == EventType.ILLNESS:
                return Event(
                    EventType.ILLNESS,
                    "You're feeling sick!",
                    {
                        "rest": "Rest for a day (lose 1 day, recover 20 health)",
                        "continue": "Continue traveling (risk worsening condition)"
                    },
                    {
                        "rest": {"health": 20, "day": 1},
                        "continue": {"health": -10}
                    }
                )
            elif event_type == EventType.WEATHER:
                weather = random.choice(self.weather_conditions)
                return Event(
                    EventType.WEATHER,
                    f"The weather has changed to {weather}!",
                    {
                        "continue": "Continue traveling",
                        "wait": "Wait for better weather"
                    },
                    {
                        "continue": {"wagon_condition": -5 if weather == "Storm" else 0},
                        "wait": {"day": 1}
                    }
                )
            elif event_type == EventType.TRADING_POST:
                return Event(
                    EventType.TRADING_POST,
                    "You've found a trading post!",
                    {
                        "buy_food": "Buy food (10 money for 15 food)",
                        "buy_ammo": "Buy ammo (5 money for 10 ammo)",
                        "repair": "Repair wagon (20 money for 30 condition)"
                    },
                    {
                        "buy_food": {"money": -10, "food": 15},
                        "buy_ammo": {"money": -5, "ammo": 10},
                        "repair": {"money": -20, "wagon_condition": 30}
                    }
                )
        return None

class GameServer:
    def __init__(self, host='127.0.0.1', port=50000):
        self.host = host
        self.port = port
        self.clients = []
        self.game_state = GameState()
        self.last_snapshot_time = time.time()
        self.snapshot_interval = 1.0  # Send snapshots every second

    def broadcast_game_state(self):
        current_time = time.time()
        if current_time - self.last_snapshot_time >= self.snapshot_interval:
            self.last_snapshot_time = current_time
            serialized = json.dumps(self.game_state.to_dict()).encode()
            for client in self.clients:
                try:
                    client.sendall(serialized)
                except Exception as e:
                    print("Error sending to client:", e)

    def handle_action(self, player_name, action, choice=None):
        player = next((p for p in self.game_state.players if p.name == player_name), None)
        if not player:
            player = Player(player_name)
            self.game_state.players.append(player)

        if action == "move":
            player.position += 1
            player.consume_food(5)
            # Check for landmarks
            if player.position in self.game_state.landmarks:
                player.events.append(Event(
                    EventType.TRADING_POST,
                    f"You've reached {self.game_state.landmarks[player.position]}!"
                ))
        elif action == "hunt":
            if player.ammo >= 2:
                player.use_ammo(2)
                if random.random() < 0.7:  # 70% success rate
                    player.add_food(20)
                    player.events.append(Event(
                        EventType.HUNTING,
                        "Successful hunt! Gained 20 food."
                    ))
                else:
                    player.events.append(Event(
                        EventType.HUNTING,
                        "The hunt was unsuccessful."
                    ))
        elif action == "event_choice" and choice:
            event = next((e for e in player.events if e.timestamp == choice["event_time"]), None)
            if event and choice["choice"] in event.effects:
                effects = event.effects[choice["choice"]]
                for key, value in effects.items():
                    if key == "health":
                        player.modify_health(value)
                    elif key == "food":
                        player.add_food(value)
                    elif key == "ammo":
                        player.add_ammo(value)
                    elif key == "money":
                        if value < 0:
                            player.spend_money(abs(value))
                        else:
                            player.earn_money(value)
                    elif key == "wagon_condition":
                        if value < 0:
                            player.damage_wagon(abs(value))
                        else:
                            player.repair_wagon(value)
                    elif key == "day":
                        self.game_state.day += value

        # Generate new event
        new_event = self.game_state.generate_event(player)
        if new_event:
            player.events.append(new_event)

        # Update weather
        if random.random() < 0.1:  # 10% chance of weather change
            self.game_state.current_weather = random.choice(self.game_state.weather_conditions)

    def handle_client(self, client_socket):
        try:
            while True:
                data = client_socket.recv(4096)
                if not data:
                    break
                action = json.loads(data.decode())
                self.handle_action(action["player"], action["action"], action.get("choice"))
                self.broadcast_game_state()
        except Exception as e:
            print("Client error:", e)
        finally:
            self.clients.remove(client_socket)
            client_socket.close()

    def start(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind((self.host, self.port))
        server_socket.listen()
        print("Server listening on", self.port)
        while True:
            client_socket, addr = server_socket.accept()
            print("Connected to", addr)
            self.clients.append(client_socket)
            threading.Thread(target=self.handle_client, args=(client_socket,), daemon=True).start()

if __name__ == "__main__":
    GameServer().start() 