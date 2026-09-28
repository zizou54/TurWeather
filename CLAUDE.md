# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
pip install -r requirements.txt
streamlit run app.py          # serves on http://localhost:8501
```

There are no tests, linter, or build step. Verify changes by running the app and exercising it in a browser (`.claude/launch.json` defines a `turweather` preview config on port 8501). A quick syntax check: `python -c "import ast; ast.parse(open('app.py', encoding='utf-8').read())"`.

Streamlit 1.64 is installed; the code relies on newer APIs (`st.container(horizontal=True)`, `horizontal_alignment=`, `st.context.theme`, `st.html`).

## Architecture

Everything lives in `app.py`, a single top-to-bottom Streamlit script that reruns in full on every interaction.

- **Data flow:** city name → Open-Meteo geocoding (`geocode`) → Open-Meteo forecast (`fetch_weather`, current + daily in one request) → `forecast_days` reshapes Open-Meteo's column-oriented `daily` arrays into one dict per day → rendered as metrics and forecast cards → `ai_summary` sends the same data to OpenAI for a prose summary.
- **Weather data needs no key; only the AI summary uses OpenAI.** The model is never asked for weather itself — it only summarizes the Open-Meteo numbers passed in the prompt. Key comes from `OPENAI_API_KEY` (`.env`, loaded via python-dotenv) or the sidebar input; model from `OPENAI_MODEL` (default `gpt-4o-mini`).
- **Caching:** `geocode` (1 h), `fetch_weather` and `ai_summary` (10 min) use `st.cache_data`. Caching `ai_summary` matters: any rerun would otherwise re-bill OpenAI.
- **Open-Meteo limits:** `FORECAST_DAYS` max is 16 (the API rejects larger values). Weather codes are WMO codes mapped in `WEATHER_CODES`.

### Session-state conventions (non-obvious)

- Results render from `st.session_state.query`, not from the submit button's return value, so they survive unrelated reruns (e.g. the dark mode toggle). `submitted` only sets/clears `query`.
- The **Refresh** button uses an `on_click` callback (`reset_form`) because a widget's session-state value (`city`) can't be changed after the widget is drawn in the same run.
- **Dark mode** is CSS injected by `apply_theme` each run, keyed off `st.session_state.dark_mode`. Streamlit can't switch themes at runtime: `st._config.set_option("theme.base", ...)` was tried and the browser ignored it. The CSS targets Streamlit `data-testid` / `data-baseweb` selectors, so new widget types may need selectors added to both palettes in `THEMES`. Streamlit's own menus/dialogs still follow the browser theme.

## Workflow

- Remote: https://github.com/zizou54/TurWeather, default branch `main`. Small changes have been committed straight to `main`; dark mode went through a feature branch and PR. The GitHub CLI (`gh`) is not installed.
- `.env` holds the real OpenAI key and is gitignored; `.env.example` is the template.
- On Windows, stopping the preview server can leave the `python -m streamlit` process holding port 8501; find it with `Get-NetTCPConnection -LocalPort 8501` and stop it before restarting.
