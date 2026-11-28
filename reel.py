"""Turn an entry's rendered slides into a 9:16 Reel (MP4, H.264 + silent AAC).

Usage:
  python3 reel.py media/002/            -> media/002/reel.mp4

Expects 1.jpg, 2.jpg, 3.jpg (1080x1350) in the folder. Each slide is centred on a
1080x1920 canvas in the diary's background colour; slides cross-fade.
"""
import pathlib
import shutil
import subprocess
import sys

W, H, SLIDE_H = 1080, 1920, 1350
COVER_S, TEXT_S, FADE_S = 3.5, 10.0, 0.7


def sample_colors(slide: pathlib.Path):
    """Average colour of the slide's empty top strip and of its amber margin line,
    so the padding blends with the (grain-textured) slide."""
    try:
        from PIL import Image
        im = Image.open(slide).convert("RGB")
        def avg(pts):
            px = [im.getpixel(p) for p in pts]
            return "0x" + "".join(f"{round(sum(c[i] for c in px) / len(px)):02x}" for i in range(3))
        bg = avg([(x, y) for x in range(300, 900, 7) for y in range(5, 60, 5)])
        line = avg([(x, y) for x in (96, 97) for y in range(5, 60, 5)])
        return bg, line
    except Exception:
        return "0x181715", "0x54422a"


def ffmpeg_bin() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg  # pip install imageio-ffmpeg --break-system-packages
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        sys.exit("ffmpeg not found: apt-get install -y ffmpeg, or pip install imageio-ffmpeg --break-system-packages")


def build(folder: pathlib.Path) -> pathlib.Path:
    slides = sorted(folder.glob("[0-9].jpg"), key=lambda p: int(p.stem))
    if len(slides) < 2:
        sys.exit(f"need at least 2 slides in {folder}")
    durs = [COVER_S] + [TEXT_S] * (len(slides) - 1)
    total = sum(durs) - FADE_S * (len(slides) - 1)
    pad_y = (H - SLIDE_H) // 2
    bg, line = sample_colors(slides[0])

    args = [ffmpeg_bin(), "-y", "-loglevel", "error"]
    for s, d in zip(slides, durs):
        args += ["-loop", "1", "-t", f"{d}", "-i", str(s)]
    args += ["-f", "lavfi", "-t", f"{total}", "-i", "anullsrc=r=48000:cl=stereo"]

    chains = [
        f"[{i}:v]scale={W}:{SLIDE_H},pad={W}:{H}:0:{pad_y}:color={bg},"
        f"drawbox=x=96:y=0:w=2:h={pad_y}:color={line}:t=fill,"
        f"drawbox=x=96:y={pad_y + SLIDE_H}:w=2:h={H - pad_y - SLIDE_H}:color={line}:t=fill,setsar=1,fps=30,format=yuv420p[v{i}]"
        for i in range(len(slides))
    ]
    prev, offset = "v0", 0.0
    for i in range(1, len(slides)):
        offset += durs[i - 1] - FADE_S
        out = f"x{i}"
        chains.append(f"[{prev}][v{i}]xfade=transition=fade:duration={FADE_S}:offset={offset:.2f}[{out}]")
        prev = out

    out_file = folder / "reel.mp4"
    args += [
        "-filter_complex", ";".join(chains),
        "-map", f"[{prev}]", "-map", f"{len(slides)}:a",
        "-c:v", "libx264", "-profile:v", "high", "-level", "4.1", "-pix_fmt", "yuv420p",
        "-r", "30", "-crf", "20", "-maxrate", "8M", "-bufsize", "16M",
        "-c:a", "aac", "-b:a", "128k", "-ar", "48000",
        "-t", f"{total}", "-movflags", "+faststart", str(out_file),
    ]
    subprocess.run(args, check=True)
    print(out_file)
    return out_file


if __name__ == "__main__":
    build(pathlib.Path(sys.argv[1]).resolve())
