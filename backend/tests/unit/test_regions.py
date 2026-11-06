from app.validation.regions import REGION_TIMEZONES, normalize_region, timezone_for_region


def test_region_catalog_covers_all_federal_subjects():
    assert len(REGION_TIMEZONES) == 85


def test_region_timezones_use_administrative_centers():
    assert timezone_for_region("Белгородская область") == "Europe/Moscow"
    assert timezone_for_region("Калининградская область") == "Europe/Kaliningrad"
    assert timezone_for_region("Самарская область") == "Europe/Samara"
    assert timezone_for_region("Свердловская область") == "Asia/Yekaterinburg"
    assert timezone_for_region("Республика Саха (Якутия)") == "Asia/Yakutsk"
    assert timezone_for_region("Камчатский край") == "Asia/Kamchatka"


def test_normalize_region_trims_and_rejects_unknown():
    assert normalize_region("  Москва  ") == "Москва"
    assert normalize_region(None) is None
    try:
        normalize_region("Москва и область")
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("unknown region must be rejected")
