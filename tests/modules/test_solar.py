from datetime import date, datetime
from zoneinfo import ZoneInfo

from homely.modules.weather.solar import sun_times

CHI = ZoneInfo("America/Chicago")


def minutes_apart(a: datetime, b: datetime) -> float:
    return abs((a - b).total_seconds()) / 60


def test_minneapolis_matches_open_meteo_fixture():
    st = sun_times(44.98, -93.27, date(2026, 9, 13), CHI)
    assert st.sunrise is not None and st.sunset is not None and st.dawn is not None and st.dusk is not None
    assert minutes_apart(st.sunrise, datetime(2026, 9, 13, 6, 49, tzinfo=CHI)) <= 2
    assert minutes_apart(st.sunset, datetime(2026, 9, 13, 19, 27, tzinfo=CHI)) <= 2
    assert st.dawn < st.sunrise < st.noon < st.sunset < st.dusk
    assert 80 <= minutes_apart(st.dawn, st.sunrise) <= 110  # astronomical twilight in September


def test_polar_night_has_no_sunrise():
    st = sun_times(78.2, 15.6, date(2026, 12, 21), ZoneInfo("Europe/Oslo"))  # Svalbard
    assert st.polar and st.sunrise is None
