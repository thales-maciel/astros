#!/usr/bin/env python3
"""Generate static astrology sky-state JSON files for GitHub Pages."""

from __future__ import annotations

import calendar
import gzip
import json
from collections import Counter
from datetime import UTC, date, datetime, time, timedelta
from itertools import combinations
from pathlib import Path
from typing import Any

import swisseph as swe


RETENTION_DAYS = 730
TIMEZONE = "UTC"
ASPECT_ORB_DEGREES = 6.0
LUNATION_FLAG_ORB_DEGREES = 6.0

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
DAYS_DIR = DATA_DIR / "days"
MONTHS_DIR = DATA_DIR / "months"
ARCHIVE_DIR = DATA_DIR / "archive"

SIGNS = [
    "Aries",
    "Taurus",
    "Gemini",
    "Cancer",
    "Leo",
    "Virgo",
    "Libra",
    "Scorpio",
    "Sagittarius",
    "Capricorn",
    "Aquarius",
    "Pisces",
]

PLANETS = {
    "sun": swe.SUN,
    "moon": swe.MOON,
    "mercury": swe.MERCURY,
    "venus": swe.VENUS,
    "mars": swe.MARS,
    "jupiter": swe.JUPITER,
    "saturn": swe.SATURN,
    "uranus": swe.URANUS,
    "neptune": swe.NEPTUNE,
    "pluto": swe.PLUTO,
}

RETROGRADE_PLANETS = [
    "mercury",
    "venus",
    "mars",
    "jupiter",
    "saturn",
    "uranus",
    "neptune",
    "pluto",
]

ASPECTS = {
    "conjunction": 0,
    "sextile": 60,
    "square": 90,
    "trine": 120,
    "opposition": 180,
}

# Moshier calculations are built into Swiss Ephemeris, so this script does not
# need separate ephemeris data files in CI or on GitHub Actions runners.
EPHEMERIS_FLAGS = swe.FLG_MOSEPH | swe.FLG_SPEED

PHASE_TEXT = {
    "New Moon": "The New Moon favors reset, intention-setting, and quiet beginnings.",
    "Waxing Crescent": "The Waxing Crescent phase supports early momentum, small commitments, and gentle growth.",
    "First Quarter": "The First Quarter Moon brings decision points, pressure to act, and useful friction.",
    "Waxing Gibbous": "The Waxing Gibbous Moon favors refinement, preparation, and steady follow-through.",
    "Full Moon": "The Full Moon brings culmination, emotional visibility, and a sense that something is reaching its peak.",
    "Waning Gibbous": "The Waning Gibbous Moon supports integration, sharing what was learned, and adjusting expectations.",
    "Last Quarter": "The Last Quarter Moon favors release, course correction, and practical closure.",
    "Waning Crescent": "The Waning Crescent Moon supports rest, reflection, and quiet completion.",
}

MOON_SIGN_TEXT = {
    "Aries": "The Moon in Aries gives the hour a direct, active, fast-moving tone.",
    "Taurus": "The Moon in Taurus favors steadiness, embodiment, comfort, and practical pacing.",
    "Gemini": "The Moon in Gemini brings curiosity, conversation, movement, and mental flexibility.",
    "Cancer": "The Moon in Cancer emphasizes care, memory, privacy, home, and emotional protection.",
    "Leo": "The Moon in Leo warms the hour with expressiveness, confidence, play, and visibility.",
    "Virgo": "The Moon in Virgo favors editing, service, routines, details, and useful improvements.",
    "Libra": "The Moon in Libra highlights balance, diplomacy, aesthetics, and relationship awareness.",
    "Scorpio": "The Moon in Scorpio gives the hour a deeper, more private, emotionally intense tone.",
    "Sagittarius": "The Moon in Sagittarius opens the mood toward candor, perspective, travel, and learning.",
    "Capricorn": "The Moon in Capricorn favors structure, responsibility, patience, and long-term priorities.",
    "Aquarius": "The Moon in Aquarius emphasizes independence, systems, friendship, and unconventional thinking.",
    "Pisces": "The Moon in Pisces softens the hour with intuition, imagination, compassion, and porous boundaries.",
}

RETROGRADE_TEXT = {
    "mercury": "Mercury is retrograde, so communication, plans, and details may feel slower or more tangled.",
    "venus": "Venus is retrograde, bringing review to relationships, values, money, and attraction.",
    "mars": "Mars is retrograde, turning action, conflict, desire, and momentum inward for reassessment.",
    "jupiter": "Jupiter is retrograde, making growth, belief, opportunity, and meaning more reflective.",
    "saturn": "Saturn is retrograde, emphasizing review around responsibility, limits, discipline, and commitments.",
    "uranus": "Uranus is retrograde, internalizing themes of disruption, liberation, and pattern-breaking.",
    "neptune": "Neptune is retrograde, clarifying dreams, ideals, illusions, and spiritual sensitivity.",
    "pluto": "Pluto is retrograde, intensifying inner work around power, release, and transformation.",
}

ASPECT_TEXT = {
    "conjunction": "{a} meets {b}, concentrating both planets into one direct theme.",
    "sextile": "{a} forms a sextile with {b}, opening cooperative opportunities with light effort.",
    "square": "{a} squares {b}, adding friction that asks for action, adjustment, or honesty.",
    "trine": "{a} trines {b}, creating ease, flow, and natural support between their themes.",
    "opposition": "{a} opposes {b}, highlighting polarity, projection, and the need for balance.",
}


def main() -> None:
    generated_at = utc_now()
    today = generated_at.date()
    tomorrow = today + timedelta(days=1)

    ensure_directories()

    generated_days = [
        write_day_file(today, generated_at),
        write_day_file(tomorrow, generated_at),
    ]

    current_month = month_start(today)
    next_month = add_month(current_month)
    generated_months = [
        write_month_file(current_month, generated_at),
        write_month_file(next_month, generated_at),
    ]

    write_latest_file(today, tomorrow, current_month, generated_at)
    archived_days = archive_old_days(today)

    print("Sky data update complete")
    print(f"- generated daily files: {', '.join(generated_days)}")
    print(f"- generated monthly files: {', '.join(generated_months)}")
    print(f"- archived old daily files: {archived_days}")


def utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def ensure_directories() -> None:
    for directory in [DATA_DIR, DAYS_DIR, MONTHS_DIR, ARCHIVE_DIR]:
        directory.mkdir(parents=True, exist_ok=True)


def write_day_file(day: date, generated_at: datetime) -> str:
    day_data = build_day(day, generated_at)
    path = DAYS_DIR / f"{day.isoformat()}.json"
    write_json(path, day_data)
    return relative_path(path)


def build_day(day: date, generated_at: datetime) -> dict[str, Any]:
    hours = [
        build_hour_snapshot(datetime.combine(day, time(hour=hour), tzinfo=UTC))
        for hour in range(24)
    ]
    daily = build_daily_interpretation(day, hours)
    return {
        "date": day.isoformat(),
        "timezone": TIMEZONE,
        "generated_at": iso_z(generated_at),
        "daily": daily,
        "hours": hours,
    }


def build_hour_snapshot(moment: datetime) -> dict[str, Any]:
    planets = calculate_planets(moment)
    moon = planets["moon"]
    sun = planets["sun"]
    moon_phase = calculate_moon_phase(moon["longitude"], sun["longitude"])
    flags = build_flags(planets, moon["longitude"], sun["longitude"])
    aspects = calculate_aspects(planets)
    headline, summary = build_hour_interpretation(moon_phase, moon["sign"], flags, aspects)

    return {
        "hour": moment.hour,
        "datetime": iso_z(moment),
        "headline": headline,
        "summary": summary,
        "moon_phase": moon_phase,
        "moon_sign": moon["sign"],
        "flags": flags,
        "planets": planets,
        "aspects": aspects,
    }


def calculate_planets(moment: datetime) -> dict[str, dict[str, Any]]:
    jd = swe.julday(
        moment.year,
        moment.month,
        moment.day,
        moment.hour + moment.minute / 60 + moment.second / 3600,
        swe.GREG_CAL,
    )

    positions: dict[str, dict[str, Any]] = {}
    for name, planet_id in PLANETS.items():
        values, _flags = swe.calc_ut(jd, planet_id, EPHEMERIS_FLAGS)
        longitude = normalize_degrees(values[0])
        speed = values[3]
        positions[name] = {
            "longitude": rounded(longitude, 4),
            "sign": zodiac_sign(longitude),
            "degree": rounded(longitude % 30, 4),
            "retrograde": bool(speed < 0),
            "speed": rounded(speed, 5),
        }
    return positions


def build_flags(
    planets: dict[str, dict[str, Any]], moon_longitude: float, sun_longitude: float
) -> dict[str, bool]:
    phase_angle = signed_arc_distance(moon_longitude, sun_longitude)
    flags = {
        f"{planet}_retrograde": bool(planets[planet]["retrograde"])
        for planet in RETROGRADE_PLANETS
    }
    flags["full_moon"] = abs(phase_angle - 180) <= LUNATION_FLAG_ORB_DEGREES
    flags["new_moon"] = min(phase_angle, 360 - phase_angle) <= LUNATION_FLAG_ORB_DEGREES
    return flags


def calculate_moon_phase(moon_longitude: float, sun_longitude: float) -> str:
    phase_angle = signed_arc_distance(moon_longitude, sun_longitude)
    if phase_angle < 22.5 or phase_angle >= 337.5:
        return "New Moon"
    if phase_angle < 67.5:
        return "Waxing Crescent"
    if phase_angle < 112.5:
        return "First Quarter"
    if phase_angle < 157.5:
        return "Waxing Gibbous"
    if phase_angle < 202.5:
        return "Full Moon"
    if phase_angle < 247.5:
        return "Waning Gibbous"
    if phase_angle < 292.5:
        return "Last Quarter"
    return "Waning Crescent"


def calculate_aspects(planets: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for planet_a, planet_b in combinations(PLANETS.keys(), 2):
        longitude_a = planets[planet_a]["longitude"]
        longitude_b = planets[planet_b]["longitude"]
        separation = shortest_arc(longitude_a, longitude_b)

        for aspect_name, exact_angle in ASPECTS.items():
            orb = abs(separation - exact_angle)
            if orb <= ASPECT_ORB_DEGREES:
                found.append(
                    {
                        "planet_a": planet_a,
                        "planet_b": planet_b,
                        "aspect": aspect_name,
                        "exact_angle": exact_angle,
                        "orb": rounded(orb, 2),
                    }
                )
                break

    return sorted(
        found,
        key=lambda aspect: (
            aspect["orb"],
            aspect["planet_a"],
            aspect["planet_b"],
            aspect["aspect"],
        ),
    )


def build_hour_interpretation(
    moon_phase: str,
    moon_sign: str,
    flags: dict[str, bool],
    aspects: list[dict[str, Any]],
) -> tuple[str, str]:
    active_retrogrades = [
        planet for planet in RETROGRADE_PLANETS if flags[f"{planet}_retrograde"]
    ]

    if flags["full_moon"]:
        headline = f"Full Moon in {moon_sign}"
    elif flags["new_moon"]:
        headline = f"New Moon in {moon_sign}"
    elif active_retrogrades and active_retrogrades[0] == "mercury":
        headline = f"Mercury Retrograde, Moon in {moon_sign}"
    elif aspects:
        top_aspect = aspects[0]
        headline = (
            f"{title_planet(top_aspect['planet_a'])} "
            f"{aspect_verb(top_aspect['aspect'])} "
            f"{title_planet(top_aspect['planet_b'])}"
        )
    else:
        headline = f"{moon_phase}, Moon in {moon_sign}"

    parts = [PHASE_TEXT[moon_phase], MOON_SIGN_TEXT[moon_sign]]
    parts.extend(RETROGRADE_TEXT[planet] for planet in active_retrogrades[:3])

    for aspect in aspects[:2]:
        parts.append(aspect_sentence(aspect))

    return headline, " ".join(parts)


def build_daily_interpretation(day: date, hours: list[dict[str, Any]]) -> dict[str, Any]:
    noon = hours[12]
    highlights = build_daily_highlights(hours)

    full_moon_hour = first_hour_with_flag(hours, "full_moon")
    new_moon_hour = first_hour_with_flag(hours, "new_moon")

    if full_moon_hour is not None:
        headline = f"Full Moon in {hours[full_moon_hour]['moon_sign']}"
    elif new_moon_hour is not None:
        headline = f"New Moon in {hours[new_moon_hour]['moon_sign']}"
    elif noon["flags"]["mercury_retrograde"]:
        headline = f"Mercury Retrograde with the Moon in {noon['moon_sign']}"
    else:
        headline = f"{noon['moon_phase']} with the Moon in {noon['moon_sign']}"

    if highlights:
        summary = " ".join(highlights)
    else:
        summary = (
            f"{day.isoformat()} carries a {noon['moon_phase']} tone with the Moon "
            f"in {noon['moon_sign']} around midday UTC."
        )

    return {
        "headline": headline,
        "summary": summary,
        "highlights": highlights,
    }


def build_daily_highlights(hours: list[dict[str, Any]]) -> list[str]:
    highlights: list[str] = []

    for flag, label in [("new_moon", "New Moon"), ("full_moon", "Full Moon")]:
        hour = first_hour_with_flag(hours, flag)
        if hour is not None:
            highlights.append(
                f"{label} conditions are active around {hour:02d}:00 UTC with the Moon in {hours[hour]['moon_sign']}."
            )

    moon_sign_counts = Counter(hour["moon_sign"] for hour in hours)
    dominant_sign, dominant_count = moon_sign_counts.most_common(1)[0]
    highlights.append(
        f"The Moon spends {dominant_count} hours in {dominant_sign}, setting the day's dominant emotional tone."
    )

    mercury_hours = [
        hour["hour"] for hour in hours if hour["flags"]["mercury_retrograde"]
    ]
    if len(mercury_hours) == 24:
        highlights.append(
            "Mercury is retrograde throughout the day, favoring extra care with messages, timing, and logistics."
        )
    elif mercury_hours:
        highlights.append(
            "Mercury retrograde is active for part of the day, so communication and planning benefit from review."
        )

    exact_aspect = most_exact_aspect(hours)
    if exact_aspect is not None:
        hour, aspect = exact_aspect
        highlights.append(
            f"The tightest major aspect is {aspect_label(aspect)} near "
            f"{hour:02d}:00 UTC with a {aspect['orb']:.2f} degree orb."
        )

    return highlights


def most_exact_aspect(hours: list[dict[str, Any]]) -> tuple[int, dict[str, Any]] | None:
    candidates = [
        (hour["hour"], aspect) for hour in hours for aspect in hour["aspects"]
    ]
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda item: (
            item[1]["orb"],
            item[0],
            item[1]["planet_a"],
            item[1]["planet_b"],
        ),
    )


def first_hour_with_flag(hours: list[dict[str, Any]], flag: str) -> int | None:
    for hour in hours:
        if hour["flags"][flag]:
            return int(hour["hour"])
    return None


def write_month_file(month: date, generated_at: datetime) -> str:
    month_data = build_month(month, generated_at)
    path = MONTHS_DIR / f"{month:%Y-%m}.json"
    write_json(path, month_data)
    return relative_path(path)


def build_month(month: date, generated_at: datetime) -> dict[str, Any]:
    _, days_in_month = calendar.monthrange(month.year, month.month)
    days = []
    for day_number in range(1, days_in_month + 1):
        day = date(month.year, month.month, day_number)
        noon = build_hour_snapshot(datetime.combine(day, time(hour=12), tzinfo=UTC))
        days.append(
            {
                "date": day.isoformat(),
                "url": f"../days/{day.isoformat()}.json",
                "moon_phase_at_noon": noon["moon_phase"],
                "moon_sign_at_noon": noon["moon_sign"],
                "mercury_retrograde_at_noon": noon["flags"][
                    "mercury_retrograde"
                ],
                "headline": noon["headline"],
            }
        )

    return {
        "month": f"{month:%Y-%m}",
        "timezone": TIMEZONE,
        "generated_at": iso_z(generated_at),
        "days": days,
    }


def write_latest_file(
    today: date, tomorrow: date, current_month: date, generated_at: datetime
) -> None:
    latest = {
        "generated_at": iso_z(generated_at),
        "timezone": TIMEZONE,
        "today": today.isoformat(),
        "tomorrow": tomorrow.isoformat(),
        "today_url": f"./days/{today.isoformat()}.json",
        "tomorrow_url": f"./days/{tomorrow.isoformat()}.json",
        "current_month": f"{current_month:%Y-%m}",
        "current_month_url": f"./months/{current_month:%Y-%m}.json",
        "retention_days": RETENTION_DAYS,
    }
    write_json(DATA_DIR / "latest.json", latest)


def archive_old_days(today: date) -> int:
    cutoff = today - timedelta(days=RETENTION_DAYS)
    old_day_files = []
    for path in sorted(DAYS_DIR.glob("*.json")):
        day = parse_day_filename(path)
        if day is not None and day < cutoff:
            old_day_files.append((day, path))

    archived_count = 0
    for year, files in group_by_year(old_day_files).items():
        archive_path = ARCHIVE_DIR / f"{year}.json.gz"
        archive = load_archive(archive_path, year)
        archive_days = archive.setdefault("days", {})
        changed = False

        for day, path in files:
            day_key = day.isoformat()
            if day_key not in archive_days:
                archive_days[day_key] = read_json(path)
                changed = True

        if changed:
            archive["days"] = dict(sorted(archive_days.items()))
            write_gzip_json(archive_path, archive)

        verified_archive = load_archive(archive_path, year)
        for day, path in files:
            if day.isoformat() in verified_archive.get("days", {}):
                path.unlink()
                archived_count += 1

    return archived_count


def group_by_year(
    day_files: list[tuple[date, Path]],
) -> dict[str, list[tuple[date, Path]]]:
    grouped: dict[str, list[tuple[date, Path]]] = {}
    for day, path in day_files:
        grouped.setdefault(f"{day:%Y}", []).append((day, path))
    return grouped


def load_archive(path: Path, year: str) -> dict[str, Any]:
    if not path.exists():
        return {"year": year, "timezone": TIMEZONE, "days": {}}
    with gzip.open(path, "rt", encoding="utf-8") as file:
        archive = json.load(file)
    archive.setdefault("year", year)
    archive.setdefault("timezone", TIMEZONE)
    archive.setdefault("days", {})
    return archive


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, ensure_ascii=True) + "\n"
    path.write_text(payload, encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_gzip_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, ensure_ascii=True, sort_keys=True).encode(
        "utf-8"
    )
    payload += b"\n"
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with gzip.GzipFile(
        filename=str(tmp_path), mode="wb", compresslevel=9, mtime=0
    ) as file:
        file.write(payload)
    tmp_path.replace(path)


def parse_day_filename(path: Path) -> date | None:
    try:
        return date.fromisoformat(path.stem)
    except ValueError:
        return None


def month_start(day: date) -> date:
    return date(day.year, day.month, 1)


def add_month(month: date) -> date:
    year = month.year + int(month.month == 12)
    next_month = 1 if month.month == 12 else month.month + 1
    return date(year, next_month, 1)


def iso_z(moment: datetime) -> str:
    return moment.astimezone(UTC).replace(tzinfo=None).isoformat(timespec="seconds") + "Z"


def normalize_degrees(value: float) -> float:
    return value % 360


def signed_arc_distance(from_longitude: float, to_longitude: float) -> float:
    return (from_longitude - to_longitude) % 360


def shortest_arc(longitude_a: float, longitude_b: float) -> float:
    difference = abs(longitude_a - longitude_b) % 360
    return min(difference, 360 - difference)


def zodiac_sign(longitude: float) -> str:
    return SIGNS[int(normalize_degrees(longitude) // 30)]


def rounded(value: float, places: int) -> float:
    return round(float(value), places)


def title_planet(name: str) -> str:
    return name.capitalize()


def aspect_verb(aspect: str) -> str:
    if aspect == "sextile":
        return "sextiles"
    if aspect == "square":
        return "squares"
    if aspect == "trine":
        return "trines"
    if aspect == "opposition":
        return "opposes"
    return "conjoins"


def aspect_label(aspect: dict[str, Any]) -> str:
    return (
        f"{title_planet(aspect['planet_a'])} {aspect['aspect']} "
        f"{title_planet(aspect['planet_b'])}"
    )


def aspect_sentence(aspect: dict[str, Any]) -> str:
    template = ASPECT_TEXT[aspect["aspect"]]
    return template.format(
        a=title_planet(aspect["planet_a"]), b=title_planet(aspect["planet_b"])
    )


def relative_path(path: Path) -> str:
    return str(path.relative_to(ROOT_DIR))


if __name__ == "__main__":
    main()
