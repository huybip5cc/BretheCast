from ui.assets import aqi_icon_data, weather_icon_data


def test_icons_load_from_shared_assets_directory():
    assert weather_icon_data("sun.png").startswith("data:image/png;base64,")
    assert aqi_icon_data("clock.png").startswith("data:image/png;base64,")
