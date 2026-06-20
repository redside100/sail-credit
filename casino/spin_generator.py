import asyncio
import io
import random
from dataclasses import dataclass
from typing import List, Optional

import aiohttp
from PIL import Image, ImageDraw, ImageOps


# ── Types ────────────────────────────────────────────────────────────────────


@dataclass
class Player:
    url: str
    weight: float  # percentage, e.g. 60.0 for 60%
    image: Optional[Image.Image] = None


# ── Image fetching ────────────────────────────────────────────────────────────


async def _fetch_image(session: aiohttp.ClientSession, url: str) -> Image.Image:
    async with session.get(url) as response:
        response.raise_for_status()
        content = await response.read()
    return Image.open(io.BytesIO(content)).convert("RGBA")


# ── Avatar helpers ────────────────────────────────────────────────────────────


def _prepare_avatar(img: Image.Image, size: int) -> Image.Image:
    return ImageOps.fit(img, (size, size), centering=(0.5, 0.5)).convert("RGBA")


def _draw_avatar_tile(img: Image.Image, tile_w: int) -> Image.Image:
    size = img.height
    tile = Image.new("RGBA", (tile_w, size), (0, 0, 0, 255))
    x = (tile_w - size) // 2
    tile.paste(img, (x, 0))
    return tile


# ── Strip builder ─────────────────────────────────────────────────────────────


def _build_strip(
    players: List[Player],
    avatar_size: int,
    tile_w: int,
    total_distance: int,
    marker_x: int,
    winner_idx: int,
) -> tuple[Image.Image, int]:
    """
    Build a strip long enough to cover total_distance, ending with the
    winner tile centered at marker_x.

    Returns (strip_image, final_offset) where final_offset is the scroll
    position that places the winner under the marker.
    """
    total_weight = sum(p.weight for p in players)
    slots: List[int] = []
    for i, p in enumerate(players):
        count = max(1, round(p.weight / total_weight * 100))
        slots.extend([i] * count)

    def shuffled_cycle() -> List[int]:
        c = slots.copy()
        random.shuffle(c)
        return c

    # Build tile sequence from shuffled cycles until we have a winner tile
    # beyond total_distance + marker_x
    min_end_pixel = total_distance + marker_x
    tile_sequence: List[int] = []

    while True:
        tile_sequence.extend(shuffled_cycle())
        candidates = [
            (i, tile_w * i + tile_w // 2)
            for i, s in enumerate(tile_sequence)
            if s == winner_idx and tile_w * i + tile_w // 2 > min_end_pixel
        ]
        if candidates:
            winner_tile_i, winner_center_x = candidates[0]
            break

    final_offset = winner_center_x - marker_x

    # Build the image up to winner_tile_i + a few extra tiles for safety
    visible_tiles = winner_tile_i + 8
    tile_sequence = tile_sequence[:visible_tiles]

    strip_w = len(tile_sequence) * tile_w
    strip = Image.new("RGBA", (strip_w, avatar_size), (0, 0, 0, 0))

    for i, pidx in enumerate(tile_sequence):
        x = i * tile_w
        tile = _draw_avatar_tile(players[pidx].image, tile_w)
        strip.paste(tile, (x, 0))

    return strip, final_offset


# ── Frame renderer ────────────────────────────────────────────────────────────


def _render_frame(
    strip: Image.Image,
    offset: int,
    canvas_w: int,
    avatar_size: int,
    marker_x: int,
    marker_color: tuple = (255, 215, 0, 255),
    marker_thickness: int = 3,
) -> Image.Image:
    frame = Image.new("RGBA", (canvas_w, avatar_size), (0, 0, 0, 0))

    strip_w = strip.width
    x_in_strip = max(0, min(offset, strip_w - 1))
    visible_end = x_in_strip + canvas_w

    if visible_end <= strip_w:
        region = strip.crop((x_in_strip, 0, visible_end, avatar_size))
        frame.paste(region, (0, 0))
    else:
        part1 = strip.crop((x_in_strip, 0, strip_w, avatar_size))
        frame.paste(part1, (0, 0))

    draw = ImageDraw.Draw(frame)
    for dx in range(-marker_thickness // 2, marker_thickness // 2 + 1):
        x = marker_x + dx
        draw.line([(x, 0), (x, avatar_size)], fill=marker_color)

    return frame


# ── GIF assembler ─────────────────────────────────────────────────────────────


def _build_gif(
    players: List[Player],
    winner_idx: int,
    *,
    avatar_size: int,
    tile_w: int,
    canvas_w: int,
    total_ms: int,
    frame_ms: int,
    hold_ms: int,
) -> io.BytesIO:
    for p in players:
        p.image = _prepare_avatar(p.image, avatar_size)

    marker_x = canvas_w // 2
    frames = max(2, total_ms // frame_ms)

    total_distance = int((total_ms / 1000) * 800 * tile_w / 112)

    strip, final_offset = _build_strip(
        players,
        avatar_size,
        tile_w,
        total_distance,
        marker_x,
        winner_idx,
    )

    # Two-phase animation:
    # Phase 1 (0 to split): constant full speed
    # Phase 2 (split to 1): ease-out deceleration into the winner
    split = 0.35  # 35% of frames at full speed, 65% decelerating
    decel_fraction = 0.15  # decel phase only covers the last 15% of distance

    def ease_out(t: float) -> float:
        return 1 - (1 - t) ** 3

    def offset_at(i: int) -> int:
        t = i / (frames - 1)
        decel_distance = int(final_offset * decel_fraction)
        cruise_end = final_offset - decel_distance
        if t <= split:
            return int((t / split) * cruise_end)
        else:
            t2 = (t - split) / (1 - split)
            return int(cruise_end + ease_out(t2) * decel_distance)

    offsets = [offset_at(i) for i in range(frames)]

    gif_frames = [
        _render_frame(strip, off, canvas_w, avatar_size, marker_x) for off in offsets
    ]

    # Hold the final frame
    durations = [frame_ms] * len(gif_frames) + [hold_ms]
    gif_frames.append(gif_frames[-1])

    output = io.BytesIO()
    gif_frames[0].save(
        output,
        format="GIF",
        save_all=True,
        append_images=gif_frames[1:],
        duration=durations,
        loop=0,  # play once
        disposal=2,
    )
    output.seek(0)
    return output


# ── Public API ────────────────────────────────────────────────────────────────


async def create_jackpot_gif(
    players: List[Player],
    winner_url: str,
    *,
    avatar_size: int = 96,
    tile_w: int = 96,
    canvas_tiles: int = 7,
    total_ms: int = 4000,
    frame_ms: int = 40,
    hold_ms: int = 2000,
) -> io.BytesIO:
    """
    Animate a CSGO-style horizontal jackpot reel and return a GIF.

    Args:
        players:      List of Player(url, weight) — weights are relative percentages.
        winner_url:   The URL of the winning player's avatar (must match one in players).
        avatar_size:  Size of each avatar in pixels (square).
        tile_w:       Width of each tile — set equal to avatar_size for no gaps/bars.
        canvas_tiles: Number of tiles visible at once (odd number looks best).
        total_ms:     Spin duration in milliseconds.
        frame_ms:     Duration of each frame in ms (~40 = 25 fps).
        hold_ms:      How long to freeze on the winner after landing.
    """
    winner_idx = next((i for i, p in enumerate(players) if p.url == winner_url), 0)

    timeout = aiohttp.ClientTimeout(total=15)
    headers = {"User-Agent": "sail-credit/1.0"}

    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        images = await asyncio.gather(*[_fetch_image(session, p.url) for p in players])

    for player, image in zip(players, images):
        player.image = image

    canvas_w = canvas_tiles * tile_w

    return await asyncio.to_thread(
        _build_gif,
        players,
        winner_idx,
        avatar_size=avatar_size,
        tile_w=tile_w,
        canvas_w=canvas_w,
        total_ms=total_ms,
        frame_ms=frame_ms,
        hold_ms=hold_ms,
    )
