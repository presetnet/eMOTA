import socket
import threading
import json

class Player:
    def __init__(self, name, position=0, food=100, ammo=20, money=50):
        self.name = name
        self.position = position
        self.food = food
        self.ammo = ammo
        self.money = money

    def to_dict(self):
        return {
            "name": self.name,
            "position": self.position,
            "food": self.food,
            "ammo": self.ammo,
            "money": self.money
        }

    @staticmethod
    def from_dict(data):
        return Player(
            data["name"],
            data.get("position", 0),
            data.get("food", 100),
            data.get("ammo", 20),
            data.get("money", 50)
        )

    def consume_food(self, amount):
        self.food = max(0, self.food - amount)

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

class GameState:
    def __init__(self, players, day, events):
        self.players = players  # List[Player]
        self.day = day
        self.events = events

    def to_dict(self):
        return {
            "players": [p.to_dict() for p in self.players],
            "day": self.day,
            "events": self.events
        }

    @staticmethod
    def from_dict(data):
        players = [Player.from_dict(p) for p in data["players"]]
        return GameState(players, data["day"], data["events"])

class GameServer:
    def __init__(self, host='127.0.0.1', port=50000):
        self.host = host
        self.port = port
        self.clients = []
        self.players = []
        self.day = 1
        self.events = []

    def broadcast_game_state(self):
        state = GameState(self.players, self.day, self.events)
        serialized = json.dumps(state.to_dict()).encode()
        for client in self.clients:
            try:
                client.sendall(serialized)
            except Exception as e:
                print("Error sending to client:", e)

    def handle_action(self, player_name, action):
        player = next((p for p in self.players if p.name == player_name), None)
        if not player:
            # New player joins
            player = Player(player_name)
            self.players.append(player)
        if action == "move":
            player.position += 1
            player.consume_food(5)
        elif action == "hunt":
            if player.ammo >= 2:
                player.use_ammo(2)
                player.add_food(20)
        elif action == "buy_food":
            if player.spend_money(10):
                player.add_food(15)
        # Add more actions as needed

    def handle_client(self, client_socket):
        try:
            while True:
                data = client_socket.recv(4096)
                if not data:
                    break
                action = json.loads(data.decode())
                self.handle_action(action["player"], action["action"])
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