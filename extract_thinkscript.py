#!/usr/bin/env python3
"""
Extract thinkScript source code from a thinkorswim tos.mx shortlink.

Usage:
    python extract_thinkscript.py <tos.mx URL>

Example:
    python extract_thinkscript.py http://tos.mx/!t9yVLssN
    python extract_thinkscript.py https://tos.mx/ABC123

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

try:
    import requests
except ImportError:
    requests = None

try:
    from urllib.request import urlopen, Request
    from urllib.error import URLError, HTTPError
except ImportError:
    pass


class TosPageParser(HTMLParser):
    """Parse the tos.mx/thinkorswim sharing page to find tossc:// links."""

    def __init__(self):
        super().__init__()
        self.tossc_links = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        href = attrs_dict.get("href", "")
        if href.startswith("tossc://"):
            self.tossc_links.append(href)

    def handle_data(self, data):
        # Some pages embed the tossc:// link in JavaScript or inline text
        for match in re.finditer(r'tossc://[^\s"\'<>]+', data):
            self.tossc_links.append(match.group(0))


def fetch_url(url, follow_redirects=True):
    """Fetch a URL and return (final_url, response_body)."""
    if requests:
        resp = requests.get(url, allow_redirects=follow_redirects, timeout=30)
        resp.raise_for_status()
        return resp.url, resp.text

    # Fallback to urllib
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    resp = urlopen(req, timeout=30)
    body = resp.read().decode("utf-8", errors="replace")
    return resp.url, body


def extract_tossc_link(html):
    """Extract tossc:// link from HTML page content."""
    parser = TosPageParser()
    parser.feed(html)

    if parser.tossc_links:
        return parser.tossc_links[0]

    # Try regex as fallback for JavaScript-embedded links
    match = re.search(r'tossc://[^\s"\'<>\\]+', html)
    if match:
        return match.group(0)

    return None


def decode_thinkscript(tossc_url):
    """Decode thinkScript source code from a tossc:// URL.

    The tossc:// URL typically contains encoded thinkScript data in
    its path or query parameters. The encoding may be:
    - URL-encoded
    - Base64-encoded
    - Base64 + zlib compressed
    """
    # Parse the tossc:// URL
    # Replace tossc:// with http:// so urllib can parse it
    parseable = tossc_url.replace("tossc://", "http://", 1)
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
        # Sometimes the data is in the path itself after the host portion
        path_and_query = parsed.path + ("?" + parsed.query if parsed.query else "")
        # Remove leading slash
        encoded_data = path_and_query.lstrip("/")

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

    return None


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
        f"Page preview (first 500 chars):\n{html[:500]}"
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
