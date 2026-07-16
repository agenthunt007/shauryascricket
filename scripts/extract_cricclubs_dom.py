import asyncio
import html
import json
import re
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

import websockets


async def fetch_page(page: dict) -> None:
    async with websockets.connect(page["webSocketDebuggerUrl"], max_size=20_000_000) as ws:
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
            if message.get("id") != 1:
                continue
            body = message["result"]["result"].get("value", "")
            slug = urlparse(page.get("url", "")).path.strip("/").split("/", 1)[0] or "cricclubs"
            title_slug = re.sub(r"[^a-zA-Z0-9]+", "-", page.get("title") or slug).strip("-")[:80]
            output_path = Path("/tmp") / f"cricclubs-{slug}-{title_slug}.html"
            output_path.write_text(body)
            links = sorted(set(re.findall(r"""href=["']([^"']+)""", body)))
            match_tokens = sorted(set(re.findall(r"matchId[=:'\"]+(\d+)", body, flags=re.IGNORECASE)))
            score_tokens = sorted(set(re.findall(r"viewScorecard\.do[^\"'\s<)]+", body, flags=re.IGNORECASE)))
            score_links = [
                html.unescape(link)
                for link in links
                if "scorecard" in link.lower() or "viewscorecard" in link.lower()
            ]
            print(f"TITLE: {page.get('title')}")
            print(f"URL: {page.get('url')}")
            print(f"SAVED: {output_path}")
            print(
                f"HTML_BYTES: {len(body)} LINKS: {len(links)} SCORE_LINKS: {len(score_links)} "
                f"MATCH_IDS: {len(match_tokens)} SCORE_TOKENS: {len(score_tokens)}"
            )
            for link in score_links[:100]:
                print(f"  {link}")
            for token in match_tokens[:100]:
                print(f"  matchId={token}")
            for token in score_tokens[:100]:
                print(f"  {html.unescape(token)}")
            print("---")
            return


async def main() -> None:
    pages = json.load(urllib.request.urlopen("http://127.0.0.1:9222/json"))
    targets = [
        page
        for page in pages
        if page.get("type") == "page" and "cricclubs.com" in page.get("url", "")
    ]
    await asyncio.gather(*(fetch_page(page) for page in targets))


if __name__ == "__main__":
    asyncio.run(main())
