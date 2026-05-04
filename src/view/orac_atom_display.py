#!/usr/bin/env python3
# Author: Clive Bostock
# Date: 2026-05-03
# Description: Animated atom-style Orac status display prototype.
"""Render an animated atom-style status display for Orac.

This standalone prototype provides a Tkinter Canvas based front-end that
can be driven by calling ``set_state()``. It does not connect to Orac or
perform any model, plugin, database, or network work.
"""

from __future__ import annotations

import argparse
import logging
import math
import random
import tkinter as tk
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from tkinter import ttk
from typing import Any

ctk: Any | None = None
HAS_CUSTOMTKINTER = False


LOGGER = logging.getLogger("orac-atom-display")

DEFAULT_WIDTH = 980
DEFAULT_HEIGHT = 720
DEFAULT_COMPACT_WIDTH = 560
DEFAULT_COMPACT_HEIGHT = 420
DEFAULT_THEME_NAME = "Cobalt"
DEFAULT_THEME_MODE = "dark"
THEMES_DIR = Path(__file__).resolve().parents[2] / "themes"
ANIMATION_INTERVAL_MS = 16
VALID_STATES = {"idle", "listening", "cogitating", "speaking", "error"}
VALID_MODES = {"kiosk", "dev", "compact"}
ATOM_SYSTEM_SCALE = 1.30
PARTICLE_SIZE_SCALE = 0.90


@dataclass(frozen=True, slots=True)
class AtomStateStyle:
  """Visual settings for an Orac runtime state.

  Args:
    core: Primary core colour.
    accent: Secondary glow colour.
    particle: Particle colour.
    orbit: Orbital ring colour.
    speed: Baseline orbital speed multiplier.
    pulse_rate: Core pulse rate.
    pulse_depth: Core pulse intensity.
    orbit_alpha: Perceived brightness of orbital paths.
    orbit_brightness: Brightness multiplier for active orbit lines.
    particles: Number of visible particles.
    disruption: Amount of intentional irregularity in the animation.
    trail_segments: Number of segments used for electron trails.
    core_scale: Relative size of the nucleus.
  """

  core: str
  accent: str
  particle: str
  orbit: str
  speed: float
  pulse_rate: float
  pulse_depth: float
  orbit_alpha: float
  orbit_brightness: float
  particles: int
  disruption: float
  trail_segments: int
  core_scale: float


@dataclass(frozen=True, slots=True)
class OrbitPath:
  """Configuration for an elliptical orbital path."""

  radius_x: float
  radius_y: float
  tilt_degrees: float
  phase: float
  speed: float


@dataclass(frozen=True, slots=True)
class Star:
  """A static background star with a deterministic twinkle phase."""

  x_ratio: float
  y_ratio: float
  radius: float
  phase: float
  strength: float


class AtomState(str, Enum):
  """Supported visual runtime states."""

  IDLE = "idle"
  LISTENING = "listening"
  COGITATING = "cogitating"
  SPEAKING = "speaking"
  ERROR = "error"


class DisplayMode(str, Enum):
  """Supported presentation modes."""

  KIOSK = "kiosk"
  DEV = "dev"
  COMPACT = "compact"


STATE_STYLES: dict[AtomState, AtomStateStyle] = {
  AtomState.IDLE: AtomStateStyle(
    core="#4fc3f7",
    accent="#1b5f91",
    particle="#bff7ff",
    orbit="#2f8cc7",
    speed=0.38,
    pulse_rate=0.85,
    pulse_depth=0.08,
    orbit_alpha=0.30,
    orbit_brightness=0.78,
    particles=5,
    disruption=0.00,
    trail_segments=3,
    core_scale=0.80,
  ),
  AtomState.LISTENING: AtomStateStyle(
    core="#7af7ff",
    accent="#29b6f6",
    particle="#e5fcff",
    orbit="#61d9ff",
    speed=0.68,
    pulse_rate=1.45,
    pulse_depth=0.18,
    orbit_alpha=0.52,
    orbit_brightness=1.08,
    particles=7,
    disruption=0.04,
    trail_segments=4,
    core_scale=0.86,
  ),
  AtomState.COGITATING: AtomStateStyle(
    core="#b69cff",
    accent="#31e6d0",
    particle="#fff6bd",
    orbit="#7dd3fc",
    speed=1.18,
    pulse_rate=2.35,
    pulse_depth=0.30,
    orbit_alpha=0.68,
    orbit_brightness=1.20,
    particles=11,
    disruption=0.13,
    trail_segments=5,
    core_scale=0.90,
  ),
  AtomState.SPEAKING: AtomStateStyle(
    core="#9be7ff",
    accent="#55d6be",
    particle="#f9ffff",
    orbit="#73e0ff",
    speed=0.78,
    pulse_rate=1.85,
    pulse_depth=0.24,
    orbit_alpha=0.56,
    orbit_brightness=1.12,
    particles=8,
    disruption=0.03,
    trail_segments=4,
    core_scale=0.88,
  ),
  AtomState.ERROR: AtomStateStyle(
    core="#ff5b4f",
    accent="#ffb02e",
    particle="#ffd166",
    orbit="#ff6b35",
    speed=0.56,
    pulse_rate=4.20,
    pulse_depth=0.38,
    orbit_alpha=0.64,
    orbit_brightness=1.16,
    particles=6,
    disruption=0.34,
    trail_segments=4,
    core_scale=0.84,
  ),
}


class OracAtomDisplay:
  """Animated atom-style runtime status display for Orac.

  Args:
    parent: Tkinter-compatible parent widget.
    width: Initial canvas width.
    height: Initial canvas height.
  """

  def __init__(
    self,
    parent: tk.Misc,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
  ) -> None:
    self.parent = parent
    self.width = width
    self.height = height
    if HAS_CUSTOMTKINTER and ctk is not None:
      self.container = ctk.CTkFrame(
        parent,
        corner_radius=18,
        border_width=2,
        border_color="#28d7ff",
      )
      self.container.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
      canvas_parent: tk.Misc = self.container
      canvas_padx = 10
      canvas_pady = 10
    else:
      self.container = tk.Frame(
        parent,
        bg="#06131d",
        bd=1,
        highlightthickness=1,
        highlightbackground="#2dcdf8",
        highlightcolor="#2dcdf8",
      )
      self.container.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
      canvas_parent = self.container
      canvas_padx = 8
      canvas_pady = 8

    self.canvas = tk.Canvas(
      canvas_parent,
      width=width,
      height=height,
      bg="#03070d",
      bd=0,
      highlightthickness=0,
      relief="flat",
    )
    self.canvas.pack(fill=tk.BOTH, expand=True, padx=canvas_padx, pady=canvas_pady)

    self.state = AtomState.IDLE
    self.transition_from_state = AtomState.IDLE
    self.transition_to_state = AtomState.IDLE
    self.transition_start_frame = 0
    self.transition_duration_frames = 26
    self.running = False
    self.frame_index = 0
    self.after_id: str | None = None
    self.ripple_events: list[tuple[float, str]] = []
    self.error_flash_until = 0
    self.mute_overlay = False
    self.blink_active = False
    self.blink_start_time = 0.0
    self.blink_duration = 0.18
    self.next_blink_time = 0.0
    self._blink_rng = random.Random(9027)
    self.focus_current = (0.0, 0.0)
    self.focus_start = (0.0, 0.0)
    self.focus_target = (0.0, 0.0)
    self.focus_move_start_time = 0.0
    self.focus_move_duration = 1.0
    self.focus_hold_duration = 0.8
    self.focus_next_time = 0.0
    self.focus_moving = False
    self.focus_phase = "pause"
    self._focus_rng = random.Random(7619)

    self.orbits = [
      OrbitPath(245.0, 76.0, -18.0, 0.0, 1.00),
      OrbitPath(230.0, 88.0, 52.0, 1.7, -0.82),
      OrbitPath(180.0, 58.0, -66.0, 3.2, 1.28),
      OrbitPath(276.0, 34.0, 13.0, 5.0, -0.55),
    ]
    self.internal_sample_scale = 2.3
    self.stars = self._build_stars(count=120)

    self.canvas.bind("<Configure>", self._on_resize)
    self._schedule_nucleus_blink(self.state, self._time_seconds)
    self._schedule_pupil_focus(self.state, self._time_seconds)
    self.focus_next_time = self._time_seconds + 0.8

  def start(self) -> None:
    """Start the non-blocking animation loop."""
    if self.running:
      return

    self.running = True
    self._schedule_next_frame()

  def stop(self) -> None:
    """Stop the animation loop."""
    self.running = False
    if self.after_id is not None:
      self.parent.after_cancel(self.after_id)
      self.after_id = None

  def set_state(self, state: str) -> None:
    """Set the display state.

    Args:
      state: One of ``idle``, ``listening``, ``cogitating``, ``speaking``,
        or ``error``. Matching is case insensitive.

    Raises:
      ValueError: If the state is not supported.
    """
    normalised = state.strip().lower()
    if normalised not in VALID_STATES:
      raise ValueError(
        f"Unsupported Orac atom display state: {state!r}. "
        f"Expected one of: {', '.join(sorted(VALID_STATES))}."
      )

    next_state = AtomState(normalised)
    if next_state == self.state:
      return

    self.transition_from_state = self.state
    self.transition_to_state = next_state
    self.transition_start_frame = self.frame_index
    self.state = next_state
    self._schedule_nucleus_blink(next_state, self._time_seconds)
    self._schedule_pupil_focus(next_state, self._time_seconds)
    now = self._time_seconds
    if next_state in {AtomState.LISTENING, AtomState.SPEAKING}:
      self.ripple_events.append((now, next_state.value))
    if next_state == AtomState.ERROR:
      self.error_flash_until = self.frame_index + 32
      self.ripple_events.append((now, "error"))

  def destroy(self) -> None:
    """Stop animation and destroy the canvas."""
    self.stop()
    self.canvas.destroy()

  @property
  def _time_seconds(self) -> float:
    """Return current animation time in seconds."""
    return self.frame_index * (ANIMATION_INTERVAL_MS / 1000.0)

  def _schedule_next_frame(self) -> None:
    """Schedule the next Tkinter ``after`` animation callback."""
    self.after_id = self.parent.after(
      ANIMATION_INTERVAL_MS,
      self._animate,
    )

  def _animate(self) -> None:
    """Draw a frame and schedule the next one."""
    if not self.running:
      return

    self.frame_index += 1
    self._update_nucleus_blink(self._time_seconds)
    self._update_pupil_focus(self._time_seconds)
    self._draw_frame()
    self._schedule_next_frame()

  def _on_resize(self, event: tk.Event[Any]) -> None:
    """Track canvas size changes."""
    self.width = max(1, int(event.width))
    self.height = max(1, int(event.height))

  def _build_stars(self, count: int) -> list[Star]:
    """Create deterministic background stars.

    Args:
      count: Number of stars to create.

    Returns:
      list[Star]: Generated stars.
    """
    randomiser = random.Random(7421)
    return [
      Star(
        x_ratio=randomiser.random(),
        y_ratio=randomiser.random(),
        radius=randomiser.uniform(0.45, 1.45),
        phase=randomiser.uniform(0.0, math.tau),
        strength=randomiser.uniform(0.25, 0.95),
      )
      for _ in range(count)
    ]

  def _draw_frame(self) -> None:
    """Redraw the complete scene."""
    self.canvas.delete("all")

    cx = self.width / 2.0
    cy = self.height / 2.0
    scale = min(self.width / DEFAULT_WIDTH, self.height / DEFAULT_HEIGHT)
    scale = max(0.58, min(1.18, scale))
    atom_scale = scale * ATOM_SYSTEM_SCALE
    particle_scale = scale * PARTICLE_SIZE_SCALE
    style = self._resolve_visual_style()
    t = self._time_seconds

    self._draw_background(t=t, style=style)
    self._draw_ambient_haze(cx=cx, cy=cy, scale=atom_scale, style=style, t=t)
    self._draw_ripples(cx=cx, cy=cy, scale=atom_scale, style=style, t=t)
    self._draw_orbits(
      cx=cx,
      cy=cy,
      scale=atom_scale,
      style=style,
      t=t,
      front=False,
    )
    self._draw_particles(
      cx=cx,
      cy=cy,
      scale=atom_scale,
      particle_scale=particle_scale,
      style=style,
      t=t,
      front=False,
    )
    self._draw_core(cx=cx, cy=cy, scale=atom_scale, style=style, t=t)
    self._draw_orbits(
      cx=cx,
      cy=cy,
      scale=atom_scale,
      style=style,
      t=t,
      front=True,
    )
    self._draw_particles(
      cx=cx,
      cy=cy,
      scale=atom_scale,
      particle_scale=particle_scale,
      style=style,
      t=t,
      front=True,
    )
    self._draw_mute_overlay(style=style, scale=scale, t=t)
    self._draw_state_label(style=style)

  def _draw_background(self, t: float, style: AtomStateStyle) -> None:
    """Draw the dark background, grid, and stars."""
    self.canvas.create_rectangle(
      0,
      0,
      self.width,
      self.height,
      fill="#03070d",
      outline="",
    )

    for index in range(10):
      ratio = index / 9
      colour = _mix_colour("#03070d", "#071a28", ratio * 0.50)
      self.canvas.create_rectangle(
        0,
        self.height * ratio,
        self.width,
        self.height * (ratio + 0.13),
        fill=colour,
        outline="",
      )

    grid_colour = _mix_colour("#06111b", style.orbit, 0.12)
    spacing = 56
    offset = int((t * 8) % spacing)
    for x_pos in range(-spacing + offset, self.width + spacing, spacing):
      self.canvas.create_line(
        x_pos,
        0,
        x_pos,
        self.height,
        fill=grid_colour,
        width=1,
      )
    for y_pos in range(-spacing + offset, self.height + spacing, spacing):
      self.canvas.create_line(
        0,
        y_pos,
        self.width,
        y_pos,
        fill=grid_colour,
        width=1,
      )

    for index, star in enumerate(self.stars):
      twinkle = self._star_twinkle(star=star, index=index, t=t)
      colour = _mix_colour("#091522", "#d9fbff", star.strength * twinkle)
      x_pos = star.x_ratio * self.width
      y_pos = star.y_ratio * self.height
      r = star.radius * (0.90 + 0.15 * twinkle)
      self.canvas.create_oval(
        x_pos - r,
        y_pos - r,
        x_pos + r,
        y_pos + r,
        fill=colour,
        outline="",
      )

  def _draw_ambient_haze(
    self,
    cx: float,
    cy: float,
    scale: float,
    style: AtomStateStyle,
    t: float,
  ) -> None:
    """Draw a low-contrast glow field around the atom."""
    pulse = 0.5 + 0.5 * math.sin(t * style.pulse_rate)
    base_radius = 255.0 * scale * (1.0 + pulse * 0.05)
    for index, ratio in enumerate((1.0, 0.74, 0.50, 0.30)):
      radius = base_radius * ratio
      colour = _mix_colour("#03070d", style.accent, 0.08 + index * 0.05)
      self.canvas.create_oval(
        cx - radius,
        cy - radius * 0.72,
        cx + radius,
        cy + radius * 0.72,
        fill=colour,
        outline="",
      )

  def _draw_ripples(
    self,
    cx: float,
    cy: float,
    scale: float,
    style: AtomStateStyle,
    t: float,
  ) -> None:
    """Draw transient inward or outward state waves."""
    if self.state == AtomState.LISTENING:
      cadence = 1.1
      if not self.ripple_events or t - self.ripple_events[-1][0] > cadence:
        self.ripple_events.append((t, "listening"))
    elif self.state == AtomState.SPEAKING:
      cadence = 0.7
      if not self.ripple_events or t - self.ripple_events[-1][0] > cadence:
        self.ripple_events.append((t, "speaking"))

    active_events: list[tuple[float, str]] = []
    for start_time, kind in self.ripple_events:
      age = t - start_time
      if age > 2.2:
        continue

      active_events.append((start_time, kind))
      progress = _clamp(age / 2.2, 0.0, 1.0)
      if kind == "listening":
        radius = (260.0 - progress * 210.0) * scale
      else:
        radius = (42.0 + progress * 300.0) * scale

      intensity = 1.0 - progress
      colour = _mix_colour("#08101a", style.accent, 0.28 * intensity)
      width = max(1, int(3 * intensity))
      self.canvas.create_oval(
        cx - radius,
        cy - radius * 0.64,
        cx + radius,
        cy + radius * 0.64,
        outline=colour,
        width=width,
      )

    self.ripple_events = active_events[-8:]

    if self.state == AtomState.SPEAKING:
      self._draw_voice_waves(cx=cx, cy=cy, scale=scale, style=style, t=t)

  def _draw_voice_waves(
    self,
    cx: float,
    cy: float,
    scale: float,
    style: AtomStateStyle,
    t: float,
  ) -> None:
    """Draw a compact speaking waveform beneath the nucleus."""
    baseline = cy + 190.0 * scale
    speech_energy = 0.68 + 0.32 * math.sin(t * 1.8 + 0.4 * math.sin(t * 0.9))
    bar_count = 41
    bar_step = 7.0 * scale
    start_x = cx - (bar_count - 1) * bar_step / 2.0

    for index in range(bar_count):
      mix = index / max(1, bar_count - 1)
      envelope = math.sin(math.pi * mix) ** 1.1
      wave = (
        0.50
        + 0.50 * math.sin(t * 6.4 + mix * 8.3 + math.sin(t * 1.2))
      )
      height = (14.0 + 42.0 * speech_energy * wave) * envelope * scale
      width = max(1, int((1.8 + speech_energy * 1.5) * scale))
      x_pos = start_x + index * bar_step

      glow_colour = _mix_colour("#06111b", style.accent, 0.20 + wave * 0.30)
      core_colour = _mix_colour("#d9fbff", style.particle, 0.20 + wave * 0.22)
      tip_colour = _mix_colour("#ffffff", style.core, 0.14 + wave * 0.12)

      self.canvas.create_line(
        x_pos,
        baseline - height * 1.06,
        x_pos,
        baseline + height * 1.06,
        fill=glow_colour,
        width=width + max(1, int(2 * scale)),
        capstyle=tk.ROUND,
      )
      self.canvas.create_line(
        x_pos,
        baseline - height,
        x_pos,
        baseline + height,
        fill=core_colour,
        width=width,
        capstyle=tk.ROUND,
      )
      self.canvas.create_line(
        x_pos,
        baseline - height * 0.66,
        x_pos,
        baseline + height * 0.66,
        fill=tip_colour,
        width=max(1, int(1.2 * scale)),
        capstyle=tk.ROUND,
      )

  def _draw_orbits(
    self,
    cx: float,
    cy: float,
    scale: float,
    style: AtomStateStyle,
    t: float,
    front: bool,
  ) -> None:
    """Draw elliptical orbital paths."""
    for index, orbit in enumerate(self.orbits):
      segments = self._orbit_segments(
        orbit=orbit,
        cx=cx,
        cy=cy,
        scale=scale,
        wobble=style.disruption * math.sin(t * 4.3 + index),
        front=front,
      )
      if not segments:
        continue

      brightness = style.orbit_brightness
      side_mix = 0.52 if not front else 1.10
      colour = _mix_colour(
        "#07101a",
        style.orbit,
        _clamp(style.orbit_alpha * brightness * side_mix, 0.0, 1.0),
      )
      highlight = _mix_colour(
        "#07101a",
        style.accent,
        _clamp(
          style.orbit_alpha * brightness * 0.66 * side_mix,
          0.0,
          1.0,
        ),
      )
      for points in segments:
        if len(points) < 8:
          continue
        line_width = max(1, int((1.45 if front else 1.15) * scale))
        glow_width = max(1, int((2.3 if front else 1.6) * scale))
        self.canvas.create_line(
          points,
          fill=colour,
          width=line_width,
          smooth=True,
          splinesteps=48,
        )
        self.canvas.create_line(
          points,
          fill=highlight,
          width=glow_width,
          smooth=True,
          splinesteps=42,
        )

  def _draw_particles(
    self,
    cx: float,
    cy: float,
    scale: float,
    particle_scale: float,
    style: AtomStateStyle,
    t: float,
    front: bool,
  ) -> None:
    """Draw particles moving around the orbital paths."""
    for index in range(style.particles):
      orbit = self.orbits[index % len(self.orbits)]
      phase_offset = (index / style.particles) * math.tau
      jitter = style.disruption * math.sin(t * 13.0 + index * 2.1)
      angle = (
        t * style.speed * orbit.speed
        + orbit.phase
        + phase_offset
        + jitter
      )
      x_pos, y_pos = self._project_orbit_point(
        orbit=orbit,
        angle=angle,
        cx=cx,
        cy=cy,
        scale=scale,
      )
      is_front = self._orbit_is_front(orbit=orbit, angle=angle)
      if is_front != front:
        continue
      depth_mix = 1.0 if front else 0.58
      apparent_depth = 0.60 + 0.40 * math.sin(angle + orbit.phase)
      particle_radius = (3.8 + apparent_depth * 2.5) * particle_scale * depth_mix
      self._draw_electron_trail(
        orbit=orbit,
        angle=angle,
        cx=cx,
        cy=cy,
        scale=scale,
        particle_scale=particle_scale,
        style=style,
        front=front,
      )
      self._draw_glowing_dot(
        x=x_pos,
        y=y_pos,
        radius=particle_radius,
        colour=self._electron_colour(style=style, front=front, t=t),
        halo=3.2 if front else 2.1,
      )

      if self.state == AtomState.COGITATING and index % 3 == 0:
        trail_x, trail_y = self._project_orbit_point(
        orbit=orbit,
        angle=angle - 0.09 * orbit.speed,
        cx=cx,
        cy=cy,
          scale=scale,
        )
        self.canvas.create_line(
          trail_x,
          trail_y,
          x_pos,
          y_pos,
          fill=_mix_colour("#07101a", style.particle, 0.38),
          width=max(1, int(2 * particle_scale)),
          capstyle=tk.ROUND,
        )

  def _draw_core(
    self,
    cx: float,
    cy: float,
    scale: float,
    style: AtomStateStyle,
    t: float,
  ) -> None:
    """Draw the central glowing intelligence core."""
    pulse = 0.5 + 0.5 * math.sin(t * math.tau * style.pulse_rate)
    breath = 0.5 + 0.5 * math.sin(t * 1.2 + math.sin(t * 0.7))
    shimmer = 0.5 + 0.5 * math.sin(t * 3.8 + math.sin(t * 1.7))
    surface_shimmer = 0.5 + 0.5 * math.sin(t * 6.4 + math.cos(t * 2.3))
    blink_open, blink_boost, blink_flicker = self._nucleus_blink_profile(
      style=style,
      t=t,
    )
    flash = 0.0
    if self.state == AtomState.ERROR and self.frame_index < self.error_flash_until:
      flash = 0.5 + 0.5 * math.sin(t * 74.0)

    core_radius = 33.0 * scale * style.core_scale
    core_radius *= 1.0 + pulse * style.pulse_depth + breath * 0.03
    core_radius *= 1.0 + blink_boost * 0.03
    glow_radius = core_radius * (2.9 + pulse * 0.72 + flash * 0.8)

    halo_steps = (
      (1.00, 0.08),
      (0.82, 0.12),
      (0.64, 0.17),
      (0.46, 0.22),
      (0.30, 0.28),
      (0.16, 0.36),
    )
    for ratio, mix_base in halo_steps:
      radius = glow_radius * ratio
      mix = mix_base + pulse * 0.05
      if flash:
        mix += flash * 0.12
      colour = _mix_colour("#03070d", style.accent, mix)
      self.canvas.create_oval(
        cx - radius,
        cy - radius,
        cx + radius,
        cy + radius,
        fill=colour,
        outline="",
      )

    outer_shell = _mix_colour(style.core, "#ffffff", 0.12 + shimmer * 0.12)
    outer_shell = _mix_colour(
      outer_shell,
      "#f8ffff",
      0.04 + blink_boost * 0.05,
    )
    self.canvas.create_oval(
      cx - core_radius,
      cy - core_radius,
      cx + core_radius,
      cy + core_radius,
      fill=_mix_colour("#07101a", style.core, 0.58),
      outline=outer_shell,
      width=max(1, int(1.5 * scale)),
    )

    inner_radius = core_radius * 0.68
    inner_colour = _mix_colour(
      style.core,
      "#f8ffff",
      0.12 + pulse * 0.08 + surface_shimmer * 0.10 + blink_boost * 0.05,
    )
    self.canvas.create_oval(
      cx - inner_radius,
      cy - inner_radius,
      cx + inner_radius,
      cy + inner_radius,
      fill=inner_colour,
      outline="",
    )

    mid_radius = core_radius * 0.38
    mid_colour = _mix_colour(
      style.accent,
      style.core,
      0.34 + surface_shimmer * 0.14 + blink_boost * 0.04,
    )
    self.canvas.create_oval(
      cx - mid_radius,
      cy - mid_radius,
      cx + mid_radius,
      cy + mid_radius,
      fill=mid_colour,
      outline="",
    )

    glint_radius = core_radius * 0.14
    glint_offset = math.sin(t * 5.7) * core_radius * 0.022
    self.canvas.create_oval(
      cx - core_radius * 0.20 - glint_radius + glint_offset,
      cy - core_radius * 0.28 - glint_radius,
      cx - core_radius * 0.20 + glint_radius + glint_offset,
      cy - core_radius * 0.28 + glint_radius,
      fill=_mix_colour("#ffffff", style.core, 0.46),
      outline="",
    )

    self.canvas.create_oval(
      cx + core_radius * 0.05 - glint_radius * 0.48,
      cy + core_radius * 0.10 - glint_radius * 0.48,
      cx + core_radius * 0.05 + glint_radius * 0.48,
      cy + core_radius * 0.10 + glint_radius * 0.48,
      fill=_mix_colour(style.core, "#ffffff", 0.58),
      outline="",
    )

    self.canvas.create_oval(
      cx - core_radius * 0.05 - glint_radius * 0.32,
      cy - core_radius * 0.02 - glint_radius * 0.32,
      cx - core_radius * 0.05 + glint_radius * 0.32,
      cy - core_radius * 0.02 + glint_radius * 0.32,
      fill=_mix_colour("#fefefe", style.accent, 0.60),
      outline="",
    )

    housing_width = core_radius * 1.54
    housing_height = core_radius * 0.80
    iris_width = core_radius * 0.90
    iris_height = core_radius * (0.31 + 0.41 * blink_open)
    pupil_width = core_radius * 0.32
    pupil_height = core_radius * (0.035 + 0.24 * blink_open)
    iris_colour = _mix_colour(
      style.core,
      "#f8ffff",
      0.18 + blink_boost * 0.10 + blink_flicker * 0.04,
    )
    pupil_colour = _mix_colour("#03070d", style.accent, 0.72)
    highlight_colour = _mix_colour("#ffffff", style.core, 0.68)
    pupil_offset_x, pupil_offset_y = self._pupil_focus_offset(
      iris_width=iris_width,
      iris_height=iris_height,
    )
    self.canvas.create_oval(
      cx - housing_width,
      cy - housing_height,
      cx + housing_width,
      cy + housing_height,
      fill=_mix_colour("#03070d", style.core, 0.70),
      outline="",
    )
    self.canvas.create_oval(
      cx - iris_width,
      cy - iris_height,
      cx + iris_width,
      cy + iris_height,
      fill=iris_colour,
      outline="",
      width=0,
    )
    self.canvas.create_oval(
      cx + pupil_offset_x - pupil_width,
      cy + pupil_offset_y - pupil_height,
      cx + pupil_offset_x + pupil_width,
      cy + pupil_offset_y + pupil_height,
      fill=pupil_colour,
      outline="",
    )
    self.canvas.create_oval(
      cx - iris_width * 0.28,
      cy - iris_height * 0.18,
      cx - iris_width * 0.08,
      cy + iris_height * 0.02,
      fill=highlight_colour,
      outline="",
    )

    if blink_boost > 0.0:
      reopen_colour = _mix_colour("#f8ffff", style.core, 0.42 + blink_boost * 0.18)
      reopen_height = core_radius * (0.05 + blink_boost * 0.06)
      self.canvas.create_oval(
        cx - iris_width * 0.86,
        cy - reopen_height,
        cx + iris_width * 0.86,
        cy + reopen_height,
        fill=reopen_colour,
        outline="",
      )

  def _draw_state_label(self, style: AtomStateStyle) -> None:
    """Draw the title and current state label."""
    title_colour = _mix_colour("#4b728a", style.core, 0.60)
    state_colour = _mix_colour("#72899a", style.particle, 0.52)
    self.canvas.create_text(
      self.width / 2.0,
      46,
      text="ORAC CORE",
      fill=title_colour,
      font=("TkDefaultFont", 18, "bold"),
    )
    self.canvas.create_text(
      self.width / 2.0,
      74,
      text=" ".join(self.state.value.upper()),
      fill=state_colour,
      font=("TkDefaultFont", 10, "bold"),
    )

  def _orbit_points(
    self,
    orbit: OrbitPath,
    cx: float,
    cy: float,
    scale: float,
    wobble: float,
  ) -> list[float]:
    """Return flattened canvas coordinates for an orbit polyline."""
    points: list[float] = []
    sample_count = int(145 * self.internal_sample_scale)
    for step in range(sample_count):
      angle = (step / max(1, sample_count - 1)) * math.tau
      x_pos, y_pos = self._project_orbit_point(
        orbit=orbit,
        angle=angle,
        cx=cx,
        cy=cy,
        scale=scale * (1.0 + wobble * 0.02),
      )
      points.extend([x_pos, y_pos])
    return points

  def _orbit_segments(
    self,
    orbit: OrbitPath,
    cx: float,
    cy: float,
    scale: float,
    wobble: float,
    front: bool,
  ) -> list[list[float]]:
    """Return orbit polylines split into front and back segments."""
    points: list[list[float]] = []
    current: list[float] = []
    sample_count = int(220 * self.internal_sample_scale)
    for step in range(sample_count + 1):
      angle = (step / sample_count) * math.tau
      x_pos, y_pos = self._project_orbit_point(
        orbit=orbit,
        angle=angle,
        cx=cx,
        cy=cy,
        scale=scale * (1.0 + wobble * 0.02),
      )
      if self._orbit_is_front(orbit=orbit, angle=angle) != front:
        if len(current) >= 4:
          points.append(current)
        current = []
        continue
      current.extend([x_pos, y_pos])
    if len(current) >= 4:
      points.append(current)
    return points

  def _orbit_is_front(self, orbit: OrbitPath, angle: float) -> bool:
    """Return whether the orbit point sits on the near side."""
    return math.sin(angle + orbit.phase) >= 0.0

  def _draw_electron_trail(
    self,
    orbit: OrbitPath,
    angle: float,
    cx: float,
    cy: float,
    scale: float,
    particle_scale: float,
    style: AtomStateStyle,
    front: bool,
  ) -> None:
    """Draw a short fading trail behind a particle."""
    segment_count = max(2, style.trail_segments)
    trail_colour = _mix_colour("#07101a", style.particle, 0.18)
    trail_points: list[tuple[float, float]] = []
    for index in range(segment_count):
      lag = 0.045 * (index + 1) * abs(orbit.speed)
      next_angle = angle - lag
      if self._orbit_is_front(orbit=orbit, angle=next_angle) != front:
        continue
      trail_points.append(
        self._project_orbit_point(
          orbit=orbit,
          angle=next_angle,
          cx=cx,
          cy=cy,
          scale=scale,
        )
      )

    if len(trail_points) < 2:
      return

    for index in range(len(trail_points) - 1):
      start = trail_points[index]
      end = trail_points[index + 1]
      fade = 0.42 * (1.0 - index / max(1, len(trail_points) - 1))
      colour = _mix_colour("#07101a", trail_colour, fade)
      width = max(1, int((3 - index * 0.35) * particle_scale * 0.5))
      self.canvas.create_line(
        start[0],
        start[1],
        end[0],
        end[1],
        fill=colour,
        width=width,
        capstyle=tk.ROUND,
      )

  def _project_orbit_point(
    self,
    orbit: OrbitPath,
    angle: float,
    cx: float,
    cy: float,
    scale: float,
  ) -> tuple[float, float]:
    """Project an orbital angle into rotated ellipse coordinates."""
    x_raw = math.cos(angle) * orbit.radius_x * scale
    y_raw = math.sin(angle) * orbit.radius_y * scale
    rotation = math.radians(orbit.tilt_degrees)
    x_pos = x_raw * math.cos(rotation) - y_raw * math.sin(rotation)
    y_pos = x_raw * math.sin(rotation) + y_raw * math.cos(rotation)
    return cx + x_pos, cy + y_pos

  def _draw_glowing_dot(
    self,
    x: float,
    y: float,
    radius: float,
    colour: str,
    halo: float,
  ) -> None:
    """Draw a particle with a soft halo."""
    for index, factor in enumerate((halo, 2.75, 2.05, 1.55, 1.15)):
      current_radius = radius * factor
      mix = 0.05 + index * 0.08
      self.canvas.create_oval(
        x - current_radius,
        y - current_radius,
        x + current_radius,
        y + current_radius,
        fill=_mix_colour("#03070d", colour, mix),
        outline="",
      )
    self.canvas.create_oval(
      x - radius,
      y - radius,
      x + radius,
      y + radius,
      fill=_mix_colour("#d9fbff", colour, 0.22),
      outline=_mix_colour(colour, "#ffffff", 0.55),
    )

  def _draw_mute_overlay(
    self,
    style: AtomStateStyle,
    scale: float,
    t: float,
  ) -> None:
    """Draw a subtle mute badge overlay when enabled."""
    if not self.mute_overlay:
      return

    size = 22.0 * scale
    x_pos = self.width - 38.0 * scale
    y_pos = 42.0 * scale
    pulse = 0.5 + 0.5 * math.sin(t * 2.0)
    glow = _mix_colour("#03070d", style.accent, 0.22 + pulse * 0.08)
    fill_colour = _mix_colour("#091522", style.accent, 0.34)
    line_colour = _mix_colour("#d9fbff", style.accent, 0.42)
    self.canvas.create_oval(
      x_pos - size * 1.18,
      y_pos - size * 1.18,
      x_pos + size * 1.18,
      y_pos + size * 1.18,
      fill=glow,
      outline="",
    )
    self.canvas.create_oval(
      x_pos - size,
      y_pos - size,
      x_pos + size,
      y_pos + size,
      fill=fill_colour,
      outline=line_colour,
      width=max(1, int(scale)),
    )
    self.canvas.create_line(
      x_pos - size * 0.38,
      y_pos - size * 0.18,
      x_pos + size * 0.18,
      y_pos - size * 0.18,
      fill=line_colour,
      width=max(1, int(2 * scale)),
      capstyle=tk.ROUND,
    )
    self.canvas.create_line(
      x_pos - size * 0.18,
      y_pos - size * 0.22,
      x_pos - size * 0.18,
      y_pos + size * 0.22,
      fill=line_colour,
      width=max(1, int(2 * scale)),
      capstyle=tk.ROUND,
    )
    self.canvas.create_line(
      x_pos - size * 0.46,
      y_pos + size * 0.34,
      x_pos + size * 0.46,
      y_pos - size * 0.34,
      fill=line_colour,
      width=max(1, int(2 * scale)),
      capstyle=tk.ROUND,
    )

  def _schedule_nucleus_blink(self, state: AtomState, now: float) -> None:
    """Schedule the next nucleus blink for the current state."""
    self.blink_active = False

    if state == AtomState.SPEAKING:
      self.next_blink_time = now + 999.0
      return

    if state == AtomState.ERROR:
      self.next_blink_time = now + self._blink_rng.uniform(0.25, 0.55)
      return

    low, high = self._blink_interval_range(state)
    self.next_blink_time = now + self._blink_rng.uniform(low, high)

  def _blink_interval_range(self, state: AtomState) -> tuple[float, float]:
    """Return the blink interval range for a state."""
    if state == AtomState.LISTENING:
      return (8.0, 14.0)
    if state == AtomState.COGITATING:
      return (10.0, 18.0)
    return (5.0, 8.0)

  def _blink_duration_range(self, state: AtomState) -> tuple[float, float]:
    """Return the blink duration range for a state."""
    if state == AtomState.LISTENING:
      return (0.15, 0.20)
    if state == AtomState.COGITATING:
      return (0.13, 0.17)
    return (0.16, 0.24)

  def _blink_min_open(self, state: AtomState) -> float:
    """Return the minimum aperture openness during a blink."""
    if state == AtomState.LISTENING:
      return 0.32
    if state == AtomState.COGITATING:
      return 0.24
    return 0.18

  def _update_nucleus_blink(self, t: float) -> None:
    """Advance the nucleus blink scheduler."""
    if self.state == AtomState.SPEAKING:
      self.blink_active = False
      self.next_blink_time = t + 999.0
      return

    if self.state == AtomState.ERROR:
      self.blink_active = False
      return

    if self.blink_active:
      end_time = self.blink_start_time + self.blink_duration
      if t >= end_time:
        self.blink_active = False
        self._schedule_nucleus_blink(self.state, t)
      return

    if t >= self.next_blink_time:
      self.blink_active = True
      self.blink_start_time = t
      low, high = self._blink_duration_range(self.state)
      self.blink_duration = self._blink_rng.uniform(low, high)

  def _nucleus_blink_profile(
    self,
    style: AtomStateStyle,
    t: float,
  ) -> tuple[float, float, float]:
    """Return aperture openness, reopen pulse, and flicker intensity."""
    if self.state == AtomState.ERROR:
      flicker = 0.72 + 0.28 * (
        0.5 + 0.5 * math.sin(t * 43.0 + math.sin(t * 11.0))
      )
      return (0.82 + 0.18 * flicker, 0.10 * flicker, flicker)

    if self.state == AtomState.SPEAKING:
      return (1.0, 0.0, 0.0)

    if not self.blink_active:
      return (1.0, 0.0, 0.0)

    progress = _clamp(
      (t - self.blink_start_time) / max(0.001, self.blink_duration),
      0.0,
      1.0,
    )
    min_open = self._blink_min_open(self.state)
    if progress < 0.5:
      close = _smoothstep(progress * 2.0)
      open_factor = 1.0 - (1.0 - min_open) * close
      reopen_boost = 0.0
    else:
      reopen = _smoothstep((progress - 0.5) * 2.0)
      open_factor = min_open + (1.0 - min_open) * reopen
      reopen_boost = reopen

    flicker = 0.10 + 0.04 * math.sin(t * 17.0 + self.frame_index * 0.31)
    return (open_factor, reopen_boost, flicker)

  def _schedule_pupil_focus(self, state: AtomState, now: float) -> None:
    """Schedule the next subtle focus movement."""
    self.focus_moving = False
    self.focus_phase = "pause"
    self.focus_current = (0.0, 0.0)
    self.focus_start = (0.0, 0.0)
    self.focus_target = (0.0, 0.0)

    low, high = self._focus_interval_range(state)
    self.focus_next_time = now + self._focus_rng.uniform(low, high)

  def _focus_interval_range(self, state: AtomState) -> tuple[float, float]:
    """Return focus dwell timing for the current state."""
    if state == AtomState.LISTENING:
      return (2.8, 5.0)
    if state == AtomState.COGITATING:
      return (0.8, 1.6)
    if state == AtomState.SPEAKING:
      return (8.0, 15.0)
    if state == AtomState.ERROR:
      return (0.8, 1.6)
    return (2.2, 4.0)

  def _focus_duration_range(self, state: AtomState) -> tuple[float, float]:
    """Return eased movement duration for the current state."""
    if state == AtomState.LISTENING:
      return (1.8, 3.0)
    if state == AtomState.COGITATING:
      return (0.45, 0.85)
    if state == AtomState.SPEAKING:
      return (1.2, 2.0)
    if state == AtomState.ERROR:
      return (0.4, 0.8)
    return (1.6, 2.7)

  def _focus_hold_range(self, state: AtomState) -> tuple[float, float]:
    """Return hold duration after a focus drift."""
    if state == AtomState.LISTENING:
      return (1.4, 2.8)
    if state == AtomState.COGITATING:
      return (0.25, 0.7)
    if state == AtomState.SPEAKING:
      return (0.5, 1.0)
    if state == AtomState.ERROR:
      return (0.15, 0.4)
    return (0.7, 1.6)

  def _next_focus_target(self, state: AtomState) -> tuple[float, float]:
    """Choose the next focus offset as a fraction of iris dimensions."""
    if self._focus_rng.random() < self._focus_centre_probability(state):
      return (0.0, 0.0)

    if state == AtomState.LISTENING:
      return (
        self._focus_rng.uniform(0.18, 0.25),
        self._focus_rng.uniform(-0.08, 0.10),
      )
    if state == AtomState.COGITATING:
      return (
        self._focus_rng.uniform(-0.14, 0.14),
        self._focus_rng.uniform(-0.11, 0.11),
      )
    if state == AtomState.SPEAKING:
      return (
        self._focus_rng.uniform(-0.045, 0.045),
        self._focus_rng.uniform(-0.03, 0.03),
      )
    if state == AtomState.ERROR:
      return (
        self._focus_rng.uniform(-0.08, 0.08),
        self._focus_rng.uniform(-0.06, 0.06),
      )
    return (
      self._focus_rng.uniform(-0.19, 0.19),
      self._focus_rng.uniform(-0.13, 0.13),
    )

  def _focus_centre_probability(self, state: AtomState) -> float:
    """Return chance that the next focus target is exact centre."""
    if state == AtomState.LISTENING:
      return 0.12
    if state == AtomState.COGITATING:
      return 0.10
    if state == AtomState.SPEAKING:
      return 0.88
    if state == AtomState.ERROR:
      return 0.10
    return 0.16

  def _update_pupil_focus(self, t: float) -> None:
    """Advance the subtle pupil focus movement."""
    if self.blink_active:
      return

    if self.focus_moving:
      progress = _clamp(
        (t - self.focus_move_start_time) / max(0.001, self.focus_move_duration),
        0.0,
        1.0,
      )
      eased = _smoothstep(progress)
      self.focus_current = (
        _lerp(self.focus_start[0], self.focus_target[0], eased),
        _lerp(self.focus_start[1], self.focus_target[1], eased),
      )
      if progress >= 1.0:
        self.focus_moving = False
        self.focus_current = self.focus_target
        if self.focus_phase == "out":
          self.focus_phase = "hold"
          low, high = self._focus_hold_range(self.state)
          self.focus_next_time = t + self._focus_rng.uniform(low, high)
        else:
          self._schedule_pupil_focus(self.state, t)
      return

    if t < self.focus_next_time:
      return

    if self.focus_phase == "hold":
      self.focus_start = self.focus_current
      self.focus_target = (0.0, 0.0)
      low, high = self._focus_duration_range(self.state)
      self.focus_move_duration = self._focus_rng.uniform(low, high)
      self.focus_move_start_time = t
      self.focus_moving = True
      self.focus_phase = "return"
      return

    self.focus_start = self.focus_current
    self.focus_target = self._next_focus_target(self.state)
    low, high = self._focus_duration_range(self.state)
    self.focus_move_duration = self._focus_rng.uniform(low, high)
    self.focus_move_start_time = t
    self.focus_moving = True
    self.focus_phase = "out"

  def _pupil_focus_offset(
    self,
    iris_width: float,
    iris_height: float,
  ) -> tuple[float, float]:
    """Return current pupil offset, centred while blinking."""
    if self.blink_active:
      return (0.0, 0.0)

    return (
      self.focus_current[0] * iris_width,
      self.focus_current[1] * iris_height,
    )

  def _resolve_visual_style(self) -> AtomStateStyle:
    """Return the blended visual style for the current transition."""
    transition_progress = self._transition_progress()
    if self.transition_from_state == self.transition_to_state:
      return STATE_STYLES[self.transition_to_state]

    from_style = STATE_STYLES[self.transition_from_state]
    to_style = STATE_STYLES[self.transition_to_state]
    return self._blend_state_style(
      from_style=from_style,
      to_style=to_style,
      blend=transition_progress,
    )

  def _transition_progress(self) -> float:
    """Return the eased state transition progress."""
    elapsed = self.frame_index - self.transition_start_frame
    if elapsed <= 0:
      return 0.0
    raw = _clamp(elapsed / max(1, self.transition_duration_frames), 0.0, 1.0)
    if raw >= 1.0:
      self.transition_from_state = self.transition_to_state
      return 1.0
    return _smoothstep(raw)

  def _blend_state_style(
    self,
    from_style: AtomStateStyle,
    to_style: AtomStateStyle,
    blend: float,
  ) -> AtomStateStyle:
    """Blend two state styles into a transition style."""
    blend = _smoothstep(_clamp(blend, 0.0, 1.0))
    return AtomStateStyle(
      core=_mix_colour(from_style.core, to_style.core, blend),
      accent=_mix_colour(from_style.accent, to_style.accent, blend),
      particle=_mix_colour(from_style.particle, to_style.particle, blend),
      orbit=_mix_colour(from_style.orbit, to_style.orbit, blend),
      speed=_lerp(from_style.speed, to_style.speed, blend),
      pulse_rate=_lerp(from_style.pulse_rate, to_style.pulse_rate, blend),
      pulse_depth=_lerp(from_style.pulse_depth, to_style.pulse_depth, blend),
      orbit_alpha=_lerp(from_style.orbit_alpha, to_style.orbit_alpha, blend),
      orbit_brightness=_lerp(
        from_style.orbit_brightness,
        to_style.orbit_brightness,
        blend,
      ),
      particles=int(round(_lerp(from_style.particles, to_style.particles, blend))),
      disruption=_lerp(from_style.disruption, to_style.disruption, blend),
      trail_segments=int(
        round(_lerp(from_style.trail_segments, to_style.trail_segments, blend))
      ),
      core_scale=_lerp(from_style.core_scale, to_style.core_scale, blend),
    )

  def _star_twinkle(self, star: Star, index: int, t: float) -> float:
    """Return a twinkle factor with a tiny random sparkle component."""
    base = 0.50 + 0.50 * math.sin(t * 0.8 + star.phase)
    sparkle_seed = (
      int(t * 7.0) * 1315423911
      + index * 2654435761
      + int(star.phase * 1000.0)
    ) & 0xFFFFFFFF
    sparkle_noise = ((sparkle_seed >> 11) ^ sparkle_seed) & 0xFFFF
    sparkle_noise = sparkle_noise / 65535.0
    sparkle = max(0.0, (sparkle_noise - 0.992) * 30.0)
    return _clamp(base + sparkle, 0.18, 1.0)

  def _electron_colour(
    self,
    style: AtomStateStyle,
    front: bool,
    t: float,
  ) -> str:
    """Return a depth-adjusted particle colour."""
    depth_mix = 0.18 + (0.24 if front else 0.06)
    shimmer = 0.04 * math.sin(t * 5.9)
    return _mix_colour(
      "#d9fbff",
      style.particle,
      _clamp(depth_mix + shimmer, 0.0, 1.0),
    )


def _clamp(value: float, low: float, high: float) -> float:
  """Clamp a value into an inclusive range."""
  return max(low, min(high, value))


def _lerp(start: float, end: float, blend: float) -> float:
  """Linearly interpolate between two numeric values."""
  return start + (end - start) * blend


def _smoothstep(value: float) -> float:
  """Ease a normalised value with a smoothstep curve."""
  value = _clamp(value, 0.0, 1.0)
  return value * value * (3.0 - 2.0 * value)


def _hex_to_rgb(colour: str) -> tuple[int, int, int]:
  """Convert a ``#rrggbb`` colour into an RGB tuple."""
  value = colour.lstrip("#")
  return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
  """Convert an RGB tuple into a ``#rrggbb`` colour."""
  return "#{:02x}{:02x}{:02x}".format(
    *[int(_clamp(value, 0, 255)) for value in rgb]
  )


def _mix_colour(colour_a: str, colour_b: str, ratio: float) -> str:
  """Mix two colours by ratio."""
  ratio = _clamp(ratio, 0.0, 1.0)
  rgb_a = _hex_to_rgb(colour_a)
  rgb_b = _hex_to_rgb(colour_b)
  return _rgb_to_hex(
    tuple(
      round(a * (1.0 - ratio) + b * ratio)
      for a, b in zip(rgb_a, rgb_b)
    )
  )


def resolve_theme_path(theme_name: str) -> Path:
  """Resolve a CustomTkinter theme name to a JSON file.

  Args:
    theme_name: Theme name, with or without the ``.json`` extension.

  Returns:
    Path: Resolved theme file path.

  Raises:
    FileNotFoundError: If the named theme file does not exist.
  """
  clean_name = theme_name.strip()
  if not clean_name.lower().endswith(".json"):
    clean_name = f"{clean_name}.json"

  theme_path = THEMES_DIR / clean_name
  if not theme_path.is_file():
    raise FileNotFoundError(
      f"Theme file not found: {theme_path}. "
      f"Use a file from {THEMES_DIR}."
    )
  return theme_path


def configure_customtkinter(theme_name: str, theme_mode: str) -> bool:
  """Configure CustomTkinter when it is available.

  Args:
    theme_name: Theme file name with or without ``.json``.
    theme_mode: Appearance mode, ``dark`` or ``light``.

  Returns:
    bool: ``True`` when CustomTkinter will be used.
  """
  mode = theme_mode.strip().lower()
  if mode not in {"dark", "light"}:
    raise ValueError("--theme-mode must be 'dark' or 'light'.")

  if not _load_customtkinter():
    LOGGER.info("CustomTkinter not available; using standard Tkinter.")
    return False

  theme_path = resolve_theme_path(theme_name=theme_name)
  ctk.set_appearance_mode(mode)
  ctk.set_default_color_theme(str(theme_path))
  return True


def _load_customtkinter() -> bool:
  """Load CustomTkinter lazily to keep module import side-effect free."""
  global ctk
  global HAS_CUSTOMTKINTER

  if HAS_CUSTOMTKINTER:
    return True

  try:
    import customtkinter as loaded_customtkinter
  except Exception:  # pragma: no cover - optional dependency
    ctk = None
    HAS_CUSTOMTKINTER = False
    return False

  ctk = loaded_customtkinter
  HAS_CUSTOMTKINTER = True
  return True


def customtkinter_available() -> bool:
  """Return whether CustomTkinter can be imported."""
  return _load_customtkinter()


def _customtkinter_enabled(use_customtkinter: bool) -> bool:
  """Return whether CustomTkinter widgets should be used."""
  if not HAS_CUSTOMTKINTER:
    return False
  return use_customtkinter


def build_controls(
  parent: tk.Misc,
  display: OracAtomDisplay,
  use_customtkinter: bool,
) -> tk.Misc:
  """Build demo controls for manually changing display state."""
  if _customtkinter_enabled(use_customtkinter=use_customtkinter):
    controls = ctk.CTkFrame(parent, corner_radius=0)
    button_class = ctk.CTkButton
  else:
    controls = ttk.Frame(parent)
    button_class = ttk.Button

  controls.pack(side=tk.BOTTOM, fill=tk.X, padx=6, pady=(0, 6))
  state_bindings = [
    ("Idle", "idle"),
    ("Listening", "listening"),
    ("Cogitating", "cogitating"),
    ("Speaking", "speaking"),
    ("Error", "error"),
  ]

  for label, state in state_bindings:
    kwargs: dict[str, Any] = {
      "text": label,
      "command": lambda selected=state: display.set_state(selected),
    }
    if _customtkinter_enabled(use_customtkinter=use_customtkinter):
      kwargs["width"] = 82
      kwargs["height"] = 24
    button = button_class(controls, **kwargs)
    button.pack(side=tk.LEFT, padx=2, pady=2)

  return controls


def bind_keyboard_shortcuts(root: tk.Misc, display: OracAtomDisplay) -> None:
  """Bind the requested keyboard shortcuts to display states."""
  shortcuts = {
    "i": "idle",
    "l": "listening",
    "c": "cogitating",
    "s": "speaking",
    "e": "error",
  }
  for key, state in shortcuts.items():
    root.bind(
      key,
      lambda _event, selected=state: display.set_state(selected),
    )


def build_parser() -> argparse.ArgumentParser:
  """Create the command line argument parser."""
  parser = argparse.ArgumentParser(
    prog="orac-atom-display",
    description="Run the standalone ORAC ATOM DISPLAY prototype.",
  )
  parser.add_argument(
    "--theme",
    default=DEFAULT_THEME_NAME,
    help=(
      "CustomTkinter theme name from the themes directory. The .json "
      "extension is optional."
    ),
  )
  parser.add_argument(
    "--theme-mode",
    default=DEFAULT_THEME_MODE,
    help="Theme appearance mode: dark or light. Case insensitive.",
  )
  parser.add_argument(
    "--mode",
    choices=sorted(VALID_MODES),
    default=DisplayMode.KIOSK.value,
    help="Presentation mode: kiosk, dev, or compact.",
  )
  parser.add_argument(
    "--width",
    type=int,
    default=DEFAULT_WIDTH,
    help="Initial window width.",
  )
  parser.add_argument(
    "--height",
    type=int,
    default=DEFAULT_HEIGHT,
    help="Initial window height.",
  )
  parser.add_argument(
    "--fullscreen",
    "--kiosk",
    dest="fullscreen",
    action="store_true",
    help="Compatibility alias for kiosk mode.",
  )
  parser.add_argument(
    "--mute-overlay",
    action="store_true",
    help="Draw a subtle mute icon overlay in the corner.",
  )
  return parser


def create_root(use_customtkinter: bool) -> tk.Misc:
  """Create the root Tk window."""
  if _customtkinter_enabled(use_customtkinter=use_customtkinter):
    return ctk.CTk()
  return tk.Tk()


def _normalise_mode(args: argparse.Namespace) -> DisplayMode:
  """Resolve the requested presentation mode."""
  if args.fullscreen:
    return DisplayMode.KIOSK
  return DisplayMode(args.mode)


def _apply_window_mode(
  root: tk.Misc,
  mode: DisplayMode,
  width: int,
  height: int,
) -> tuple[int, int]:
  """Apply the selected window mode and return the active size."""
  if mode == DisplayMode.COMPACT:
    width = width if width != DEFAULT_WIDTH else DEFAULT_COMPACT_WIDTH
    height = height if height != DEFAULT_HEIGHT else DEFAULT_COMPACT_HEIGHT
    root.geometry(f"{width}x{height}")
    root.minsize(420, 320)
    root.resizable(True, True)
    return width, height

  root.geometry(f"{width}x{height}")
  root.minsize(720, 520)
  root.resizable(True, True)
  if mode == DisplayMode.KIOSK:
    root.attributes("-fullscreen", True)
  return width, height


def main() -> int:
  """Run the standalone demo harness."""
  logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
  parser = build_parser()
  args = parser.parse_args()
  mode = _normalise_mode(args)

  try:
    use_customtkinter = configure_customtkinter(
      theme_name=args.theme,
      theme_mode=args.theme_mode,
    )
  except (FileNotFoundError, ValueError) as exc:
    parser.error(str(exc))

  root = create_root(use_customtkinter=use_customtkinter)
  root.title("ORAC CORE")

  if not use_customtkinter:
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("TFrame", background="#050912")
    style.configure(
      "TButton",
      padding=(12, 7),
      background="#0e2435",
      foreground="#d8fbff",
    )

  width, height = _apply_window_mode(
    root=root,
    mode=mode,
    width=args.width,
    height=args.height,
  )

  display = OracAtomDisplay(parent=root, width=width, height=height)
  display.mute_overlay = args.mute_overlay

  if mode == DisplayMode.DEV:
    build_controls(
      parent=root,
      display=display,
      use_customtkinter=use_customtkinter,
    )
    bind_keyboard_shortcuts(root=root, display=display)
  elif mode == DisplayMode.KIOSK:
    root.bind("<Escape>", lambda _event: _close_window(root, display))

  root.protocol("WM_DELETE_WINDOW", lambda: _close_window(root, display))
  display.start()
  root.mainloop()
  return 0


def _close_window(root: tk.Misc, display: OracAtomDisplay) -> None:
  """Stop animation and close the demo window."""
  display.destroy()
  root.destroy()


if __name__ == "__main__":
  raise SystemExit(main())
