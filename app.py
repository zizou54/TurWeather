"""TurWeather - a simple Streamlit weather app powered by Open-Meteo and OpenAI."""

import os
from datetime import date

import requests
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
FORECAST_DAYS = 16  # Open-Meteo maximum
CARDS_PER_ROW = 4

# WMO weather interpretation codes -> (description, emoji)
WEATHER_CODES = {
    0: ("Clear sky", "☀️"),
    1: ("Mainly clear", "🌤️"),
    2: ("Partly cloudy", "⛅"),
    3: ("Overcast", "☁️"),
    45: ("Fog", "🌫️"),
    48: ("Depositing rime fog", "🌫️"),
    51: ("Light drizzle", "🌦️"),
    53: ("Moderate drizzle", "🌦️"),
    55: ("Dense drizzle", "🌧️"),
    56: ("Light freezing drizzle", "🌧️"),
    57: ("Dense freezing drizzle", "🌧️"),
    61: ("Slight rain", "🌦️"),
    63: ("Moderate rain", "🌧️"),
    65: ("Heavy rain", "🌧️"),
    66: ("Light freezing rain", "🌧️"),
    67: ("Heavy freezing rain", "🌧️"),
    71: ("Slight snowfall", "🌨️"),
    73: ("Moderate snowfall", "🌨️"),
    75: ("Heavy snowfall", "❄️"),
    77: ("Snow grains", "🌨️"),
    80: ("Slight rain showers", "🌦️"),
    81: ("Moderate rain showers", "🌧️"),
    82: ("Violent rain showers", "⛈️"),
    85: ("Slight snow showers", "🌨️"),
    86: ("Heavy snow showers", "❄️"),
    95: ("Thunderstorm", "⛈️"),
    96: ("Thunderstorm with slight hail", "⛈️"),
    99: ("Thunderstorm with heavy hail", "⛈️"),
}


@st.cache_data(ttl=3600)
def geocode(city: str) -> dict | None:
    """Look up a city's coordinates. Returns None if not found."""
    resp = requests.get(GEOCODE_URL, params={"name": city, "count": 1}, timeout=10)
    resp.raise_for_status()
    results = resp.json().get("results")
    return results[0] if results else None


@st.cache_data(ttl=600)
def fetch_weather(lat: float, lon: float) -> dict:
    """Fetch current conditions and a daily forecast for the given coordinates."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": ",".join([
            "temperature_2m",
            "apparent_temperature",
            "relative_humidity_2m",
            "wind_speed_10m",
            "precipitation",
            "weather_code",
            "is_day",
        ]),
        "daily": ",".join([
            "weather_code",
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_probability_max",
            "wind_speed_10m_max",
        ]),
        "forecast_days": FORECAST_DAYS,
        "timezone": "auto",
    }
    resp = requests.get(FORECAST_URL, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def forecast_days(daily: dict) -> list[dict]:
    """Turn Open-Meteo's column-oriented daily data into one dict per day."""
    days = []
    for i, date_str in enumerate(daily["time"]):
        day = date.fromisoformat(date_str)
        description, emoji = WEATHER_CODES.get(daily["weather_code"][i], ("Unknown", "🌡️"))
        days.append({
            "label": "Today" if i == 0 else day.strftime("%a"),
            "date": day.strftime("%b %d"),
            "description": description,
            "emoji": emoji,
            "max": daily["temperature_2m_max"][i],
            "min": daily["temperature_2m_min"][i],
            "rain_chance": daily["precipitation_probability_max"][i],
            "wind": daily["wind_speed_10m_max"][i],
        })
    return days


def ai_summary(api_key: str, place: str, weather: dict, description: str, days: list[dict]) -> str:
    """Ask OpenAI for a short, friendly summary with practical advice."""
    client = OpenAI(api_key=api_key)
    outlook = "\n".join(
        f"- {d['label']} {d['date']}: {d['description']}, {d['min']}–{d['max']}°C, "
        f"{d['rain_chance']}% chance of rain, wind up to {d['wind']} km/h"
        for d in days
    )
    prompt = (
        f"Current weather in {place}: {description}, "
        f"{weather['temperature_2m']}°C (feels like {weather['apparent_temperature']}°C), "
        f"humidity {weather['relative_humidity_2m']}%, "
        f"wind {weather['wind_speed_10m']} km/h, "
        f"precipitation {weather['precipitation']} mm, "
        f"{'daytime' if weather['is_day'] else 'nighttime'}, local time {weather['time']}.\n\n"
        f"{len(days)}-day forecast:\n{outlook}\n\n"
        "Write a friendly 3-4 sentence summary: describe current conditions, suggest "
        "what to wear or whether to bring an umbrella, and highlight any notable "
        "changes in the coming days. Use only the data given."
    )
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": "You are TurWeather, a concise and friendly weather assistant."},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content


st.set_page_config(page_title="TurWeather", page_icon="🌤️")
st.title("🌤️ TurWeather")
st.caption("Current weather for any city, with an AI-powered summary.")

with st.sidebar:
    st.header("Settings")
    api_key = st.text_input(
        "OpenAI API key",
        value=os.getenv("OPENAI_API_KEY", ""),
        type="password",
        help="Read from OPENAI_API_KEY if set.",
    )

with st.form("search"):
    city = st.text_input("City", placeholder="e.g. Istanbul")
    submitted = st.form_submit_button("Get weather")

if submitted:
    if not city.strip():
        st.warning("Please enter a city name.")
        st.stop()

    try:
        location = geocode(city.strip())
    except requests.RequestException as exc:
        st.error(f"Could not reach the geocoding service: {exc}")
        st.stop()

    if location is None:
        st.error(f"City '{city}' not found.")
        st.stop()

    place = ", ".join(
        part for part in (location.get("name"), location.get("admin1"), location.get("country")) if part
    )

    try:
        data = fetch_weather(location["latitude"], location["longitude"])
    except requests.RequestException as exc:
        st.error(f"Could not fetch weather data: {exc}")
        st.stop()

    weather = data["current"]
    days = forecast_days(data["daily"])

    description, emoji = WEATHER_CODES.get(weather["weather_code"], ("Unknown", "🌡️"))

    st.subheader(f"{emoji} {place}")
    st.write(f"**{description}** · local time {weather['time'].replace('T', ' ')}")

    col1, col2, col3 = st.columns(3)
    col1.metric("Temperature", f"{weather['temperature_2m']} °C", f"feels {weather['apparent_temperature']} °C", delta_color="off")
    col2.metric("Humidity", f"{weather['relative_humidity_2m']} %")
    col3.metric("Wind", f"{weather['wind_speed_10m']} km/h")

    st.divider()
    st.markdown(f"#### 📅 {len(days)}-day forecast")
    for start in range(0, len(days), CARDS_PER_ROW):
        for col, d in zip(st.columns(CARDS_PER_ROW), days[start:start + CARDS_PER_ROW]):
            with col.container(border=True):
                st.markdown(f"**{d['label']}**  \n{d['date']}")
                st.markdown(f"<div style='font-size:2rem'>{d['emoji']}</div>", unsafe_allow_html=True)
                st.caption(d["description"])
                st.markdown(f"**{round(d['max'])}°** / {round(d['min'])}°")
                st.caption(f"💧 {d['rain_chance']}% · 💨 {round(d['wind'])} km/h")

    st.divider()
    st.markdown("#### 🤖 AI summary")
    if not api_key:
        st.info("Add your OpenAI API key in the sidebar to get an AI summary.")
    else:
        with st.spinner("Asking OpenAI..."):
            try:
                st.write(ai_summary(api_key, place, weather, description, days))
            except Exception as exc:
                st.error(f"OpenAI request failed: {exc}")
