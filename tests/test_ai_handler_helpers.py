import re
import asyncio

from app.ai_handler import _parse_date, _looks_like_expected_input
from app.ai_handler import _resolve_room


def test_parse_date_rejects_invalid_dates():
    assert _parse_date("31.02") is None
    assert _parse_date("2026-02-31") is None


def test_parse_date_accepts_iso_and_dmy_with_year_without_rollover():
    iso = _parse_date("2026-12-11")
    dmy = _parse_date("11.12.2026")

    assert iso == "2026-12-11"
    assert dmy == "2026-12-11"


def test_looks_like_expected_phone_and_room():
    rooms = [{"name": "VIP Room"}, {"name": "Family Room"}]

    assert _looks_like_expected_input("phone", "+998901112233", rooms)
    assert _looks_like_expected_input("room", "vip", rooms)
    assert not _looks_like_expected_input("room", "qaysi yaxshi", rooms)


def test_parse_date_month_name_format_returns_iso():
    parsed = _parse_date("5 fevral")
    assert parsed is not None
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", parsed)


def test_parse_date_finds_dd_mm_inside_sentence():
    parsed = _parse_date("kelish sanasi 11.12 bo'lsin")
    assert parsed is not None
    assert parsed.endswith("-12-11")


def test_resolve_room_supports_numeric_room_id_without_crash():
    rooms = [{"id": 101, "name": "Standart Room"}, {"id": 202, "name": "VIP Room"}]
    selected = asyncio.run(_resolve_room({}, "101 xona", rooms))
    assert selected is not None
    assert selected["id"] == 101
