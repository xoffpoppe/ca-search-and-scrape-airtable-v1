# CA Search and Scrape v1

Combined actor that searches Vistage/Salesforce for candidates and automatically scrapes high-confidence matches (≥70%).

## Workflow

```
Input: Name/Company/LinkedIn/Domain + Credentials
    ↓
Phase 1: SEARCH (CA Search V2 logic)
    ↓
Check confidence level
    ↓
┌───────────────┴───────────────┐
│                               │
High (≥70%)              Medium/Low (<70%)
│                               │
↓                               ↓
Phase 2: AUTO-SCRAPE        STOP - Return search only
(CA Scrape V3 logic)            │
│                               ↓
↓                          Output: Search results
Output: Search + 18 fields      with salesforce_url for
                                manual scraping
```

## Input

```json
{
  "linkedin_slug": "https://www.linkedin.com/in/john-smith",
  "domain": "acme.com",
  "search_name": "John Smith",
  "expected_company": "Acme Corp",
  "vistage_username": "your@email.com",
  "vistage_password": "yourpassword"
}
```

**Search Priority:** LinkedIn → Domain → Name+Company

## Output - High Confidence (≥70%)

```json
{
  "search_successful": true,
  "match_found": true,
  "confidence": "high",
  "match_score": 95.0,
  "auto_scraped": true,

  "search_metadata": {
    "search_type": "linkedin",
    "name": "John Smith",
    "company": "Acme Corp",
    "salesforce_url": "https://app.vistage.com/..."
  },

  "scrape_data": {
    "ca name": "John Smith",
    "ca email": "john@acme.com",
    "ca phone": "(312) 555-1234",
    // ... 15 more fields
    "proposed ca status": "Available"
  },

  "timing": {
    "search_duration_seconds": 15.0,
    "scrape_duration_seconds": 23.0,
    "total_duration_seconds": 38.0
  }
}
```

## Output - Medium/Low Confidence (<70%)

```json
{
  "search_successful": true,
  "match_found": true,
  "confidence": "needs_review",
  "match_score": 65.0,
  "auto_scraped": false,

  "name": "John Smith",
  "company": "Similar Company Inc",
  "salesforce_url": "https://app.vistage.com/...",
  "message": "Manual review recommended - scraping skipped",

  "timing": {
    "search_duration_seconds": 18.0
  }
}
```

## Performance

- High confidence run: ~38-43 seconds (search + scrape)
- Medium/low confidence run: ~12-20 seconds (search only)
- Under Clay's 60-second timeout ✅
- Over AirTable automation 30-second limit ❌

## Features

✅ Single browser session (efficient)
✅ Cascading search (LinkedIn → Domain → Name)
✅ Fuzzy matching with 100+ nickname variations
✅ Chicago MSA tiebreaker
✅ Auto-scrape for high confidence
✅ Graceful degradation if scrape fails
✅ Rules engine for proposed status
✅ Complete timing information

## Version History

**v1.0** - Initial release combining CA Search V2 and CA Scrape V3
