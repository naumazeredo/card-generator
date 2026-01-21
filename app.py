from flask import Flask, request, send_file, abort
from PIL import Image, ImageDraw, ImageFont
import io

app = Flask(__name__)

# Standard poker card size (mm)
POKER_WIDTH = 63
POKER_HEIGHT = 88

DEFAULT_DPI = 300
DEFAULT_MARGIN = 5     # mm
DEFAULT_BLEED = 3      # mm
MIN_FONT_SIZE = 10     # px
TITLE_BODY_GAP = 4     # px vertical spacing

def mm_to_px(mm, dpi=DEFAULT_DPI):
    return int((mm / 25.4) * dpi)

def load_font(size):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except IOError:
        return ImageFont.load_default()

def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines = []
    current = ""

    for word in words:
        test = current + (" " if current else "") + word
        if draw.textlength(test, font=font) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines

@app.route("/card")
def render_card():
    text = request.args.get("text")
    title = request.args.get("title")
    size = request.args.get("size")
    margin = request.args.get("margin", type=float, default=DEFAULT_MARGIN)
    bleed = request.args.get("bleed", type=float, default=DEFAULT_BLEED)
    font_size = request.args.get("font_size", type=int)
    title_size = request.args.get("title_size", type=int)

    if not text and not title:
        abort(400, "At least one of 'text' or 'title' is required")

    # Parse card size (mm)
    if size:
        try:
            width, height = map(float, size.lower().split("x"))
        except ValueError:
            abort(400, 'Invalid size format. Use "<width>x<height>"')
    else:
        width = POKER_WIDTH
        height = POKER_HEIGHT

    # Convert to pixels
    card_w_px = mm_to_px(width)
    card_h_px = mm_to_px(height)
    bleed_px = mm_to_px(bleed)
    margin_px = mm_to_px(margin)

    img_w = card_w_px + bleed_px * 2
    img_h = card_h_px + bleed_px * 2

    # Create image
    img = Image.new("RGB", (img_w, img_h), "#eeeeee")
    draw = ImageDraw.Draw(img)

    # Card background
    card_x0 = bleed_px
    card_y0 = bleed_px
    card_x1 = card_x0 + card_w_px
    card_y1 = card_y0 + card_h_px

    draw.rectangle([card_x0, card_y0, card_x1, card_y1], fill="white")

    # Safe area
    safe_x0 = card_x0 + margin_px
    safe_y0 = card_y0 + margin_px
    safe_x1 = card_x1 - margin_px
    safe_y1 = card_y1 - margin_px

    safe_width = safe_x1 - safe_x0
    current_y = safe_y0

    # -------- TITLE --------
    if title:
        if title_size:
            title_font = load_font(title_size)
        else:
            # Auto-scale title to fit one line
            test_size = int(safe_width * 0.15)
            while test_size > MIN_FONT_SIZE:
                title_font = load_font(test_size)
                if draw.textlength(title, font=title_font) <= safe_width:
                    break
                test_size -= 2

        title_lines = wrap_text(draw, title, title_font, safe_width)
        title_line_height = title_font.getbbox("Ay")[3]

        for line in title_lines:
            draw.text(
                (safe_x0, current_y),
                line,
                fill="black",
                font=title_font
            )
            current_y += title_line_height

        current_y += TITLE_BODY_GAP

    # -------- BODY TEXT --------
    remaining_height = safe_y1 - current_y

    if text:
        if font_size:
            body_font = load_font(font_size)
            body_lines = wrap_text(draw, text, body_font, safe_width)
            line_height = body_font.getbbox("Ay")[3]
            total_height = line_height * len(body_lines)
        else:
            # Auto-scale body text
            font_size_auto = int(remaining_height * 0.25)
            while font_size_auto > MIN_FONT_SIZE:
                body_font = load_font(font_size_auto)
                body_lines = wrap_text(draw, text, body_font, safe_width)
                line_height = body_font.getbbox("Ay")[3]
                total_height = line_height * len(body_lines)

                if total_height <= remaining_height:
                    break

                font_size_auto -= 2

        # Vertical centering in remaining space
        y = current_y + (remaining_height - total_height) // 2

        for line in body_lines:
            line_width = draw.textlength(line, font=body_font)
            x = safe_x0 + (safe_width - line_width) // 2
            draw.text((x, y), line, fill="black", font=body_font)
            y += line_height

    # Output image
    img_io = io.BytesIO()
    img.save(img_io, "PNG")
    img_io.seek(0)

    return send_file(img_io, mimetype="image/png")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
