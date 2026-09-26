"""Draw an original GitHub preview using the existing app icon."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    image = Image.new("RGB", (1280, 640), "#101923")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((64, 64, 1216, 576), radius=28, fill="#172534", outline="#29445b", width=2)
    icon = Image.open(ROOT / "assets/icons/app_icon_256.png").convert("RGBA")
    image.paste(icon, (100, 192), icon)
    font_dir = Path("C:/Windows/Fonts")
    title = ImageFont.truetype(str(font_dir / "segoeuib.ttf"), 55)
    subtitle = ImageFont.truetype(str(font_dir / "segoeui.ttf"), 29)
    small = ImageFont.truetype(str(font_dir / "segoeui.ttf"), 22)
    draw.text((390, 222), "Links Manga Studio", font=title, fill="#f2f6fa")
    draw.text((394, 304), "Local-first Manga Localization Studio", font=subtitle, fill="#b6c8d8")
    draw.text((395, 393), "Created by Links Tam", font=small, fill="#7e99b0")
    output = ROOT / "docs/images/github-social-preview.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)


if __name__ == "__main__":
    main()
