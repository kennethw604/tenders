"""Shared Scrapy Item definition for all PurchasingCAD spiders.

All spiders across Phases 2-6 yield TenderItem instances. The shared
TenderPipeline validates, fingerprints, and upserts them into PostgreSQL.
"""
import scrapy


class TenderItem(scrapy.Item):
    source_slug = scrapy.Field()       # "canadabuys" or "seao"
    external_id = scrapy.Field()       # unique ID from source
    title = scrapy.Field()             # English title (or None)
    title_fr = scrapy.Field()          # French title (or None)
    description = scrapy.Field()       # English description (or None)
    description_fr = scrapy.Field()    # French description (or None)
    buyer_org = scrapy.Field()
    buyer_id = scrapy.Field()
    status = scrapy.Field()            # open/closed/awarded/cancelled
    published_date = scrapy.Field()    # ISO datetime string or None
    closing_date = scrapy.Field()      # ISO datetime string or None
    province = scrapy.Field()          # 2-letter ISO 3166-2 CA code or None
    jurisdiction = scrapy.Field()      # "fed" or "prov"
    category = scrapy.Field()          # goods/services/works
    unspsc_codes = scrapy.Field()      # list[str]
    value_amount = scrapy.Field()      # Decimal or None
    value_currency = scrapy.Field()    # "CAD" default
    source_url = scrapy.Field()
    raw_ocds = scrapy.Field()          # dict — full raw record
    # Extended fields (populated by sources that provide them)
    notice_type = scrapy.Field()       # "Request for Proposal", etc.
    procurement_method = scrapy.Field()  # "Competitive - Open bidding", etc.
    contact_name = scrapy.Field()
    contact_email = scrapy.Field()
    contact_phone = scrapy.Field()
    buyer_city = scrapy.Field()
    buyer_postal_code = scrapy.Field()
    delivery_regions = scrapy.Field()  # comma-separated regions
    end_user_entity = scrapy.Field()   # actual department using the goods/services
    contract_start_date = scrapy.Field()
    contract_end_date = scrapy.Field()
    selection_criteria = scrapy.Field()
    trade_agreements = scrapy.Field()
    solicitation_number = scrapy.Field()
