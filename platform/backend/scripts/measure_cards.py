"""Measure a card-reading model on a folder of real card photos, to choose a provider before launch.

Writes what it read to a CSV for a person to mark right or wrong, and prints speed, estimated cost and how many cards
passed the app's own checks. Photos and the CSV hold people's details, so keep them outside this repository.

uv run python scripts/measure_cards.py --provider gemini --photos ../../../card-photos --out ../../../gemini.csv
uv run python scripts/measure_cards.py --provider anthropic --photos ../../../card-photos --out ../../../claude.csv
"""

import argparse
import asyncio
import csv
import json
import mimetypes
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import ai  # noqa: E402
from app.cards import clean_reading  # noqa: E402
from app.config import get_settings  # noqa: E402

COLUMNS = [
    "file",
    "seconds",
    "usable",
    "problems",
    "name",
    "title",
    "company",
    "phones",
    "email",
    "website",
    "correct?",
]


def _provider(name: str) -> ai.Provider:
    settings = get_settings()
    if name == "gemini" and settings.gemini_api_key:
        return ai.GeminiProvider()
    if name == "anthropic" and settings.anthropic_api_key:
        return ai.ClaudeProvider()
    if name == "fake":
        return ai.FakeProvider()
    raise SystemExit(f"No API key set for {name}. Add it to .env; don't paste it into chat.")


async def _measure(provider: ai.Provider, photos: list[Path], out: Path) -> None:
    seconds: list[float] = []
    usable = failed = input_tokens = output_tokens = 0
    with out.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        writer.writerow(COLUMNS)
        for photo in photos:
            mime = mimetypes.guess_type(photo.name)[0] or "image/jpeg"
            started = time.perf_counter()
            try:
                completion = await provider.complete(
                    ai.READ_CARD, None, (await asyncio.to_thread(photo.read_bytes), mime), ai.CardReading
                )
                reading = ai.CardReading.model_validate(json.loads(completion.text))
            except (ai.AiError, ValueError) as exc:
                failed += 1
                writer.writerow([photo.name, "", "", f"Failed: {exc}"])
                continue
            elapsed = time.perf_counter() - started
            seconds.append(elapsed)
            input_tokens += completion.input_tokens
            output_tokens += completion.output_tokens
            card = clean_reading(reading)
            usable += card.usable
            writer.writerow(
                [
                    photo.name,
                    f"{elapsed:.1f}",
                    card.usable,
                    "; ".join(card.problems),
                    card.full_name,
                    card.job_title,
                    card.company,
                    " ".join(card.phones),
                    card.email,
                    card.website,
                    "",
                ]
            )
    cost = (input_tokens * provider.input_usd_per_mtok + output_tokens * provider.output_usd_per_mtok) / 1_000_000
    seconds.sort()
    print(f"{provider.name} ({provider.model}): {len(photos)} photos, {failed} failed, {usable} passed the checks")
    if seconds:
        print(f"Seconds: median {seconds[len(seconds) // 2]:.1f}, slowest {seconds[-1]:.1f}")
    print(f"Estimated cost: ${cost:.4f} (${cost / max(1, len(photos)):.5f} a card), using the prices in the settings")
    print(f"Now mark the 'correct?' column in {out}; passing the checks doesn't prove a card was read correctly.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--provider", choices=["gemini", "anthropic", "fake"], required=True)
    parser.add_argument("--photos", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    photos = sorted(p for p in args.photos.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"})
    if not photos:
        raise SystemExit(f"No photos found in {args.photos}")
    asyncio.run(_measure(_provider(args.provider), photos, args.out))


if __name__ == "__main__":
    main()
