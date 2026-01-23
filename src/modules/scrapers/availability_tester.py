"""Test availability by attempting to request ownership"""

async def test_availability(page, current_available_value: str, logger) -> str:
    """
    Test if a lead/opportunity is actually available by clicking Request Ownership.
    
    Args:
        page: Playwright page object
        current_available_value: The "Available Candidate" field value ("Yes" or "No")
        logger: Actor logger
        
    Returns:
        ca_status: 'Available' or 'Taken'
    """
    
    # If Available = "Yes", no need to test
    if current_available_value == "Yes":
        logger.info('Available Candidate = Yes, status is Available')
        return 'Available'
    
    # If Available = "No", we need to test by requesting ownership
    logger.info('Available Candidate = No, testing actual availability...')
    
    try:
        # Click "Request Ownership" button
        request_button = page.locator('button:has-text("Request Ownership")')
        
        if not await request_button.is_visible(timeout=2000):
            logger.warning('Request Ownership button not found, assuming Taken')
            return 'Taken'
        
        logger.info('Found Request Ownership button, clicking...')
        await request_button.click()
        await page.wait_for_timeout(3000)  # Wait for response
        
        # Check for popup with "Cancel Request" button
        logger.info('Checking for Cancel Request popup...')
        cancel_button = page.locator('button:has-text("Cancel Request")')
        
        if await cancel_button.is_visible(timeout=2000):
            logger.info('POPUP DETECTED - Candidate is Available')
            # Cancel the request to avoid claiming
            await cancel_button.click()
            await page.wait_for_timeout(1000)
            return 'Available'
        
        logger.info('No popup found, checking for error toast...')
        
        # Check for Salesforce toast notification (error type)
        # Look for the toast container with error/warning styling
        toast_locator = page.locator('div[role="status"].forceToastMessage, div.toastContainer')
        
        try:
            if await toast_locator.first.is_visible(timeout=2000):
                logger.info('ERROR TOAST DETECTED - Candidate is Taken')
                # Try to close the toast
                close_button = page.locator('button[title="Close"], button.toastClose').first
                if await close_button.is_visible(timeout=1000):
                    await close_button.click()
                    await page.wait_for_timeout(500)
                return 'Taken'
        except Exception as e:
            logger.warning(f'Error checking toast: {e}')
        
        # Fallback: if neither popup nor error toast, assume Taken
        logger.warning('No clear response after clicking Request Ownership, assuming Taken')
        return 'Taken'
        
    except Exception as e:
        logger.error(f'Error testing availability: {str(e)}')
        return 'Taken'