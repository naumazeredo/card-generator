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
DEFAULT_BLEED = 0

# --- Typography defaults ---
DEFAULT_BODY_FONT_SIZE = 32
DEFAULT_TITLE_FONT_SIZE = 48
MIN_FONT_SIZE = 10
TITLE_BODY_GAP = 4
LIST_INDENT_PX = 24
LIST_GAP_PX = 4

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

# ---------- Markdown parsing ----------

MD_INLINE = re.compile(r'(\*\*.*?\*\*|__.*?__|\*.*?\*|_.*?_)')
LIST_ITEM = re.compile(r'^(\d+\.|[-*])\s+(.*)')

def parse_inline(text):
    spans = []
    for part in MD_INLINE.split(text):
        if not part:
            continue
        if part.startswith(("**", "__")):
            spans.append((part[2:-2], {"bold": True}))
        elif part.startswith(("*", "_")):
            spans.append((part[1:-1], {"italic": True}))
        else:
            spans.append((part, {}))
    return spans

def parse_blocks(text):
    blocks = []
    for line in text.splitlines():
        m = LIST_ITEM.match(line)
        if m:
            marker, content = m.groups()
            blocks.append({
                "type": "list",
                "marker": marker,
                "spans": parse_inline(content)
            })
        else:
            blocks.append({
                "type": "paragraph",
                "spans": parse_inline(line)
            })
    return blocks

def wrap_spans(draw, spans, max_width, font_size):
    lines = []
    current = []
    width = 0
    for text, style in spans:
        for i, word in enumerate(text.split(" ")):
            chunk = word + (" " if i < len(text.split(" ")) - 1 else "")
            font = load_font(font_size, **style)
            w = draw.textlength(chunk, font=font)
            if width + w <= max_width:
                current.append((chunk, style))
                width += w
            else:
                lines.append(current)
                current = [(chunk, style)]
                width = w
    if current:
        lines.append(current)
    return lines

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

@app.route("/card")
def render_card():
    title = request.args.get("title")
    if not title:
        abort(400, "'title' parameter is required")

    text = request.args.get("text")
    size = request.args.get("size")
    margin = request.args.get("margin", type=float, default=DEFAULT_MARGIN)
    bleed = request.args.get("bleed", type=float, default=DEFAULT_BLEED)
    font_size = request.args.get("font_size", type=int)
    title_size = request.args.get("title_size", type=int)
    bg_color = request.args.get("bg_color", default="white")
    border_color = request.args.get("border_color", default="black")
    border_size_mm = request.args.get("border_size", type=float, default=1)
    auto_format = request.args.get("auto_format", default="false").lower() == "true"
    center = request.args.get("center", default="false").lower() == "true"

    if size:
        width, height = map(float, size.lower().split("x"))
    else:
        width, height = POKER_WIDTH, POKER_HEIGHT

    card_w = mm_to_px(width)
    card_h = mm_to_px(height)
    bleed_px = mm_to_px(bleed)
    margin_px = mm_to_px(margin)
    border_size_px = mm_to_px(border_size_mm)

    img = Image.new("RGB", (card_w + bleed_px * 2, card_h + bleed_px * 2), "#eeeeee")
    draw = ImageDraw.Draw(img)

    cx0, cy0 = bleed_px, bleed_px
    cx1, cy1 = cx0 + card_w, cy0 + card_h
    draw.rectangle([cx0, cy0, cx1, cy1], fill=bg_color)

    if border_size_px > 0:
        draw.rectangle(
            [cx0 + border_size_px, cy0 + border_size_px,
             cx1 - border_size_px, cy1 - border_size_px],
            outline=border_color
        )

    sx0 = cx0 + margin_px
    sy0 = cy0 + margin_px
    sx1 = cx1 - margin_px
    sy1 = cy1 - margin_px
    safe_width = sx1 - sx0

    # ---------- TITLE ----------
    if auto_format:
        size_try = title_size or int(safe_width * 0.18)
        while size_try > MIN_FONT_SIZE:
            font = load_font(size_try, bold=True)
            title_lines = wrap_plain(draw, title, font, safe_width)
            title_line_height = font.getbbox("Ay")[3]
            title_height = len(title_lines) * title_line_height
            if title_height <= (sy1 - sy0) * 0.5 or title_size:
                break
            size_try -= 2
    else:
        font = load_font(title_size or DEFAULT_TITLE_FONT_SIZE, bold=True)
        title_lines = wrap_plain(draw, title, font, safe_width)
        title_line_height = font.getbbox("Ay")[3]
        title_height = len(title_lines) * title_line_height

    # ---------- BODY ----------
    body_lines = []
    body_lh = 0
    if text:
        blocks = parse_blocks(text)
        body_size = font_size or (int((sy1 - sy0) * 0.22) if auto_format else DEFAULT_BODY_FONT_SIZE)

        while True:
            total_height = 0
            layout = []
            for block in blocks:
                indent = LIST_INDENT_PX if block["type"] == "list" else 0
                lines = wrap_spans(draw, block["spans"], safe_width - indent, body_size)
                lh = load_font(body_size).getbbox("Ay")[3]
                h = len(lines) * lh + LIST_GAP_PX
                total_height += h
                layout.append((block, lines, lh))
            if not auto_format or total_height <= (sy1 - sy0) or body_size <= MIN_FONT_SIZE:
                body_lines = layout
                body_lh = body_size
                break
            body_size -= 2

    # ---------- Vertical positioning ----------
    total_content_height = len(title_lines) * title_line_height
    if text:
        total_content_height += TITLE_BODY_GAP
        for block, lines, lh in body_lines:
            total_content_height += len(lines) * lh + LIST_GAP_PX

    y = sy0
    if center:
        y += max(0, ((sy1 - sy0) - total_content_height) // 2)

    # ---------- Draw title ----------
    for line in title_lines:
        x = sx0
        if center:
            x += max(0, (safe_width - draw.textlength(line, font=font)) // 2)
        draw.text((x, y), line, fill="black", font=font)
        y += title_line_height
    y += TITLE_BODY_GAP

    # ---------- Draw body ----------
    if text:
        for block, lines, lh in body_lines:
            indent = LIST_INDENT_PX if block["type"] == "list" else 0
            x0 = sx0 + indent
            if block["type"] == "list":
                bullet = "•" if not block["marker"].endswith(".") else block["marker"]
                bx = sx0
                if center:
                    # center bullet + text together
                    line_width = draw.textlength(bullet, font=load_font(body_lh)) + max(draw.textlength("".join([c for c,s in line]), font=load_font(body_lh)) for line in lines)
                    bx += max(0, (safe_width - line_width) // 2)
                    x0 = bx + indent
                draw.text((bx, y), bullet, fill="black", font=load_font(body_lh))

            for line in lines:
                x = x0
                if center:
                    line_width = sum(draw.textlength(chunk, font=load_font(body_lh, **style)) for chunk, style in line)
                    x += max(0, (safe_width - line_width) // 2)
                for chunk, style in line:
                    font = load_font(body_lh, **style)
                    draw.text((x, y), chunk, fill="black", font=font)
                    x += draw.textlength(chunk, font=font)
                y += lh
            y += LIST_GAP_PX

    img_io = io.BytesIO()
    img.save(img_io, "PNG")
    img_io.seek(0)
    return send_file(img_io, mimetype="image/png")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
