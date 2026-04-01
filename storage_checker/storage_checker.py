import asyncio
import aiohttp
import argparse
import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

# ----------------------------
# Patterns (expanded)
# ----------------------------
PATTERNS = {
    "aws_s3": [
        r"https?://([a-z0-9.\-]+)\.s3(?:[.-][a-z0-9-]+)?\.amazonaws\.com",
        r"https?://s3(?:[.-][a-z0-9-]+)?\.amazonaws\.com/([a-z0-9.\-_]+)",
        r"s3://([a-z0-9.\-]+)",                                            
    ],
    "gcp": [
        r"https?://storage\.googleapis\.com/([a-z0-9.\-_]+)",
        r"gs://([a-z0-9.\-_]+)",
    ],
    "azure": [
        r"https?://([a-z0-9\-]+)\.blob\.core\.windows\.net",
        r"azure://([a-z0-9\-]+)",
    ]
}

# ----------------------------
# Async Fetch
# ----------------------------
async def fetch(session, url):
    try:
        async with session.get(url, timeout=10) as resp:
            if resp.status == 200:
                return await resp.text()
    except:
        return ""
    return ""


# ----------------------------
# Extract buckets
# ----------------------------
def extract_buckets(text, url):
    found = set()

    for provider, patterns in PATTERNS.items():
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for m in matches:
                found.add((provider, m, url))
                print(f"\033[31m[!] Bucket Found\033[0m at {url}")

    return found


# ----------------------------
# Extract links
# ----------------------------

def extract_links(base_url, html):
    links = set()
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup.find_all("a", href=True):
        href = tag["href"]
        full_url = urljoin(base_url, href)

        # Keep only HTTP(S)
        if full_url.startswith("http"):
            links.add(full_url)

    return links


# ----------------------------
# Check bucket existence
# ----------------------------
async def check_bucket(session, provider, bucket):
    if provider == "aws_s3":
        url = f"http://{bucket}.s3.amazonaws.com"
    elif provider == "gcp":
        url = f"https://storage.googleapis.com/{bucket}"
    elif provider == "azure":
        url = f"https://{bucket}.blob.core.windows.net/a"
    else:
        return False

    try:
        async with session.head(url, timeout=5) as resp:
            return resp.status in [200, 403, 409]
    except:
        return False


# ----------------------------
# Crawler
# ----------------------------

def is_allowed(url, allowed_domains):
    if not allowed_domains:
        return True  # no restriction

    hostname = urlparse(url).hostname or ""

    for domain in allowed_domains:
        if hostname == domain or hostname.endswith("." + domain):
            return True

    return False

async def crawl(start_urls, max_depth, concurrency, allowed_domains=None):
    visited = set()
    found_buckets = set()
    queue = [(url, 0) for url in start_urls]

    USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36" #"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36 Edg/111.0.1661.54"
    connector = aiohttp.TCPConnector(limit=concurrency)
    async with aiohttp.ClientSession(connector=connector, headers={"User-Agent": USER_AGENT}) as session:

        while queue:
            url, depth = queue.pop(0)

            if url in visited or depth > max_depth:
                continue

            visited.add(url)
            print(f"[+] Crawling ({depth}): {url}")

            html = await fetch(session, url)
            if not html:
                continue

            # Extract buckets
            buckets = extract_buckets(html, url)
            for b in buckets:
                found_buckets.add(b)

            # Extract links for recursion
            if depth < max_depth:
                links = extract_links(url, html)
                for link in links:
                    if link not in visited and is_allowed(link, allowed_domains):
                        if any(link.endswith(ext) for ext in [".jpg", ".png", ".pdf", ".zip"]):
                            continue
                        queue.append((link, depth + 1))

        # Check buckets existence
        print("\n[+] Checking bucket existence...\n")

        results = []
        tasks = []

        for provider, bucket, url in found_buckets:
            tasks.append(check_bucket(session, provider, bucket))

        checks = await asyncio.gather(*tasks)

        for (provider, bucket, url), exists in zip(found_buckets, checks):
            results.append({
                "provider": provider,
                "bucket": bucket,
                "exists": exists,
                "url": url
            })

        return results


# ----------------------------
# CLI
# ----------------------------
def main():
    parser = argparse.ArgumentParser(description="Async Cloud Bucket Crawler")
    parser.add_argument("-u", "--urls", nargs="+", help="Target URLs")
    parser.add_argument("-f", "--file", help="File containing list of URLs (one per line)")
    parser.add_argument("-d", "--depth", type=int, default=2, help="Max crawl depth")
    parser.add_argument("-c", "--concurrency", type=int, default=10, help="Concurrency level")
    parser.add_argument("-g", "--guardrails", nargs="+", help="Allowed domains for crawling (e.g. example.com)")

    args = parser.parse_args()

    # Collect URLs from CLI or file
    urls = set(args.urls or [])
    if args.file:
        try:
            with open(args.file, "r") as f:
                file_urls = [line.strip() for line in f if line.strip()]
                urls.update(file_urls)
        except Exception as e:
            print(f"[!] Failed to read file: {e}")
            return

    if not urls:
        print("[!] No URLs provided. Use -u or -f")
        return

    results = asyncio.run(crawl(list(urls), args.depth, args.concurrency, args.guardrails))

    # Determine column widths
    provider_width = 8 #max((len(r['provider']) for r in results), default=10)
    bucket_width = max((len(r['bucket']) for r in results), default=20)

    print("\n=== Results ===")
    header = f"Provider | {'Bucket'.ljust(bucket_width)} | Exists | Url"
    print(header)
    print("-" * len(header))

    for r in results:
        exists_str = "Yes" if r['exists'] else "No"
        print(f"{r['provider'].ljust(provider_width)} | {r['bucket'].ljust(bucket_width)} | {exists_str.ljust(6)} | {r['url']}")


if __name__ == "__main__":
    main()