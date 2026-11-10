"""Prepare 1080p60 story movies from a local Xbox 360 game installation."""

import argparse
import json
import os
import subprocess
from fractions import Fraction
from pathlib import Path


def probe(ffprobe, path):
    return json.loads(subprocess.check_output([
        str(ffprobe), "-v", "error", "-show_streams", "-show_format",
        "-of", "json", str(path),
    ]))


def audio_hashes(ffmpeg, path):
    return subprocess.check_output([
        str(ffmpeg), "-nostdin", "-v", "error", "-i", str(path),
        "-map", "0:a?", "-c", "copy", "-f", "streamhash", "-",
    ])


def prepare(ffmpeg, ffprobe, source, target):
    original = probe(ffprobe, source)
    video = max(
        (stream for stream in original["streams"] if stream["codec_type"] == "video"),
        key=lambda stream: stream["width"] * stream["height"],
    )
    duration = original["format"]["duration"]
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(f".{os.getpid()}.partial.wmv")
    try:
        subprocess.run([
            str(ffmpeg), "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(source), "-map", f"0:{video['index']}", "-map", "0:a?",
            "-t", duration, "-vf",
            "tpad=stop_mode=clone:stop_duration=0.2,"
            "minterpolate=fps=60:mi_mode=mci:mc_mode=obmc:me_mode=bilat:me=epzs,"
            "scale=1920:1080:force_original_aspect_ratio=decrease:flags=lanczos,"
            "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1",
            "-c:v", "wmv2", "-q:v", "3", "-c:a", "copy", str(temporary),
        ], check=True)
        result = probe(ffprobe, temporary)
        encoded = result["streams"][0]
        if (encoded["width"], encoded["height"]) != (1920, 1080) or Fraction(
            encoded["r_frame_rate"]
        ) != 60:
            raise RuntimeError(f"{source.name}: incorrect video dimensions or frame rate")
        # The ASF muxer can report the end of the final copied WMA packet.
        if abs(float(result["format"]["duration"]) - float(duration)) > 0.2:
            raise RuntimeError(f"{source.name}: output duration differs from the original")
        audio = lambda info: [s["codec_name"] for s in info["streams"] if s["codec_type"] == "audio"]
        if audio(result) != audio(original):
            raise RuntimeError(f"{source.name}: original audio streams missing")
        if audio(original) and audio_hashes(ffmpeg, temporary) != audio_hashes(ffmpeg, source):
            raise RuntimeError(f"{source.name}: audio packets differ from the original")
        if not target.is_file():
            temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--clip", action="append", help="limit preparation to these clip stems")
    args = parser.parse_args()
    fmv = args.game / "fmv"
    if args.output.resolve().is_relative_to(args.game.resolve()):
        parser.error("output must be outside the original game directory")
    clips = sorted(fmv.glob("l_*/*.wmv"))
    if args.clip:
        available = {source.stem: source for source in clips}
        missing = set(args.clip) - available.keys()
        if missing:
            parser.error(f"unknown clips: {', '.join(sorted(missing))}")
        clips = [available[name] for name in dict.fromkeys(args.clip)]
    if not clips:
        parser.error(f"no story movies found in {fmv}")
    ffprobe = args.ffmpeg.with_name("ffprobe.exe")
    for source in clips:
        clip = source.relative_to(fmv)
        target = args.output / clip
        if not target.is_file():
            print(f"Preparing {clip}", flush=True)
            prepare(args.ffmpeg, ffprobe, source, target)
            print(f"Ready {clip}", flush=True)


if __name__ == "__main__":
    main()
