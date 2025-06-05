import socket
import json
import threading
import pygame
import sys
import time
import math
import random
from enum import Enum

class PredictionConfig:
    def __init__(self):
        # Optimized prediction parameters
        self.prediction_speed_multiplier = 1.15  # Slightly reduced for smoother movement
        self.reconciliation_tolerance = 0.15     # Increased tolerance for fewer corrections
        self.interpolation_factor = 0.25         # Smoother interpolation
        self.max_prediction_time = 0.3          # Reduced for more accurate predictions
        self.jitter_threshold = 0.05            # Threshold for jitter detection
        self.smoothing_window = 5               # Number of positions to average

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
        self.running = True
        self.prediction_config = PredictionConfig()
        self.last_update_time = time.time()
        self.predicted_position = 0
        self.last_server_position = 0
        self.pending_actions = []
        self.position_history = []
        self.skill_levels = {
            SkillType.HUNTING: 1,
            SkillType.GATHERING: 1,
            SkillType.REPAIR: 1,
            SkillType.NAVIGATION: 1,
            SkillType.TRADING: 1
        }
        self.debug_info = {
            "latency": 0,
            "prediction_error": 0,
            "corrections": 0,
            "jitter": 0,
            "skill_checks": {},
            "event_chains": [],
            "network_stats": {
                "packets_sent": 0,
                "packets_received": 0,
                "average_latency": 0
            }
        }

    def connect(self, player_name):
        self.player_name = player_name
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))
        threading.Thread(target=self.receive_updates, daemon=True).start()

    def predict_position(self, current_time):
        if not self.game_state:
            return self.predicted_position

        player = next((p for p in self.game_state["players"] 
                      if p["name"] == self.player_name), None)
        if not player:
            return self.predicted_position

        delta_time = current_time - self.last_update_time
        
        if delta_time < self.prediction_config.max_prediction_time:
            # Calculate predicted position
            predicted = player["position"] + (
                delta_time * self.prediction_config.prediction_speed_multiplier
            )
            
            # Add to position history
            self.position_history.append(predicted)
            if len(self.position_history) > self.prediction_config.smoothing_window:
                self.position_history.pop(0)
            
            # Calculate smoothed position
            self.predicted_position = sum(self.position_history) / len(self.position_history)
            
            # Calculate jitter
            if len(self.position_history) > 1:
                jitter = sum(abs(self.position_history[i] - self.position_history[i-1]) 
                           for i in range(1, len(self.position_history)))
                self.debug_info["jitter"] = jitter / (len(self.position_history) - 1)
        
        return self.predicted_position

    def reconcile_position(self, server_position):
        error = abs(self.predicted_position - server_position)
        self.debug_info["prediction_error"] = error

        if error > self.prediction_config.reconciliation_tolerance:
            self.debug_info["corrections"] += 1
            
            # Adjust interpolation factor based on error magnitude
            factor = min(0.5, max(0.1, error * 2))
            
            # Smoothly interpolate to the correct position
            self.predicted_position = (
                self.predicted_position * (1 - factor) +
                server_position * factor
            )
            
            # Clear position history on large corrections
            if error > self.prediction_config.jitter_threshold * 2:
                self.position_history.clear()
                self.position_history.append(server_position)
        
        self.last_server_position = server_position

    def handle_skill_check(self, skill_type, difficulty):
        skill_level = self.skill_levels[skill_type]
        success_chance = min(0.95, 0.5 + (skill_level * 0.1))
        success = random.random() < success_chance
        
        if success and random.random() < 0.3:  # 30% chance to improve skill
            self.skill_levels[skill_type] = min(5, skill_level + 1)
        
        self.debug_info["skill_checks"][skill_type.value] = {
            "success": success,
            "difficulty": difficulty,
            "skill_level": skill_level
        }
        
        return success

    def receive_updates(self):
        while self.running:
            try:
                start_time = time.time()
                data = self.socket.recv(4096)
                if not data:
                    break
                
                self.game_state = json.loads(data.decode())
                latency = time.time() - start_time
                
                # Update network stats
                self.debug_info["network_stats"]["packets_received"] += 1
                self.debug_info["network_stats"]["average_latency"] = (
                    (self.debug_info["network_stats"]["average_latency"] * 
                     (self.debug_info["network_stats"]["packets_received"] - 1) +
                     latency) / self.debug_info["network_stats"]["packets_received"]
                )
                
                # Handle event chains
                if "event_chains" in self.game_state:
                    self.debug_info["event_chains"] = self.game_state["event_chains"]
                
                # Reconcile positions
                player = next((p for p in self.game_state["players"] 
                             if p["name"] == self.player_name), None)
                if player:
                    self.reconcile_position(player["position"])
                
                self.last_update_time = time.time()
            except Exception as e:
                print("Error receiving update:", e)
                break
        self.socket.close()

    def send_action(self, action, choice=None):
        if self.socket:
            try:
                message = {
                    "player": self.player_name,
                    "action": action,
                    "timestamp": time.time(),
                    "skills": {k.value: v for k, v in self.skill_levels.items()}
                }
                if choice:
                    message["choice"] = choice
                self.socket.sendall(json.dumps(message).encode())
                self.pending_actions.append(message)
                self.debug_info["network_stats"]["packets_sent"] += 1
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
        self.screen = pygame.display.set_mode((1024, 768))
        pygame.display.set_caption("Oregon Trail Multiplayer")
        self.font = pygame.font.Font(None, 36)
        self.small_font = pygame.font.Font(None, 24)
        self.clock = pygame.time.Clock()
        self.colors = {
            "white": (255, 255, 255),
            "black": (0, 0, 0),
            "red": (255, 0, 0),
            "green": (0, 255, 0),
            "blue": (0, 0, 255),
            "yellow": (255, 255, 0),
            "orange": (255, 165, 0),
            "purple": (128, 0, 128)
        }
        self.show_debug = False
        self.debug_mode = 0  # 0: Basic, 1: Network, 2: Skills, 3: Events

    def draw_debug_info(self):
        if not self.show_debug:
            return

        if self.debug_mode == 0:  # Basic debug info
            debug_texts = [
                f"Latency: {self.client.debug_info['latency']*1000:.1f}ms",
                f"Prediction Error: {self.client.debug_info['prediction_error']:.2f}",
                f"Corrections: {self.client.debug_info['corrections']}",
                f"Jitter: {self.client.debug_info['jitter']:.3f}",
                f"Speed Multiplier: {self.client.prediction_config.prediction_speed_multiplier:.2f}",
                f"Tolerance: {self.client.prediction_config.reconciliation_tolerance:.2f}"
            ]
        elif self.debug_mode == 1:  # Network stats
            stats = self.client.debug_info["network_stats"]
            debug_texts = [
                f"Packets Sent: {stats['packets_sent']}",
                f"Packets Received: {stats['packets_received']}",
                f"Average Latency: {stats['average_latency']*1000:.1f}ms",
                f"Packet Loss: {((stats['packets_sent'] - stats['packets_received']) / max(1, stats['packets_sent']) * 100):.1f}%"
            ]
        elif self.debug_mode == 2:  # Skills
            debug_texts = ["Skill Levels:"]
            for skill, level in self.client.skill_levels.items():
                checks = self.client.debug_info["skill_checks"].get(skill.value, {})
                success_rate = checks.get("success_rate", 0) if checks else 0
                debug_texts.append(f"{skill.value}: {level} (Success: {success_rate:.1%})")
        else:  # Event chains
            debug_texts = ["Active Event Chains:"]
            for chain in self.client.game_state["event_chains"]:
                debug_texts.append(f"- {chain['type']}: {chain['progress']}/{chain['total']}")

        y = 50
        for text in debug_texts:
            surface = self.small_font.render(text, True, self.colors["yellow"])
            self.screen.blit(surface, (800, y))
            y += 25

    def draw_skill_bars(self):
        y = 200
        for skill, level in self.client.skill_levels.items():
            # Draw skill name
            surface = self.small_font.render(f"{skill.value}:", True, self.colors["white"])
            self.screen.blit(surface, (20, y))
            
            # Draw skill bar
            bar_width = 200
            bar_height = 20
            pygame.draw.rect(self.screen, self.colors["black"], (150, y, bar_width, bar_height), 1)
            fill_width = (bar_width * level) / 5  # 5 is max level
            pygame.draw.rect(self.screen, self.colors["green"], (150, y, fill_width, bar_height))
            
            y += 30

    def draw_event_chains(self):
        if not self.client.game_state or "event_chains" not in self.client.game_state:
            return

        y = 300
        self.screen.blit(self.font.render("Active Events:", True, self.colors["white"]), (20, y))
        y += 40

        for chain in self.client.game_state["event_chains"]:
            # Draw event chain progress
            progress = chain["progress"] / chain["total"]
            bar_width = 200
            bar_height = 20
            
            pygame.draw.rect(self.screen, self.colors["black"], (20, y, bar_width, bar_height), 1)
            fill_width = bar_width * progress
            pygame.draw.rect(self.screen, self.colors["blue"], (20, y, fill_width, bar_height))
            
            # Draw event description
            surface = self.small_font.render(chain["description"], True, self.colors["white"])
            self.screen.blit(surface, (230, y))
            
            y += 30

    def draw_player_status(self, player_data):
        y = 50
        for player in player_data:
            # Basic info
            text = f"{player['name']}: Position {player['position']:.1f}"
            surface = self.font.render(text, True, self.colors["white"])
            self.screen.blit(surface, (20, y))
            y += 30

            # Resources
            resources = [
                f"Food: {player['food']}",
                f"Ammo: {player['ammo']}",
                f"Money: ${player['money']}",
                f"Health: {player['health']}%",
                f"Wagon: {player['wagon_condition']}%"
            ]
            for resource in resources:
                surface = self.small_font.render(resource, True, self.colors["white"])
                self.screen.blit(surface, (40, y))
                y += 25

            # Active effects
            if player['active_effects']:
                effects_text = "Active Effects: " + ", ".join(player['active_effects'])
                surface = self.small_font.render(effects_text, True, self.colors["yellow"])
                self.screen.blit(surface, (40, y))
                y += 25

            y += 20  # Add space between players

    def draw_events(self, player_data):
        if not player_data:
            return

        # Find current player
        current_player = next((p for p in player_data if p['name'] == self.client.player_name), None)
        if not current_player or not current_player['events']:
            return

        # Draw event log
        y = 400
        self.screen.blit(self.font.render("Recent Events:", True, self.colors["white"]), (20, y))
        y += 40

        for event in current_player['events']:
            # Event description
            surface = self.small_font.render(event['description'], True, self.colors["white"])
            self.screen.blit(surface, (40, y))
            y += 25

            # Event choices
            if event['choices']:
                for choice, description in event['choices'].items():
                    color = self.colors["green"]
                    surface = self.small_font.render(f"- {description}", True, color)
                    self.screen.blit(surface, (60, y))
                    y += 25
            y += 10

    def draw_controls(self):
        controls = [
            "Controls:",
            "M - Move",
            "H - Hunt",
            "B - Buy Food",
            "R - Rest",
            "P - Repair Wagon",
            "D - Toggle Debug Info",
            "TAB - Switch Debug Mode",
            "Q - Quit"
        ]
        y = 600
        for text in controls:
            surface = self.font.render(text, True, self.colors["white"])
            self.screen.blit(surface, (20, y))
            y += 40

    def draw_weather(self):
        if self.client.game_state:
            weather_text = f"Weather: {self.client.game_state['current_weather']}"
            surface = self.font.render(weather_text, True, self.colors["white"])
            self.screen.blit(surface, (20, 700))

    def handle_event_click(self, pos):
        if not self.client.game_state:
            return

        current_player = next((p for p in self.client.game_state['players'] 
                             if p['name'] == self.client.player_name), None)
        if not current_player or not current_player['events']:
            return

        y = 440  # Starting y position for events
        for event in current_player['events']:
            if event['choices']:
                for choice, description in event['choices'].items():
                    choice_rect = pygame.Rect(60, y, 300, 25)
                    if choice_rect.collidepoint(pos):
                        self.client.send_action("event_choice", {
                            "event_time": event['timestamp'],
                            "choice": choice
                        })
                        return
                    y += 25
            y += 35

    def run(self):
        while True:
            current_time = time.time()
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
                    elif event.key == pygame.K_r:
                        self.client.send_action("rest")
                    elif event.key == pygame.K_p:
                        self.client.send_action("repair")
                    elif event.key == pygame.K_d:
                        self.show_debug = not self.show_debug
                    elif event.key == pygame.K_TAB and self.show_debug:
                        self.debug_mode = (self.debug_mode + 1) % 4
                    elif event.key == pygame.K_q:
                        self.client.disconnect()
                        pygame.quit()
                        return
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:  # Left click
                        self.handle_event_click(event.pos)

            self.screen.fill(self.colors["black"])
            if self.client.game_state:
                self.client.predict_position(current_time)
                self.draw_player_status(self.client.game_state['players'])
                self.draw_events(self.client.game_state['players'])
                self.draw_skill_bars()
                self.draw_event_chains()
            self.draw_controls()
            self.draw_weather()
            self.draw_debug_info()
            pygame.display.flip()
            self.clock.tick(60)

def main():
    client = GameClient()
    client.connect("Player1")  # You can make this dynamic
    ui = GameUI(client)
    ui.run()

if __name__ == "__main__":
    main() 