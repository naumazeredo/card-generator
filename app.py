from flask import Flask, request, send_file, abort
from PIL import Image, ImageDraw, ImageFont
import io
import re

app = Flask(__name__)

# --- Card defaults (mm) ---
POKER_WIDTH = 63
POKER_HEIGHT = 88

DEFAULT_DPI = 300
DEFAULT_MARGIN = 5
DEFAULT_BLEED = 3

# --- Typography defaults ---
DEFAULT_BODY_FONT_SIZE = 24   # px – realistic card text
MIN_FONT_SIZE = 10
TITLE_BODY_GAP = 4

def mm_to_px(mm, dpi=DEFAULT_DPI):
    return int((mm / 25.4) * dpi)

def load_font(size, bold=False, italic=False):
    try:
        if bold and italic:
            return ImageFont.truetype("arialbi.ttf", size)
        if bold:
            return ImageFont.truetype("arialbd.ttf", size)
        if italic:
            return ImageFont.truetype("ariali.ttf", size)
        return ImageFont.truetype("arial.ttf", size)
    except IOError:
        return ImageFont.load_default()

# ---------- Markdown parsing (body only) ----------

MD_PATTERN = re.compile(r'(\*\*.*?\*\*|__.*?__|\*.*?\*|_.*?_)')

def parse_markdown(text):
    spans = []
    for part in MD_PATTERN.split(text):
        if not part:
            continue
        if part.startswith(("**", "__")):
            spans.append((part[2:-2], {"bold": True}))
        elif part.startswith(("*", "_")):
            spans.append((part[1:-1], {"italic": True}))
        else:
            spans.append((part, {}))
    return spans

def wrap_plain(draw, text, font, max_width):
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

def wrap_markdown(draw, spans, max_width, font_size):
    lines = []
    current_line = []
    current_width = 0

    for text, style in spans:
        words = text.split(" ")
        for i, word in enumerate(words):
            chunk = word + (" " if i < len(words) - 1 else "")
            font = load_font(font_size, **style)
            w = draw.textlength(chunk, font=font)

            if current_width + w <= max_width:
                current_line.append((chunk, style))
                current_width += w
            else:
                lines.append(current_line)
                current_line = [(chunk, style)]
                current_width = w

    if current_line:
        lines.append(current_line)

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
    auto_format = request.args.get("auto_format", default="false").lower() == "true"

    if not text and not title:
        abort(400, "At least one of 'text' or 'title' is required")

    # --- Card size ---
    if size:
        try:
            width, height = map(float, size.lower().split("x"))
        except ValueError:
            abort(400, 'Invalid size format. Use "<width>x<height>"')
    else:
        width, height = POKER_WIDTH, POKER_HEIGHT

    # --- Pixel conversion ---
    card_w = mm_to_px(width)
    card_h = mm_to_px(height)
    bleed_px = mm_to_px(bleed)
    margin_px = mm_to_px(margin)

    img = Image.new(
        "RGB",
        (card_w + bleed_px * 2, card_h + bleed_px * 2),
        "#eeeeee"
    )
    draw = ImageDraw.Draw(img)

    # Card background
    cx0, cy0 = bleed_px, bleed_px
    cx1, cy1 = cx0 + card_w, cy0 + card_h
    draw.rectangle([cx0, cy0, cx1, cy1], fill="white")

    # Safe area
    sx0 = cx0 + margin_px
    sy0 = cy0 + margin_px
    sx1 = cx1 - margin_px
    sy1 = cy1 - margin_px
    safe_width = sx1 - sx0
    current_y = sy0

    # ---------- TITLE (WRAPS BY DEFAULT) ----------
    if title:
        if title_size:
            size_try = title_size
        else:
            size_try = int(safe_width * 0.18)

        while size_try > MIN_FONT_SIZE:
            title_font = load_font(size_try, bold=True)
            title_lines = wrap_plain(draw, title, title_font, safe_width)
            title_height = len(title_lines) * title_font.getbbox("Ay")[3]

            # allow reasonable title block height
            if title_height <= (sy1 - sy0) * 0.3 or title_size:
                break

            size_try -= 2

        line_height = title_font.getbbox("Ay")[3]
        for line in title_lines:
            draw.text((sx0, current_y), line, fill="black", font=title_font)
            current_y += line_height

        current_y += TITLE_BODY_GAP

    # ---------- BODY TEXT ----------
    if text:
        spans = parse_markdown(text)
        remaining_height = sy1 - current_y

        if font_size:
            body_size = font_size
        elif auto_format:
            body_size = int(remaining_height * 0.22)
        else:
            body_size = DEFAULT_BODY_FONT_SIZE

        if auto_format:
            while body_size > MIN_FONT_SIZE:
                lines = wrap_markdown(draw, spans, safe_width, body_size)
                line_height = load_font(body_size).getbbox("Ay")[3]
                if len(lines) * line_height <= remaining_height:
                    break
                body_size -= 2
        else:
            lines = wrap_markdown(draw, spans, safe_width, body_size)
            line_height = load_font(body_size).getbbox("Ay")[3]

        y = current_y
        for line in lines:
            x = sx0
            for chunk, style in line:
                font = load_font(body_size, **style)
                draw.text((x, y), chunk, fill="black", font=font)
                x += draw.textlength(chunk, font=font)
            y += line_height

    img_io = io.BytesIO()
    img.save(img_io, "PNG")
    img_io.seek(0)
    return send_file(img_io, mimetype="image/png")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
