"""
Scraper module for extracting tweet data from X.com
Handles tweet element detection, parsing, and data extraction
"""
import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
import re
from browser import BrowserManager
import config

logger = logging.getLogger(__name__)


class TweetScraper:
    """Extracts tweet data from X.com using Playwright"""
    
    def __init__(self, browser_manager: BrowserManager):
        """
        Initialize scraper
        
        Args:
            browser_manager: BrowserManager instance
        """
        self.browser = browser_manager
        self.scraped_tweet_ids = set()
    
    async def scrape_feed(self, scroll_iterations: int = None) -> List[Dict[str, Any]]:
        """
        Scrape tweets from X.com feed
        
        Args:
            scroll_iterations: Number of times to scroll (default: MAX_SCROLL_ATTEMPTS)
            
        Returns:
            List of extracted tweet data
        """
        if not await self.browser.check_login_status():
            logger.error("Not logged into X.com. Please login manually first.")
            return []
        
        scroll_iterations = scroll_iterations or config.MAX_SCROLL_ATTEMPTS
        tweets = []
        
        try:
            # Navigate to feed
            await self.browser.navigate_to(config.X_COM_URL)
            await asyncio.sleep(2)  # Wait for page to fully load
            
            # Scroll and extract tweets
            for i in range(scroll_iterations):
                logger.info(f"Scraping iteration {i+1}/{scroll_iterations}")
                
                # Extract tweets from current view
                current_tweets = await self._extract_tweets_from_page()
                logger.info(f"Found {len(current_tweets)} tweets in iteration {i+1}")
                
                # Add new tweets to list
                for tweet in current_tweets:
                    if tweet['id'] not in self.scraped_tweet_ids:
                        tweets.append(tweet)
                        self.scraped_tweet_ids.add(tweet['id'])
                
                # Scroll down
                if i < scroll_iterations - 1:
                    await asyncio.sleep(config.SCROLL_PAUSE_TIME)
                    await self.browser.scroll_page(distance=500)
                    await asyncio.sleep(1)  # Wait for lazy loading
            
            logger.info(f"Total tweets scraped: {len(tweets)}")
            await self.browser.take_screenshot("scrape_complete.png")
            
            return tweets
            
        except Exception as e:
            logger.error(f"Error scraping feed: {e}")
            await self.browser.take_screenshot("scrape_error.png")
            return tweets
    
    async def _extract_tweets_from_page(self) -> List[Dict[str, Any]]:
        """
        Extract all tweets visible on current page
        
        Returns:
            List of tweet data dictionaries
        """
        tweets = []
        
        try:
            # Get all tweet elements
            tweet_elements = await self.browser.page.query_selector_all(config.TWEET_SELECTOR)
            logger.debug(f"Found {len(tweet_elements)} tweet elements")
            
            for idx, tweet_el in enumerate(tweet_elements):
                try:
                    tweet_data = await self._extract_tweet_data(tweet_el)
                    if tweet_data and tweet_data.get('id'):
                        tweets.append(tweet_data)
                        logger.debug(f"Extracted tweet {idx+1}: {tweet_data['id']}")
                except Exception as e:
                    logger.warning(f"Failed to extract tweet {idx+1}: {e}")
                    continue
            
            return tweets
            
        except Exception as e:
            logger.error(f"Error extracting tweets from page: {e}")
            return tweets
    
    async def _extract_tweet_data(self, tweet_element) -> Optional[Dict[str, Any]]:
        """
        Extract data from a single tweet element
        
        Args:
            tweet_element: Playwright element handle
            
        Returns:
            Dictionary with tweet data or None if extraction failed
        """
        try:
            tweet_data = {
                'id': None,
                'username': None,
                'text': None,
                'like_count': 0,
                'retweet_count': 0,
                'view_count': 0,
                'url': None,
            }
            
            # Extract tweet ID from URL attribute
            tweet_link = await tweet_element.query_selector('a[href*="/status/"]')
            if tweet_link:
                href = await tweet_link.get_attribute('href')
                match = re.search(r'/status/(\d+)', href)
                if match:
                    tweet_data['id'] = match.group(1)
                    tweet_data['url'] = f"https://x.com{href}"
            
            if not tweet_data['id']:
                logger.warning("Could not extract tweet ID")
                return None
            
            # Extract username
            username_el = await tweet_element.query_selector('[data-testid="User-Name"]')
            if username_el:
                username_text = await username_el.text_content()
                # Parse username from format "Display Name @handle"
                if '@' in username_text:
                    tweet_data['username'] = username_text.split('@')[1].split()[0]
                else:
                    tweet_data['username'] = username_text.strip()
            
            # Extract tweet text
            text_spans = await tweet_element.query_selector_all('[data-testid="tweetText"] span')
            if text_spans:
                text_parts = []
                for span in text_spans:
                    text = await span.text_content()
                    if text:
                        text_parts.append(text)
                tweet_data['text'] = ' '.join(text_parts).strip()
            
            # Extract engagement metrics
            # Like count
            like_el = await tweet_element.query_selector('[data-testid="like"]')
            if like_el:
                tweet_data['like_count'] = await self._extract_count(like_el)
            
            # Retweet count
            retweet_el = await tweet_element.query_selector('[data-testid="retweet"]')
            if retweet_el:
                tweet_data['retweet_count'] = await self._extract_count(retweet_el)
            
            # View count
            view_el = await tweet_element.query_selector('[data-testid="views"]')
            if view_el:
                tweet_data['view_count'] = await self._extract_count(view_el)
            
            # Validate tweet has minimum required data
            if tweet_data['text'] and tweet_data['username']:
                return tweet_data
            else:
                logger.warning(f"Incomplete tweet data: {tweet_data}")
                return None
            
        except Exception as e:
            logger.error(f"Error extracting tweet data: {e}")
            return None
    
    async def _extract_count(self, element) -> int:
        """
        Extract numeric count from element (e.g., "1.2K" -> 1200)
        
        Args:
            element: Playwright element handle
            
        Returns:
            Numeric value
        """
        try:
            count_text = await element.text_content()
            if not count_text:
                return 0
            
            count_text = count_text.strip().upper()
            
            # Handle different formats
            if 'K' in count_text:
                number = float(count_text.replace('K', '').strip())
                return int(number * 1000)
            elif 'M' in count_text:
                number = float(count_text.replace('M', '').strip())
                return int(number * 1000000)
            else:
                # Try to parse as plain number
                match = re.search(r'[\d.]+', count_text)
                if match:
                    return int(float(match.group()))
            
            return 0
            
        except Exception as e:
            logger.debug(f"Could not extract count: {e}")
            return 0
    
    async def scrape_specific_url(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Scrape a single tweet from specific URL
        
        Args:
            url: Twitter/X.com tweet URL
            
        Returns:
            Tweet data or None if failed
        """
        try:
            await self.browser.navigate_to(url)
            await asyncio.sleep(2)
            
            # Find the main tweet element
            tweet_el = await self.browser.page.query_selector(config.TWEET_SELECTOR)
            
            if tweet_el:
                return await self._extract_tweet_data(tweet_el)
            else:
                logger.warning(f"Could not find tweet at {url}")
                return None
                
        except Exception as e:
            logger.error(f"Error scraping specific URL {url}: {e}")
            return None
    
    def reset_session(self):
        """Reset scraper session (clear seen tweet IDs)"""
        self.scraped_tweet_ids.clear()
        logger.info("Scraper session reset")


async def scrape_tweets(headless: bool = False, iterations: int = None) -> List[Dict[str, Any]]:
    """
    Convenience function to scrape tweets with automatic browser management
    
    Args:
        headless: Run browser in headless mode
        iterations: Number of scroll iterations
        
    Returns:
        List of extracted tweets
    """
    browser_manager = None
    try:
        from browser import create_browser_manager
        browser_manager = await create_browser_manager(headless=headless)
        
        scraper = TweetScraper(browser_manager)
        tweets = await scraper.scrape_feed(scroll_iterations=iterations)
        
        return tweets
        
    except Exception as e:
        logger.error(f"Error in scrape_tweets: {e}")
        return []
    finally:
        if browser_manager:
            await browser_manager.close()
