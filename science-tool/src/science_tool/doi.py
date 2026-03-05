from __future__ import annotations

import json
from urllib.parse import quote
from urllib.request import urlopen

import click


def lookup_doi_metadata(doi: str) -> dict[str, str]:
    doi = doi.strip()
    if not doi or "/" not in doi:
        raise click.ClickException(f"Invalid DOI: {doi}")

    url = f"https://api.crossref.org/works/{quote(doi)}"
    try:
        with urlopen(url, timeout=10) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise click.ClickException(f"DOI lookup failed: {exc}") from exc

    message = payload.get("message")
    if not isinstance(message, dict):
        raise click.ClickException("DOI lookup returned unexpected response format")

    title_values = message.get("title")
    title = ""
    if isinstance(title_values, list) and title_values:
        title = str(title_values[0])

    metadata = {
        "doi": str(message.get("DOI") or doi),
        "title": title,
        "publisher": str(message.get("publisher") or ""),
        "source": "crossref",
    }

    issued = message.get("issued")
    if isinstance(issued, dict):
        date_parts = issued.get("date-parts")
        if isinstance(date_parts, list) and date_parts and isinstance(date_parts[0], list):
            date_tokens = [str(part) for part in date_parts[0]]
            metadata["issued"] = "-".join(date_tokens)

    link = message.get("URL")
    if isinstance(link, str):
        metadata["url"] = link

    return {key: value for key, value in metadata.items() if value}
