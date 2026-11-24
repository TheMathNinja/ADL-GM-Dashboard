"""Prepare the pinned headless browser before any official league writes."""
import subprocess
import sys
from time import sleep

from playwright.sync_api import Error, sync_playwright


def playwright(*arguments, timeout):
    subprocess.run([sys.executable, '-m', 'playwright', *arguments], check=True, timeout=timeout)


def download_shell():
    command = [sys.executable, '-m', 'playwright', 'install', '--only-shell', 'chromium']
    for attempt in range(2):
        try:
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, check=True, timeout=55)
            print(result.stdout, end='')
            return
        except subprocess.TimeoutExpired:
            if attempt:
                raise
        except subprocess.CalledProcessError as error:
            output = error.stdout or ''
            print(output, end='')
            transient = ('econnreset', 'etimedout', 'timed out', 'eai_again', '502', '503', '504')
            if attempt or not any(marker in output.lower() for marker in transient):
                raise
        print('Chromium download did not finish; retrying the same pinned shell once.')
        sleep(3)


def smoke():
    with sync_playwright() as runtime:
        with runtime.chromium.launch(timeout=15000) as browser:
            page = browser.new_page()
            page.goto('about:blank', timeout=10000)
            if page.evaluate('1 + 1') != 2:
                raise RuntimeError('Chromium did not execute the smoke test')


def prepare():
    try:
        smoke()
    except Error as error:
        if "executable doesn't exist" in str(error).lower():
            download_shell()
            try:
                smoke()
            except Error as installed_error:
                repair_missing_libraries(installed_error)
        else:
            repair_missing_libraries(error)
    print('Pinned headless Chromium launched and ran JavaScript.')


def repair_missing_libraries(error):
    message = str(error).lower()
    missing_libraries = 'host system is missing' in message or 'error while loading shared libraries' in message
    if not sys.platform.startswith('linux') or not missing_libraries:
        raise error
    playwright('install-deps', 'chromium', timeout=150)
    smoke()


if __name__ == '__main__':
    prepare()
