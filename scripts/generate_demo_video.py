"""Generate a detailed narrated demo video (MP4) for TokenOptimizer.

Builds ``docs/TokenOptimizer-Demo.mp4`` — a captioned, voice-over walkthrough of
every feature. Fully offline:

  * Voice-over: Windows SAPI (``System.Speech``) synthesised to WAV per scene.
  * Frames: real app screenshots (``docs/assets/video/*.png``) + branded title
    and bullet slides rendered with Pillow. Every frame is 1280x720 with a
    caption bar showing the narration (subtitles).
  * Encoding: ffmpeg (bundled via ``imageio-ffmpeg``) makes one segment per
    scene (still image + its narration) and concatenates them.

Run (after capturing the app screenshots — see scripts/capture_demo_frames.sh):

    python scripts/generate_demo_video.py [output.mp4]

A scene whose screenshot is missing falls back to a rendered card/bullets slide,
so the video always builds.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = PROJECT_ROOT / "docs" / "TokenOptimizer-Demo.mp4"
V = PROJECT_ROOT / "docs" / "assets" / "video"
DASHBOARD_IMG = PROJECT_ROOT / "docs" / "assets" / "hackcelerate-dashboard.png"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

W, H = 1280, 720
NAVY = (18, 54, 92)
BLUE = (26, 94, 184)
INK = (22, 35, 58)
WHITE = (255, 255, 255)
SUBTLE = (183, 198, 218)
GREEN = (110, 209, 154)


def _font(bold: bool, size: int):
    for name in (("segoeuib.ttf", "arialbd.ttf") if bold else ("segoeui.ttf", "arial.ttf")):
        p = Path("C:/Windows/Fonts") / name
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def _wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for wd in words:
        trial = (cur + " " + wd).strip()
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def _caption(img: Image.Image, text: str) -> None:
    """Translucent bottom bar with the narration text (subtitles)."""
    draw = ImageDraw.Draw(img, "RGBA")
    font = _font(False, 25)
    lines = _wrap(draw, text, font, W - 130)
    bar_h = 30 + len(lines) * 33 + 12
    draw.rectangle([0, H - bar_h, W, H], fill=(8, 18, 34, 210))
    draw.rectangle([0, H - bar_h, W, H - bar_h + 4], fill=BLUE)
    y = H - bar_h + 14
    for ln in lines:
        w = draw.textlength(ln, font=font)
        draw.text(((W - w) / 2, y), ln, font=font, fill=WHITE)
        y += 33


def _card(title: str, subtitle: str) -> Image.Image:
    img = Image.new("RGB", (W, H), NAVY)
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 300, W, 306], fill=BLUE)
    draw.rounded_rectangle([90, 150, 190, 250], radius=14, fill=BLUE)
    draw.text((104, 178), "T:O", font=_font(True, 40), fill=WHITE)
    draw.text((90, 330), title, font=_font(True, 62), fill=WHITE)
    if subtitle:
        fs = _font(False, 28)
        for i, ln in enumerate(_wrap(draw, subtitle, fs, W - 180)):
            draw.text((92, 425 + i * 38), ln, font=fs, fill=SUBTLE)
    return img


def _bullets(title: str, items) -> Image.Image:
    img = Image.new("RGB", (W, H), NAVY)
    draw = ImageDraw.Draw(img)
    draw.text((80, 58), title, font=_font(True, 40), fill=WHITE)
    draw.rectangle([80, 120, W - 80, 123], fill=BLUE)
    fb = _font(False, 25)
    y = 150
    for it in items:
        draw.ellipse([84, y + 11, 96, y + 23], fill=GREEN)
        for j, ln in enumerate(_wrap(draw, it, fb, W - 260)):
            draw.text((116, y), ln, font=fb, fill=(226, 234, 247))
            y += 34
        y += 12
    return img


def _fit(path: Path) -> Image.Image:
    img = Image.new("RGB", (W, H), NAVY)
    try:
        shot = Image.open(path).convert("RGB")
    except Exception:
        return img
    scale = min((W - 60) / shot.width, (H - 170) / shot.height)
    nw, nh = int(shot.width * scale), int(shot.height * scale)
    shot = shot.resize((nw, nh), Image.LANCZOS)
    img.paste(shot, ((W - nw) // 2, (H - 170 - nh) // 2 + 18))
    return img


def _speakable(s: str) -> str:
    for a, b in (("—", ", "), ("–", ", "), ("·", ", "), ("→", " to "), ("’", "'"), ("“", ""), ("”", "")):
        s = s.replace(a, b)
    return s


def _synth_wav(text: str, out: Path) -> float:
    ps = (
        "[Console]::InputEncoding=[System.Text.Encoding]::UTF8;"
        "Add-Type -AssemblyName System.Speech;"
        "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;$s.Rate=1;"
        f"$s.SetOutputToWaveFile('{out.as_posix()}');"
        "$s.Speak([Console]::In.ReadToEnd());$s.Dispose()"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                   input=text.encode("utf-8"), check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with wave.open(str(out), "rb") as w:
        return max(2.0, w.getnframes() / float(w.getframerate())) + 0.6


def _scenes():
    return [
        {"card": ("TokenOptimizer", "Enterprise Token Optimization Console — a detailed walkthrough"),
         "say": "TokenOptimizer cuts the tokens you send to a language model, lowering cost "
                "and latency while preserving every fact an agent needs. Let's walk through "
                "all of its features."},
        {"img": V / "app_optimizer.png",
         "say": "The desktop console has three tabs — Token Optimizer, Feature-Dev Skills, "
                "and Dashboard — plus a header with a one-click Guided Demo and a mode "
                "indicator. It runs fully offline, and gets better with a Claude key or a "
                "local model."},
        {"img": V / "app_optimized.png",
         "say": "On the Token Optimizer tab, pick a document and it optimizes on load. Here a "
                "verbose report drops from eight hundred eighty-seven tokens to thirty-two, "
                "about ninety-six percent smaller, shown side by side with the count method "
                "and a per-run log."},
        {"img": V / "app_jira.png",
         "say": "Beyond files, you can optimize live data. The JIRA source connects with a "
                "base URL, email, and token, then fetches issues by a JQL query. Blank fields "
                "fall back to your dot-env."},
        {"img": V / "app_github.png",
         "say": "The GitHub source reviews a single pull request or triages every open PR, "
                "optionally pulling the diff, which is compressed with a diff-aware pass that "
                "keeps changed lines and drops unchanged context."},
        {"bullets": ("Optimization pipeline — offline, no API key", [
            "Unicode folded to ASCII; emoji and zero-width chars stripped",
            "Conversational framing, page numbers, footers and TOC removed",
            "Structure-aware collapse of Jira-style label / value blocks",
            "Filler phrases shortened; near-duplicate paragraphs de-duplicated",
            "Whitespace and repeated lines compressed"]),
         "say": "Under the hood, a stack of deterministic passes runs with no API key: it "
                "folds unicode, strips framing and boilerplate, collapses structured fields, "
                "shortens filler, de-duplicates paragraphs, and compresses whitespace."},
        {"bullets": ("Summarization, token counting & logging", [
            "Summary tiers: Claude Haiku, then a local Ollama model, then extractive",
            "Extractive tier never drops error codes, IDs, versions, paths or URLs",
            "Tokens counted via API count_tokens, else tiktoken, else an estimate",
            "Every run writes a timestamped log; secrets are never recorded"]),
         "say": "An optional summary pass picks the best available engine: Claude Haiku, a "
                "local model, or a no-L-L-M extractive summarizer that always keeps critical "
                "entities. Tokens are counted exactly when possible, and every run is logged "
                "without recording secrets."},
        {"img": V / "app_skills.png",
         "say": "The Feature-Dev Skills tab hosts two skills that optimize tokens during "
                "feature development, with a live result console on the right."},
        {"bullets": ("Skill 1 · PRD Compression", [
            "Distills a verbose PRD into structured requirement atoms",
            "Goals, acceptance criteria, constraints, non-functional, dependencies",
            "Acceptance criteria kept verbatim — never paraphrased",
            "About 67 to 73 percent fewer input tokens (e.g. 425 to 125)"]),
         "say": "Skill one compresses a product requirements document into dense requirement "
                "atoms, keeping acceptance criteria word for word, and cutting input tokens "
                "by around seventy percent."},
        {"bullets": ("Skill 2a · Codebase Anchoring", [
            "Indexes the repo: AST for Python, regex for JS, TS, Java, Go, Ruby, C#",
            "Anchors each plan step to a real file:line reference",
            "Flags unresolved symbols as possible hallucinations",
            "Example: 'Call compress_prd' resolves to compressor.py:237"]),
         "say": "Skill two-A grounds an AI plan in the real codebase: it indexes your "
                "repository and anchors every step to a real file and line, flagging invented "
                "references as possible hallucinations."},
        {"bullets": ("Skill 2b · Model Router", [
            "Classifies each task trivial, standard, or complex, with a confidence score",
            "Routes trivial to Haiku, standard to Sonnet, complex to Opus",
            "Low confidence upgrades one tier toward premium — safety first",
            "Example: 'fix a typo' routes to claude-haiku-4-5"]),
         "say": "Skill two-B routes each task to the cheapest capable model by complexity, and "
                "upgrades toward a premium model whenever it isn't confident, so you never "
                "underpower a hard task."},
        {"bullets": ("A/B Validation", [
            "Baseline: raw PRD to a premium model, no anchoring",
            "Optimised: compressed PRD, anchored plan, routed model",
            "8 feature requests across 2 business units (Payments, Platform)",
            "Deterministic 25-point quality rubric — fully reproducible"]),
         "say": "To prove it works, an offline A B suite compares a baseline against the "
                "optimized pipeline across eight feature requests in two business units, "
                "scored on a deterministic twenty-five-point rubric."},
        {"img": DASHBOARD_IMG,
         "say": "The Dashboard shows the outcome: about fifty-eight percent cost savings, "
                "seventy-three percent PRD compression, and twenty-four out of twenty-five "
                "quality, equal or better than baseline in every case. It also exports an "
                "interactive HTML report."},
        {"img": V / "app_demo.png",
         "say": "A built-in guided demo, launched from the header button, walks through every "
                "feature automatically, with an on-screen caption and a spoken voice-over you "
                "can mute at any time."},
        {"bullets": ("Also on the command line (tokenopt)", [
            "optimize-doc  ·  compress-prd  ·  anchor-plan  ·  route",
            "ab-suite  ·  dashboard — run validation and export the report",
            "triage-jira  ·  triage-jenkins  ·  review-github-pr  ·  triage-github-prs",
            "Everything the UI does, scriptable and CI-friendly"]),
         "say": "Every capability is also on the command line via the tokenopt command: "
                "optimize documents, run the skills, launch the A B suite and dashboard, and "
                "triage Jira, Jenkins, or GitHub, all scriptable for automation."},
        {"card": ("35% cheaper. Equal or better quality.",
                  "Proven across 8 A/B tests and 2 business units."),
         "say": "TokenOptimizer: cheaper AI-assisted development, with equal or better "
                "quality, proven by evidence. Thank you for watching."},
    ]


def build(out: Path) -> None:
    V.mkdir(parents=True, exist_ok=True)
    scenes = _scenes()
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        segs = []
        for i, sc in enumerate(scenes):
            if "img" in sc and Path(sc["img"]).exists():
                frame = _fit(Path(sc["img"]))
            elif "bullets" in sc:
                frame = _bullets(*sc["bullets"])
            else:
                frame = _card(*sc["card"])
            _caption(frame, sc["say"])
            fpng = tmp / f"frame{i}.png"
            frame.save(fpng)
            wav = tmp / f"scene{i}.wav"
            dur = _synth_wav(_speakable(sc["say"]), wav)
            seg = tmp / f"seg{i}.mp4"
            subprocess.run(
                [FFMPEG, "-y", "-loop", "1", "-i", str(fpng), "-i", str(wav),
                 "-c:v", "libx264", "-tune", "stillimage", "-r", "25",
                 "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
                 "-t", f"{dur:.2f}", str(seg)],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            segs.append(seg)
            print(f"  scene {i + 1}/{len(scenes)}: {dur:.1f}s")
        listing = tmp / "segs.txt"
        listing.write_text("".join(f"file '{p.as_posix()}'\n" for p in segs))
        out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
             "-c", "copy", str(out)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"MP4 written to: {out}")


def main(argv):
    build(Path(argv[1]) if len(argv) > 1 else DEFAULT_OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
