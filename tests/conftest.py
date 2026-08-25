"""Pytest configuration: load .env before test collection so skipif checks see API keys."""

from dotenv import load_dotenv

load_dotenv()
