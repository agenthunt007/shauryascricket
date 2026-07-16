import asyncio
import html
import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import websockets
from bs4 import BeautifulSoup


@dataclass(frozen=True)
class DiscoveryTarget:
    league_name: str
    seed_url: str


TARGETS = [
    DiscoveryTarget(
        league_name="Houston United Premier League",
        seed_url="https://cricclubs.com/HoustonUnitedPremierLeague/searchTeams.do?clubId=13647",
    ),
    DiscoveryTarget(
        league_name="Houston Premier T20 League",
        seed_url="https://cricclubs.com/HoustonPremierT20League/searchTeams.do?clubId=1366",
    ),
    DiscoveryTarget(
        league_name="Houston Taped Ball Cricket",
        seed_url="https://cricclubs.com/HTBC/searchTeams.do?clubId=8755",
    ),
    DiscoveryTarget(
        league_name="Saturday Super Cricket League - Houston",
        seed_url="https://cricclubs.com/SSCLHouston/searchTeams.do?clubId=4110",
    ),
    DiscoveryTarget(
        league_name="Triggers Tapedball Cricket League",
        seed_url="https://cricclubs.com/3T/searchTeams.do?clubId=8675",
    ),
]


def chrome_json(path: str):
    return json.load(urllib.request.urlopen(f"http://127.0.0.1:9222{path}"))


def open_tab(url: str) -> None:
    request = urllib.request.Request(
        f"http://127.0.0.1:9222/json/new?{urllib.parse.quote(url, safe='')}",
        method="PUT",
    )
    urllib.request.urlopen(request).read()


def close_tab(page_id: str) -> None:
    try:
        urllib.request.urlopen(f"http://127.0.0.1:9222/json/close/{page_id}").read()
    except Exception:
        pass


async def page_html(page: dict) -> str:
    async with websockets.connect(page["webSocketDebuggerUrl"], max_size=30_000_000) as ws:
        await ws.send(
            json.dumps(
                {
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": "document.documentElement.outerHTML",
                        "returnByValue": True,
                    },
                }
            )
        )
        while True:
            message = json.loads(await ws.recv())
            if message.get("id") == 1:
                return message["result"]["result"].get("value", "")


def same_page(actual_url: str, expected_url: str) -> bool:
    actual = urlparse(actual_url)
    expected = urlparse(expected_url)
    if actual.netloc != expected.netloc or actual.path != expected.path:
        return False
    if expected.path.endswith("/searchTeams.do"):
        return True
    expected_query = urllib.parse.parse_qs(expected.query)
    actual_query = urllib.parse.parse_qs(actual.query)
    for key, values in expected_query.items():
        if key == "year":
            continue
        if actual_query.get(key) != values:
            return False
    return True


async def rendered_html_for_url(url: str, timeout_seconds: int = 30) -> str | None:
    for page in chrome_json("/json"):
        if page.get("type") == "page" and same_page(page.get("url", ""), url):
            body = await page_html(page)
            if "Just a moment" not in body:
                return body
    open_tab(url)
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        for page in chrome_json("/json"):
            if page.get("type") == "page" and same_page(page.get("url", ""), url) and page.get("title"):
                body = await page_html(page)
                if "Just a moment" not in body:
                    close_tab(page["id"])
                    return body
        time.sleep(1)
    return None


async def submit_team_search(url: str, team_name: str = "Shauryas", timeout_seconds: int = 30) -> str | None:
    await rendered_html_for_url(url, timeout_seconds=timeout_seconds)
    deadline = time.time() + timeout_seconds
    target_page = None
    while time.time() < deadline:
        for page in chrome_json("/json"):
            if page.get("type") == "page" and same_page(page.get("url", ""), url):
                target_page = page
                break
        if target_page:
            break
        time.sleep(1)
    if not target_page:
        return None
    async with websockets.connect(target_page["webSocketDebuggerUrl"], max_size=30_000_000) as ws:
        expression = (
            f"document.querySelector('#teamName').value={json.dumps(team_name)}; "
            "document.querySelector('#searchTeam').submit(); 'submitted';"
        )
        await ws.send(
            json.dumps(
                {
                    "id": 2,
                    "method": "Runtime.evaluate",
                    "params": {"expression": expression, "returnByValue": True},
                }
            )
        )
        try:
            while True:
                message = json.loads(await ws.recv())
                if message.get("id") == 2:
                    break
        except websockets.ConnectionClosed:
            pass
    time.sleep(3)
    for page in chrome_json("/json"):
        if page.get("type") == "page" and same_page(page.get("url", ""), url):
            return await page_html(page)
    return None


def discover_team_pages(seed_url: str, body: str) -> list[str]:
    base = f"{urlparse(seed_url).scheme}://{urlparse(seed_url).netloc}"
    soup = BeautifulSoup(body, "html.parser")
    pages = {seed_url}
    for link in soup.find_all("a", href=re.compile(r"viewTeams\.do")):
        href = html.unescape(link.get("href") or "")
        if not href:
            continue
        pages.add(urljoin(base, href))
    return sorted(pages)


def find_shauryas_team_links(page_url: str, body: str) -> list[dict]:
    base = f"{urlparse(page_url).scheme}://{urlparse(page_url).netloc}"
    soup = BeautifulSoup(body, "html.parser")
    results = []
    for link in soup.find_all("a", href=re.compile(r"viewTeam\.do")):
        name = " ".join(link.get_text(" ", strip=True).split())
        if "shauryas" not in name.lower():
            continue
        href = urljoin(base, html.unescape(link.get("href") or ""))
        parsed = urlparse(href)
        query = urllib.parse.parse_qs(parsed.query)
        results.append(
            {
                "name": name,
                "team_url": href,
                "results_url": href.replace("viewTeam.do", "teamResults.do"),
                "team_id": (query.get("teamId") or [""])[0],
                "league_id": (query.get("league") or [""])[0],
                "club_id": (query.get("clubId") or [""])[0],
                "source_page": page_url,
                "source_title": soup.title.string.strip() if soup.title and soup.title.string else "",
            }
        )
    return results


async def main() -> None:
    all_results = []
    for target in TARGETS:
        print(f"target: {target.league_name}", flush=True)
        seed_body = await submit_team_search(target.seed_url)
        if not seed_body:
            print(f"  seed failed: {target.seed_url}", flush=True)
            continue
        for result in find_shauryas_team_links(target.seed_url, seed_body):
            result["league_name"] = target.league_name
            all_results.append(result)
            print(json.dumps(result, sort_keys=True), flush=True)
    print(json.dumps({"found": len(all_results), "teams": all_results}, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
