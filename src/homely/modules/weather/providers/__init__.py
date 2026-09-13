from homely.modules.weather.providers.base import Current, Daily, Forecast, Hourly, WeatherProvider
from homely.modules.weather.providers.open_meteo import OpenMeteoProvider

PROVIDERS: dict[str, type[WeatherProvider]] = {"open_meteo": OpenMeteoProvider}

__all__ = ["PROVIDERS", "Current", "Daily", "Forecast", "Hourly", "OpenMeteoProvider", "WeatherProvider"]
