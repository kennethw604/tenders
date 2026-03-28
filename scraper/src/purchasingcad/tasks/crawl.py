"""Celery task: run_spider launches a Scrapy spider as a subprocess.

Simplified version for Supabase integration — no CrawlLog or DataSource tables.
Just runs the spider and logs results.
"""
import json
import logging
import os
import re
import subprocess

from purchasingcad.celery_app import app

logger = logging.getLogger(__name__)


def _parse_item_count(stderr: str) -> int:
    if not stderr:
        return 0
    for line in stderr.splitlines():
        if "Dumping Scrapy stats:" in line:
            try:
                json_part = line.split("Dumping Scrapy stats:", 1)[1].strip()
                stats = json.loads(json_part)
                return int(stats.get("item_scraped_count", 0))
            except (json.JSONDecodeError, ValueError, IndexError):
                pass
    match = re.search(r"['\"]?item_scraped_count['\"]?\s*[:=]\s*(\d+)", stderr)
    if match:
        return int(match.group(1))
    return 0


@app.task(bind=True, max_retries=3, default_retry_delay=300)
def run_spider(self, spider_name: str) -> dict:
    """Run a Scrapy spider by name.

    Args:
        spider_name: Spider name (e.g. "canadabuys", "seao")

    Returns:
        dict with status and records_found
    """
    try:
        result = subprocess.run(
            ["scrapy", "crawl", spider_name],
            capture_output=True,
            text=True,
            env={**os.environ, "SCRAPY_SETTINGS_MODULE": "purchasingcad.scrapy_settings"},
        )

        records_found = _parse_item_count(result.stderr)
        status = "success" if result.returncode == 0 else "error"

        if result.returncode != 0:
            logger.error(
                "Spider %s failed (rc=%d): %s",
                spider_name,
                result.returncode,
                result.stderr[-1000:] if result.stderr else "no output",
            )

        logger.info(
            "run_spider: spider=%s status=%s records_found=%d",
            spider_name,
            status,
            records_found,
        )
        return {"status": status, "records_found": records_found}

    except Exception as exc:
        logger.exception("run_spider failed for %s: %s", spider_name, exc)
        raise self.retry(exc=exc)
