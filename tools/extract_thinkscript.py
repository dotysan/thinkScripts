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
    ./extract_thinkscript.py <tos.mx URL>

Example:
    ./extract_thinkscript.py http://tos.mx/!t9yVLssN
    ./extract_thinkscript.py https://tos.mx/ABC123

How it works:
    1. Follows the tos.mx redirect to the thinkorswim sharing page.
    2. Extracts the tossc:// protocol link from the page HTML.
    3. Decodes the base64-encoded (and optionally zlib-compressed)
       thinkScript source code from the link parameters.
"""

import argparse
import base64
import binascii
import re
import sys
import urllib.parse
import zlib
from html.parser import HTMLParser

import requests


class TosPageParser(HTMLParser):
    """Parse the tos.mx/thinkorswim sharing page to find tossc: links."""

    # Matches tossc: with or without // (e.g. "tossc:3Kykh6C" or "tossc://...")
    TOSSC_RE = re.compile(r'tossc:/?/?[^\s"\'<>\\]+')

    def __init__(self):
        super().__init__()
        self.tossc_links = []

    def handle_starttag(self, tag, attrs):
        # Check all attributes for tossc: links (href, data-href, onclick, etc.)
        for _name, value in attrs:
            if value and "tossc:" in value:
                for match in self.TOSSC_RE.finditer(value):
                    self.tossc_links.append(match.group(0))

    def handle_data(self, data):
        # Some pages embed the tossc: link in JavaScript or inline text
        for match in self.TOSSC_RE.finditer(data):
            self.tossc_links.append(match.group(0))


def fetch_url(url, follow_redirects=True):
    """Fetch a URL and return (final_url, response_body)."""
    resp = requests.get(url, allow_redirects=follow_redirects, timeout=30)
    resp.raise_for_status()
    return resp.url, resp.text


def extract_tossc_link(html):
    """Extract tossc: link from HTML page content."""
    parser = TosPageParser()
    parser.feed(html)

    if parser.tossc_links:
        return parser.tossc_links[0]

    # Try regex as fallback for JavaScript-embedded links
    match = re.search(r'tossc:/?/?[^\s"\'<>\\]+', html)
    if match:
        return match.group(0)

    return None


def decode_thinkscript(tossc_url):
    """Decode thinkScript source code from a tossc: URL.

    The tossc: URL contains an encoded ID or thinkScript data.
    Formats seen in the wild:
    - tossc:3Kykh6C  (just an ID after the colon)
    - tossc://host/path?code=...
    """
    # Normalize: strip the tossc: (and optional //) prefix to get the payload
    payload = re.sub(r'^tossc:/?/?', '', tossc_url)

    if not payload:
        return None

    # If it looks like a URL path with query params, parse it
    if '?' in payload or '/' in payload:
        parseable = "http://" + payload
        parsed = urllib.parse.urlparse(parseable)
        params = urllib.parse.parse_qs(parsed.query)

        # Look for encoded content in common parameter names
        code_params = ["code", "data", "script", "studies", "strategy", "content"]
        encoded_data = None

        for param in code_params:
            if param in params:
                encoded_data = params[param][0]
                break

        # If no known parameter, try the entire query string or path
        if not encoded_data:
            path_and_query = parsed.path + ("?" + parsed.query if parsed.query else "")
            encoded_data = path_and_query.lstrip("/")
    else:
        # Simple format: tossc:ENCODED_ID
        encoded_data = payload

    if not encoded_data:
        return None

    # URL-decode first
    encoded_data = urllib.parse.unquote(encoded_data)

    # Try to base64-decode
    decoded = try_base64_decode(encoded_data)
    if decoded is None:
        # Maybe the data is already plain text thinkScript
        if looks_like_thinkscript(encoded_data):
            return encoded_data
        return encoded_data  # Return raw data as-is

    # Try zlib decompression on the decoded bytes
    text = try_decompress(decoded)
    if text:
        return text

    # Try interpreting raw bytes as text
    try:
        text = decoded.decode("utf-8")
        return text
    except (UnicodeDecodeError, AttributeError):
        pass

    # Base64 decoded to binary garbage — the original data is likely
    # just a sharing ID (e.g. "3Kykh6C"), not encoded content
    return encoded_data


def try_base64_decode(data):
    """Attempt base64 decoding with various padding fixes."""
    # Fix padding
    data_stripped = data.strip()
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
        url: A tos.mx shortlink URL (e.g., http://tos.mx/!t9yVLssN)

    Returns:
        A string containing the thinkScript source code, or an error message.
    """
    # Normalize URL
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    print(f"Fetching: {url}", file=sys.stderr)

    # Step 1: Follow redirects and get the sharing page
    try:
        final_url, html = fetch_url(url)
    except Exception as e:
        return f"Error fetching URL: {e}"

    print(f"Redirected to: {final_url}", file=sys.stderr)

    # Step 2: Extract the tossc:// link from the page
    tossc_link = extract_tossc_link(html)

    if tossc_link:
        print(f"Found tossc link: {tossc_link}", file=sys.stderr)
        # Step 3: Decode the thinkScript from the tossc:// link
        script = decode_thinkscript(tossc_link)
        if script:
            return script
        return f"Found tossc link but could not decode: {tossc_link}"

    # Fallback: check if the final URL itself has encoded data
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

    # If we got HTML back, show what we found for debugging
    return (
        f"Could not find tossc:// link in the page.\n"
        f"Final URL: {final_url}\n"
        f"Page preview (first 1000 chars):\n{html[:1000]}"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Extract thinkScript source code from a tos.mx shortlink.",
        epilog="Example: python extract_thinkscript.py http://tos.mx/!t9yVLssN",
    )
    parser.add_argument(
        "url",
        help="The tos.mx shortlink URL to extract thinkScript from",
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
