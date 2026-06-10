import math
from typing import List

# Configuration
COLS, ROWS = 40, 20
W, H = COLS * 2, ROWS * 4
B = 0x2800


def render_dynamic_crash(current_return: float) -> list[str]:
    buf = [0.0] * (W * H)
    y_min, y_max = 1.0, max(2.0, current_return)

    # 1. Determine horizontal limit:
    # 1.5x is 50%, 2.0x is 100%.
    # Formula: (return - 1.0) / (2.0 - 1.0)
    draw_percentage = max(0.0, min(1.0, (current_return - 1.0) / (2.0 - 1.0)))
    max_px = int(W * draw_percentage)

    # 2. Dynamic growth rate 'k'
    # We want val(t=1.0) = current_return.
    # If val = exp(k*t), then k = log(current_return).
    k = math.log(current_return)

    for px in range(max_px):
        t = px / (W - 1)
        # Growth curve that scales with current_return
        val = math.exp(k * t)

        norm_y = (val - y_min) / (y_max - y_min)
        y_center = (1.0 - norm_y) * (H - 1)

        # Anti-aliased line drawing (standard)
        y0, y1 = int(math.floor(y_center - 1.0)), int(math.ceil(y_center + 1.0))
        for py in range(max(0, y0), min(H - 1, y1) + 1):
            dist = abs(py + 0.5 - y_center)
            intensity = max(0.0, 1.0 - dist)
            if intensity > 0:
                idx = py * W + px
                buf[idx] = max(buf[idx], intensity)

    # Quantize and Label
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

        # Consistent label mapping
        y_label = y_max - (row / (ROWS - 1)) * (y_max - y_min)
        out.append(f"{y_label:>5.1f}x ┤{line}")

    out.append(" " * 7 + "\u2514" + "\u2500" * W)
    return out

def render_graph(current_return: float) -> str:
    graph = render_dynamic_crash(current_return)
    x_0 = math.floor(COLS * 1 / 4)
    y_0 = math.floor(ROWS * 1 / 4)

    display_return = "🚀 " + format(round(current_return, 3), ".2f") + "x"

    graph[y_0] = (
        graph[y_0][:x_0] + display_return + graph[y_0][x_0 + len(display_return) :]
    )

    return "\n".join(graph)
    
# Simulation loop
def run_simulation(crash: float = 100.0):
    # Demonstrating the graph starting from 1.0 upwards. i = 0.01x
    for i in range(10000):
        current_return = 1.0 + (i * 0.01)
        graph = render_dynamic_crash(current_return)

        x_0 = math.floor(COLS * 1 / 4)
        y_0 = math.floor(ROWS * 1 / 4)

        display_return = "🚀 " + format(round(current_return, 3), ".2f") + "x"

        graph[y_0] = (
            graph[y_0][:x_0] + display_return + graph[y_0][x_0 + len(display_return) :]
        )

        print("\n".join(graph))

        print(f"Current Return: {current_return:.2f}x\n")
        import time

        if current_return == crash:
            break

        delay = 0.05 - min(0.049, 0.04 * 2 * i / 1000)
        # print(f"delay: {delay}")
        time.sleep(delay)
        # break


if __name__ == "__main__":
    run_simulation(crash=40.0)
