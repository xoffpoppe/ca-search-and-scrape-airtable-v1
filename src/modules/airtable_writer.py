"""Airtable API integration for writing search/scrape results back to Airtable."""

import aiohttp
from typing import Dict, Any, Optional


class AirtableWriter:
    """Handles writing results to Airtable via API."""

    def __init__(self, token: str, base_id: str, table_name: str, record_id: str, logger):
        self.token = token
        self.base_id = base_id
        self.table_name = table_name
        self.record_id = record_id
        self.logger = logger
        self.base_url = f"https://api.airtable.com/v0/{base_id}/{table_name}"

    async def update_record(self, fields: Dict[str, Any]) -> bool:
        """
        Update an Airtable record with the provided fields.

        Args:
            fields: Dictionary of field names and values to update

        Returns:
            True if successful, False otherwise
        """
        url = f"{self.base_url}/{self.record_id}"

        headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }

        payload = {'fields': fields}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.patch(url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        self.logger.info(f'✅ Airtable record {self.record_id} updated successfully')
                        return True
                    else:
                        error_text = await response.text()
                        self.logger.error(f'Airtable update failed ({response.status}): {error_text}')
                        return False
        except Exception as e:
            self.logger.error(f'Airtable update exception: {str(e)}')
            return False

    async def write_search_start(self) -> None:
        """Write initial status when search starts."""
        fields = {
            'CA Search Notes': '⏳ CA Search in progress...\n\nSearching Vistage database...'
        }
        await self.update_record(fields)

    async def write_search_results(self, result: Dict[str, Any]) -> None:
        """
        Format and write search/scrape results to Airtable.

        Args:
            result: The output dictionary from the actor
        """
        fields = {}

        if not result.get('match_found'):
            # No match found
            fields['CA Search Notes'] = self._format_no_match(result)
        else:
            # Match found - build fields
            ca_search_notes, ca_url, ca_status = self._format_match_found(result)
            fields['CA Search Notes'] = ca_search_notes

            # Only add CA URL and Status if high confidence (≥70%)
            if result.get('confidence') == 'high':
                if ca_url:
                    fields['CA URL Possible Match'] = ca_url
                if ca_status:
                    fields['CA Possible Status'] = ca_status

        await self.update_record(fields)

    async def write_error(self, error_message: str) -> None:
        """Write error message to Airtable."""
        fields = {
            'CA Search Notes': f'❌ Error occurred during search/scrape\n\n{error_message}'
        }
        await self.update_record(fields)

    def _format_no_match(self, result: Dict[str, Any]) -> str:
        """Format output for no match found."""
        notes = '❌ NO MATCH FOUND\n\n'

        metadata = result.get('search_metadata', {})
        if metadata.get('search_attempts'):
            notes += f'Search attempts: {", ".join(metadata["search_attempts"])}\n'
        if metadata.get('total_results_found') is not None:
            notes += f'Total results examined: {metadata["total_results_found"]}\n'

        notes += '\nNo matching records found in Vistage database.\n'
        notes += 'All search results scored below 50% threshold.\n'

        timing = result.get('timing', {})
        if timing.get('search_end'):
            notes += f'\n---\n❌ Search Complete (No Match) | {timing["search_end"]}\n'

        return notes

    def _format_match_found(self, result: Dict[str, Any]) -> tuple:
        """
        Format output for match found (with or without scrape).

        Returns:
            (ca_search_notes, ca_url, ca_status) tuple
        """
        confidence = result.get('confidence', 'needs_review')
        match_score = result.get('match_score', 0)
        auto_scraped = result.get('auto_scraped', False)

        # Status icon
        status_icon = '✅' if confidence == 'high' else '⚠️'

        # CA Search Notes (detailed)
        status_text = 'MATCH FOUND' if confidence == 'high' else 'MATCH FOUND - NEEDS REVIEW'
        notes = f'{status_icon} {status_text}\n\n'

        # Match details from search_metadata
        metadata = result.get('search_metadata', {})
        notes += '--- MATCH DETAILS ---\n'
        notes += f'Score: {match_score}%\n'
        notes += f'Name: {metadata.get("name", "N/A")}\n'
        notes += f'Company: {metadata.get("company", "N/A")}\n'
        notes += f'Title: {metadata.get("title", "N/A")}\n'
        notes += f'MSA: {metadata.get("msa", "N/A")}\n'
        notes += f'Section: {metadata.get("section", "N/A")}\n'
        notes += f'Record Type: {metadata.get("record_type", "N/A")}\n'
        notes += f'Salesforce URL: {metadata.get("salesforce_url", "N/A")}\n'
        notes += f'\nConfidence: {"High (≥70%)" if confidence == "high" else "Medium (50-69%)"}\n'

        if metadata.get('search_type'):
            notes += f'Search Method: {metadata["search_type"]}\n'
        if metadata.get('search_attempts'):
            notes += f'Search Attempts: {", ".join(metadata["search_attempts"])}\n'

        if confidence == 'needs_review':
            notes += '\n⚠️ Manual Review Recommended\n'
            notes += 'Score is between 50-69%. Please verify this is the correct person.\n'

        # Add scraped data if available
        if auto_scraped and result.get('scrape_data'):
            notes += '\n--- SCRAPED PROFILE DATA ---\n'
            notes += self._format_scrape_data(result['scrape_data'])

        # Timing info
        timing = result.get('timing', {})
        notes += f'\n---\n{status_icon} Search Complete'
        if auto_scraped:
            notes += ' + Profile Scraped'
        if timing.get('search_end'):
            notes += f' | {timing["search_end"]}\n'
        else:
            notes += '\n'

        # Extract CA URL (Salesforce URL)
        ca_url = metadata.get('salesforce_url', None)

        # Extract CA Possible Status from scrape_data (only if scraped)
        ca_status = None
        if auto_scraped and result.get('scrape_data'):
            ca_status = result['scrape_data'].get('proposed ca status', None)

        return notes, ca_url, ca_status

    def _format_scrape_data(self, scrape_data: Dict[str, Any]) -> str:
        """Format scraped profile data for Airtable display."""
        formatted = ''

        # Basic info
        formatted += f'Full Name: {scrape_data.get("full_name", "N/A")}\n'
        if scrape_data.get('preferred_name'):
            formatted += f'Preferred Name: {scrape_data["preferred_name"]}\n'
        formatted += f'Company: {scrape_data.get("company_name", "N/A")}\n'
        formatted += f'Title: {scrape_data.get("title", "N/A")}\n'

        # Contact info
        if scrape_data.get('email'):
            formatted += f'Email: {scrape_data["email"]}\n'
        if scrape_data.get('phone'):
            formatted += f'Phone: {scrape_data["phone"]}\n'

        # Location
        city = scrape_data.get('city', '')
        state = scrape_data.get('state', '')
        if city or state:
            formatted += f'Location: {city}, {state}\n'

        # LinkedIn
        if scrape_data.get('linkedin_url'):
            formatted += f'LinkedIn: {scrape_data["linkedin_url"]}\n'

        # Membership details
        if scrape_data.get('member_since'):
            formatted += f'Member Since: {scrape_data["member_since"]}\n'
        if scrape_data.get('group_name'):
            formatted += f'Group: {scrape_data["group_name"]}\n'
        if scrape_data.get('chair_name'):
            formatted += f'Chair: {scrape_data["chair_name"]}\n'

        # Company details
        if scrape_data.get('company_revenue'):
            formatted += f'Company Revenue: {scrape_data["company_revenue"]}\n'
        if scrape_data.get('company_employees'):
            formatted += f'Employees: {scrape_data["company_employees"]}\n'
        if scrape_data.get('industry'):
            formatted += f'Industry: {scrape_data["industry"]}\n'

        # Bio
        if scrape_data.get('bio'):
            formatted += f'\nBio:\n{scrape_data["bio"]}\n'

        # Professional highlights
        highlights = scrape_data.get('professional_highlights', [])
        if highlights:
            formatted += '\nProfessional Highlights:\n'
            for h in highlights:
                formatted += f'• {h}\n'

        # Education
        education = scrape_data.get('education', [])
        if education:
            formatted += '\nEducation:\n'
            for e in education:
                formatted += f'• {e}\n'

        return formatted
