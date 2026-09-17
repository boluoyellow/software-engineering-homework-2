import math
import os
import random

import pygame

from arrow import clear_render_cache, polyline_length, sample_route_span, smooth_route
from audio import SoundManager
from config import get_layout
from generator import generate_level
from levels import LEVELS


BG_TOP = (7, 10, 25)
BG_BOTTOM = (20, 26, 52)
PANEL = (22, 31, 54)
PANEL_LIGHT = (32, 44, 72)
CELL_A = (20, 29, 51)
CELL_B = (24, 34, 58)
GRID = (48, 69, 101)
WHITE = (240, 248, 255)
MUTED = (134, 154, 184)
CYAN = (55, 217, 255)
CYAN_HOVER = (139, 241, 255)
PURPLE = (164, 104, 255)
RED = (255, 75, 110)
GREEN = (69, 235, 160)
GOLD = (255, 201, 77)
PINK = (255, 102, 211)

ARROW_COLORS = {
    "straight": CYAN,
    "long_straight": (63, 192, 255),
    "turn_left": PURPLE,
    "turn_right": GREEN,
    "zigzag_left": GOLD,
    "zigzag_right": PINK,
    "hook_left": (255, 132, 92),
    "hook_right": (84, 238, 210),
    "stair_left": (188, 122, 255),
    "stair_right": (113, 225, 94),
    "wave_left": (255, 164, 64),
    "wave_right": (255, 89, 164),
    "snake_left": (255, 151, 72),
    "snake_right": (103, 232, 255),
}

MAZE_COLORS = (
    (80, 218, 255),
    (103, 232, 196),
    (255, 174, 84),
    (255, 121, 155),
    (185, 137, 255),
    (255, 213, 80),
    (131, 221, 120),
    (235, 145, 235),
)


def _arrow_color(arrow):
    if arrow.kind == "maze":
        return MAZE_COLORS[arrow.color_index % len(MAZE_COLORS)]
    return ARROW_COLORS[arrow.kind]


def _brighten(color, amount=72):
    return tuple(min(255, channel + amount) for channel in color)


def _load_ui_font(size, bold=False):
    """Load Chinese fonts directly, bypassing Pygame's fragile registry scan."""
    windows_dir = os.environ.get("WINDIR", r"C:\Windows")
    fonts_dir = os.path.join(windows_dir, "Fonts")
    filenames = (
        ("msyhbd.ttc", "msyh.ttc", "simhei.ttf", "simsun.ttc")
        if bold
        else ("msyh.ttc", "simhei.ttf", "simsun.ttc")
    )
    for filename in filenames:
        font_path = os.path.join(fonts_dir, filename)
        if os.path.isfile(font_path):
            font = pygame.font.Font(font_path, size)
            font.set_bold(bold)
            return font
    fallback = pygame.font.Font(None, size)
    fallback.set_bold(bold)
    return fallback


class Game:
    def __init__(self):
        self.rng = random.Random()
        self.title_font = _load_ui_font(35, bold=True)
        self.font = _load_ui_font(25, bold=True)
        self.small_font = _load_ui_font(18)
        self.tiny_font = _load_ui_font(15)
        self.audio = SoundManager()
        self.level_index = 0
        self.score = 0
        self.level_start_score = 0
        self._start_level(0)

    @property
    def spec(self):
        return LEVELS[self.level_index]

    @property
    def window_size(self):
        return self.layout.window_width, self.layout.window_height

    def _start_level(self, level_index, retry=False):
        self.audio.stop_victory()
        self.level_index = level_index
        self.layout = get_layout(self.spec.grid_size)
        clear_render_cache()
        if retry:
            self.score = self.level_start_score
            self.audio.play_restart()
        else:
            self.level_start_score = self.score
        self._build_scene_assets()
        if retry:
            self.arrows = list(self.level_initial_arrows)
        else:
            self.arrows = generate_level(
                count=self.spec.arrow_count,
                rng=self.rng,
                grid_size=self.spec.grid_size,
                kinds=self.spec.kinds,
            )
            self.level_initial_arrows = tuple(self.arrows)
        self.lives = 3
        self.combo = 0
        self.combo_until = 0
        self.state = "playing"
        self._reset_effects()

    def _reset_effects(self):
        self.bad_arrow = None
        self.shake_until = 0
        self.particles = []
        self.shockwaves = []
        self.flying_arrows = []
        self.camera_shake_time = 0.0
        self.camera_shake_power = 0
        self.render_offset = (0, 0)

    def _build_scene_assets(self):
        width, height = self.window_size
        self.stars = [
            (
                self.rng.randrange(width),
                self.rng.randrange(height),
                self.rng.choice((1, 1, 1, 2)),
                self.rng.uniform(0, math.tau),
                self.rng.uniform(0.8, 2.2),
            )
            for _ in range(max(54, width * height // 7200))
        ]
        self.background = pygame.Surface((width, height))
        self._draw_gradient(self.background)
        self.board_shadow = self._build_board_shadow()

    def reset_campaign(self):
        self.score = 0
        self.level_start_score = 0
        self._start_level(0)
        self.audio.play_restart()

    def board_rect(self):
        return pygame.Rect(
            self.layout.board_x,
            self.layout.board_y,
            self.layout.board_width,
            self.layout.board_height,
        )

    def action_button_rect(self):
        button = pygame.Rect(0, 0, 220, 54)
        button.center = (
            self.layout.window_width // 2,
            self.layout.board_y + self.layout.board_height // 2 + 46,
        )
        return button

    def _cell_center(self, arrow):
        return (
            self.layout.board_x + arrow.col * self.layout.cell_size + self.layout.cell_size // 2,
            self.layout.board_y + arrow.row * self.layout.cell_size + self.layout.cell_size // 2,
        )

    def _cell_center_at(self, row, col):
        return (
            self.layout.board_x + col * self.layout.cell_size + self.layout.cell_size // 2,
            self.layout.board_y + row * self.layout.cell_size + self.layout.cell_size // 2,
        )

    def _draw_gradient(self, surface):
        width, height = surface.get_size()
        for y in range(height):
            ratio = y / max(1, height - 1)
            color = tuple(int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * ratio) for i in range(3))
            pygame.draw.line(surface, color, (0, y), (width, y))

    def _build_board_shadow(self):
        width = self.layout.board_width
        height = self.layout.board_height
        shadow = pygame.Surface((width + 56, height + 64), pygame.SRCALPHA)
        for spread, alpha in ((20, 22), (12, 38), (6, 62)):
            rect = pygame.Rect(28 - spread // 2, 25 - spread // 2, width + spread, height + spread)
            pygame.draw.rect(shadow, (0, 0, 0, alpha), rect, border_radius=20)
        return shadow

    @staticmethod
    def _draw_heart(surface, center, filled):
        color = RED if filled else (61, 72, 96)
        x, y = center
        pygame.draw.circle(surface, color, (x - 5, y - 3), 6)
        pygame.draw.circle(surface, color, (x + 5, y - 3), 6)
        pygame.draw.polygon(surface, color, [(x - 11, y), (x, y + 12), (x + 11, y)])

    def _spawn_particles(self, position, color, count, speed_min=90, speed_max=310):
        for _ in range(count):
            angle = self.rng.uniform(0, math.tau)
            speed = self.rng.uniform(speed_min, speed_max)
            life = self.rng.uniform(0.35, 0.85)
            self.particles.append(
                {
                    "x": float(position[0]),
                    "y": float(position[1]),
                    "vx": math.cos(angle) * speed,
                    "vy": math.sin(angle) * speed,
                    "life": life,
                    "max_life": life,
                    "size": self.rng.uniform(2.0, 5.5),
                    "color": color,
                }
            )

    def _spawn_shockwave(self, position, color, speed=270):
        self.shockwaves.append(
            {
                "x": position[0],
                "y": position[1],
                "radius": 7.0,
                "life": 0.48,
                "max_life": 0.48,
                "speed": speed,
                "color": color,
            }
        )

    def _spawn_success_effect(self, arrow):
        center = self._cell_center_at(*arrow.head_cell)
        color = _arrow_color(arrow)
        self._spawn_particles(center, color, 20)
        self._spawn_particles(center, PURPLE, 9, 55, 190)
        self._spawn_shockwave(center, color)
        guide, rope_length, max_progress, sample_count = self._rope_guide(arrow)
        self.flying_arrows.append(
            {
                "arrow": arrow,
                "mode": "success",
                "phase": "outbound",
                "guide": guide,
                "rope_length": rope_length,
                "sample_count": sample_count,
                "progress": 0.0,
                "max_progress": max_progress,
                "speed": 820.0,
                "color": color,
            }
        )
        self.camera_shake_time = max(self.camera_shake_time, 0.12)
        self.camera_shake_power = max(self.camera_shake_power, 3)

    def _rope_guide(self, arrow, max_progress=None):
        raw_points = arrow._board_points(
            self.layout.board_x,
            self.layout.board_y,
            self.layout.cell_size,
        )
        route = smooth_route(raw_points, self.layout.cell_size * 0.38, 12)
        rope_length = polyline_length(route)
        dx, dy = arrow.final_vector
        tip_x, tip_y = route[-1]
        if max_progress is None:
            if dx > 0:
                edge_distance = self.layout.window_width - tip_x
            elif dx < 0:
                edge_distance = tip_x
            elif dy > 0:
                edge_distance = self.layout.window_height - tip_y
            else:
                edge_distance = tip_y
            max_progress = rope_length + edge_distance + self.layout.cell_size * 2
        extension = max_progress + rope_length + self.layout.cell_size * 2
        guide = route + [(tip_x + dx * extension, tip_y + dy * extension)]
        sample_count = max(12, int(rope_length / max(2.0, self.layout.cell_size * 0.16)))
        return guide, rope_length, max_progress, sample_count

    def _spawn_blocked_animation(self, arrow, blocker_cell):
        tip = arrow._board_points(
            self.layout.board_x,
            self.layout.board_y,
            self.layout.cell_size,
        )[-1]
        blocker = self._cell_center_at(*blocker_cell)
        dx, dy = arrow.final_vector
        projected_distance = (blocker[0] - tip[0]) * dx + (blocker[1] - tip[1]) * dy
        collision_distance = max(
            self.layout.cell_size * 0.14,
            projected_distance - self.layout.cell_size * 0.48,
        )
        guide, rope_length, _, sample_count = self._rope_guide(arrow, collision_distance)
        self.flying_arrows.append(
            {
                "arrow": arrow,
                "mode": "blocked",
                "phase": "outbound",
                "guide": guide,
                "rope_length": rope_length,
                "sample_count": sample_count,
                "progress": 0.0,
                "max_progress": collision_distance,
                "speed": 560.0,
                "impact_time": 0.0,
                "color": _arrow_color(arrow),
                "collision_point": (
                    tip[0] + dx * collision_distance,
                    tip[1] + dy * collision_distance,
                ),
            }
        )

    def _spawn_collision_effect(self, center):
        self._spawn_particles(center, RED, 28, 80, 280)
        self._spawn_shockwave(center, RED, 330)
        self.camera_shake_time = 0.34
        self.camera_shake_power = 9

    def _spawn_win_effect(self):
        colors = (CYAN, PURPLE, GREEN, GOLD, RED)
        margin = min(50, self.layout.board_width // 5)
        for _ in range(7):
            center = (
                self.rng.randint(self.layout.board_x + margin, self.layout.board_x + self.layout.board_width - margin),
                self.rng.randint(self.layout.board_y + margin, self.layout.board_y + self.layout.board_height - margin),
            )
            self._spawn_particles(center, self.rng.choice(colors), 24, 100, 360)
            self._spawn_shockwave(center, self.rng.choice(colors), 350)
        self.camera_shake_time = 0.45
        self.camera_shake_power = 5

    def update(self, dt):
        dt = min(dt, 0.05)
        now = pygame.time.get_ticks()
        if self.combo and now > self.combo_until:
            self.combo = 0

        for particle in self.particles:
            particle["x"] += particle["vx"] * dt
            particle["y"] += particle["vy"] * dt
            particle["vy"] += 95 * dt
            particle["vx"] *= max(0.0, 1.0 - 1.6 * dt)
            particle["life"] -= dt
        self.particles = [particle for particle in self.particles if particle["life"] > 0]

        for wave in self.shockwaves:
            wave["radius"] += wave["speed"] * dt
            wave["life"] -= dt
        self.shockwaves = [wave for wave in self.shockwaves if wave["life"] > 0]

        for flying in self.flying_arrows:
            if flying["mode"] == "success":
                flying["progress"] = min(
                    flying["max_progress"],
                    flying["progress"] + flying["speed"] * dt,
                )
                flying["done"] = flying["progress"] >= flying["max_progress"]
            elif flying["phase"] == "outbound":
                flying["progress"] = min(
                    flying["max_progress"],
                    flying["progress"] + flying["speed"] * dt,
                )
                if flying["progress"] >= flying["max_progress"]:
                    flying["phase"] = "impact"
                    flying["impact_time"] = 0.13
                    self._spawn_collision_effect(flying["collision_point"])
                    self.audio.play_blocked()
            elif flying["phase"] == "impact":
                flying["impact_time"] -= dt
                if flying["impact_time"] <= 0:
                    flying["phase"] = "return"
            else:
                flying["progress"] = max(0.0, flying["progress"] - 430.0 * dt)
                flying["done"] = flying["progress"] <= 0
        self.flying_arrows = [flying for flying in self.flying_arrows if not flying.get("done", False)]

        if self.state == "blocked_anim" and not any(
            flying["mode"] == "blocked" for flying in self.flying_arrows
        ):
            self.state = self.pending_after_collision

        if self.state == "clearing" and not self.flying_arrows:
            self.state = self.pending_end_state
            self._spawn_win_effect()
            self.audio.play_victory()

        if self.camera_shake_time > 0:
            self.camera_shake_time = max(0.0, self.camera_shake_time - dt)
            power = self.camera_shake_power
            self.render_offset = (self.rng.randint(-power, power), self.rng.randint(-power, power))
        else:
            self.render_offset = (0, 0)

    def camera_offset(self):
        return self.render_offset

    def _draw_stars(self, surface, now):
        time_value = now / 1000.0
        for x, y, radius, phase, speed in self.stars:
            glow = (math.sin(time_value * speed + phase) + 1) / 2
            brightness = int(40 + glow * 105)
            drift_y = int(math.sin(time_value * 0.45 + phase) * 3)
            pygame.draw.circle(
                surface,
                (brightness // 2, brightness, min(255, brightness + 65)),
                (x, y + drift_y),
                radius,
            )

    def _draw_header(self, surface):
        width = self.layout.window_width
        title_x = 36
        title_shadow = self.title_font.render("箭迹突围", True, (0, 0, 0))
        surface.blit(title_shadow, (title_x + 2, 21))
        surface.blit(self.title_font.render("箭迹突围", True, WHITE), (title_x, 18))
        subtitle = f"第 {self.level_index + 1} / {len(LEVELS)} 关"
        surface.blit(self.tiny_font.render(subtitle, True, CYAN), (title_x + 2, 60))

        timer_card = pygame.Rect(width - 164, 22, 128, 52)
        score_card = pygame.Rect(timer_card.x - 96, 22, 86, 52)
        lives_card = pygame.Rect(score_card.x - 130, 22, 120, 52)
        for card in (lives_card, score_card, timer_card):
            pygame.draw.rect(surface, (3, 7, 18), card.move(0, 4), border_radius=12)
            pygame.draw.rect(surface, PANEL_LIGHT, card, border_radius=12)
            pygame.draw.rect(surface, (55, 78, 112), card, 1, border_radius=12)

        surface.blit(self.tiny_font.render("生命", True, MUTED), (lives_card.x + 10, lives_card.y + 7))
        for index in range(3):
            self._draw_heart(surface, (lives_card.x + 62 + index * 24, lives_card.y + 28), index < self.lives)
        surface.blit(self.tiny_font.render("分数", True, MUTED), (score_card.x + 10, score_card.y + 6))
        surface.blit(self.font.render(str(self.score), True, GOLD), (score_card.x + 10, score_card.y + 23))

        now = pygame.time.get_ticks()
        remaining_ms = max(0, self.combo_until - now) if self.combo else 0
        remaining_seconds = remaining_ms / 1000.0
        timer_color = GOLD if remaining_ms > 0 else MUTED
        surface.blit(self.tiny_font.render("连击倒计时", True, MUTED), (timer_card.x + 10, timer_card.y + 6))
        timer_text = self.small_font.render(f"×{self.combo}  {remaining_seconds:.1f} 秒", True, timer_color)
        surface.blit(timer_text, (timer_card.x + 10, timer_card.y + 22))
        progress_bg = pygame.Rect(timer_card.x + 10, timer_card.bottom - 8, timer_card.width - 20, 4)
        pygame.draw.rect(surface, (14, 21, 38), progress_bg, border_radius=2)
        progress_width = int(progress_bg.width * min(1.0, remaining_ms / 1000.0))
        if progress_width > 0:
            progress = pygame.Rect(progress_bg.x, progress_bg.y, progress_width, progress_bg.height)
            pygame.draw.rect(surface, timer_color, progress, border_radius=2)

    def _draw_board(self, surface, now):
        board = self.board_rect()
        bx, by = self.layout.board_x, self.layout.board_y
        surface.blit(self.board_shadow, (bx - 28, by - 25))
        pygame.draw.rect(surface, PANEL, board, border_radius=12)
        for row in range(self.spec.grid_size):
            for col in range(self.spec.grid_size):
                cell = pygame.Rect(
                    bx + col * self.layout.cell_size,
                    by + row * self.layout.cell_size,
                    self.layout.cell_size,
                    self.layout.cell_size,
                )
                pygame.draw.rect(surface, CELL_A if (row + col) % 2 == 0 else CELL_B, cell)
        for index in range(1, self.spec.grid_size):
            x = bx + index * self.layout.cell_size
            y = by + index * self.layout.cell_size
            pygame.draw.line(surface, GRID, (x, by), (x, by + self.layout.board_height), 1)
            pygame.draw.line(surface, GRID, (bx, y), (bx + self.layout.board_width, y), 1)
        pulse = (math.sin(now / 520.0) + 1) / 2
        border_color = (45, int(120 + pulse * 65), int(175 + pulse * 70))
        pygame.draw.rect(surface, border_color, board, 3, border_radius=12)

    def _draw_effects(self, surface):
        layer = pygame.Surface(self.window_size, pygame.SRCALPHA)
        for wave in self.shockwaves:
            ratio = wave["life"] / wave["max_life"]
            pygame.draw.circle(
                layer,
                (*wave["color"], int(220 * ratio)),
                (int(wave["x"]), int(wave["y"])),
                max(1, int(wave["radius"])),
                max(1, int(4 * ratio)),
            )
        for particle in self.particles:
            ratio = particle["life"] / particle["max_life"]
            alpha = int(255 * ratio)
            radius = max(1, int(particle["size"] * (0.45 + ratio)))
            pos = (int(particle["x"]), int(particle["y"]))
            pygame.draw.circle(layer, (*particle["color"], alpha // 4), pos, radius * 3)
            pygame.draw.circle(layer, (*particle["color"], alpha), pos, radius)
        for flying in self.flying_arrows:
            points = sample_route_span(
                flying["guide"],
                flying["progress"],
                flying["rope_length"],
                flying["sample_count"],
            )
            is_impact = flying["mode"] == "blocked" and flying["phase"] in ("impact", "return")
            shake = (0, 0)
            if flying["mode"] == "blocked" and flying["phase"] == "impact":
                shake = (self.rng.randint(-3, 3), self.rng.randint(-3, 3))
            flying["arrow"].draw_moving(
                layer,
                points,
                RED if is_impact else flying["color"],
                self.layout.cell_size,
                shake,
            )
        surface.blit(layer, (0, 0))

    def _end_copy(self):
        if self.state == "level_clear":
            return "关卡完成", f"第 {self.level_index + 1} 关完成。", "进入下一关", GREEN
        if self.state == "campaign_won":
            return "全部通关", "所有箭头均已清除，你已完成全部挑战。", "重新挑战", GOLD
        return "挑战失败", "生命已耗尽，将恢复本关的初始布局。", "重试本关", RED

    def _draw_end_panel(self, surface):
        overlay = pygame.Surface((self.layout.board_width, self.layout.board_height), pygame.SRCALPHA)
        overlay.fill((3, 6, 17, 184))
        surface.blit(overlay, (self.layout.board_x, self.layout.board_y))
        panel = pygame.Rect(0, 0, min(420, self.layout.board_width - 36), 258)
        panel.center = (self.layout.window_width // 2, self.layout.board_y + self.layout.board_height // 2)
        pygame.draw.rect(surface, (2, 6, 16), panel.move(0, 9), border_radius=20)
        pygame.draw.rect(surface, PANEL_LIGHT, panel, border_radius=20)
        label, detail, button_label, accent = self._end_copy()
        pygame.draw.rect(surface, accent, panel, 2, border_radius=20)
        badge = pygame.Rect(0, 0, 58, 6)
        badge.midtop = (panel.centerx, panel.top + 20)
        pygame.draw.rect(surface, accent, badge, border_radius=3)
        label_text = self.title_font.render(label, True, WHITE)
        surface.blit(label_text, label_text.get_rect(center=(panel.centerx, panel.top + 62)))
        detail_text = self.tiny_font.render(detail, True, MUTED)
        surface.blit(detail_text, detail_text.get_rect(center=(panel.centerx, panel.top + 101)))
        button = self.action_button_rect()
        mouse_over = button.collidepoint(self._mouse_in_scene())
        button_color = CYAN_HOVER if mouse_over else CYAN
        pygame.draw.rect(surface, (2, 7, 16), button.move(0, 6), border_radius=14)
        if mouse_over:
            pygame.draw.rect(surface, (70, 139, 174), button.inflate(8, 8), 2, border_radius=17)
        pygame.draw.rect(surface, button_color, button, border_radius=14)
        button_text = self.font.render(button_label, True, (4, 17, 28))
        surface.blit(button_text, button_text.get_rect(center=button.center))
        remaining = self.tiny_font.render(f"分数 {self.score}  ·  剩余 {len(LEVELS) - self.level_index - 1} 关", True, MUTED)
        surface.blit(remaining, remaining.get_rect(center=(panel.centerx, panel.bottom - 22)))

    def _mouse_in_scene(self):
        mouse_x, mouse_y = pygame.mouse.get_pos()
        return mouse_x - self.render_offset[0], mouse_y - self.render_offset[1]

    def draw(self, surface):
        now = pygame.time.get_ticks()
        surface.blit(self.background, (0, 0))
        self._draw_stars(surface, now)
        self._draw_header(surface)
        self._draw_board(surface, now)
        hovered = self.arrow_at(self._mouse_in_scene()) if self.state == "playing" else None
        shake = (random.choice((-4, -2, 0, 2, 4)), 0) if now < self.shake_until else (0, 0)
        moving_arrows = {flying["arrow"] for flying in self.flying_arrows}
        for arrow in self.arrows:
            if arrow in moving_arrows:
                continue
            is_bad = arrow is self.bad_arrow and now < self.shake_until
            base_color = _arrow_color(arrow)
            color = RED if is_bad else (_brighten(base_color) if arrow is hovered else base_color)
            arrow.draw(
                surface,
                self.layout.board_x,
                self.layout.board_y,
                color,
                self.layout.cell_size,
                shake if is_bad else (0, 0),
                highlighted=arrow is hovered and not is_bad,
            )
        self._draw_effects(surface)
        if self.state in ("level_clear", "campaign_won", "lost"):
            self._draw_end_panel(surface)

    def arrow_at(self, pos):
        x, y = pos
        if not self.board_rect().collidepoint(x, y):
            return None
        col = (x - self.layout.board_x) // self.layout.cell_size
        row = (y - self.layout.board_y) // self.layout.cell_size
        if not (0 <= row < self.spec.grid_size and 0 <= col < self.spec.grid_size):
            return None
        for arrow in self.arrows:
            if arrow.occupies(row, col):
                return arrow
        return None

    def _handle_end_action(self):
        if self.state == "level_clear":
            self._start_level(self.level_index + 1)
        elif self.state == "campaign_won":
            self.reset_campaign()
        else:
            self._start_level(self.level_index, retry=True)

    def click(self, pos):
        scene_pos = (pos[0] - self.render_offset[0], pos[1] - self.render_offset[1])
        if self.state in ("clearing", "blocked_anim"):
            return
        if self.state != "playing":
            if self.action_button_rect().collidepoint(scene_pos):
                self._handle_end_action()
            return
        chosen = self.arrow_at(scene_pos)
        if chosen is None:
            return
        occupied = set()
        for arrow in self.arrows:
            occupied.update(arrow.body_cells())
        if all(cell not in occupied for cell in chosen.path_cells(self.spec.grid_size)):
            self._spawn_success_effect(chosen)
            self.arrows.remove(chosen)
            now = pygame.time.get_ticks()
            self.combo = self.combo + 1 if now <= self.combo_until else 1
            self.combo_until = now + 1000
            self.score += 10 + max(0, self.combo - 1) * 3
            self.audio.play_clear(self.combo)
            if not self.arrows:
                self.score += 100 * (self.level_index + 1)
                self.pending_end_state = "campaign_won" if self.level_index == len(LEVELS) - 1 else "level_clear"
                self.state = "clearing"
        else:
            self.combo = 0
            self.lives = max(0, self.lives - 1)
            self.bad_arrow = chosen
            self.shake_until = pygame.time.get_ticks() + 310
            blocker = next(cell for cell in chosen.path_cells(self.spec.grid_size) if cell in occupied)
            self._spawn_blocked_animation(chosen, blocker)
            self.pending_after_collision = "lost" if self.lives == 0 else "playing"
            self.state = "blocked_anim"


def run():
    pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.init()
    game = Game()
    screen = pygame.display.set_mode(game.window_size)
    pygame.display.set_caption("箭迹突围")
    scene = pygame.Surface(game.window_size)
    clock = pygame.time.Clock()
    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                game.click(event.pos)
        if screen.get_size() != game.window_size:
            screen = pygame.display.set_mode(game.window_size)
            scene = pygame.Surface(game.window_size)
        game.update(dt)
        game.draw(scene)
        screen.fill(BG_TOP)
        screen.blit(scene, game.camera_offset())
        pygame.display.flip()
    pygame.quit()
