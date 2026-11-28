#!/bin/zsh
cd "$(dirname "$0")"
exec .venv/bin/python -m streamlit run app.py
