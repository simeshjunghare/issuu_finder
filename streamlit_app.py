import streamlit as st

# Set page config must be the first Streamlit command
st.set_page_config(page_title="Issuu Scraper", page_icon="📄", layout="wide")

import json
import asyncio
import logging
import platform
import pandas as pd
import subprocess
from issue_scraper import scrape_issuu_results

# Configure logging for Streamlit at the module level
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# --- Ensure Chromium and dependencies are installed for Playwright ---
@st.cache_resource
def install_playwright():
    try:
        # Install Playwright and its dependencies
        subprocess.run(["playwright", "install", "chromium"], check=True)
        subprocess.run(["playwright", "install-deps", "chromium"], check=True)
        logger.info("Successfully installed Playwright Chromium and dependencies")
    except subprocess.CalledProcessError as e:
        logger.warning(f"Playwright installation warning: {e}")
        st.warning("Some Playwright dependencies might be missing. The app may not work correctly.")
    except Exception as e:
        logger.error(f"Failed to install Playwright: {e}")
        st.error(f"Failed to install Playwright: {e}")

# Initialize Playwright at app startup
install_playwright()

# Set WindowsProactorEventLoopPolicy for Windows
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    logger.info("Applied WindowsProactorEventLoopPolicy for asyncio compatibility")

# Title and description
st.title("Issuu Publication Scraper")
st.markdown("Enter a company name to scrape publications from Issuu and view or download the results.")

# Input for company name with unique key
company_name = st.text_input("Company Name", placeholder="e.g., Securite Et Signalisation S.A.S.", key="company_name_input")

# Button to trigger scraping
if st.button("Scrape Issuu", key="scrape_button"):
    if not company_name:
        logger.error("No company name provided in UI")
        st.error("Please enter a company name.")
    else:
        logger.info(f"Starting scrape for company: {company_name}")
        with st.spinner("Scraping Issuu... This may take a moment."):
            try:
                # Call the async scraper function
                matching_results, non_matching_results = asyncio.run(scrape_issuu_results(company_name))
                
                if matching_results or non_matching_results:
                    logger.info(f"Found {len(matching_results)} matching and {len(non_matching_results)} non-matching publications")
                    st.success(f"Found {len(matching_results)} matching and {len(non_matching_results)} non-matching publications!")
                    
                    # Display Matching Results
                    if matching_results:
                        st.subheader("Matching Results (Author Link Similar to Company Name)")
                        df_matching = pd.DataFrame(matching_results)
                        df_matching['title'] = df_matching.apply(lambda row: f'<a href="{row["publication_link"]}" target="_blank">{row["title"]}</a>', axis=1)
                        df_matching['author_link'] = df_matching['author_link'].apply(lambda x: f'<a href="{x}" target="_blank">{x}</a>')
                        st.markdown(df_matching[['title', 'author_link', 'price']].to_html(escape=False, index=False), unsafe_allow_html=True)
                    else:
                        st.info("No matching results found.")
                    
                    # Display Non-Matching Results
                    if non_matching_results:
                        st.subheader("Non-Matching Results")
                        df_non_matching = pd.DataFrame(non_matching_results)
                        df_non_matching['title'] = df_non_matching.apply(lambda row: f'<a href="{row["publication_link"]}" target="_blank">{row["title"]}</a>', axis=1)
                        df_non_matching['author_link'] = df_non_matching['author_link'].apply(lambda x: f'<a href="{x}" target="_blank">{x}</a>')
                        st.markdown(df_non_matching[['title', 'author_link', 'price']].to_html(escape=False, index=False), unsafe_allow_html=True)
                    else:
                        st.info("No non-matching results found.")
                    
                    # Prepare JSON for download
                    all_results = matching_results + non_matching_results
                    json_data = json.dumps(all_results, indent=2, ensure_ascii=False)
                    st.download_button(
                        label="Download All Results as JSON",
                        data=json_data,
                        file_name=f"issuu_results_{company_name.replace(' ', '_')}.json",
                        mime="application/json",
                        key="download_button"
                    )
                else:
                    logger.warning("No results found or an error occurred")
                    st.warning("No results found or an error occurred. Check the logs for details.")
            except Exception as e:
                logger.error(f"Error during scraping in Streamlit: {str(e)}")
                st.error(f"Error during scraping: {str(e)}")

# Footer
st.markdown("---")
st.markdown("Built with Streamlit and Playwright. Logs are available in the terminal for debugging.")
