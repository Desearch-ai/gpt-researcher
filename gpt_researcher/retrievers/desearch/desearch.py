"""Web search through the Desearch API."""

import os

import requests


class DesearchSearch:
    """Return Desearch web results in the researcher's search result format."""

    def __init__(self, query, query_domains=None):
        self.query = query
        # Accepted for compatibility; the endpoint has no domain filter parameter.
        self.query_domains = query_domains
        self.api_key = os.environ.get("DESEARCH_API_KEY")
        if not self.api_key or not self.api_key.strip():
            raise ValueError("Set the DESEARCH_API_KEY environment variable.")

    def search(self, max_results=7):
        """Fetch up to max_results results; return an empty list on API failure."""
        if max_results <= 0:
            return []
        try:
            response = requests.get(
                "https://api.desearch.ai/web",
                params={"query": self.query, "num": max_results},
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError):
            # Request exceptions can carry authenticated request details.
            return []

        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            return []
        results = []
        for item in data:
            if not isinstance(item, dict):
                continue
            link = item.get("link")
            if not isinstance(link, str) or not link.strip():
                continue
            results.append({
                "title": item.get("title") if isinstance(item.get("title"), str) else "",
                "href": link,
                "body": item.get("snippet") if isinstance(item.get("snippet"), str) else "",
            })
            if len(results) >= max_results:
                break
        return results
