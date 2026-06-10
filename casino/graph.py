import math

# Configuration
COLS, ROWS = 40, 20
W, H = COLS * 2, ROWS * 4
B = 0x2800


def get_y_ticks(y_min: float, y_max: float) -> list[float]:
    """Return the tick values to label on the Y axis."""
    span = y_max - y_min

    if y_max < 2.0:
        return [1.0, 1.5, 2.0]
    if y_max < 5.0:
        return [float(v) for v in range(1, math.ceil(y_max) + 1)]

    # Pick a step size that gives roughly 4–8 ticks
    raw_step = span / 6
    magnitude = 10 ** math.floor(math.log10(raw_step))
    for factor in [1, 2, 5, 10]:
        step = magnitude * factor
        if span / step <= 8:
            break

    lo = math.ceil(y_min / step) * step
    ticks = []
    v = lo
    while v <= y_max + step * 0.01:
        ticks.append(round(v, 10))
        v += step
    return ticks


def format_label(value: float) -> str:
    """Format a tick value: use .1f for values < 10, else int."""
    if value < 10:
        return f"{value:>5.1f}x"
    return f"{int(round(value)):>5d}x"


def render_dynamic_crash(current_return: float) -> list[str]:
    buf = [0.0] * (W * H)
    y_min, y_max = 1.0, max(2.0, current_return)

    # 1. Determine horizontal limit
    draw_percentage = max(0.0, min(1.0, (current_return - 1.0) / (2.0 - 1.0)))
    max_px = int(W * draw_percentage)

    # 2. Dynamic growth rate k so that exp(k*1) == current_return
    k = math.log(current_return)

    for px in range(max_px):
        t = px / (W - 1)
        val = math.exp(k * t)

        norm_y = (val - y_min) / (y_max - y_min)
        y_center = (1.0 - norm_y) * (H - 1)

        y0 = int(math.floor(y_center - 1.0))
        y1 = int(math.ceil(y_center + 1.0))
        for py in range(max(0, y0), min(H - 1, y1) + 1):
            dist = abs(py + 0.5 - y_center)
            intensity = max(0.0, 1.0 - dist)
            if intensity > 0:
                idx = py * W + px
                buf[idx] = max(buf[idx], intensity)

    # Build tick lookup: map each row to a label string (or None)
    ticks = get_y_ticks(y_min, y_max)

    # For each row, compute the y value and check if it snaps to a tick
    row_labels: list[str | None] = []
    for row in range(ROWS):
        y_val = y_max - (row / (ROWS - 1)) * (y_max - y_min)
        # Find the closest tick and see if this row is close enough to show it
        closest = min(ticks, key=lambda t: abs(t - y_val))
        pixel_span = y_max - y_min  # value units across full height
        row_height_in_values = pixel_span / (ROWS - 1)
        if abs(closest - y_val) <= row_height_in_values * 0.5:
            row_labels.append(format_label(closest))
        else:
            row_labels.append(None)

    # Quantize and render
    out = []
    for row in range(ROWS):
        line = ""
        for col in range(COLS):
            bits = 0
            for dc, dr, bit in [
                (0, 0, 0x01),
                (0, 1, 0x02),
                (0, 2, 0x04),
                (0, 3, 0x40),
                (1, 0, 0x08),
                (1, 1, 0x10),
                (1, 2, 0x20),
                (1, 3, 0x80),
            ]:
                px, py = col * 2 + dc, row * 4 + dr
                if px < W and py < H and buf[py * W + px] > 0.35:
                    bits |= bit
            line += chr(B | bits)

        label = row_labels[row]
        if label is not None:
            out.append(f"{label} ┤{line}")
        else:
            out.append(f"{'':>6s} │{line}")  # blank but same width

    out.append(" " * 7 + "\u2514" + "\u2500" * (COLS + 10))
    return out


def render_graph(current_return: float, crashed: bool) -> str:
    graph = render_dynamic_crash(current_return)
    x_0 = math.floor(COLS * 1 / 4)
    y_0 = math.floor(ROWS * 1 / 4)

    emoji = "🚀"
    if crashed:
        emoji = "🪦"

    display_return = emoji + " " + format(round(current_return, 3), ".2f") + "x"

    graph[y_0] = (
        graph[y_0][:x_0] + display_return + graph[y_0][x_0 + len(display_return) :]
    )

    return "\n".join(graph)


# Simulation loop
def run_simulation(crash: float = 100.0):
    for i in range(10000):
        current_return = 1.0 + (i * 0.01)
        graph = render_dynamic_crash(current_return)

        x_0 = max(10, math.floor(COLS * 1 / 4))
        y_0 = math.floor(ROWS * 1 / 4)

        emoji = "🚀"
        if crash == current_return:
            emoji = "🪦"

        display_return = emoji + " " + format(round(current_return, 3), ".2f") + "x"
        graph[y_0] = (
            graph[y_0][:x_0] + display_return + graph[y_0][x_0 + len(display_return) :]
        )

        print(chr(27) + "[2J")
        print("\n".join(graph))

        import time

        if current_return == crash:
            break

        delay = 0.05 - min(0.049, 0.04 * 2 * i / 1000)
        time.sleep(delay)


if __name__ == "__main__":
    run_simulation(crash=4.2)
