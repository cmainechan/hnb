"""
Convert a spreadsheet of Hebrew nouns (CSV) into the words.json format
used by the Noun Builder app.

Usage:
    python convert_csv_to_json.py words.csv words.json

CSV columns (header row, in any order):
    id        - required. Unique slug, e.g. "lekhem"
    emoji     - required. The emoji shown on the card, e.g. "🍞"
    letters   - required. Consonants in READING order, separated by spaces,
                e.g. "ל ח ם". Final forms (ך ם ן ף ץ) must be used at the end
                of the word, because the keyboard has separate keys for them.
    translit  - required. Transliteration shown after a correct answer
    gloss     - required. English gloss shown after a correct answer
    pointed   - optional. The vocalized word (e.g. "לֶחֶם"), shown after a
                correct answer instead of the bare consonants. Its consonants
                must match `letters`.
    hint      - optional. One or two words shown above the emoji when the
                emoji alone could mean several words (e.g. "land").
    image     - optional. Path to an image (e.g. "img/ohel.svg"), relative to
                the folder that words.json is written to. Shown instead of
                the emoji; the emoji, if any, is the fallback. A row needs an
                emoji or an image.
"""

import csv
import json
import sys
import unicodedata
from pathlib import Path

REQUIRED_COLUMNS = {"id", "emoji", "letters", "translit", "gloss"}

# Medial form -> final form. A final form may only appear as the last letter,
# and a word's last letter must be the final form when one exists.
FINAL_OF = {"כ": "ך", "מ": "ם", "נ": "ן", "פ": "ף", "צ": "ץ"}
FINALS = set(FINAL_OF.values())
HEBREW_LETTERS = set("אבגדהוזחטיכךלמםנןסעפףצץקרשת")


def strip_niqqud(text: str) -> str:
    """Remove vowel points / cantillation marks, keeping consonants only."""
    decomposed = unicodedata.normalize("NFD", text)
    consonants_only = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    return unicodedata.normalize("NFC", consonants_only)


def check_word(letters, pointed):
    """Return a list of problems with one word (empty list if it is fine)."""
    problems = []
    bad = [c for c in letters if c not in HEBREW_LETTERS]
    if bad:
        problems.append(f"non-Hebrew-consonant token(s): {' '.join(bad)}")
        return problems
    for i, c in enumerate(letters):
        last = i == len(letters) - 1
        if c in FINALS and not last:
            problems.append(f"final form {c} in position {i + 1}; use {next(k for k, v in FINAL_OF.items() if v == c)}")
        if c in FINAL_OF and last:
            problems.append(f"last letter {c} should be its final form {FINAL_OF[c]}")
    if pointed and strip_niqqud(pointed) != "".join(letters):
        problems.append(f"pointed form {pointed} has different consonants than letters")
    return problems


def convert(csv_path: Path, json_path: Path) -> None:
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            sys.exit(f"CSV is missing required column(s): {', '.join(sorted(missing))}")

        words = []
        seen_ids = set()
        errors = []

        for row_num, row in enumerate(reader, start=2):  # row 1 is the header
            word_id = row["id"].strip()
            # Strip any vowel points/cantillation and normalize, so consonants
            # come out identical regardless of whether the source was typed
            # by hand or copy-pasted from a fully pointed text.
            letters = [
                strip_niqqud(token)
                for token in row["letters"].strip().split()
            ]
            pointed = unicodedata.normalize("NFC", (row.get("pointed") or "").strip())
            emoji = row["emoji"].strip()
            image = (row.get("image") or "").strip()

            if not word_id:
                errors.append(f"Row {row_num}: missing id")
                continue
            if word_id in seen_ids:
                errors.append(f"Row {row_num}: duplicate id '{word_id}'")
                continue
            if not letters:
                errors.append(f"Row {row_num} ('{word_id}'): no letters found")
                continue
            if not emoji and not image:
                errors.append(f"Row {row_num} ('{word_id}'): missing emoji or image")
                continue
            if image and not (json_path.parent / image).is_file():
                errors.append(f"Row {row_num} ('{word_id}'): image file not found: {image}")
            for problem in check_word(letters, pointed):
                errors.append(f"Row {row_num} ('{word_id}'): {problem}")

            seen_ids.add(word_id)
            word = {
                "id": word_id,
                "emoji": emoji,
                "letters": letters,
                "translit": row["translit"].strip(),
                "gloss": row["gloss"].strip(),
            }
            if pointed:
                word["pointed"] = pointed
            hint = (row.get("hint") or "").strip()
            if hint:
                word["hint"] = hint
            if image:
                word["image"] = image
            words.append(word)

        if errors:
            print("Found problems — fix these rows and re-run:")
            for e in errors:
                print(f"  - {e}")
            sys.exit(1)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(words, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"Wrote {len(words)} word(s) to {json_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Usage: python convert_csv_to_json.py <input.csv> <output.json>")
    convert(Path(sys.argv[1]), Path(sys.argv[2]))
