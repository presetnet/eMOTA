import socket
import json
import threading
import pygame
import sys
import math
import random
from enum import Enum

class PredictionConfig:
    def __init__(self):
        self.prediction_speed_multiplier = 1.2  # Slightly faster than server
        self.reconciliation_tolerance = 2.0  # Pixels
        self.interpolation_factor = 0.3  # Smoothing factor
        self.max_prediction_time = 0.5  # Maximum time to predict ahead
        self.jitter_threshold = 5.0  # Minimum movement to consider
        self.smoothing_window = 5  # Number of positions to average

class EventType(Enum):
    ILLNESS = "illness"
    WEATHER = "weather"
    BANDITS = "bandits"
    TRADING_POST = "trading_post"
    HUNTING = "hunting"
    SKILL_CHECK = "skill_check"
    RESOURCE_DISCOVERY = "resource_discovery"
    WAGON_DAMAGE = "wagon_damage"
    TRAIL_FORK = "trail_fork"
    ENCOUNTER = "encounter"
    WEATHER_CHAIN = "weather_chain"
    RESOURCE_CHAIN = "resource_chain"
    COOPERATIVE = "cooperative"
    ENVIRONMENTAL = "environmental"
    HIDDEN_LOCATION = "hidden_location"

class SkillType(Enum):
    HUNTING = "hunting"
    GATHERING = "gathering"
    REPAIR = "repair"
    NAVIGATION = "navigation"
    TRADING = "trading"

class GameClient:
    def __init__(self, host='127.0.0.1', port=50000):
        self.host = host
        self.port = port
        self.socket = None
        self.game_state = None
        self.player_name = None
        self.prediction_config = PredictionConfig()
        self.skills = {skill: 1 for skill in SkillType}
        self.position_history = []
        self.debug_info = {
            "latency": [],
            "prediction_error": [],
            "corrections": 0,
            "jitter": [],
            "skill_checks": 0,
            "event_chains": 0,
            "network_stats": {
                "packets_sent": 0,
                "packets_received": 0,
                "bytes_sent": 0,
                "bytes_received": 0
            }
        }
        self.last_update_time = 0
        self.predicted_position = None
        self.last_server_position = None
        self.event_chain_progress = 0
        self.show_debug = False

    def connect(self, player_name):
        self.player_name = player_name
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))
        threading.Thread(target=self.receive_updates, daemon=True).start()

    def receive_updates(self):
        while True:
            try:
                data = self.socket.recv(4096)
                if not data:
                    break
                self.debug_info["network_stats"]["packets_received"] += 1
                self.debug_info["network_stats"]["bytes_received"] += len(data)
                
                game_state = json.loads(data.decode())
                self.last_update_time = pygame.time.get_ticks()
                
                # Update debug info
                if self.predicted_position is not None:
                    server_pos = next((p["position"] for p in game_state["players"] 
                                     if p["name"] == self.player_name), None)
                    if server_pos is not None:
                        error = abs(server_pos - self.predicted_position)
                        self.debug_info["prediction_error"].append(error)
                        if error > self.prediction_config.reconciliation_tolerance:
                            self.debug_info["corrections"] += 1
                
                self.game_state = game_state
            except Exception as e:
                print("Error receiving update:", e)
                break

    def predict_position(self, current_pos, direction):
        if not self.position_history:
            return current_pos + direction

        # Calculate average velocity
        velocities = []
        for i in range(1, len(self.position_history)):
            dt = self.position_history[i][1] - self.position_history[i-1][1]
            if dt > 0:
                velocity = (self.position_history[i][0] - self.position_history[i-1][0]) / dt
                velocities.append(velocity)

        if velocities:
            avg_velocity = sum(velocities) / len(velocities)
            # Apply smoothing
            smoothed_velocity = avg_velocity * self.prediction_config.interpolation_factor + \
                              direction * (1 - self.prediction_config.interpolation_factor)
            
            # Predict position
            prediction_time = min(self.prediction_config.max_prediction_time,
                                (pygame.time.get_ticks() - self.last_update_time) / 1000.0)
            predicted_pos = current_pos + smoothed_velocity * prediction_time * \
                          self.prediction_config.prediction_speed_multiplier
            
            # Store prediction
            self.predicted_position = predicted_pos
            return predicted_pos
        return current_pos + direction

    def reconcile_position(self, server_pos):
        if self.predicted_position is not None:
            error = abs(server_pos - self.predicted_position)
            if error > self.prediction_config.reconciliation_tolerance:
                # Calculate correction factor
                correction = (server_pos - self.predicted_position) * \
                           self.prediction_config.interpolation_factor
                return server_pos + correction
        return server_pos

    def handle_skill_check(self, skill_type, difficulty):
        skill_level = self.skills.get(skill_type, 1)
        success_chance = 0.5 + (skill_level * 0.1) - (difficulty * 0.1)
        success = random.random() < success_chance
        
        # Chance to improve skill
        if success and random.random() < 0.3:
            self.skills[skill_type] = min(5, self.skills[skill_type] + 1)
        
        self.debug_info["skill_checks"] += 1
        return success

    def send_action(self, action, choice=None):
        if not self.socket:
            return
        
        message = {
            "player": self.player_name,
            "action": action,
            "skills": {skill.value: level for skill, level in self.skills.items()}
        }
        if choice:
            message["choice"] = choice
        
        try:
            data = json.dumps(message).encode()
            self.socket.sendall(data)
            self.debug_info["network_stats"]["packets_sent"] += 1
            self.debug_info["network_stats"]["bytes_sent"] += len(data)
        except Exception as e:
            print("Error sending action:", e)

    def disconnect(self):
        if self.socket:
            self.socket.close()

class GameUI:
    def __init__(self, width=800, height=600):
        pygame.init()
        self.width = width
        self.height = height
        self.screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption("Oregon Trail Multiplayer")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 24)
        self.title_font = pygame.font.Font(None, 36)
        self.colors = {
            "background": (50, 50, 50),
            "text": (255, 255, 255),
            "trail": (139, 69, 19),
            "player": (0, 255, 0),
            "landmark": (255, 215, 0),
            "event": (255, 165, 0),
            "skill": (0, 191, 255),
            "debug": (255, 0, 0)
        }
        self.layout = {
            "status_panel": pygame.Rect(10, 10, 200, 300),
            "event_panel": pygame.Rect(10, 320, 200, 200),
            "trail_panel": pygame.Rect(220, 10, 560, 400),
            "control_panel": pygame.Rect(220, 420, 560, 150),
            "debug_panel": pygame.Rect(10, 530, 780, 60)
        }
        self.show_debug = False
        self.custom_layout = False

    def draw_player_status(self, player_data):
        if not player_data:
            return

        # Draw status panel background
        pygame.draw.rect(self.screen, (30, 30, 30), self.layout["status_panel"])
        pygame.draw.rect(self.screen, self.colors["text"], self.layout["status_panel"], 1)

        y = self.layout["status_panel"].top + 10
        # Player name and position
        name_text = self.font.render(f"Player: {player_data['name']}", True, self.colors["text"])
        self.screen.blit(name_text, (self.layout["status_panel"].left + 10, y))
        y += 30

        # Resources
        resources = [
            ("Food", player_data["food"]),
            ("Ammo", player_data["ammo"]),
            ("Money", player_data["money"]),
            ("Health", player_data["health"]),
            ("Wagon", player_data["wagon_condition"])
        ]

        for resource, value in resources:
            # Draw resource bar
            bar_width = 150
            bar_height = 20
            bar_rect = pygame.Rect(self.layout["status_panel"].left + 10, y, bar_width, bar_height)
            pygame.draw.rect(self.screen, (50, 50, 50), bar_rect)
            
            # Calculate fill width based on value
            if resource in ["Health", "Wagon"]:
                fill_width = int((value / 100) * bar_width)
            else:
                fill_width = int((value / 200) * bar_width)  # Assuming max of 200 for other resources
            
            fill_rect = pygame.Rect(bar_rect.left, bar_rect.top, fill_width, bar_height)
            color = (0, 255, 0) if value > 50 else (255, 0, 0) if value < 20 else (255, 255, 0)
            pygame.draw.rect(self.screen, color, fill_rect)
            
            # Draw text
            text = self.font.render(f"{resource}: {value}", True, self.colors["text"])
            self.screen.blit(text, (bar_rect.right + 10, y))
            y += 30

        # Skills
        y += 10
        skills_text = self.font.render("Skills:", True, self.colors["text"])
        self.screen.blit(skills_text, (self.layout["status_panel"].left + 10, y))
        y += 30

        for skill, level in player_data.get("skills", {}).items():
            # Draw skill bar
            bar_width = 150
            bar_height = 15
            bar_rect = pygame.Rect(self.layout["status_panel"].left + 10, y, bar_width, bar_height)
            pygame.draw.rect(self.screen, (50, 50, 50), bar_rect)
            
            # Calculate fill width based on skill level (1-5)
            fill_width = int((level / 5) * bar_width)
            fill_rect = pygame.Rect(bar_rect.left, bar_rect.top, fill_width, bar_height)
            pygame.draw.rect(self.screen, self.colors["skill"], fill_rect)
            
            # Draw text
            text = self.font.render(f"{skill}: {level}", True, self.colors["text"])
            self.screen.blit(text, (bar_rect.right + 10, y))
            y += 25

        # Active effects
        if player_data.get("effects"):
            y += 10
            effects_text = self.font.render("Active Effects:", True, self.colors["text"])
            self.screen.blit(effects_text, (self.layout["status_panel"].left + 10, y))
            y += 30

            for effect in player_data["effects"]:
                text = self.font.render(effect, True, self.colors["event"])
                self.screen.blit(text, (self.layout["status_panel"].left + 10, y))
                y += 25

    def draw_events(self, events):
        # Draw event panel background
        pygame.draw.rect(self.screen, (30, 30, 30), self.layout["event_panel"])
        pygame.draw.rect(self.screen, self.colors["text"], self.layout["event_panel"], 1)

        y = self.layout["event_panel"].top + 10
        title = self.font.render("Recent Events:", True, self.colors["text"])
        self.screen.blit(title, (self.layout["event_panel"].left + 10, y))
        y += 30

        for event in events[-5:]:  # Show last 5 events
            text = self.font.render(event, True, self.colors["event"])
            self.screen.blit(text, (self.layout["event_panel"].left + 10, y))
            y += 25

    def draw_trail(self, game_state):
        if not game_state:
            return

        # Draw trail panel background
        pygame.draw.rect(self.screen, (30, 30, 30), self.layout["trail_panel"])
        pygame.draw.rect(self.screen, self.colors["text"], self.layout["trail_panel"], 1)

        # Draw trail
        trail_start = (self.layout["trail_panel"].left + 50, self.layout["trail_panel"].centery)
        trail_end = (self.layout["trail_panel"].right - 50, self.layout["trail_panel"].centery)
        pygame.draw.line(self.screen, self.colors["trail"], trail_start, trail_end, 5)

        # Draw landmarks
        for pos, name in game_state["landmarks"].items():
            x = trail_start[0] + (pos / game_state["trail_length"]) * (trail_end[0] - trail_start[0])
            y = trail_start[1]
            pygame.draw.circle(self.screen, self.colors["landmark"], (int(x), int(y)), 10)
            text = self.font.render(name, True, self.colors["landmark"])
            self.screen.blit(text, (int(x) - text.get_width()//2, int(y) + 15))

        # Draw players
        for player in game_state["players"]:
            x = trail_start[0] + (player["position"] / game_state["trail_length"]) * (trail_end[0] - trail_start[0])
            y = trail_start[1]
            pygame.draw.circle(self.screen, self.colors["player"], (int(x), int(y)), 8)
            text = self.font.render(player["name"], True, self.colors["player"])
            self.screen.blit(text, (int(x) - text.get_width()//2, int(y) - 20))

        # Draw weather indicator
        weather_text = self.font.render(f"Weather: {game_state['current_weather']}", True, self.colors["text"])
        self.screen.blit(weather_text, (self.layout["trail_panel"].left + 10, self.layout["trail_panel"].top + 10))

    def draw_controls(self):
        # Draw control panel background
        pygame.draw.rect(self.screen, (30, 30, 30), self.layout["control_panel"])
        pygame.draw.rect(self.screen, self.colors["text"], self.layout["control_panel"], 1)

        y = self.layout["control_panel"].top + 10
        controls = [
            "Controls:",
            "W/S - Move forward/backward",
            "H - Hunt for food",
            "B - Buy food",
            "R - Repair wagon",
            "D - Toggle debug info",
            "L - Toggle layout",
            "Q - Quit"
        ]

        for control in controls:
            text = self.font.render(control, True, self.colors["text"])
            self.screen.blit(text, (self.layout["control_panel"].left + 10, y))
            y += 25

    def draw_debug_info(self, debug_info):
        if not self.show_debug:
            return

        # Draw debug panel background
        pygame.draw.rect(self.screen, (30, 30, 30), self.layout["debug_panel"])
        pygame.draw.rect(self.screen, self.colors["debug"], self.layout["debug_panel"], 1)

        y = self.layout["debug_panel"].top + 10
        debug_texts = [
            f"Latency: {sum(debug_info['latency'][-10:])/len(debug_info['latency'][-10:]) if debug_info['latency'] else 0:.2f}ms",
            f"Prediction Error: {sum(debug_info['prediction_error'][-10:])/len(debug_info['prediction_error'][-10:]) if debug_info['prediction_error'] else 0:.2f}",
            f"Corrections: {debug_info['corrections']}",
            f"Skill Checks: {debug_info['skill_checks']}",
            f"Event Chains: {debug_info['event_chains']}",
            f"Network: {debug_info['network_stats']['packets_sent']}/{debug_info['network_stats']['packets_received']} packets"
        ]

        x = self.layout["debug_panel"].left + 10
        for text in debug_texts:
            debug_text = self.font.render(text, True, self.colors["debug"])
            self.screen.blit(debug_text, (x, y))
            x += 150

    def draw_skill_bars(self, skills):
        if not skills:
            return

        y = self.layout["status_panel"].bottom + 10
        for skill, level in skills.items():
            # Draw skill bar
            bar_width = 150
            bar_height = 15
            bar_rect = pygame.Rect(self.layout["status_panel"].left + 10, y, bar_width, bar_height)
            pygame.draw.rect(self.screen, (50, 50, 50), bar_rect)
            
            # Calculate fill width based on skill level (1-5)
            fill_width = int((level / 5) * bar_width)
            fill_rect = pygame.Rect(bar_rect.left, bar_rect.top, fill_width, bar_height)
            pygame.draw.rect(self.screen, self.colors["skill"], fill_rect)
            
            # Draw text
            text = self.font.render(f"{skill}: {level}", True, self.colors["text"])
            self.screen.blit(text, (bar_rect.right + 10, y))
            y += 25

    def draw_event_chains(self, event_chains):
        if not event_chains:
            return

        y = self.layout["event_panel"].top + 10
        for chain in event_chains:
            # Draw event chain progress
            bar_width = 150
            bar_height = 15
            bar_rect = pygame.Rect(self.layout["event_panel"].left + 10, y, bar_width, bar_height)
            pygame.draw.rect(self.screen, (50, 50, 50), bar_rect)
            
            # Calculate fill width based on progress
            fill_width = int((chain["progress"] / chain["total_steps"]) * bar_width)
            fill_rect = pygame.Rect(bar_rect.left, bar_rect.top, fill_width, bar_height)
            pygame.draw.rect(self.screen, self.colors["event"], fill_rect)
            
            # Draw text
            text = self.font.render(f"{chain['type']}: {chain['progress']}/{chain['total_steps']}", 
                                  True, self.colors["text"])
            self.screen.blit(text, (bar_rect.right + 10, y))
            y += 25

    def toggle_layout(self):
        self.custom_layout = not self.custom_layout
        if self.custom_layout:
            # Custom layout with larger trail panel
            self.layout = {
                "status_panel": pygame.Rect(10, 10, 150, 300),
                "event_panel": pygame.Rect(10, 320, 150, 200),
                "trail_panel": pygame.Rect(170, 10, 620, 400),
                "control_panel": pygame.Rect(170, 420, 620, 150),
                "debug_panel": pygame.Rect(10, 530, 780, 60)
            }
        else:
            # Default layout
            self.layout = {
                "status_panel": pygame.Rect(10, 10, 200, 300),
                "event_panel": pygame.Rect(10, 320, 200, 200),
                "trail_panel": pygame.Rect(220, 10, 560, 400),
                "control_panel": pygame.Rect(220, 420, 560, 150),
                "debug_panel": pygame.Rect(10, 530, 780, 60)
            }

    def run(self, client):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_w:
                        client.send_action("move", {"direction": 1})
                    elif event.key == pygame.K_s:
                        client.send_action("move", {"direction": -1})
                    elif event.key == pygame.K_h:
                        client.send_action("hunt")
                    elif event.key == pygame.K_b:
                        client.send_action("buy_food")
                    elif event.key == pygame.K_r:
                        client.send_action("repair_wagon")
                    elif event.key == pygame.K_d:
                        self.show_debug = not self.show_debug
                    elif event.key == pygame.K_l:
                        self.toggle_layout()
                    elif event.key == pygame.K_q:
                        running = False

            # Clear screen
            self.screen.fill(self.colors["background"])

            # Draw game state
            if client.game_state:
                player_data = next((p for p in client.game_state["players"] 
                                  if p["name"] == client.player_name), None)
                if player_data:
                    self.draw_player_status(player_data)
                    self.draw_events(player_data.get("event_log", []))
                    self.draw_trail(client.game_state)
                    self.draw_controls()
                    if self.show_debug:
                        self.draw_debug_info(client.debug_info)
                    self.draw_skill_bars(player_data.get("skills", {}))
                    self.draw_event_chains(client.game_state.get("event_chains", []))

            # Update display
            pygame.display.flip()
            self.clock.tick(60)

        pygame.quit()
        client.disconnect()

def main():
    if len(sys.argv) != 2:
        print("Usage: python client.py <player_name>")
        return

    player_name = sys.argv[1]
    client = GameClient()
    client.connect(player_name)
    
    ui = GameUI()
    ui.run(client)

if __name__ == "__main__":
    main() 