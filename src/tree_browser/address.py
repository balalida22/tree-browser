"""URL normalization independent of the Qt user interface."""

from urllib.parse import quote_plus

HOME_URL = "https://www.google.com"


def normalise_address(address: str) -> str:
    """Turn user input into a navigable URL or a web search URL."""
    address = address.strip()
    if not address:
        return HOME_URL
    if " " in address or "." not in address.split("/")[0]:
        return f"https://www.google.com/search?q={quote_plus(address)}"
    if "://" not in address:
        return f"https://{address}"
    return address
