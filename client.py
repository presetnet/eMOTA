import socket
import json
import threading
import pygame
import sys

class GameClient:
    def __init__(self, host='127.0.0.1', port=50000):
        self.host = host
        self.port = port
        self.socket = None
        self.game_state = None
        self.player_name = None
        self.running = True

    def connect(self, player_name):
        self.player_name = player_name
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))
        threading.Thread(target=self.receive_updates, daemon=True).start()

    def receive_updates(self):
        while self.running:
            try:
                data = self.socket.recv(4096)
                if not data:
                    break
                self.game_state = json.loads(data.decode())
            except Exception as e:
                print("Error receiving update:", e)
                break
        self.socket.close()

    def send_action(self, action):
        if self.socket:
            try:
                message = json.dumps({
                    "player": self.player_name,
                    "action": action
                }).encode()
                self.socket.sendall(message)
            except Exception as e:
                print("Error sending action:", e)

    def disconnect(self):
        self.running = False
        if self.socket:
            self.socket.close()

class GameUI:
    def __init__(self, client):
        pygame.init()
        self.client = client
        self.screen = pygame.display.set_mode((800, 600))
        pygame.display.set_caption("Oregon Trail Multiplayer")
        self.font = pygame.font.Font(None, 36)
        self.clock = pygame.time.Clock()

    def draw_player_status(self, player_data):
        y = 50
        for player in player_data:
            text = f"{player['name']}: Food: {player['food']}, Ammo: {player['ammo']}, Money: {player['money']}"
            surface = self.font.render(text, True, (255, 255, 255))
            self.screen.blit(surface, (20, y))
            y += 40

    def draw_controls(self):
        controls = [
            "Controls:",
            "M - Move",
            "H - Hunt",
            "B - Buy Food",
            "Q - Quit"
        ]
        y = 300
        for text in controls:
            surface = self.font.render(text, True, (255, 255, 255))
            self.screen.blit(surface, (20, y))
            y += 40

    def run(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.client.disconnect()
                    pygame.quit()
                    return
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_m:
                        self.client.send_action("move")
                    elif event.key == pygame.K_h:
                        self.client.send_action("hunt")
                    elif event.key == pygame.K_b:
                        self.client.send_action("buy_food")
                    elif event.key == pygame.K_q:
                        self.client.disconnect()
                        pygame.quit()
                        return

            self.screen.fill((0, 0, 0))
            if self.client.game_state:
                self.draw_player_status(self.client.game_state["players"])
            self.draw_controls()
            pygame.display.flip()
            self.clock.tick(60)

def main():
    client = GameClient()
    client.connect("Player1")  # You can make this dynamic
    ui = GameUI(client)
    ui.run()

if __name__ == "__main__":
    main() 