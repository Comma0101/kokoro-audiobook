import argparse
import sys
from pathlib import Path

from .engine import generate_audiobook

def main():
    parser = argparse.ArgumentParser(description="Convert PDF/EPUB/TXT/URL to Audiobook")
    parser.add_argument("input", help="Path to input file or URL")
    parser.add_argument("-o", "--output-dir", default="./out", help="Output directory")
    parser.add_argument("--voice", default="af_heart", help="Kokoro voice to use (English)")
    parser.add_argument("--voice-zh", default="zf_xiaobei", help="Kokoro voice to use (Chinese)")
    parser.add_argument("--speed", type=float, default=1.0, help="Speech speed")
    parser.add_argument("--lang", default="auto", help="Language code ('auto', 'a', 'z')")
    parser.add_argument("--single-file", action="store_true", help="Also concatenate all chapter MP3s into one Audiobook.mp3")
    parser.add_argument("--no-srt", action="store_true", help="Skip subtitle generation")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    parser.add_argument("--no-normalize", action="store_true", help="Disable narration normalization (purist mode)")
    
    args = parser.parse_args()
    
    # Fast-fail for non-URL input path
    is_url = args.input.startswith("http://") or args.input.startswith("https://")
    if not is_url:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"Error: Input file {input_path} does not exist.")
            sys.exit(1)
            
    def on_progress(stage, **kwargs):
        if stage == "chapter_start":
            print(f"[{kwargs['index']}/{kwargs['total']}] {kwargs['title']}: synthesizing...", file=sys.stderr)
        elif stage == "chapter_skipped":
            print("  -> Skipped (already exists). Use --force to overwrite.", file=sys.stderr)
        elif stage == "chapter_done":
            print(f"  -> Generated {kwargs['seconds'] / 60:.1f} min audio "
                  f"in {kwargs['elapsed']:.0f}s (RTF {kwargs['rtf']:.2f})", file=sys.stderr)

    print(f"Processing {args.input}...")
    try:
        res = generate_audiobook(
            source_input=args.input,
            out_dir=Path(args.output_dir),
            voice=args.voice,
            voice_zh=args.voice_zh,
            speed=args.speed,
            lang=args.lang,
            normalize=not args.no_normalize,
            write_srt=not args.no_srt,
            single_file=args.single_file,
            force=args.force,
            progress_cb=on_progress
        )
        print(f"Done! Output saved to {res.out_dir}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
