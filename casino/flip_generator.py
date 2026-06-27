import asyncio
import io
import math
from typing import Literal, Tuple

import aiohttp
from PIL import Image, ImageDraw, ImageOps

from casino.util import fetch_image


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
    total_ms: int,
    frame_ms: int,
    front_label: Literal["H", "T"] | None,
    back_label: Literal["H", "T"] | None,
    result: Literal["front", "back"] = "front",
) -> io.BytesIO:
    front = _to_circle(front, size, front_label)
    back = _to_circle(back, size, back_label)

    frames = max(2, total_ms // frame_ms)

    # Rotations scaled to duration: ~3 per second feels natural
    rotations = max(1, round(total_ms / 1000 * 3))

    def eased_angle(t: float) -> float:
        """t in [0, 1] -> angle in radians, cubic ease-out deceleration."""
        ease = 1 - (1 - t) ** 3
        return ease * (rotations * 2 * math.pi)

    angles = [eased_angle(i / (frames - 1)) for i in range(frames)]

    # Offset by pi so the back face is forward at t=1
    if result == "back":
        angles = [a + math.pi for a in angles]

    gif_frames = [_render_flip_frame(front, back, a, size) for a in angles]

    # Hold the final frame for 1s
    hold_frames = max(1, 1000 // frame_ms)
    gif_frames = gif_frames + [gif_frames[-1]] * hold_frames
    durations = [frame_ms] * (len(gif_frames) - hold_frames) + [frame_ms] * hold_frames
    # Encode the hold as a single long-duration frame to keep file size down
    durations[-hold_frames] = frame_ms * hold_frames
    gif_frames = gif_frames[: len(gif_frames) - hold_frames + 1]
    durations = durations[: len(gif_frames)]

    output = io.BytesIO()
    gif_frames[0].save(
        output,
        format="GIF",
        save_all=True,
        append_images=gif_frames[1:],
        duration=durations,
        loop=1,
        disposal=2,
    )
    output.seek(0)
    return output


async def create_coinflip_gif(
    front_url: str,
    back_url: str,
    *,
    front_label: Literal["H", "T"] | None = None,
    back_label: Literal["H", "T"] | None = None,
    result: Literal["front", "back"] = "front",
    size: int = 128,
    total_ms: int = 2000,
    frame_ms: int = 40,
) -> io.BytesIO:
    """
    Download two images, mask them as circles, animate a coin flip between them,
    and return an endlessly looping GIF that decelerates and lands on a given side.

    Args:
        front_url:   URL of the heads-side image.
        back_url:    URL of the tails-side image.
        front_label: Optional "H" or "T" drawn over the front face.
        back_label:  Optional "H" or "T" drawn over the back face.
        result:      Which face to land on — "front" or "back".
        size:        Output GIF dimensions in pixels (square).
        total_ms:    Total animation duration in milliseconds (default 2000).
        frame_ms:    Duration of each frame in milliseconds (default 40 = 25 fps).
    """
    timeout = aiohttp.ClientTimeout(total=15)
    headers = {"User-Agent": "sail-credit/1.0"}

    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        front, back = await asyncio.gather(
            fetch_image(session, front_url),
            fetch_image(session, back_url),
        )

    return await asyncio.to_thread(
        _build_gif,
        front,
        back,
        size=size,
        total_ms=total_ms,
        frame_ms=frame_ms,
        front_label=front_label,
        back_label=back_label,
        result=result,
    )
