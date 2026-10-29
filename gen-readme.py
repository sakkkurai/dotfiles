from __future__ import annotations

import argparse
import html
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

try:
    from PIL import Image, UnidentifiedImageError
except ImportError:
    sys.exit("Pillow is required: python -m pip install pillow")


TITLE = "dotfiles"
EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
UW_RATIO = 2.1


@dataclass
class Wallpaper:
    path: Path
    device: str
    category: str
    name: str
    size: tuple[int, int] | None


def natural_key(value: str) -> list[tuple[int, int | str]]:
    """Sort file2 before file10, without mixing integers and strings."""
    return [
        (0, int(part)) if part.isdigit() else (1, part.lower())
        for part in re.split(r"(\d+)", value)
    ]


def get_size(path: Path) -> tuple[int, int] | None:
    try:
        with Image.open(path) as image:
            return image.size
    except (UnidentifiedImageError, OSError):
        return None


def make_tags(width: int, height: int) -> list[str]:
    tags = []

    if width >= 3840 or height >= 2160:
        tags.append("4K+")
    elif width >= 1920 or height >= 1080:
        tags.append("FHD")

    if width >= height * UW_RATIO:
        tags.append("UW")

    return tags


def make_name(filename: str) -> str:
    stem = Path(filename).stem

    stem = re.sub(
        r"[-_ ]*\d{3,5}x\d{3,5}$",
        "",
        stem,
    )
    stem = re.sub(r"[-_]+", " ", stem)

    return " ".join(
        word[:1].upper() + word[1:]
        for word in stem.split()
    ) or Path(filename).stem


def format_category(category: str) -> str:
    if not category:
        return "General"

    return " ".join(
        word[:1].upper() + word[1:].lower()
        for word in re.sub(r"[-_]", " ", category).split()
    )


def slugify(value: str) -> str:
    """Create a GitHub-style heading slug."""
    value = value.lower()
    value = re.sub(r"[^\w -]", "", value)
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"-+", "-", value)
    return value.strip("-")


class Anchors:
    """Make heading anchors unique, including duplicate headings."""

    def __init__(self) -> None:
        self.seen: dict[str, int] = {}

    def make(self, heading: str) -> str:
        base = slugify(heading)
        number = self.seen.get(base, 0)
        self.seen[base] = number + 1

        return base if number == 0 else f"{base}-{number}"


def classify(path: Path, root: Path) -> tuple[str, str]:
    """Classify by directory location, never by image dimensions."""
    parts = path.relative_to(root).parts

    if len(parts) == 1:
        return "other", ""

    first = parts[0].lower()
    category_parts = parts[1:-1]

    if first in {"desktop", "mobile"}:
        return first, "/".join(category_parts)

    return "other", "/".join(parts[:-1])


def collect(root: Path) -> list[Wallpaper]:
    wallpapers = []

    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
            continue

        device, category = classify(path, root)

        wallpapers.append(
            Wallpaper(
                path=path,
                device=device,
                category=category,
                name=make_name(path.name),
                size=get_size(path),
            )
        )

    wallpapers.sort(
        key=lambda wallpaper: (
            natural_key(wallpaper.device),
            natural_key(wallpaper.category),
            natural_key(wallpaper.path.name),
        )
    )

    return wallpapers
def render_cell(wallpaper: Wallpaper, root: Path, out_dir: Path) -> str:
    try:
        relative_path = wallpaper.path.resolve().relative_to(out_dir.resolve())
    except ValueError:
        import os
        relative_path = Path(
            os.path.relpath(
                wallpaper.path.resolve(),
                out_dir.resolve(),
            )
        )

    src = quote(relative_path.as_posix(), safe="/")
    name = html.escape(wallpaper.name, quote=True)

    if wallpaper.size:
        width, height = wallpaper.size
        info = f"{width} × {height}"
        tags = make_tags(width, height)

        if tags:
            info += " · " + " · ".join(tags)
    else:
        info = "Resolution unknown"

    info = html.escape(info)

    return "\n".join([
        '<td width="50%" valign="top">',
        f'<img src="{src}" alt="{name}" width="100%">',
        "",
        f'<strong>{name}</strong><br>',
        f'<sub>{info}</sub>',
        '</td>',
    ])


def render_table(
    wallpapers: list[Wallpaper],
    root: Path,
    out_dir: Path,
) -> str:
    lines = ['<table><tbody>']

    for index in range(0, len(wallpapers), 2):
        row = wallpapers[index:index + 2]
        lines.append('<tr>')

        for wallpaper in row:
            lines.append(render_cell(wallpaper, root, out_dir))

        if len(row) == 1:
            lines.append('<td width="50%"></td>')

        lines.append('</tr>')

    lines.append('</tbody></table>')
    return "\n".join(lines)

def build(out: Path, root: Path, wallpapers: list[Wallpaper]) -> str:
    out_dir = out.resolve().parent

    device_order = ["desktop", "mobile", "other"]
    device_titles = {
        "desktop": "Desktop Wallpapers",
        "mobile": "Mobile Wallpapers",
        "other": "Other Wallpapers",
    }

    tree: dict[str, dict[str, list[Wallpaper]]] = {
        device: {} for device in device_order
    }

    for wallpaper in wallpapers:
        tree[wallpaper.device].setdefault(
            wallpaper.category, []
        ).append(wallpaper)

    anchors = Anchors()
    anchors.make(TITLE)
    anchors.make("Contents")
    anchors.make("Wallpapers")

    lines = [
        f"# {TITLE}",
        "",
        "## Contents",
        "",
        "- [Wallpapers](#wallpapers)",
    ]

    for device in device_order:
        categories = tree[device]
        if not categories:
            continue

        device_title = device_titles[device]
        device_anchor = anchors.make(device_title)

        lines.append(f"  - [{device_title}](#{device_anchor})")

        for category in categories:
            category_title = format_category(category)
            heading = (
                f"{format_category(device)} {category_title}"
            )
            category_anchor = anchors.make(heading)

            lines.append(
                f"    - [{category_title}](#{category_anchor})"
            )

    lines.extend(["", "## Wallpapers", ""])

    for device in device_order:
        categories = tree[device]
        if not categories:
            continue

        device_title = device_titles[device]
        lines.extend([f"### {device_title}", ""])

        for category, group in categories.items():
            category_title = format_category(category)
            heading = category_title

            lines.extend([
                f"#### {heading}",
                "",
                render_table(group, root, out_dir),
                "",
            ])

    lines.extend([
        "---",
        "",
        f"<sub>{len(wallpapers)} wallpapers · Automatically generated</sub>",
        "",
    ])

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate README.md with wallpaper galleries."
    )
    parser.add_argument(
        "root",
        nargs="?",
        default="wallpapers",
        help="Directory containing wallpapers",
    )
    parser.add_argument(
        "out",
        nargs="?",
        default="README.md",
        help="Output Markdown file",
    )

    args = parser.parse_args()
    root = Path(args.root).resolve()
    out = Path(args.out)

    if not root.is_dir():
        sys.exit(f"Directory not found: {root}")

    wallpapers = collect(root)

    for wallpaper in wallpapers:
        if wallpaper.size is None:
            print(
                f"Warning: cannot read image dimensions: {wallpaper.path}",
                file=sys.stderr,
            )

    out.parent.mkdir(parents=True, exist_ok=True)
    content = build(out, root, wallpapers)

    out.write_text(content, encoding="utf-8", newline="\n")

    print(f"Done: {out} ({len(wallpapers)} wallpapers)")


if __name__ == "__main__":
    main()
