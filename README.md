# TurWeather

A simple Streamlit app that shows the current weather for any city.

- **Live weather data** comes from [Open-Meteo](https://open-meteo.com/). It's free and needs no API key.
- **OpenAI** writes a short, friendly summary of the conditions with advice on what to wear.

## Setup

```bash
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add your OpenAI API key, or paste the key into the app's sidebar.

## Run

```bash
streamlit run app.py
```
