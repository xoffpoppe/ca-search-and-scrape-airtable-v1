"""Authentication module for Vistage/Salesforce login.

Extracted from Actor 1 (ca-api-search) main.py login logic
"""


async def login_to_vistage(page, username: str, password: str, logger):
    """
    Log in to Vistage/Salesforce platform.
    
    Args:
        page: Playwright page object
        username: Vistage username
        password: Vistage password
        logger: Actor logger
        
    Returns:
        bool: True if login successful, False otherwise
    """
    logger.info('Navigating to Vistage login page...')
    await page.goto('https://app.vistage.com/chairapp/Login')
    
    # Wait for the page to load
    await page.wait_for_load_state('networkidle')
    
    # Fill in login credentials with correct selectors
    logger.info('Entering credentials...')
    await page.fill('input[name="loginPage:loginForm:loginUsername"]', username)
    await page.fill('input[name="loginPage:loginForm:loginPassword"]', password)
    
    # Click the login button
    logger.info('Clicking login button...')
    await page.click('input[name="loginPage:loginForm:login-submit"]')
    
    # Wait for login to complete and verify we're actually logged in
    await page.wait_for_load_state('networkidle')
    await page.wait_for_timeout(3000)
    
    # Check if we're still on the login page or successfully logged in
    current_url = page.url
    logger.info(f'After login, current URL: {current_url}')
    
    if 'Login' in current_url:
        logger.error('Still on login page - login may have failed!')
        await page.screenshot(path='login_failed.png')
        page_text = await page.inner_text('body')
        logger.error(f'Page content: {page_text[:500]}')
        return False
    else:
        logger.info('Login successful!')
        return True