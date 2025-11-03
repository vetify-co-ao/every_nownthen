#!/usr/bin/env python3
"""
Say Hello Script

A simple example script that demonstrates the Every Now & Then script runner.
This script reads environment variables and prints a greeting message.
"""

import os
from datetime import datetime


def main():
    """Main entry point for the say_hello script."""

    # Get environment variables with defaults
    name = os.getenv("GREETING_NAME", "World")
    language = os.getenv("GREETING_LANGUAGE", "en")

    # Greetings in different languages
    greetings = {
        "en": "Hello",
        "pt": "Olá",
        "es": "Hola",
        "fr": "Bonjour",
        "de": "Hallo",
    }

    greeting = greetings.get(language, greetings["en"])

    # Print greeting with timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {greeting}, {name}!")
    print(f"[{timestamp}] Script executed successfully from Every Now & Then")

    # Optional: Show some environment info
    script_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"[{timestamp}] Running from: {script_dir}")

    return 0


if __name__ == "__main__":
    exit(main())
