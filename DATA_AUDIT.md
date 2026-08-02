# Tender Data Audit: Source Platform Metadata Mapping

> Generated: 2026-03-28
> Purpose: Map every source platform's available metadata against our DB schema to identify capture gaps and standardization needs.

---

## Our Database Schema (Target Fields)

| DB Column | Type | Description | Currently Populated? |
|---|---|---|---|
| `title` | string | Tender name | Yes (all sources) |
| `description` | string | Full description | Sparse (only CanadaBuys, Toronto) |
| `source` | string | Platform slug | Yes |
| `source_reference` | string | External ID | Yes |
| `source_url` | string | Link to original | Yes |
| `status` | string | open/closed/awarded/cancelled | Yes |
| `published_date` | datetime | When posted | Partial |
| `closing_date` | datetime | Submission deadline | Yes (most sources) |
| `contract_start_date` | datetime | Contract begin | Never populated |
| `contracting_entity_name` | string | Buyer org name | Yes (most sources) |
| `contracting_entity_city` | string | Buyer city | **Never populated** |
| `contracting_entity_province` | string | 2-letter code | Yes (from spider config) |
| `contracting_entity_country` | string | Country | Hard-coded "Canada" |
| `category_primary` | string | goods/services/works | Sparse (CanadaBuys, Toronto, Nova Scotia) |
| `procurement_type` | string | rfp/rfq/tender | **Never populated** |
| `procurement_method` | string | open/limited | **Never populated** |
| `unspsc` | string | Commodity codes | Only CanadaBuys |
| `gsin` | string | GSIN codes | **Never populated** |
| `estimated_value_min` | number | Dollar amount | Only Nova Scotia |
| `currency` | string | CAD | Default |
| `delivery_location` | string | Misused for jurisdiction | Stores "Federal"/"Provincial (XX)" |
| `contact_name` | string | Contact person | **Never populated** |
| `contact_email` | string | Contact email | **Never populated** |
| `contact_phone` | string | Contact phone | **Never populated** |
| `plan_takers_count` | number | # interested bidders | **Never populated** |
| `submissions_count` | number | # bids received | **Never populated** |
| `summary` | string | AI-generated summary | Separate process |

---

## Source Platform Audit

---

### 1. CanadaBuys (Federal)

**Source:** CSV open data export
**URL:** `https://canadabuys.canada.ca/opendata/pub/openTenderNotice-ouvertAvisAppelOffres.csv`
**Spider:** `canadabuys`
**Jurisdiction:** Federal

#### Available Metadata

| Source Field | Sample Value | Maps To | Captured? |
|---|---|---|---|
| `referenceNumber-numeroReference` | PW-24-01084261 | `source_reference` | Yes |
| `title-titre-eng` | "Supply and Delivery of Office Furniture" | `title` | Yes |
| `title-titre-fra` | "Fourniture et livraison de mobilier de bureau" | (title fallback) | Yes |
| `tenderDescription-descriptionAppelOffres-eng` | Full description text | `description` | Yes |
| `tenderDescription-descriptionAppelOffres-fra` | French description | (description fallback) | Yes |
| `contractingEntityName-nomEntitContractante-eng` | "Public Services and Procurement Canada" | `contracting_entity_name` | Yes |
| `contractingEntityAddressProvince-eng` | "Ontario" | `contracting_entity_province` | Yes (mapped to "ON") |
| `tenderStatus-appelOffresStatut-eng` | "Open" | `status` | Yes |
| `publicationDate-datePublication` | 2026-01-15 | `published_date` | Yes |
| `tenderClosingDate-appelOffresDateCloture` | 2026-02-28T14:00:00 | `closing_date` | Yes |
| `procurementCategory-categorieApprovisionnement` | "Goods" / "Services" / "Construction" | `category_primary` | Yes |
| `gsin-nibs` | "N7610" | `gsin` | **No** (parsing attempted, not mapped) |
| `unspsc` | "44121600;44121700" | `unspsc` | Yes |
| `noticeURL-URLavis-eng` | Full URL | `source_url` | Yes |

#### NOT Available from Source
- Contract value / estimated amount
- Contact name/email/phone
- Plan takers
- Procurement type (RFP/RFQ)
- City-level location
- Amendment history

#### Standardization Issues
- **Mixed languages**: French title used as fallback when English missing — no language flag
- **Province field**: Comes as full name ("Ontario"), mapped to 2-letter code
- **Category**: "Construction" mapped to "works" — good
- **GSIN codes**: Parsed but not stored (mapping table missing)
- **Date formats**: Standard ISO — clean

---

### 2. SEAO (Quebec)

**Source:** REST API
**URL:** `https://api.seao.gouv.qc.ca/prod/api/recherche`
**Spider:** `seao`
**Jurisdiction:** Provincial (QC)

#### Available Metadata

| Source Field | Sample Value | Maps To | Captured? |
|---|---|---|---|
| `uuid` / `id` | "abc-123-def" | `source_reference` | Yes |
| `numero` | "SEAO-2026-001" | (fallback external_id) | Yes |
| `titre` | "Services d'entretien ménager" | `title` + `title_fr` | Yes (FR only) |
| `nomDonneurOuvrage` | "Ville de Montréal" | `contracting_entity_name` | Yes |
| `donneurOuvrageUUID` | UUID | `buyer_id` | Yes |
| `statutAvisId` | 6 | `status` | Yes (6=open, 7=closed, 8=awarded, 9=cancelled) |
| `datePublicationUtc` | ISO datetime | `published_date` | Yes |
| `dateFermetureUtc` | ISO datetime | `closing_date` | Yes |
| Additional API fields | Category IDs, sector codes, metadata | — | **No** |

#### NOT Available / NOT Captured
- **Description**: API returns no description field
- **Category/sector codes**: Available in API response but **not extracted**
- **Value amounts**: Not in API
- **Contact info**: Not in API
- **UNSPSC codes**: Not available

#### Standardization Issues
- **French-only titles**: No English translation available — shows up as French in table
- **Status mapping**: Only maps IDs 6-9; unknown IDs default to "open" (risky)
- **Additional API fields exist but are discarded** — need to investigate what's available

---

### 3. Alberta (Provincial)

**Source:** Angular SPA with XHR interception
**URL:** `https://purchasing.alberta.ca/search`
**Spider:** `alberta`
**Jurisdiction:** Provincial (AB)

#### Available Metadata

| Source Field | Sample Value | Maps To | Captured? |
|---|---|---|---|
| `id` / `solicitation_id` | "SOL-2026-001" | `source_reference` | Yes |
| `title` / `name` | "Road Maintenance Services" | `title` | Yes |
| `organizationName` / `ministry` | "Alberta Transportation" | `contracting_entity_name` | Yes |
| `status` | "Open" | `status` | Yes |
| `closingDate` | ISO datetime | `closing_date` | Yes |
| `publishDate` | ISO datetime | `published_date` | Yes |
| `category` | Category text | `category_primary` | Attempted (usually null) |

#### NOT Available / NOT Captured
- **Description**: Not in SPA listing view
- **Value amounts**: Not displayed
- **UNSPSC/commodity codes**: Not available
- **Contact info**: Not in listing
- **Plan takers**: Not exposed

#### Standardization Issues
- **XHR field names are guessed** — actual API contract unknown
- **DOM fallback** extracts minimal data if XHR interception fails
- **No bilingual content**

---

### 4. BC Bid (Provincial)

**Source:** ASP.NET server-rendered HTML
**URL:** `https://www.bcbid.gov.bc.ca/page.aspx/en/rfp/request_browse_public`
**Spider:** `bcbid`
**Jurisdiction:** Provincial (BC)

#### Available Metadata

| Source Field | Sample Value | Maps To | Captured? |
|---|---|---|---|
| Title cell (linked) | "IT Consulting Services" | `title` | Yes |
| Organization cell | "Ministry of Health" | `contracting_entity_name` | Yes |
| Location cell | "Victoria" | — | **No** (available but not captured!) |
| Published Date cell | "2026-01-10" | `published_date` | Yes |
| Closing Date cell | "2026-02-15" | `closing_date` | Yes |
| URL query param | `purchasingGroupId=12345` | `source_reference` | Yes |

#### NOT Available / NOT Captured
- **Location**: Available in table but **not mapped** to `contracting_entity_city`
- **Description**: Not in listing view
- **Category**: Not in listing
- **Value**: Not displayed
- **Contact info**: Not in listing

#### Standardization Issues
- **reCAPTCHA**: May block scraping entirely — no data captured when triggered
- **Location data is thrown away** — easy win to capture

---

### 5. Toronto (Municipal)

**Source:** OData JSON API
**URL:** `https://secure.toronto.ca/c3api_data/v2/DataAccess.svc/pmmd_solicitations/feis_solicitation`
**Spider:** `toronto`
**Jurisdiction:** Municipal (ON)

#### Available Metadata

| Source Field | Sample Value | Maps To | Captured? |
|---|---|---|---|
| `Solicitation_Document_Number` | "Doc-2026-001" | `source_reference` | Yes |
| `Posting_Title` | "Snow Removal Services" | `title` | Yes |
| `Solicitation_Document_Description` | Full description | `description` | Yes |
| `Status` | "Open" | `status` | Yes (mapped) |
| `High_Level_Category` | "Services" | `category_primary` | Yes (mapped) |
| `Issue_Date` | ISO datetime | `published_date` | Yes |
| `Closing_Date` | ISO datetime | `closing_date` | Yes |
| `Client_Division` | ["Parks, Forestry & Recreation"] | appended to `contracting_entity_name` | Yes |
| `Ariba_Discovery_Posting_Link` | URL | `source_url` | Yes |

#### NOT Available / NOT Captured
- **Value amounts**: Not in API
- **UNSPSC codes**: Not available
- **Contact info**: Not in API
- **Plan takers**: Not exposed
- **Procurement type**: Not explicitly in API (could be parsed from title patterns like "RFP", "RFQ")

#### Standardization Issues
- **Category mapping**: "Supply" → "goods", "Service" → "services", "Construction" → "works" — good
- **Division array**: Only first item used — multi-division tenders lose info
- **Status mapping**: Comprehensive (open/active/closed/complete/awarded/cancelled)

---

### 6. Calgary (Municipal)

**Source:** SAP Ariba Discovery
**URL:** `https://service.ariba.com/Discovery.aw/ad/profile?key=AN11042088414`
**Spider:** `calgary`
**Jurisdiction:** Municipal (AB)

#### Available Metadata

| Source Field | Sample Value | Maps To | Captured? |
|---|---|---|---|
| Title cell (linked) | "Fleet Vehicle Maintenance" | `title` | Yes |
| Reference # cell | "2026-0123" | `source_reference` | Yes |
| Closing Date cell | "Feb 28, 2026" | `closing_date` | Yes |
| Category cell | — | `category_primary` | Attempted (usually null) |
| Value cell | — | `estimated_value_min` | Attempted (usually null) |

#### NOT Available / NOT Captured
- **Description**: Only on detail page (not scraped)
- **Published date**: Rarely found in listing
- **Contact info**: On detail page only
- **UNSPSC codes**: Not in listing
- **Ariba detail pages have rich metadata** — currently only listing is scraped

#### Standardization Issues
- **Session-based tokens**: URLs expire, can't be stored permanently
- **buyer_org hard-coded**: "City of Calgary" — no department/division info
- **Ariba detail pages could provide**: description, category, contact info, value — but require authenticated session

---

### 7. Edmonton (Municipal)

**Source:** SAP Ariba Discovery (same platform as Calgary)
**URL:** `https://service.ariba.com/Discovery.aw/ad/profile?key=AN01394774623`
**Spider:** `edmonton`
**Jurisdiction:** Municipal (AB)

Same structure as Calgary — identical Ariba platform. buyer_org hard-coded "City of Edmonton".

---

### 8. MERX Platform (Ottawa, Manitoba, Newfoundland, Winnipeg)

**Source:** MERX commercial platform (server-rendered HTML)
**Spiders:** `ottawa`, `manitoba`, `newfoundland`, `winnipeg`
**Jurisdictions:** Mixed (muni/prov)

#### Available Metadata (All MERX spiders)

| Source Field | Sample Value | Maps To | Captured? |
|---|---|---|---|
| Solicitation link text | "Janitorial Services" | `title` | Yes |
| Organization element | "City of Ottawa" | `contracting_entity_name` | Attempted |
| Closing date element | "2026-03-15" | `closing_date` | Attempted |
| Published date element | "2026-02-01" | `published_date` | Attempted |
| `purchasingGroupId` param | "12345" | `source_reference` | Yes |

#### MERX Detail Pages (NOT Scraped) Contain
- **Full description**
- **Document downloads**
- **Contact information**
- **Category/commodity codes**
- **Amendment history**
- **Plan takers / registered vendors**

#### Standardization Issues
- **Captcha/429 blocking**: Common on MERX — scraper yields nothing when blocked
- **Detail pages have rich data** but require clicking through from listing
- **buyer_org extraction unreliable** — depends on CSS class selectors that may not exist

---

### 9. Ontario (Provincial)

**Source:** Jaggaer JSP portal
**URL:** `https://ontariotenders.app.jaggaer.com/esop/toolkit/opportunity/opportunityList.do`
**Spider:** `ontario`
**Jurisdiction:** Provincial (ON)

#### Available Metadata

| Source Field | Sample Value | Maps To | Captured? |
|---|---|---|---|
| Title cell (linked) | "Highway Bridge Repair" | `title` | Yes |
| Reference # | "ON-2026-001" | `source_reference` | Yes |
| Organization cell | "Ministry of Transportation" | `contracting_entity_name` | Yes |
| Closing Date cell | "2026-04-01" | `closing_date` | Yes |
| Published Date cell | "2026-03-01" | `published_date` | Yes |
| Status cell | "Open" | `status` | Yes |

#### NOT Available / NOT Captured
- **Description**: Only on detail page
- **Category**: Not in listing table
- **Value**: Not displayed
- **UNSPSC**: Not in listing
- **Contact**: Detail page only

#### Standardization Issues
- **Login wall detection**: Yields nothing if login page detected
- **Detail pages accessible** but not scraped — would provide description, category, documents

---

### 10. BidsandTenders / Yukon (Territorial)

**Source:** BidsandTenders aggregator CSV export
**URL:** `https://yukon.bidsandtenders.ca/Module/Tenders/en/OpenData/GenerateReport?report=OpenTenders`
**Spider:** `yukon`
**Jurisdiction:** Territorial (YT)

#### Available Metadata (CSV Export)

| Source Field | Sample Value | Maps To | Captured? |
|---|---|---|---|
| `Project Number` | "RFB-2026-3-5186" | `source_reference` | Yes |
| `Project Description` | "Electrical Repairs and Maintenance..." | `title` | Yes |
| `Department` | "Yukon Housing Corporation" | `contracting_entity_name` | Yes |
| `Project Status` | "Open" | `status` | Yes |
| `Published Date` | "2026-03-15" | `published_date` | Yes |
| `Closing Date` | "2026-04-21" | `closing_date` | Yes |

#### Detail Page Has (from screenshot) — NOT Captured

| Detail Field | Sample Value | Could Map To |
|---|---|---|
| **Bid Classification** | "Services" | `category_primary` |
| **Bid Type** | "Request for Bids" | `procurement_type` |
| **Question Deadline** | "Tue Apr 14, 2026 3:00:00 PM" | (new field needed) |
| **Description** | Full paragraph | `description` |
| **Community** | "Dawson City" | `contracting_entity_city` |
| **Traditional Territory** | "Tr'ondëk Hwëch'in" | (new field — indigenous territory) |
| **Categories (tree)** | "Trade Services > Electrical" | `category_primary` + subcategory |
| **Submission Type** | "Online Submissions Only" | (new field) |
| **Public Opening** | "No" | (new field) |
| **Language for Submissions** | "English" | (new field) |
| **Plan Takers** | 4 companies with contact details | `plan_takers_count` + new related table |
| **Documents** | Downloadable bid documents | (new feature) |

#### Standardization Issues
- **CSV is listing-only** — no detail metadata captured
- **Detail pages have 15+ additional fields** — huge data gap
- **Plan takers with full contact info** available on detail pages
- **Hierarchical categories** (Trade Services > Electrical) not representable in single `category_primary` field
- **Community/location data** available but not captured

---

### 11. Nova Scotia (Provincial)

**Source:** Socrata SODA API (awarded contracts only)
**URL:** `https://data.novascotia.ca/resource/m6ps-8j6u.json`
**Spider:** `novascotia`
**Jurisdiction:** Provincial (NS)

#### Available Metadata

| Source Field | Sample Value | Maps To | Captured? |
|---|---|---|---|
| `tender_id` | "NS-2026-001" | `source_reference` | Yes |
| `tender_description` | "IT Services Contract" | `title` | Yes |
| `entity` | "Dept of Internal Services" | `contracting_entity_name` | Yes |
| `tender_start_date` | ISO datetime | `published_date` | Yes |
| `tender_close_date` | ISO datetime | `closing_date` | Yes |
| `awarded_amount` | 150000.00 | `estimated_value_min` | Yes |
| `goods` / `service` / `construction` | "Y" / "N" | `category_primary` | Yes (boolean flags) |

#### Standardization Issues
- **Awarded contracts only** — no open tenders
- **Only source with dollar amounts**
- **Category from boolean flags**: Multiple can be "Y" — only first match used
- **Status hard-coded "awarded"** for all records

---

### 12. New Brunswick (Provincial)

**Source:** NBON iframe portal
**URL:** `https://nbon-rpanb.gnb.ca/welcome?Language=En`
**Spider:** `newbrunswick`
**Jurisdiction:** Provincial (NB)

#### Available Metadata

| Source Field | Sample Value | Maps To | Captured? |
|---|---|---|---|
| Reference cell | "NB-2026-001" | `source_reference` | Yes |
| Title cell | "Building Renovation Services" | `title` | Yes |
| Organization cell | "Dept of Transportation" | `contracting_entity_name` | Yes |
| Closing Date cell | "2026-03-30" | `closing_date` | Yes |
| Status cell | "Open" | `status` | Yes |

#### NOT Available / NOT Captured
- No description, category, value, contact info, published date
- **Iframe-based**: Complex extraction, data is minimal

---

### 13. PEI (Provincial)

**Source:** Drupal Views
**URL:** `https://www.princeedwardisland.ca/en/tenders?items_per_page=100`
**Spider:** `pei`
**Jurisdiction:** Provincial (PE)

#### Available Metadata

| Source Field | Sample Value | Maps To | Captured? |
|---|---|---|---|
| Link text | "Road Paving Contract" | `title` | Yes |
| `.views-field-field-closing-date` | "2026-04-15" | `closing_date` | Yes |
| `.views-field-created` | "2026-03-01" | `published_date` | Yes |
| `.views-field-field-status` | "Open" | `status` | Yes |
| URL slug | "/tenders/road-paving-contract" | `source_reference` | Yes |

#### NOT Available / NOT Captured
- No buyer_org, description, category, value, contact info
- **Radware bot detection** may block entirely

---

### 14. Saskatchewan (Provincial)

**Source:** ASP.NET HTML table
**URL:** `https://sasktenders.ca/Content/Public/Search.aspx`
**Spider:** `saskatchewan`
**Jurisdiction:** Provincial (SK)

#### Available Metadata

| Source Field | Sample Value | Maps To | Captured? |
|---|---|---|---|
| Competition Name (linked) | "IT Equipment Supply" | `title` | Yes |
| Organization | "Saskatchewan Health Authority" | `contracting_entity_name` | Yes |
| Competition Number | "SK-2026-001" | `source_reference` | Yes |
| Open Date | "2026-02-15" | `published_date` | Yes |
| Close Date | "2026-03-15" | `closing_date` | Yes |
| Status | "Open" | `status` | Yes |

#### NOT Available / NOT Captured
- No description, category, value, UNSPSC, contact info

---

### 15. Nunavut (Territorial)

**Source:** Static HTML with sectioned tables
**URL:** `https://www.nunavuttenders.ca/Default.aspx`
**Spider:** `nunavut`
**Jurisdiction:** Territorial (NU)

#### Available Metadata

| Source Field | Sample Value | Maps To | Captured? |
|---|---|---|---|
| Ref# (linked) | "NU-2026-001" | `source_reference` | Yes |
| Description | "Airport Runway Repair" | `title` | Yes |
| Issued Date | "2026-01-20" | `published_date` | Yes |
| Closing Date | "2026-02-28" | `closing_date` | Yes |
| Section header | "Open" / "Awarded" | `status` | Yes |
| **FOB Point** | "Iqaluit" | — | **Stored in raw_ocds only** |
| **Contact** | "John Smith" | — | **Stored in raw_ocds only** |
| **Phone/Email** | "867-555-1234" | — | **Stored in raw_ocds only** |

#### Standardization Issues
- **Contact info and location ARE captured in raw_ocds** but never mapped to DB fields
- Easy win: extract from raw_ocds → `contact_name`, `contact_phone`, `contracting_entity_city`

---

### 16. NWT (Territorial)

**Source:** Django portal with CSV export
**URL:** `https://contracts.opennwt.ca/tenders/`
**Spider:** `nwt`
**Jurisdiction:** Territorial (NT)

#### Available Metadata

| Source Field | Sample Value | Maps To | Captured? |
|---|---|---|---|
| `title` / `description` | "Building Maintenance" | `title` | Yes |
| `buyer` / `organization` | "GNWT Public Works" | `contracting_entity_name` | Yes |
| `reference` | "NWT-2026-001" | `source_reference` | Yes |
| `published` | ISO datetime | `published_date` | Yes |
| `closing` | ISO datetime | `closing_date` | Yes |
| `status` | "open" | `status` | Yes |

#### NOT Available / NOT Captured
- No description, category, value, UNSPSC, contact info

---

### 17. Vancouver (Municipal)

**Source:** Jaggaer/SciQuest platform
**URL:** `https://bids.sciquest.com/apps/Router/PublicEvent?CustomerOrg=CityofVancouver`
**Spider:** `vancouver`
**Jurisdiction:** Municipal (BC)

#### Available Metadata

| Source Field | Sample Value | Maps To | Captured? |
|---|---|---|---|
| Title (linked) | "Park Maintenance Services" | `title` | Yes |
| Status badge | "Open" | `status` | Yes |
| Open Date | "2026-02-01" | `published_date` | Yes |
| Close Date | "2026-03-01" | `closing_date` | Yes |
| Reference # | "PS20261234" | `source_reference` | Yes |
| **Procurement Type** | "RFP" / "ITT" | — | **Visible but not captured** |
| **Contact** | Name shown in table | — | **Visible but not captured** |

#### Standardization Issues
- **AuthToken URLs expire** — source_url fallback to listing page (dead link for detail)
- **Procurement type and contact visible in table** but not captured

---

## Gap Analysis Summary

### Fields by Capture Rate

| Field | Sources That Have It | Sources That Capture It | Gap |
|---|---|---|---|
| `title` | 20/20 | 20/20 | None |
| `closing_date` | 20/20 | 20/20 | None |
| `source_reference` | 20/20 | 20/20 | None |
| `status` | 20/20 | 20/20 | None |
| `published_date` | 18/20 | 16/20 | Small |
| `contracting_entity_name` | 18/20 | 16/20 | Small |
| `description` | 12/20 (on detail pages) | 2/20 | **Large** |
| `category_primary` | 10/20 | 3/20 | **Large** |
| `procurement_type` | 8/20 | 0/20 | **Total** |
| `contracting_entity_city` | 6/20 | 0/20 | **Total** |
| `contact_name/email/phone` | 5/20 | 0/20 | **Total** |
| `estimated_value_min` | 2/20 | 1/20 | Small (limited source) |
| `plan_takers_count` | 2/20 | 0/20 | **Total** |
| `unspsc` | 1/20 | 1/20 | None (limited source) |

### Quick Wins (Data Already Available, Just Not Mapped)

1. **Nunavut contact info** — in `raw_ocds`, needs mapping to `contact_name`, `contact_phone`
2. **Nunavut FOB Point** — in `raw_ocds`, map to `contracting_entity_city`
3. **BC Bid location** — in HTML table, not captured → `contracting_entity_city`
4. **Vancouver procurement type + contact** — in HTML table, not captured
5. **SEAO category/sector codes** — in API response, not extracted
6. **CanadaBuys GSIN codes** — parsed but not stored in `gsin` field

### Medium Effort (Requires Detail Page Scraping)

1. **BidsandTenders detail pages** (Yukon) — description, category, community, plan takers, procurement type
2. **MERX detail pages** (Ottawa, Manitoba, NL, Winnipeg) — description, contact, documents, amendments
3. **Ontario Jaggaer detail pages** — description, category
4. **Ariba detail pages** (Calgary, Edmonton) — description, category, contact

### Standardization Needs

| Issue | Affected Sources | Fix |
|---|---|---|
| **Category values inconsistent** | All sources with categories | Normalize to: goods / services / works / mixed |
| **Procurement type not extracted** | All sources | Parse from title patterns (RFP, RFQ, RFI, ITT, ITQ) + source fields |
| **French-only titles** | SEAO (QC) | Flag language or add translation |
| **Mixed language titles** | CanadaBuys (fallback logic) | Add `language` field or always prefer EN |
| **Date format variations** | All HTML scrapers | Enforce ISO 8601 parsing with locale handling |
| **Status value inconsistency** | Cross-source | Normalize to exactly: open / closed / awarded / cancelled |
| **Province codes** | Some store full name, some 2-letter | Always store 2-letter ISO code |
| **delivery_location misuse** | Pipeline mapping | Rename/repurpose: store jurisdiction separately |
| **buyer_org hard-coded** | Calgary, Edmonton, Toronto, Vancouver | Include department/division when available |

### Proposed New DB Fields

| Field | Purpose | Sources |
|---|---|---|
| `question_deadline` | Deadline to submit questions | BidsandTenders, some MERX |
| `language` | "en" / "fr" / "en,fr" | All (derived) |
| `jurisdiction` | "federal" / "provincial" / "municipal" | All (currently misused in delivery_location) |
| `subcategory` | Detailed category (e.g., "Electrical") | BidsandTenders, CanadaBuys |
| `community` | Delivery/work location city | BidsandTenders, Nunavut |
| `indigenous_territory` | Traditional territory name | BidsandTenders |

### Proposed New Tables

| Table | Purpose |
|---|---|
| `plan_takers` | Company name, contact name, address, phone for each registered bidder per tender |
| `tender_documents` | Document name, URL, type for downloadable bid documents |
| `tender_amendments` | Amendment number, date, description for tender changes |
| `tender_awards` | Winning company, amount, date for awarded tenders |

---

## Next Steps

1. **Review this document** — confirm priority areas
2. **Fix quick wins** — map existing raw_ocds data, capture visible-but-skipped fields
3. **Standardize pipeline** — normalize categories, procurement types, status values
4. **Add detail page scraping** — BidsandTenders and MERX first (highest metadata ROI)
5. **Schema migration** — add new fields and tables for richer data model
6. **Data backfill** — re-scrape with enhanced spiders to populate missing fields
