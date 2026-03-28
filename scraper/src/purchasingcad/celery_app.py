"""Celery application and Beat schedule for tenders scraper.

20 spiders scheduled: canadabuys every 2h, SEAO every 12h, all others every 8h.
"""
import os

from celery import Celery

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")

app = Celery(
    "purchasingcad",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["purchasingcad.tasks.crawl"],
)

app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    result_expires=86400,
    timezone="America/Toronto",
    enable_utc=True,
    beat_schedule={
        # Federal (every 2h)
        "crawl-canadabuys": {
            "task": "purchasingcad.tasks.crawl.run_spider",
            "schedule": 7200,
            "args": ("canadabuys",),
        },
        # Provincial
        "crawl-seao": {
            "task": "purchasingcad.tasks.crawl.run_spider",
            "schedule": 43200,
            "args": ("seao",),
        },
        "crawl-nova_scotia": {
            "task": "purchasingcad.tasks.crawl.run_spider",
            "schedule": 28800,
            "args": ("nova_scotia",),
        },
        "crawl-yukon": {
            "task": "purchasingcad.tasks.crawl.run_spider",
            "schedule": 28800,
            "args": ("yukon",),
        },
        "crawl-pei": {
            "task": "purchasingcad.tasks.crawl.run_spider",
            "schedule": 28800,
            "args": ("pei",),
        },
        "crawl-new_brunswick": {
            "task": "purchasingcad.tasks.crawl.run_spider",
            "schedule": 28800,
            "args": ("new_brunswick",),
        },
        "crawl-saskatchewan": {
            "task": "purchasingcad.tasks.crawl.run_spider",
            "schedule": 28800,
            "args": ("saskatchewan",),
        },
        "crawl-nwt": {
            "task": "purchasingcad.tasks.crawl.run_spider",
            "schedule": 28800,
            "args": ("nwt",),
        },
        "crawl-nunavut": {
            "task": "purchasingcad.tasks.crawl.run_spider",
            "schedule": 28800,
            "args": ("nunavut",),
        },
        "crawl-newfoundland": {
            "task": "purchasingcad.tasks.crawl.run_spider",
            "schedule": 28800,
            "args": ("newfoundland",),
        },
        "crawl-ontario": {
            "task": "purchasingcad.tasks.crawl.run_spider",
            "schedule": 28800,
            "args": ("ontario",),
        },
        "crawl-bc": {
            "task": "purchasingcad.tasks.crawl.run_spider",
            "schedule": 28800,
            "args": ("bc",),
        },
        "crawl-alberta": {
            "task": "purchasingcad.tasks.crawl.run_spider",
            "schedule": 28800,
            "args": ("alberta",),
        },
        "crawl-manitoba": {
            "task": "purchasingcad.tasks.crawl.run_spider",
            "schedule": 28800,
            "args": ("manitoba",),
        },
        # Municipal
        "crawl-calgary": {
            "task": "purchasingcad.tasks.crawl.run_spider",
            "schedule": 28800,
            "args": ("calgary",),
        },
        "crawl-ottawa": {
            "task": "purchasingcad.tasks.crawl.run_spider",
            "schedule": 28800,
            "args": ("ottawa",),
        },
        "crawl-toronto": {
            "task": "purchasingcad.tasks.crawl.run_spider",
            "schedule": 28800,
            "args": ("toronto",),
        },
        "crawl-vancouver": {
            "task": "purchasingcad.tasks.crawl.run_spider",
            "schedule": 28800,
            "args": ("vancouver",),
        },
        "crawl-edmonton": {
            "task": "purchasingcad.tasks.crawl.run_spider",
            "schedule": 28800,
            "args": ("edmonton",),
        },
        "crawl-winnipeg": {
            "task": "purchasingcad.tasks.crawl.run_spider",
            "schedule": 28800,
            "args": ("winnipeg",),
        },
    },
)
