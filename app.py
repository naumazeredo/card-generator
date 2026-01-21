from flask import Flask, request, send_file, abort
from PIL import Image, ImageDraw, ImageFont
import io

app = Flask(__name__)

# Standard poker card size in mm
POKER_WIDTH_MM = 63
POKER_HEIGHT_MM = 88

# Convert mm to pixels (at 300 DPI)
def mm_to_px(mm, dpi=300):
    return int((mm / 25.4) * dpi)

@app.route("/card")
def render_card():
    text = request.args.get("text")
    size = request.args.get("size")

    if not text:
        abort(400, "Parameter required: text")

    # Parse size
    if size:
        try:
            width_mm, height_mm = map(float, size.lower().split("x"))
        except ValueError:
            abort(400, 'Invalid size format. Use "<width>x<height>", e.g. "50x100"')
    else:
        width_mm = POKER_WIDTH_MM
        height_mm = POKER_HEIGHT_MM

    # Convert to pixels
    width_px = mm_to_px(width_mm)
    height_px = mm_to_px(height_mm)

    # Create image
    img = Image.new("RGB", (width_px, height_px), "white")
    draw = ImageDraw.Draw(img)

    # Load font
    try:
        font_size = int(height_px * 0.15)
        font = ImageFont.truetype("arial.ttf", font_size)
    except IOError:
        font = ImageFont.load_default()

    # Center text
    text_bbox = draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]

    x = (width_px - text_width) // 2
    y = (height_px - text_height) // 2

    draw.text((x, y), text, fill="black", font=font)

    # Return image
    img_io = io.BytesIO()
    img.save(img_io, "PNG")
    img_io.seek(0)

    return send_file(img_io, mimetype="image/png")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
