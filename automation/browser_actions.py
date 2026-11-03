"""
VERONIKA AI - Browser Actions
Opens websites, browser searches, and manages browser interactions.
"""
import logging
import subprocess
import webbrowser
from typing import Dict
from urllib.parse import quote_plus

from automation.permissions import permissions

logger = logging.getLogger(__name__)

# Known Windows Settings pages (ms-settings: URIs)
SETTINGS_PAGES = {
    "display": "ms-settings:display",
    "sound": "ms-settings:sound",
    "notifications": "ms-settings:notifications",
    "power": "ms-settings:powersleep",
    "battery": "ms-settings:batterysaver",
    "storage": "ms-settings:storagesense",
    "bluetooth": "ms-settings:bluetooth",
    "wifi": "ms-settings:network-wifi",
    "network": "ms-settings:network-status",
    "vpn": "ms-settings:network-vpn",
    "background": "ms-settings:personalization-background",
    "colors": "ms-settings:personalization-colors",
    "lock screen": "ms-settings:lockscreen",
    "themes": "ms-settings:themes",
    "apps": "ms-settings:appsfeatures",
    "default apps": "ms-settings:defaultapps",
    "about": "ms-settings:about",
    "windows update": "ms-settings:windowsupdate",
    "date time": "ms-settings:dateandtime",
    "language": "ms-settings:regionlanguage",
    "keyboard": "ms-settings:keyboard",
    "mouse": "ms-settings:mousetouchpad",
    "privacy": "ms-settings:privacy",
    "accounts": "ms-settings:yourinfo",
}


class BrowserActions:
    """Safe browser and URL operations."""

    def open_url(self, url: str) -> Dict:
        """Open a URL in the default browser."""
        result = {"success": False, "message": ""}

        if not permissions.validate_url(url):
            result["message"] = (
                f"Invalid or unsafe URL: {url}. "
                "Only http:// and https:// URLs are allowed."
            )
            return result

        try:
            webbrowser.open(url)
            result["success"] = True
            result["message"] = f"Opened {url} in default browser"
        except Exception as e:
            result["message"] = f"Failed to open URL: {e}"

        return result

    def browser_search(self, query: str) -> Dict:
        """Open a search query in the default browser."""
        result = {"success": False, "message": ""}

        if not query.strip():
            result["message"] = "Search query cannot be empty."
            return result

        url = f"https://www.google.com/search?q={quote_plus(query)}"
        try:
            webbrowser.open(url)
            result["success"] = True
            result["message"] = f"Searching for: {query}"
        except Exception as e:
            result["message"] = f"Failed to open browser search: {e}"

        return result

    def open_youtube(self, query: str = "") -> Dict:
        """Open YouTube, optionally with a search query."""
        if query:
            url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
        else:
            url = "https://www.youtube.com"
        return self.open_url(url)

    def open_settings(self, page: str) -> Dict:
        """Open a Windows Settings page."""
        result = {"success": False, "message": ""}

        page_lower = page.lower().strip()
        uri = SETTINGS_PAGES.get(page_lower)

        if not uri:
            # Try direct ms-settings URI
            if page.startswith("ms-settings:"):
                uri = page
            else:
                available = ", ".join(sorted(SETTINGS_PAGES.keys()))
                result["message"] = (
                    f"Unknown settings page: '{page}'. "
                    f"Available pages: {available}"
                )
                return result

        try:
            subprocess.Popen(["cmd", "/c", "start", uri], creationflags=subprocess.CREATE_NO_WINDOW)
            result["success"] = True
            result["message"] = f"Opened Windows Settings: {page}"
        except Exception as e:
            result["message"] = f"Failed to open settings: {e}"

        return result

    def get_available_settings(self) -> list:
        """Return list of available settings pages."""
        return sorted(SETTINGS_PAGES.keys())
