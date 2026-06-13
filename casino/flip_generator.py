import asyncio
import io
import math
from typing import Literal, Tuple

import aiohttp
from PIL import Image, ImageDraw, ImageOps
import discord


async def _fetch_image(session: aiohttp.ClientSession, url: str) -> Image.Image:
    async with session.get(url) as response:
        response.raise_for_status()
        content = await response.read()
    return Image.open(io.BytesIO(content)).convert("RGBA")


def _to_circle(
    img: Image.Image,
    size: int,
    label: Literal["H", "T"] | None = None,
) -> Image.Image:
    img = ImageOps.fit(img, (size, size), centering=(0.5, 0.5))
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size - 1, size - 1), fill=255)
    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(img, (0, 0), mask)

    if label:
        overlay = ImageDraw.Draw(result)
        font_size = size // 2
        cx, cy = size // 2, size // 2
        # Drop shadow for legibility
        for dx, dy in ((-2, -2), (2, -2), (-2, 2), (2, 2)):
            overlay.text(
                (cx + dx, cy + dy),
                label,
                fill=(0, 0, 0, 180),
                anchor="mm",
                font_size=font_size,
            )
        overlay.text(
            (cx, cy),
            label,
            fill=(255, 215, 0, 230),
            anchor="mm",
            font_size=font_size,
        )

    return result


def _render_flip_frame(
    front: Image.Image,
    back: Image.Image,
    angle: float,
    size: int,
    edge_color: Tuple[int, int, int, int] = (255, 215, 0, 255),
) -> Image.Image:
    cos_a = math.cos(angle)
    width_factor = abs(cos_a)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    if width_factor < 0.08:
        edge_width = max(2, size // 16)
        edge = Image.new("RGBA", (edge_width, size), edge_color)
        mask = Image.new("L", (edge_width, size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, edge_width - 1, size - 1), fill=255)
        edge.putalpha(mask)
        canvas.paste(edge, ((size - edge_width) // 2, 0), edge)
        return canvas

    face = front if cos_a >= 0 else back
    scaled_w = max(1, int(size * width_factor))
    scaled = face.resize((scaled_w, size), Image.Resampling.LANCZOS)
    canvas.paste(scaled, ((size - scaled_w) // 2, 0), scaled)
    return canvas


def _build_gif(
    front: Image.Image,
    back: Image.Image,
    *,
    size: int,
    frames: int,
    duration_ms: int,
    front_label: Literal["H", "T"] | None,
    back_label: Literal["H", "T"] | None,
) -> bytes:
    front = _to_circle(front, size, front_label)
    back = _to_circle(back, size, back_label)

    gif_frames = [
        _render_flip_frame(front, back, (2 * math.pi * i) / frames, size)
        for i in range(frames)
    ]

    output = io.BytesIO()
    gif_frames[0].save(
        output,
        format="GIF",
        save_all=True,
        append_images=gif_frames[1:],
        duration=duration_ms,
        loop=0,
        disposal=2,
    )
    return output.getvalue()


async def create_coinflip_gif(
    front_url: str,
    back_url: str,
    *,
    front_label: Literal["H", "T"] | None = None,
    back_label: Literal["H", "T"] | None = None,
    size: int = 256,
    frames: int = 30,
    duration_ms: int = 20,
) -> bytes:
    """
    Download two images, mask them as circles, animate a coin flip between them,
    and return an endlessly looping GIF.

    Args:
        front_url:    URL of the heads-side image.
        back_url:     URL of the tails-side image.
        front_label:  Optional "H" or "T" drawn over the front face.
        back_label:   Optional "H" or "T" drawn over the back face.
        size:         Output GIF dimensions in pixels (square).
        frames:       Number of animation frames per full rotation.
        duration_ms:  Delay between frames in milliseconds.
    """
    timeout = aiohttp.ClientTimeout(total=15)
    headers = {"User-Agent": "sail-credit/1.0"}

    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        front, back = await asyncio.gather(
            _fetch_image(session, front_url),
            _fetch_image(session, back_url),
        )

    return await asyncio.to_thread(
        _build_gif,
        front,
        back,
        size=size,
        frames=frames,
        duration_ms=duration_ms,
        front_label=front_label,
        back_label=back_label,
    )
