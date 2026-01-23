# CA Search and Scrape - Airtable Integration v1

Automated Vistage CA member search and profile scraping with direct Airtable integration. Designed to work seamlessly with Airtable Automations without runtime limits.

## Features

- **Direct Airtable Integration**: Writes results directly to Airtable via API
- **No Runtime Limits**: Runs on Apify infrastructure, bypassing Airtable's automation timeout
- **Multi-method Search**: LinkedIn, domain, or name-based search
- **Intelligent Matching**: Fuzzy matching with confidence scoring
- **Auto-scraping**: Automatically scrapes full profile for high-confidence (≥70%) matches
- **Real-time Updates**: Updates Airtable in real-time as the search progresses

## How It Works

1. **Airtable Automation** triggers and sends a webhook to Apify with record ID and search params
2. **Apify Actor** runs the search and scrape (no timeout issues)
3. **Actor writes results** back to Airtable using the Airtable API
4. **Done!** - Results appear in Airtable automatically

## Setup

### 1. Create Airtable Personal Access Token

1. Go to https://airtable.com/create/tokens
2. Click "Create new token"
3. Name it "Apify CA Search Integration"
4. Add these scopes:
   - `data.records:read`
   - `data.records:write`
5. Add access to your specific base
6. Copy the token (starts with `pat...`)

### 2. Get Your Airtable Base ID

1. Open your Airtable base
2. Look at the URL: `https://airtable.com/appXXXXXXXXXXXXXX/...`
3. The part starting with `app` is your Base ID

### 3. Configure the Actor

Set these as **default values** in the Actor input schema on Apify:

- **airtable_token**: Your Personal Access Token from step 1
- **airtable_base_id**: Your Base ID from step 2
- **airtable_table_name**: `HubSpot Sync` (or your table name)
- **vistage_username**: `christoff.poppe@vistagechair.com`
- **vistage_password**: Your Vistage password

### 4. Create Airtable Automation

In Airtable, create an automation:

**Trigger**: When record matches conditions (e.g., "Prospect Linkedin URL is not empty")

**Action**: Send webhook request
- **URL**: `https://api.apify.com/v2/acts/xoffpoppe~ca-search-and-scrape-airtable-v1/runs?token=YOUR_APIFY_TOKEN`
- **Method**: POST
- **Headers**: `Content-Type: application/json`
- **Body**:
```json
{
  "record_id": "{{Record ID}}",
  "linkedin_slug": "{{Prospect Linkedin URL}}",
  "domain": "{{Company Domain}}",
  "search_name": "{{Full Name}}",
  "expected_company": "{{Company Name}}"
}
```

**Note**: The webhook only needs to send the record ID and search parameters. Airtable credentials are already stored in the Actor defaults.

## Input Parameters

### Required (set as Actor defaults)
- `airtable_token` - Airtable Personal Access Token
- `airtable_base_id` - Your Airtable base ID
- `vistage_username` - Vistage login email
- `vistage_password` - Vistage password

### Required (from Airtable automation)
- `record_id` - Airtable record ID to update

### Search Parameters (at least one required)
- `linkedin_slug` - LinkedIn profile URL or slug
- `domain` - Company website domain
- `search_name` + `expected_company` - Name and company for search

### Optional
- `auto_scrape` - Auto-scrape profiles for high-confidence matches (default: `true`)
- `airtable_table_name` - Override default table name (default: `HubSpot Sync`)

## Output

The Actor updates two Airtable fields:

### Notepad
Simple status summary:
```
✅ Match found (85%) + Profile scraped
See CA Search Notes for details
```

### CA Search Notes
Detailed results including:
- Match score and confidence level
- Member details (name, company, title, MSA, section)
- Salesforce URL
- Full scraped profile data (if auto_scrape enabled):
  - Contact info (email, phone)
  - Location
  - LinkedIn URL
  - Membership details
  - Company details (revenue, employees, industry)
  - Bio
  - Professional highlights
  - Education

## Search Logic

1. **LinkedIn Search** (if `linkedin_slug` provided)
   - Searches Vistage by LinkedIn profile
   - Highest accuracy for finding the right person

2. **Domain Search** (if `domain` provided)
   - Searches by company domain
   - Good for finding company members

3. **Name Search** (if `search_name` + `expected_company` provided)
   - Searches by person's name
   - Validates against expected company

## Matching Confidence

- **High (≥70%)**: Auto-scraped, green checkmark ✅
- **Medium (50-69%)**: Manual review recommended, yellow warning ⚠️
- **Low (<50%)**: Not returned as match

## Example Airtable Automation Webhook

```json
{
  "record_id": "recABC123XYZ",
  "linkedin_slug": "john-smith-12345",
  "domain": "acmecorp.com",
  "search_name": "John Smith",
  "expected_company": "Acme Corporation"
}
```

## Troubleshooting

### "Login failed - check credentials"
- Verify `vistage_username` and `vistage_password` in Actor defaults

### "Missing required Airtable configuration"
- Ensure `airtable_token`, `airtable_base_id`, and `record_id` are provided

### "Airtable update failed"
- Check your Personal Access Token has write permissions
- Verify the token has access to the specific base
- Confirm field names match exactly: "Notepad" and "CA Search Notes"

### No results in Airtable
- Check Apify run logs for errors
- Verify the `record_id` passed from Airtable is correct
- Ensure field names match your table

## Cost Optimization

- Each run costs ~$0.01-0.05 depending on search complexity
- Auto-scraping adds minimal cost (~10% more)
- Runs typically complete in 30-90 seconds

## Security

- Airtable token is stored as a secret in Apify
- Vistage password is stored as a secret
- All credentials are encrypted at rest
- Never exposed in logs or datasets
