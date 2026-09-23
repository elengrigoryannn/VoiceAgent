"""
Scrapes the pages listed in config/institutions.yaml and saves cleaned
text + metadata as JSON files in raw_data/<institution>/<topic>__<slug>.json

This is a separate step from ingestion (rag.py) so you can inspect what
was scraped before it gets chunked and embedded.

Usage:
  pip install requests beautifulsoup4 pyyaml
  python scrape.py                  # scrape everything in the config
  python scrape.py --institution "Ameriabank"   # scrape just one

Run this again any time to refresh data — it overwrites the JSON file
for each (institution, url) pair, and rag.py's ingest step will upsert
the corresponding chunks (old chunks from that page get replaced, other
institutions/pages are untouched).
"""

import argparse
import hashlib
import json
import os
import time
from datetime import datetime, timezone

import requests
import yaml
from bs4 import BeautifulSoup

from bank_rag.adapters import get_adapter

CONFIG_PATH = "institutions.yaml"
RAW_DATA_DIR = "../raw_data"
USER_AGENT = "BankRAGBot/1.0 (educational project; contact: you@example.com)"
REQUEST_DELAY_SECONDS = 1.5  # be polite — don't hammer the sites


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["institutions"]


def slugify(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]


def fetch_page(url: str) -> BeautifulSoup:
    headers = {"User-Agent": USER_AGENT}
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def scrape_page(institution: dict, page: dict) -> dict:
    url = page["url"]
    topic = page["topic"]
    adapter_name = institution.get("adapter", "default")
    clean_fn = get_adapter(adapter_name)

    soup = fetch_page(url)
    title = soup.title.get_text(strip=True) if soup.title else ""
    text = clean_fn(soup)

    record = {
        "institution": institution["name"],
        "url": url,
        "title": title,
        "topic": topic,
        "text": text,
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }
    return record


def save_record(record: dict):
    inst_dir = os.path.join(RAW_DATA_DIR, record["institution"])
    os.makedirs(inst_dir, exist_ok=True)
    filename = f"{record['topic']}__{slugify(record['url'])}.json"
    path = os.path.join(inst_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    return path


def run(institution_filter: str = None):
    institutions = load_config()
    if institution_filter:
        institutions = [i for i in institutions if i["name"] == institution_filter]
        if not institutions:
            print(f"No institution named '{institution_filter}' in config.")
            return

    total_ok, total_fail = 0, 0

    for institution in institutions:
        print(f"\n== {institution['name']} ==")
        for page in institution["pages"]:
            try:
                record = scrape_page(institution, page)
                path = save_record(record)
                print(f"  OK   [{page['topic']}] {page['url']} -> {path} "
                      f"({len(record['text'])} chars)")
                total_ok += 1
            except Exception as e:
                print(f"  FAIL [{page['topic']}] {page['url']} -> {e}")
                total_fail += 1
            time.sleep(REQUEST_DELAY_SECONDS)

    print(f"\nDone. {total_ok} page(s) scraped, {total_fail} failed.")
    if total_ok:
        print("Next: python rag.py ingest")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--institution", default=None,
                         help="Only scrape this institution (must match config name)")
    args = parser.parse_args()
    run(institution_filter=args.institution)
