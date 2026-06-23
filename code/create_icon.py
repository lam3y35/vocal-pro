"""Generate VocalPro desktop icon (.ico) with the app's dark + purple theme."""

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os

def create_icon(output_path: str = "vocalpro.ico") -> None:
    """Create a multi-size .ico file with a cool music/vocal-themed design."""
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = []

    for size in sizes:
        img = _draw_icon(size)
        images.append(img)

    # Save as .ico (use largest as the base, embed all sizes)
    images[-1].save(
        output_path,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[:-1],
    )
    print(f"Icon saved: {output_path}")


def _draw_icon(size: int) -> Image.Image:
    """Draw a professional, 'cool' icon: deep gradient background with neon wave."""
    # ── Colors ──
    # Deep gradient colors
    BG_TOP = (20, 20, 35)      # Deep midnight
    BG_BOT = (10, 10, 20)      # Near black
    
    # Neon colors
    NEON_PURPLE = (168, 85, 247)   # Vibrant purple
    NEON_BLUE   = (59, 130, 246)   # Electric blue
    WHITE       = (255, 255, 255)
    
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # ── Gradient Rounded Rect ──
    pad = max(1, size // 24)
    r = max(4, size // 4)
    
    # Create background mask
    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([pad, pad, size - pad, size - pad], radius=r, fill=255)
    
    # Draw gradient
    for y in range(size):
        ratio = y / size
        r_val = int(BG_TOP[0] * (1 - ratio) + BG_BOT[0] * ratio)
        g_val = int(BG_TOP[1] * (1 - ratio) + BG_BOT[1] * ratio)
        b_val = int(BG_TOP[2] * (1 - ratio) + BG_BOT[2] * ratio)
        draw.line([(0, y), (size, y)], fill=(r_val, g_val, b_val, 255))
    
    # Apply rounded corner mask
    img.putalpha(mask)
    
    # ── Subtle Outer Glow / Border ──
    draw.rounded_rectangle([pad, pad, size - pad, size - pad], radius=r, outline=NEON_PURPLE + (100,), width=max(1, size // 64))

    # ── Neon Sound Wave ──
    cx, cy = size // 2, size // 2
    wave_w = int(size * 0.65)
    wave_h = int(size * 0.4)
    
    num_bars = 9 if size >= 32 else 5
    bar_gap = max(1, int(wave_w / (num_bars * 2.5)))
    bar_width = max(1, (wave_w - bar_gap * (num_bars - 1)) // num_bars)
    start_x = cx - (bar_width * num_bars + bar_gap * (num_bars - 1)) // 2
    
    # Symmetric wave pattern
    heights = [0.3, 0.5, 0.8, 1.0, 0.8, 0.5, 0.3]
    if num_bars == 9:
        heights = [0.2, 0.4, 0.7, 0.9, 1.0, 0.9, 0.7, 0.4, 0.2]
    elif num_bars == 5:
        heights = [0.4, 0.8, 1.0, 0.8, 0.4]

    for i, h in enumerate(heights):
        x = start_x + i * (bar_width + bar_gap)
        bh = int(wave_h * h)
        y1 = cy - bh // 2
        y2 = cy + bh // 2
        
        # Color gradient for the bar (Purple to Blue)
        ratio = i / (num_bars - 1)
        br = int(NEON_PURPLE[0] * (1 - ratio) + NEON_BLUE[0] * ratio)
        bg = int(NEON_PURPLE[1] * (1 - ratio) + NEON_BLUE[1] * ratio)
        bb = int(NEON_PURPLE[2] * (1 - ratio) + NEON_BLUE[2] * ratio)
        
        # Draw the bar with rounded ends
        draw.rounded_rectangle([x, y1, x + bar_width, y2], radius=bar_width // 2, fill=(br, bg, bb, 255))
        
        # Top-glow spot
        if size >= 64:
            glow_size = max(1, bar_width // 2)
            draw.ellipse([x, y1 - glow_size, x + bar_width, y1 + glow_size], fill=WHITE + (150,))

    # ── Central Neon Pulse ──
    if size >= 48:
        pulse_r = int(size * 0.35)
        # Create a separate layer for the blur/glow
        glow_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow_layer)
        glow_draw.ellipse([cx - pulse_r, cy - pulse_r, cx + pulse_r, cy + pulse_r], outline=NEON_PURPLE + (50,), width=max(1, size // 32))
        img = Image.alpha_composite(img, glow_layer)

    # ── "VocalPro" Text (Large only) ──
    if size >= 128:
        try:
            # Try to find a bold modern font
            font = ImageFont.truetype("arialbd.ttf", size // 8)
        except Exception:
            font = ImageFont.load_default()
            
        txt = "VOCALPRO"
        bbox = draw.textbbox((0, 0), txt, font=font)
        tw = bbox[2] - bbox[0]
        draw.text((cx - tw // 2, int(size * 0.78)), txt, fill=WHITE + (200,), font=font)

    return img


if __name__ == "__main__":
    create_icon(os.path.join(os.path.dirname(os.path.abspath(__file__)), "vocalpro.ico"))
