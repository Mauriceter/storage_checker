# Storage_checker

Small vibe coded project to crawl a list of urls and extract aws, azure and gcp buckets.

## Installation

```
pipx install git+https://github.com/Mauriceter/storage_checker.git
```

## Usage

```
storage-checker -h                                                
usage: storage-checker [-h] [-u URLS [URLS ...]] [-f FILE] [-d DEPTH] [-c CONCURRENCY] [-g GUARDRAILS [GUARDRAILS ...]]

Async Cloud Bucket Crawler

options:
  -h, --help            show this help message and exit
  -u, --urls URLS [URLS ...]
                        Target URLs
  -f, --file FILE       File containing list of URLs (one per line)
  -d, --depth DEPTH     Max crawl depth
  -c, --concurrency CONCURRENCY
                        Concurrency level
  -g, --guardrails GUARDRAILS [GUARDRAILS ...]
                        Allowed domains for crawling (e.g. example.com)

```