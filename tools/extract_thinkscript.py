#! /usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "requests>=2.28",
# ]
# ///
"""
Extract thinkScript source code from a thinkorswim tos.mx shortlink.

Usage:
    ./extract_thinkscript.py <tos.mx URL or sharing ID>

Example:
    ./extract_thinkscript.py https://tos.mx/3Kykh6C
    ./extract_thinkscript.py 3Kykh6C

How it works:
    1. Follows the tos.mx redirect to the thinkorswim sharing page.
    2. Extracts the tossc: sharing ID from the page HTML.
    3. Fetches the actual thinkScript source code from the thinkorswim
       sharing API using the sharing ID.
"""

import argparse
import base64
import binascii
import json
import re
import sys
import urllib.parse
import zlib
from html.parser import HTMLParser

import requests

# Base URL for tos.mx sharing site
TOSMX_BASE = "https://tos.mx"

# Sharing IDs are short alphanumeric strings (typically 7 chars).
# Anything longer than this is likely encoded content, not an ID.
MAX_SHARING_ID_LENGTH = 20

# Known API endpoints to try for fetching shared content.
#
# Architecture (from decompiled tos-suit-1991.3.0.jar):
#   tossc: URL → PlatformProtocol.TOSSC.getURLValue(url)
#     → SharedConfigurationManager.addLinkFromSharingCenter(sharingId)
#   The desktop app registers tossc: as a custom protocol handler via
#   nptossc.dll (Windows) dispatching through WindowsCommandHelper →
#   WindowsSharedConfigurationLauncher → SharedConfigurationRunHelper.
#   Server endpoint: toslc.thinkorswim.com (from SuitStartupManager).
#
# The tossc: protocol link just contains a short ID that the desktop app
# uses to retrieve the content. These endpoints are the known ways to
# fetch it externally.
SHARING_API_ENDPOINTS = [
    # toslc.thinkorswim.com - primary sharing server (from JAR decompilation)
    "https://toslc.thinkorswim.com/api/sharing/{sharing_id}",
    "https://toslc.thinkorswim.com/api/shared/{sharing_id}",
    "https://toslc.thinkorswim.com/api/content/{sharing_id}",
    "https://toslc.thinkorswim.com/sharing/{sharing_id}",
    # tos.mx API patterns
    "{base}/api/sharing/{sharing_id}",
    "{base}/api/shared/{sharing_id}",
    "{base}/api/content/{sharing_id}",
    "{base}/sharing/{sharing_id}",
    "{base}/shared/{sharing_id}",
    # trade.thinkorswim.com patterns
    "https://trade.thinkorswim.com/sharing/study/{sharing_id}",
    "https://trade.thinkorswim.com/sharing/watchlistcolumn/{sharing_id}",
    "https://trade.thinkorswim.com/sharing/strategy/{sharing_id}",
    "https://trade.thinkorswim.com/sharing/scan/{sharing_id}",
    "https://trade.thinkorswim.com/api/sharing/{sharing_id}",
]


class TosPageParser(HTMLParser):
    """Parse the tos.mx/thinkorswim sharing page to find tossc: links."""

    # Matches tossc: with or without // (e.g. "tossc:3Kykh6C" or "tossc://...")
    TOSSC_RE = re.compile(r'tossc:/?/?[^\s"\'<>\\]+')

    def __init__(self):
        super().__init__()
        self.tossc_links = []
        self.content_type = None  # e.g. "Custom Watchlist Column"

    def handle_starttag(self, tag, attrs):
        for _name, value in attrs:
            if value and "tossc:" in value:
                for match in self.TOSSC_RE.finditer(value):
                    self.tossc_links.append(match.group(0))

    def handle_data(self, data):
        for match in self.TOSSC_RE.finditer(data):
            self.tossc_links.append(match.group(0))
        # Try to capture the content type from the page title
        if "Open shared" in data:
            match = re.search(r"Open shared (.+?) in thinkorswim", data)
            if match:
                self.content_type = match.group(1)


def fetch_url(url, follow_redirects=True):
    """Fetch a URL and return (final_url, response_body)."""
    resp = requests.get(url, allow_redirects=follow_redirects, timeout=30)
    resp.raise_for_status()
    return resp.url, resp.text


def extract_sharing_id(html):
    """Extract the tossc: sharing ID from HTML page content.

    Returns (sharing_id, content_type) tuple.
    """
    parser = TosPageParser()
    parser.feed(html)

    sharing_id = None
    if parser.tossc_links:
        # Strip the tossc: prefix (and optional //) to get the ID
        sharing_id = re.sub(r'^tossc:/?/?', '', parser.tossc_links[0])

    if not sharing_id:
        # Try regex as fallback
        match = re.search(r'tossc:/?/?([^\s"\'<>\\]+)', html)
        if match:
            sharing_id = match.group(1)

    return sharing_id, parser.content_type


def fetch_shared_content(sharing_id):
    """Fetch thinkScript source code from the sharing API using the ID.

    Tries multiple known/likely API endpoints to retrieve the content
    associated with the sharing ID.

    Returns the thinkScript source code string, or None if not found.
    """
    session = requests.Session()
    # Set headers to look like the thinkorswim client
    session.headers.update({
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "Mozilla/5.0 (compatible; thinkorswim)",
    })

    for endpoint_template in SHARING_API_ENDPOINTS:
        endpoint = endpoint_template.format(
            base=TOSMX_BASE, sharing_id=sharing_id
        )
        try:
            print(f"  Trying: {endpoint}", file=sys.stderr)
            resp = session.get(endpoint, timeout=15)
            if resp.status_code == 200:
                content = _parse_api_response(resp)
                if content:
                    return content
        except requests.RequestException:
            continue

    return None


def _parse_api_response(resp):
    """Parse a sharing API response to extract thinkScript content.

    The response could be:
    - JSON with a field containing the script source
    - Plain text thinkScript
    - HTML with embedded script content
    - Base64-encoded content
    """
    content_type = resp.headers.get("Content-Type", "")
    text = resp.text.strip()

    if not text:
        return None

    # Try JSON response
    if "json" in content_type or text.startswith(("{", "[")):
        try:
            data = resp.json()
            return _extract_from_json(data)
        except (json.JSONDecodeError, ValueError):
            pass

    # Try plain text (if it looks like thinkScript)
    if looks_like_thinkscript(text):
        return text

    # Try base64-encoded content
    decoded = try_base64_decode(text)
    if decoded:
        result = try_decompress(decoded)
        if result and looks_like_thinkscript(result):
            return result
        try:
            result = decoded.decode("utf-8")
            if looks_like_thinkscript(result):
                return result
        except UnicodeDecodeError:
            pass

    return None


def _extract_from_json(data):
    """Recursively search JSON data for thinkScript content."""
    if isinstance(data, str):
        if looks_like_thinkscript(data):
            return data
        # Try base64 decoding
        decoded = try_base64_decode(data)
        if decoded:
            result = try_decompress(decoded)
            if result and looks_like_thinkscript(result):
                return result
            try:
                result = decoded.decode("utf-8")
                if looks_like_thinkscript(result):
                    return result
            except UnicodeDecodeError:
                pass
        return None

    if isinstance(data, dict):
        # Check known field names first
        for key in ["source", "script", "code", "content", "data",
                    "thinkScript", "thinkscript", "body", "text"]:
            if key in data:
                result = _extract_from_json(data[key])
                if result:
                    return result
        # Check all values
        for value in data.values():
            result = _extract_from_json(value)
            if result:
                return result

    if isinstance(data, list):
        for item in data:
            result = _extract_from_json(item)
            if result:
                return result

    return None


def try_base64_decode(data):
    """Attempt base64 decoding with various padding fixes."""
    data_stripped = data.strip()
    # Skip very short strings (sharing IDs, not encoded content)
    if len(data_stripped) < MAX_SHARING_ID_LENGTH:
        return None

    # Try standard base64
    for candidate in [data_stripped, data_stripped + "=", data_stripped + "=="]:
        try:
            return base64.b64decode(candidate)
        except (ValueError, binascii.Error):
            pass

    # Try URL-safe base64
    for candidate in [data_stripped, data_stripped + "=", data_stripped + "=="]:
        try:
            return base64.urlsafe_b64decode(candidate)
        except (ValueError, binascii.Error):
            pass

    return None


def try_decompress(data):
    """Try various decompression methods on binary data."""
    # Try raw deflate
    try:
        decompressed = zlib.decompress(data, -zlib.MAX_WBITS)
        return decompressed.decode("utf-8")
    except (zlib.error, UnicodeDecodeError):
        pass

    # Try zlib (with header)
    try:
        decompressed = zlib.decompress(data)
        return decompressed.decode("utf-8")
    except (zlib.error, UnicodeDecodeError):
        pass

    # Try gzip
    try:
        decompressed = zlib.decompress(data, zlib.MAX_WBITS | 16)
        return decompressed.decode("utf-8")
    except (zlib.error, UnicodeDecodeError):
        pass

    return None


def looks_like_thinkscript(text):
    """Heuristic check if text looks like thinkScript code."""
    keywords = [
        "declare",
        "input",
        "def ",
        "plot ",
        "AddCloud",
        "AddLabel",
        "MovingAverage",
        "close",
        "open",
        "high",
        "low",
        "volume",
    ]
    return any(kw in text for kw in keywords)


def extract_from_shortlink(url):
    """Main function: extract thinkScript from a tos.mx shortlink.

    Args:
        url: A tos.mx shortlink URL (e.g., https://tos.mx/3Kykh6C)
             or a bare sharing ID (e.g., 3Kykh6C)

    Returns:
        A string containing the thinkScript source code, or an error message.
    """
    # Handle bare sharing IDs (no URL scheme)
    if not url.startswith(("http://", "https://", "tossc:")):
        # Could be a bare sharing ID like "3Kykh6C"
        if re.match(r'^[A-Za-z0-9_-]+$', url) and len(url) < MAX_SHARING_ID_LENGTH:
            sharing_id = url
            print(f"Using sharing ID directly: {sharing_id}", file=sys.stderr)
            return _fetch_and_return(sharing_id, content_type=None)
        url = "https://" + url

    # Handle tossc: protocol links directly
    if url.startswith("tossc:"):
        sharing_id = re.sub(r'^tossc:/?/?', '', url)
        print(f"Extracted sharing ID from tossc link: {sharing_id}",
              file=sys.stderr)
        return _fetch_and_return(sharing_id, content_type=None)

    print(f"Fetching: {url}", file=sys.stderr)

    # Step 1: Follow redirects and get the sharing page
    try:
        final_url, html = fetch_url(url)
    except Exception as e:
        return f"Error fetching URL: {e}"

    print(f"Resolved to: {final_url}", file=sys.stderr)

    # Check if the redirect itself contains encoded content
    # (some tos.mx links redirect to URLs with code= parameter)
    if "code=" in final_url or "encodedId=" in final_url:
        parsed = urllib.parse.urlparse(final_url)
        params = urllib.parse.parse_qs(parsed.query)
        for key in ["code", "encodedId"]:
            if key in params:
                encoded = params[key][0]
                decoded = try_base64_decode(encoded)
                if decoded:
                    text = try_decompress(decoded)
                    if text:
                        return text
                    try:
                        return decoded.decode("utf-8")
                    except UnicodeDecodeError:
                        pass

    # Step 2: Extract the tossc: sharing ID from the page
    sharing_id, content_type = extract_sharing_id(html)

    if not sharing_id:
        return (
            f"Could not find tossc: sharing link in the page.\n"
            f"Final URL: {final_url}\n"
            f"Page preview (first 1000 chars):\n{html[:1000]}"
        )

    if content_type:
        print(f"Content type: {content_type}", file=sys.stderr)
    print(f"Sharing ID: {sharing_id}", file=sys.stderr)

    # Step 3: Fetch the actual thinkScript content using the sharing ID
    return _fetch_and_return(sharing_id, content_type)


def _fetch_and_return(sharing_id, content_type):
    """Fetch thinkScript content for a sharing ID and return result."""
    print(f"Fetching shared content for ID: {sharing_id}", file=sys.stderr)

    script = fetch_shared_content(sharing_id)
    if script:
        return script

    # Could not fetch from any API endpoint
    type_desc = f" ({content_type})" if content_type else ""
    return (
        f"Error: Could not fetch thinkScript source code.\n"
        f"\n"
        f"Sharing ID: {sharing_id}{type_desc}\n"
        f"The tossc:{sharing_id} link is a thinkorswim custom protocol\n"
        f"handler. The thinkScript source is stored server-side and\n"
        f"none of the known API endpoints returned valid content.\n"
        f"\n"
        f"To import this in thinkorswim:\n"
        f"  1. Open thinkorswim desktop app\n"
        f"  2. Go to Setup > Open Shared Item\n"
        f"  3. Paste: https://tos.mx/{sharing_id}\n"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Extract thinkScript source code from a tos.mx shortlink.",
        epilog="Example: ./extract_thinkscript.py https://tos.mx/3Kykh6C",
    )
    parser.add_argument(
        "url",
        help="tos.mx shortlink URL, tossc: link, or bare sharing ID",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output file (default: stdout)",
        default=None,
    )

    args = parser.parse_args()
    result = extract_from_shortlink(args.url)

    if args.output:
        with open(args.output, "w") as f:
            f.write(result)
        print(f"Script saved to: {args.output}", file=sys.stderr)
    else:
        print(result)


if __name__ == "__main__":
    main()
