"""
Browser module for Playwright-based browser automation
Handles browser initialization, session persistence, and navigation
"""
import logging
from pathlib import Path
from typing import Optional
import asyncio
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
import config

logger = logging.getLogger(__name__)


class BrowserManager:
    """Manages Playwright browser lifecycle and session persistence"""
    
    def __init__(self, headless: bool = False):
        """
        Initialize browser manager
        
        Args:
            headless: Whether to run browser in headless mode
        """
        self.headless = headless
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
    
    async def init_browser(self) -> Page:
        """
        Initialize browser with persistent session
        
        Returns:
            Playwright Page object
        """
        try:
            self.playwright = await async_playwright().start()
            
            # Launch browser with persistent user data directory
            self.browser = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(config.BROWSER_USER_DATA_DIR),
                headless=self.headless,
                timeout=config.BROWSER_TIMEOUT,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                ]
            )
            
            # Get first page or create new one
            if len(self.browser.pages) > 0:
                self.page = self.browser.pages[0]
                logger.info("Using existing browser page")
            else:
                self.page = await self.browser.new_page()
                logger.info("Created new browser page")
            
            # Set viewport
            await self.page.set_viewport_size({"width": 1280, "height": 720})
            
            logger.info("Browser initialized successfully")
            return self.page
            
        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")
            raise
    
    async def navigate_to(self, url: str) -> bool:
        """
        Navigate to URL with retry logic
        
        Args:
            url: URL to navigate to
            
        Returns:
            True if successful, False otherwise
        """
        if not self.page:
            logger.error("Browser page not initialized")
            return False
        
        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=config.BROWSER_TIMEOUT)
            logger.info(f"Navigated to: {url}")
            return True
        except Exception as e:
            logger.error(f"Failed to navigate to {url}: {e}")
            return False
    
    async def wait_for_element(self, selector: str, timeout: int = None) -> bool:
        """
        Wait for element to appear on page
        
        Args:
            selector: CSS or XPath selector
            timeout: Timeout in milliseconds
            
        Returns:
            True if element found, False if timeout
        """
        if not self.page:
            return False
        
        timeout = timeout or config.TWEET_EXTRACTION_TIMEOUT
        
        try:
            await self.page.wait_for_selector(selector, timeout=timeout)
            logger.debug(f"Element found: {selector}")
            return True
        except Exception as e:
            logger.warning(f"Element not found {selector}: {e}")
            return False
    
    async def scroll_page(self, distance: int = 300) -> bool:
        """
        Scroll page down
        
        Args:
            distance: Number of pixels to scroll
            
        Returns:
            True if successful
        """
        if not self.page:
            return False
        
        try:
            await self.page.evaluate(f"window.scrollBy(0, {distance})")
            logger.debug(f"Scrolled {distance}px")
            return True
        except Exception as e:
            logger.error(f"Failed to scroll: {e}")
            return False
    
    async def get_page_height(self) -> int:
        """Get total height of page"""
        if not self.page:
            return 0
        
        try:
            height = await self.page.evaluate("document.documentElement.scrollHeight")
            return height
        except Exception as e:
            logger.error(f"Failed to get page height: {e}")
            return 0
    
    async def take_screenshot(self, filename: str = None) -> Optional[str]:
        """
        Take screenshot for debugging
        
        Args:
            filename: Filename to save screenshot as
            
        Returns:
            Path to screenshot or None if failed
        """
        if not self.page or not config.DEBUG_SCREENSHOTS:
            return None
        
        try:
            from datetime import datetime
            
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"screenshot_{timestamp}.png"
            
            filepath = config.SCREENSHOTS_DIR / filename
            await self.page.screenshot(path=str(filepath))
            
            logger.info(f"Screenshot saved: {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Failed to take screenshot: {e}")
            return None
    
    async def execute_script(self, script: str, *args):
        """
        Execute JavaScript on page
        
        Args:
            script: JavaScript code
            *args: Arguments to pass to script
            
        Returns:
            Result of script execution
        """
        if not self.page:
            return None
        
        try:
            result = await self.page.evaluate(script, *args)
            return result
        except Exception as e:
            logger.error(f"Failed to execute script: {e}")
            return None
    
    async def get_cookies(self) -> list:
        """Get all browser cookies"""
        if not self.page:
            return []
        
        try:
            cookies = await self.page.context.cookies()
            return cookies
        except Exception as e:
            logger.error(f"Failed to get cookies: {e}")
            return []
    
    async def close(self):
        """Close browser and cleanup"""
        try:
            if self.page:
                await self.page.close()
            
            if self.browser:
                await self.browser.close()
            
            if self.playwright:
                await self.playwright.stop()
            
            logger.info("Browser closed successfully")
            
        except Exception as e:
            logger.error(f"Error closing browser: {e}")
    
    async def check_login_status(self) -> bool:
        """
        Check if user is logged into X.com
        
        Returns:
            True if logged in, False otherwise
        """
        if not self.page:
            return False
        
        try:
            # Check for presence of home timeline element (only visible when logged in)
            await self.page.goto("https://x.com/home", wait_until="domcontentloaded")
            
            # Wait briefly for page to load
            await asyncio.sleep(2)
            
            # Check for logged-in indicators
            is_logged_in = await self.page.evaluate('''
                () => {
                    // Check if navigation element present (logged-in only)
                    return document.querySelector('[data-testid="SideNav_NewTweet_Button"]') !== null;
                }
            ''')
            
            return is_logged_in
            
        except Exception as e:
            logger.error(f"Failed to check login status: {e}")
            return False


# Async wrapper functions for convenience
async def create_browser_manager(headless: bool = False) -> BrowserManager:
    """Create and initialize browser manager"""
    manager = BrowserManager(headless=headless)
    await manager.init_browser()
    return manager
