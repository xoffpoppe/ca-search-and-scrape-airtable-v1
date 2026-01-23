// CA Search and Scrape - Airtable Integration v1
// Searches Vistage CA, scrapes profile, and writes results back to Airtable

import { Actor } from 'apify';
import { gotScraping } from 'got-scraping';
import { chromium } from 'playwright';

await Actor.init();

const input = await Actor.getInput();
const {
    // Airtable config (set as defaults in Actor input schema)
    airtable_token,
    airtable_base_id,
    airtable_table_name = 'HubSpot Sync',

    // Record to update
    record_id,

    // Vistage credentials
    vistage_username,
    vistage_password,

    // Search parameters (at least one required)
    linkedin_slug,
    domain,
    search_name,
    expected_company,

    // Options
    auto_scrape = true
} = input;

// Validate required fields
if (!airtable_token || !airtable_base_id || !record_id) {
    throw new Error('Missing required Airtable configuration: airtable_token, airtable_base_id, and record_id are required');
}

if (!vistage_username || !vistage_password) {
    throw new Error('Missing Vistage credentials: vistage_username and vistage_password are required');
}

if (!linkedin_slug && !domain && !(search_name && expected_company)) {
    throw new Error('At least one search parameter required: linkedin_slug, domain, or (search_name + expected_company)');
}

// Airtable field names (matching your table)
const AIRTABLE_FIELDS = {
    results: 'Notepad',
    caSearchNotes: 'CA Search Notes'
};

// Airtable API helper
async function updateAirtableRecord(recordId, fields) {
    const url = `https://api.airtable.com/v0/${airtable_base_id}/${encodeURIComponent(airtable_table_name)}/${recordId}`;

    console.log(`Updating Airtable record: ${recordId}`);

    try {
        const response = await gotScraping({
            url,
            method: 'PATCH',
            headers: {
                'Authorization': `Bearer ${airtable_token}`,
                'Content-Type': 'application/json'
            },
            json: { fields },
            responseType: 'json'
        });

        console.log('Airtable update successful');
        return response.body;
    } catch (error) {
        console.error('Airtable update failed:', error.message);
        throw error;
    }
}

// Update Airtable with initial status
await updateAirtableRecord(record_id, {
    [AIRTABLE_FIELDS.results]: '⏳ Search in progress...',
    [AIRTABLE_FIELDS.caSearchNotes]: `Search started at ${new Date().toLocaleString()}\n\nSearching Vistage database...`
});

// Import the search and scrape logic from the main actor
// We'll use the same logic but adapted for Airtable output

let browser;
let result;

try {
    console.log('Launching browser...');
    browser = await chromium.launch({ headless: true });
    const context = await browser.newContext();
    const page = await context.newPage();

    // Login to Vistage
    console.log('Logging in to Vistage...');
    await page.goto('https://app.vistage.com/login');
    await page.fill('input[name="username"]', vistage_username);
    await page.fill('input[name="password"]', vistage_password);
    await page.click('button[type="submit"]');
    await page.waitForLoadState('networkidle');

    // Check if login was successful
    const currentUrl = page.url();
    if (currentUrl.includes('/login')) {
        throw new Error('Login failed - check credentials');
    }

    console.log('Login successful');

    // Initialize result object
    result = {
        match_found: false,
        confidence: null,
        match_score: 0,
        search_metadata: {
            search_attempts: [],
            search_type: null,
            total_results_found: 0
        }
    };

    // Search logic (same as ca-search-v2)
    let matchFound = false;

    // Try LinkedIn search first if provided
    if (linkedin_slug && !matchFound) {
        console.log(`Searching by LinkedIn: ${linkedin_slug}`);
        result.search_metadata.search_attempts.push('linkedin');

        const slug = linkedin_slug.replace(/.*linkedin\.com\/in\//, '').replace(/\/$/, '');
        await page.goto(`https://app.vistage.com/members?search=${encodeURIComponent(slug)}`);
        await page.waitForLoadState('networkidle');

        const searchResults = await page.$$('[data-testid="member-card"]');
        result.search_metadata.total_results_found += searchResults.length;

        if (searchResults.length > 0) {
            matchFound = await evaluateMatch(page, searchResults[0], expected_company);
            if (matchFound) {
                result.search_metadata.search_type = 'linkedin';
            }
        }
    }

    // Try domain search if no match yet
    if (domain && !matchFound) {
        console.log(`Searching by domain: ${domain}`);
        result.search_metadata.search_attempts.push('domain');

        await page.goto(`https://app.vistage.com/members?search=${encodeURIComponent(domain)}`);
        await page.waitForLoadState('networkidle');

        const searchResults = await page.$$('[data-testid="member-card"]');
        result.search_metadata.total_results_found += searchResults.length;

        for (const card of searchResults) {
            matchFound = await evaluateMatch(page, card, expected_company, search_name);
            if (matchFound) {
                result.search_metadata.search_type = 'domain';
                break;
            }
        }
    }

    // Try name search if no match yet
    if (search_name && !matchFound) {
        console.log(`Searching by name: ${search_name}`);
        result.search_metadata.search_attempts.push('name');

        await page.goto(`https://app.vistage.com/members?search=${encodeURIComponent(search_name)}`);
        await page.waitForLoadState('networkidle');

        const searchResults = await page.$$('[data-testid="member-card"]');
        result.search_metadata.total_results_found += searchResults.length;

        for (const card of searchResults) {
            matchFound = await evaluateMatch(page, card, expected_company, search_name);
            if (matchFound) {
                result.search_metadata.search_type = 'name';
                break;
            }
        }
    }

    // Helper function to evaluate match and extract data
    async function evaluateMatch(page, card, expectedCompany, expectedName) {
        try {
            const nameEl = await card.$('[data-testid="member-name"]');
            const companyEl = await card.$('[data-testid="member-company"]');
            const titleEl = await card.$('[data-testid="member-title"]');

            const name = nameEl ? await nameEl.textContent() : '';
            const company = companyEl ? await companyEl.textContent() : '';
            const title = titleEl ? await titleEl.textContent() : '';

            // Calculate match score (same logic as ca-search-v2)
            let score = 0;

            // Name matching (if provided)
            if (expectedName) {
                const nameSimilarity = calculateStringSimilarity(name.toLowerCase(), expectedName.toLowerCase());
                score += nameSimilarity * 50; // Max 50 points
            } else {
                score += 50; // Give full name points if not checking name
            }

            // Company matching (if provided)
            if (expectedCompany) {
                const companySimilarity = calculateStringSimilarity(company.toLowerCase(), expectedCompany.toLowerCase());
                score += companySimilarity * 50; // Max 50 points
            } else {
                score += 50; // Give full company points if not checking company
            }

            console.log(`Match score: ${score}% for ${name} at ${company}`);

            // Only consider matches >= 50%
            if (score >= 50) {
                // Click to get full profile URL and additional details
                await card.click();
                await page.waitForLoadState('networkidle');

                const profileUrl = page.url();
                const salesforceUrl = profileUrl; // Vistage uses Salesforce URLs

                // Extract additional details from profile page
                const msa = await extractText(page, '[data-testid="member-msa"]');
                const section = await extractText(page, '[data-testid="member-section"]');
                const recordType = await extractText(page, '[data-testid="member-type"]');

                result.match_found = true;
                result.match_score = Math.round(score);
                result.confidence = score >= 70 ? 'high' : 'needs_review';
                result.name = name;
                result.company = company;
                result.title = title;
                result.msa = msa;
                result.section = section;
                result.record_type = recordType;
                result.salesforce_url = salesforceUrl;

                // Auto-scrape if enabled and high confidence
                if (auto_scrape && score >= 70) {
                    console.log('Auto-scraping profile (high confidence match)...');
                    result.scrape_data = await scrapeProfile(page);
                }

                return true;
            }

            return false;
        } catch (error) {
            console.error('Error evaluating match:', error.message);
            return false;
        }
    }

    // String similarity helper (Levenshtein distance)
    function calculateStringSimilarity(str1, str2) {
        const matrix = [];

        for (let i = 0; i <= str2.length; i++) {
            matrix[i] = [i];
        }

        for (let j = 0; j <= str1.length; j++) {
            matrix[0][j] = j;
        }

        for (let i = 1; i <= str2.length; i++) {
            for (let j = 1; j <= str1.length; j++) {
                if (str2.charAt(i - 1) === str1.charAt(j - 1)) {
                    matrix[i][j] = matrix[i - 1][j - 1];
                } else {
                    matrix[i][j] = Math.min(
                        matrix[i - 1][j - 1] + 1,
                        matrix[i][j - 1] + 1,
                        matrix[i - 1][j] + 1
                    );
                }
            }
        }

        const maxLen = Math.max(str1.length, str2.length);
        const distance = matrix[str2.length][str1.length];
        return (1 - distance / maxLen) * 100;
    }

    // Profile scraper
    async function scrapeProfile(page) {
        const scrapeData = {};

        try {
            // Basic info
            scrapeData.full_name = await extractText(page, '[data-testid="profile-name"]');
            scrapeData.preferred_name = await extractText(page, '[data-testid="profile-preferred-name"]');
            scrapeData.company_name = await extractText(page, '[data-testid="profile-company"]');
            scrapeData.title = await extractText(page, '[data-testid="profile-title"]');

            // Contact info
            scrapeData.email = await extractText(page, '[data-testid="profile-email"]');
            scrapeData.phone = await extractText(page, '[data-testid="profile-phone"]');

            // Location
            scrapeData.city = await extractText(page, '[data-testid="profile-city"]');
            scrapeData.state = await extractText(page, '[data-testid="profile-state"]');

            // LinkedIn
            const linkedinLink = await page.$('[data-testid="profile-linkedin"]');
            if (linkedinLink) {
                scrapeData.linkedin_url = await linkedinLink.getAttribute('href');
            }

            // Membership details
            scrapeData.member_since = await extractText(page, '[data-testid="profile-member-since"]');
            scrapeData.group_name = await extractText(page, '[data-testid="profile-group"]');
            scrapeData.chair_name = await extractText(page, '[data-testid="profile-chair"]');

            // Company details
            scrapeData.company_revenue = await extractText(page, '[data-testid="profile-revenue"]');
            scrapeData.company_employees = await extractText(page, '[data-testid="profile-employees"]');
            scrapeData.industry = await extractText(page, '[data-testid="profile-industry"]');

            // Bio
            scrapeData.bio = await extractText(page, '[data-testid="profile-bio"]');

            // Professional highlights (array)
            const highlights = await page.$$('[data-testid="profile-highlight"]');
            scrapeData.professional_highlights = [];
            for (const highlight of highlights) {
                const text = await highlight.textContent();
                if (text) scrapeData.professional_highlights.push(text.trim());
            }

            // Education (array)
            const education = await page.$$('[data-testid="profile-education"]');
            scrapeData.education = [];
            for (const edu of education) {
                const text = await edu.textContent();
                if (text) scrapeData.education.push(text.trim());
            }

            console.log('Profile scraping complete');
            return scrapeData;
        } catch (error) {
            console.error('Error scraping profile:', error.message);
            return scrapeData; // Return partial data
        }
    }

    // Helper to extract text safely
    async function extractText(page, selector) {
        try {
            const element = await page.$(selector);
            if (element) {
                const text = await element.textContent();
                return text ? text.trim() : null;
            }
            return null;
        } catch {
            return null;
        }
    }

} catch (error) {
    console.error('Search/scrape failed:', error.message);

    // Update Airtable with error
    await updateAirtableRecord(record_id, {
        [AIRTABLE_FIELDS.results]: `❌ Error: ${error.message}`,
        [AIRTABLE_FIELDS.caSearchNotes]: `❌ Error: ${error.message}\nRun failed at ${new Date().toLocaleString()}`
    });

    throw error;
} finally {
    if (browser) {
        await browser.close();
    }
}

// Format results for Airtable
console.log('Formatting results for Airtable...');

let notepad = '';
let caSearchNotes = '';

if (result.match_found) {
    const statusIcon = result.confidence === 'high' ? '✅' : '⚠️';

    // Notepad (simple summary)
    notepad = `${statusIcon} Match found (${result.match_score}%)`;
    if (result.scrape_data) {
        notepad += ` + Profile scraped`;
    }
    notepad += `\nSee CA Search Notes for details`;

    // CA Search Notes (detailed)
    const statusText = result.confidence === 'high' ? 'MATCH FOUND' : 'MATCH FOUND - NEEDS REVIEW';
    caSearchNotes = `${statusIcon} ${statusText}\n`;
    caSearchNotes += `\n--- MATCH DETAILS ---\n`;
    caSearchNotes += `Score: ${result.match_score}%\n`;
    caSearchNotes += `Name: ${result.name || 'N/A'}\n`;
    caSearchNotes += `Company: ${result.company || 'N/A'}\n`;
    caSearchNotes += `Title: ${result.title || 'N/A'}\n`;
    caSearchNotes += `MSA: ${result.msa || 'N/A'}\n`;
    caSearchNotes += `Section: ${result.section || 'N/A'}\n`;
    caSearchNotes += `Record Type: ${result.record_type || 'N/A'}\n`;
    caSearchNotes += `Salesforce URL: ${result.salesforce_url || 'N/A'}\n`;
    caSearchNotes += `\nConfidence: ${result.confidence === 'high' ? 'High (≥70%)' : 'Medium (50-69%)'}\n`;

    if (result.search_metadata) {
        caSearchNotes += `Search Method: ${result.search_metadata.search_type}\n`;
        caSearchNotes += `Search Attempts: ${result.search_metadata.search_attempts.join(', ')}\n`;
    }

    if (result.confidence === 'needs_review') {
        caSearchNotes += `\n⚠️ Manual Review Recommended\n`;
        caSearchNotes += `Score is between 50-69%. Please verify this is the correct person.\n`;
    }

    // Add scraped data if available
    if (result.scrape_data) {
        caSearchNotes += `\n--- SCRAPED PROFILE DATA ---\n`;
        const scrape = result.scrape_data;

        caSearchNotes += `Full Name: ${scrape.full_name || 'N/A'}\n`;
        if (scrape.preferred_name) caSearchNotes += `Preferred Name: ${scrape.preferred_name}\n`;
        caSearchNotes += `Company: ${scrape.company_name || 'N/A'}\n`;
        caSearchNotes += `Title: ${scrape.title || 'N/A'}\n`;

        if (scrape.email) caSearchNotes += `Email: ${scrape.email}\n`;
        if (scrape.phone) caSearchNotes += `Phone: ${scrape.phone}\n`;

        if (scrape.city || scrape.state) {
            caSearchNotes += `Location: ${scrape.city || ''}, ${scrape.state || ''}\n`;
        }

        if (scrape.linkedin_url) caSearchNotes += `LinkedIn: ${scrape.linkedin_url}\n`;

        if (scrape.member_since) caSearchNotes += `Member Since: ${scrape.member_since}\n`;
        if (scrape.group_name) caSearchNotes += `Group: ${scrape.group_name}\n`;
        if (scrape.chair_name) caSearchNotes += `Chair: ${scrape.chair_name}\n`;

        if (scrape.company_revenue) caSearchNotes += `Company Revenue: ${scrape.company_revenue}\n`;
        if (scrape.company_employees) caSearchNotes += `Employees: ${scrape.company_employees}\n`;
        if (scrape.industry) caSearchNotes += `Industry: ${scrape.industry}\n`;

        if (scrape.bio) caSearchNotes += `\nBio:\n${scrape.bio}\n`;

        if (scrape.professional_highlights?.length > 0) {
            caSearchNotes += `\nProfessional Highlights:\n`;
            scrape.professional_highlights.forEach(h => caSearchNotes += `• ${h}\n`);
        }

        if (scrape.education?.length > 0) {
            caSearchNotes += `\nEducation:\n`;
            scrape.education.forEach(e => caSearchNotes += `• ${e}\n`);
        }
    }

    caSearchNotes += `\n---\n${statusIcon} Search Complete`;
    if (result.scrape_data) caSearchNotes += ` + Profile Scraped`;
    caSearchNotes += ` | ${new Date().toLocaleString()}\n`;

} else {
    // No match found
    notepad = `❌ No match found`;

    caSearchNotes = `❌ NO MATCH FOUND\n`;
    if (result.search_metadata?.search_attempts) {
        caSearchNotes += `Search attempts: ${result.search_metadata.search_attempts.join(', ')}\n`;
    }
    if (result.search_metadata?.total_results_found !== undefined) {
        caSearchNotes += `Total results examined: ${result.search_metadata.total_results_found}\n`;
    }
    caSearchNotes += `\nNo matching records found in Vistage database.\n`;
    caSearchNotes += `All search results scored below 50% threshold.\n`;
    caSearchNotes += `\n---\n❌ Search Complete (No Match) | ${new Date().toLocaleString()}\n`;
}

// Update Airtable with final results
await updateAirtableRecord(record_id, {
    [AIRTABLE_FIELDS.results]: notepad,
    [AIRTABLE_FIELDS.caSearchNotes]: caSearchNotes
});

// Save to Apify dataset as well (for debugging)
await Actor.pushData(result);

console.log('✅ Complete! Results written to Airtable.');

await Actor.exit();
