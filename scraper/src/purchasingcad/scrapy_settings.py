"""Scrapy project settings for PurchasingCAD.

All spiders in purchasingcad.spiders use this settings module.
Rate limiting and autothrottle are configured to respect government portals.
"""
import os

BOT_NAME = "purchasingcad"
SPIDER_MODULES = ["purchasingcad.spiders"]
NEWSPIDER_MODULE = "purchasingcad.spiders"

# Use asyncio reactor to match the async SQLAlchemy pipeline (D-07)
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

# scrapy-playwright download handler — routes requests with meta={"playwright": True}
# through a real Chromium browser for JS-heavy portals (PEI, NB, ON, BC, AB, MB)
DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}

# Respect robots.txt — required for government portals
ROBOTSTXT_OBEY = True

# Rate limiting — be polite to government portals
DOWNLOAD_DELAY = 1.0
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1
AUTOTHROTTLE_MAX_DELAY = 10
CONCURRENT_REQUESTS = 4

# Supabase pipeline: validate + map fields + REST API upsert
ITEM_PIPELINES = {
    "purchasingcad.pipelines.supabase_pipeline.SupabasePipeline": 300,
}
