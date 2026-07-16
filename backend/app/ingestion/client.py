import httpx


class CricClubsClient:
    def __init__(self, user_agent: str, timeout_seconds: float = 20.0):
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds

    async def fetch_scorecard(self, url: str) -> str:
        async with httpx.AsyncClient(
            headers={"User-Agent": self.user_agent},
            follow_redirects=True,
            timeout=self.timeout_seconds,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text

