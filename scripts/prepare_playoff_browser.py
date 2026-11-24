"""Prepare the pinned headless browser before any official league writes."""
import subprocess
import sys

from playwright.sync_api import Error, sync_playwright


def playwright(*arguments, timeout):
    subprocess.run([sys.executable, '-m', 'playwright', *arguments], check=True, timeout=timeout)


def smoke():
    with sync_playwright() as runtime:
        with runtime.chromium.launch(timeout=15000) as browser:
            page = browser.new_page()
            page.goto('about:blank', timeout=10000)
            if page.evaluate('1 + 1') != 2:
                raise RuntimeError('Chromium did not execute the smoke test')


def prepare():
    playwright('install', '--only-shell', 'chromium', timeout=100)
    try:
        smoke()
    except Error as error:
        message = str(error).lower()
        missing_libraries = 'host system is missing' in message or 'error while loading shared libraries' in message
        if not sys.platform.startswith('linux') or not missing_libraries:
            raise
        playwright('install-deps', 'chromium', timeout=150)
        smoke()
    print('Pinned headless Chromium launched and ran JavaScript.')


if __name__ == '__main__':
    prepare()
