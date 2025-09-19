import logging
import json
import urllib.parse
from playwright.async_api import async_playwright
import asyncio
import sys
import platform
from difflib import SequenceMatcher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Set WindowsProactorEventLoopPolicy for Windows
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    logger.info("Applied WindowsProactorEventLoopPolicy for asyncio compatibility")

def calculate_similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

async def scrape_issuu_results(company_name):
    # Generate URL by encoding the company name
    base_url = "https://issuu.com/search?q="
    encoded_company = urllib.parse.quote(company_name)
    url = f"{base_url}{encoded_company}"
    
    logger.info(f"Generated URL for company '{company_name}': {url}")
    
    try:
        async with async_playwright() as p:
            # Launch browser
            logger.info("Attempting to launch Chromium browser (headless=False)")
            try:
                browser = await p.chromium.launch(headless=True)  # Keep headless=False for debugging
            except Exception as e:
                logger.error(f"Failed to launch browser: {str(e)}")
                raise
            
            logger.info("Browser launched successfully")
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            logger.info("New browser context and page created")
            
            # Log browser console messages
            page.on("console", lambda msg: logger.debug(f"Browser console: {msg.text}"))
            
            try:
                # Navigate to the URL
                logger.info(f"Navigating to {url}")
                await page.goto(url, timeout=60000, wait_until="domcontentloaded")
                logger.info("Page navigation completed")
                
                # Handle cookie consent popup
                logger.info("Checking for cookie consent popup")
                try:
                    cookie_button = page.locator('//*[@id="CybotCookiebotDialogBodyButtonAccept"]')
                    logger.info("Waiting for cookie 'Accept' button (7s timeout)")
                    await cookie_button.wait_for(state='visible', timeout=7000)
                    logger.info("Clicking 'Accept' button for cookies")
                    await cookie_button.click()
                    logger.info("Waiting for cookie popup to disappear")
                    await page.wait_for_selector('#CybotCookiebotDialog', state='hidden', timeout=10000)
                    logger.info("Cookie popup dismissed successfully")
                except Exception as e:
                    logger.info(f"No cookie popup detected or failed to dismiss: {str(e)}")
                
                # Wait for search results
                price_selector = '.PublicationCard__publication-card__price__SATkI__0-0-3199'
                results_selector = f'li:has({price_selector})'
                logger.info(f"Waiting for search results with selector: {results_selector}")
                await page.wait_for_selector(results_selector, state='visible', timeout=30000)
                logger.info("Search results loaded")
                
                # Scroll to load all results
                logger.info("Scrolling to the bottom of the page to load all results")
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1000)  # 1s wait for dynamic content
                logger.info("Scroll completed, waited 1s for dynamic content")
                
                # Extract data using JavaScript
                logger.info("Extracting data from all <li> elements using JavaScript")
                results = await page.evaluate("""
                    () => {
                        const items = document.querySelectorAll('li:has(.PublicationCard__publication-card__price__SATkI__0-0-3199)');
                        const data = [];
                        items.forEach(item => {
                            const titleElement = item.querySelector('h3.PublicationCard__publication-card__card-title__jufAN__0-0-3199');
                            const title = titleElement?.innerText.trim();
                            const authorLink = item.querySelector('a.PublicationCard__publication-card__author-link__-bT0k__0-0-3199')?.getAttribute('href');
                            const price = item.querySelector('.PublicationCard__publication-card__price__SATkI__0-0-3199')?.innerText.trim();
                            const publicationLinkElement = titleElement?.closest('a') || item.querySelector('a:has(h3.PublicationCard__publication-card__card-title__jufAN__0-0-3199)');
                            const publicationLink = publicationLinkElement?.getAttribute('href');
                            if (title && authorLink && price && publicationLink) {
                                data.push({
                                    title,
                                    author_link: `https://issuu.com/${authorLink}`,
                                    price,
                                    publication_link: publicationLink.startsWith('https://') ? publicationLink : `https://issuu.com/${publicationLink}`
                                });
                            }
                        });
                        return data;
                    }
                """)
                logger.info(f"Extracted {len(results)} valid results")
                
                # Filter duplicates based on title
                seen_titles = set()
                unique_results = []
                for result in results:
                    if result['title'] not in seen_titles:
                        seen_titles.add(result['title'])
                        unique_results.append(result)
                        logger.info(f"Added unique result: {result['title']}")
                    else:
                        logger.info(f"Skipped duplicate result: {result['title']}")
                
                # Compare author_link with company_name
                matching_results = []
                non_matching_results = []
                similarity_threshold = 0.8
                company_domain = company_name.lower().replace(" ", "").replace(".", "")
                for result in unique_results:
                    author_domain = result['author_link'].replace("https://issuu.com/", "").lower().replace(" ", "").replace(".", "")
                    similarity = calculate_similarity(company_domain, author_domain)
                    if similarity >= similarity_threshold:
                        matching_results.append(result)
                        logger.info(f"Matched: {result['title']} (Similarity: {similarity:.2f})")
                    else:
                        non_matching_results.append(result)
                        logger.info(f"Non-matched: {result['title']} (Similarity: {similarity:.2f})")
                
                logger.info(f"Scraping completed. {len(matching_results)} matching, {len(non_matching_results)} non-matching results")
                return matching_results, non_matching_results
            
            except Exception as e:
                logger.error(f"Error during scraping: {str(e)}")
                return [], []
            
            finally:
                logger.info("Closing browser")
                await browser.close()
    
    except Exception as e:
        logger.error(f"Failed to initialize Playwright: {str(e)}")
        return [], []

if __name__ == "__main__":
    import sys
    logger.info("Starting the scraping process")
    if len(sys.argv) < 2:
        logger.error("No company name provided. Usage: python issue_scraper.py <company_name>")
        sys.exit(1)
    
    company_name = sys.argv[1]
    logger.info(f"Scraping for company: {company_name}")
    matching_results, non_matching_results = asyncio.run(scrape_issuu_results(company_name))
    logger.info("Printing scraped results as JSON")
    print("Matching Results:")
    print(json.dumps(matching_results, indent=2, ensure_ascii=False))
    print("Non-Matching Results:")
    print(json.dumps(non_matching_results, indent=2, ensure_ascii=False))
    logger.info("Scraping process finished")