import argparse
from functools import partial
from hashlib import sha256
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from time import monotonic, sleep
from urllib.request import Request, urlopen

from playwright.sync_api import expect, sync_playwright


def verify(page, url):
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    conference_teams = {}
    for conference in ("AFC", "NFC"):
        button = page.locator(f'button[data-conf="{conference}"]')
        button.click()
        expect(button).to_have_attribute("aria-pressed", "true")
        teams = page.locator(".adl-team:visible, .fafl-team:visible")
        expect(teams).to_have_count(16)
        conference_teams[conference] = set(teams.all_text_contents())
        if len(conference_teams[conference]) != 16 or "" in conference_teams[conference]:
            raise AssertionError(f"{conference} franchise names are blank or duplicated")
    if conference_teams["AFC"] & conference_teams["NFC"]:
        raise AssertionError("The conference toggle did not switch the franchise list")
    expect(page.locator("footer.adl-foot, footer.fafl-foot")).to_contain_text("2021\u20132025 training data")
    if errors:
        raise AssertionError("Uncaught JavaScript errors: " + "; ".join(errors))


def wait_for_publication(url, expected):
    deadline = monotonic() + 270
    while monotonic() < deadline:
        candidate = f"{url}?playoff-check={monotonic()}"
        try:
            with urlopen(Request(candidate, headers={"Cache-Control": "no-cache"}), timeout=15) as response:
                if sha256(response.read()).digest() == expected:
                    return candidate
        except OSError:
            pass
        sleep(5)
    raise RuntimeError("GitHub Pages did not serve the newly generated Playoff Picture")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live-url")
    parser.add_argument("--executable")
    args = parser.parse_args()
    docs = Path("docs")
    server = None
    if args.live_url:
        url = wait_for_publication(args.live_url, sha256((docs / "playoff-picture/index.html").read_bytes()).digest())
    else:
        server = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(docs)))
        Thread(target=server.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{server.server_port}/playoff-picture/"
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=args.executable)
            verify(browser.new_page(), url)
        print("Playoff Picture passed: both conference views, franchise rows, footer, and JavaScript.")
    finally:
        if server:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()

