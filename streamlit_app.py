import streamlit as st
import json
import asyncio
import logging
import platform
import pandas as pd
import subprocess
from issuu_scraper import scrape_issuu_results

# --- Streamlit must start with set_page_config ---
st.set_page_config(page_title="Issuu Scraper", page_icon="📄", layout="wide")

# --- Ensure Chromium is installed for Playwright ---
@st.cache_resource
def install_playwright():
    try:
        subprocess.run(["playwright", "install", "chromium"], check=True)
    except Exception as e:
        # ⚠️ Don't use st.error here (it breaks the "first command" rule)
        print(f"❌ Failed to install Playwright Chromium: {e}")

install_playwright()

# Configure logging for Streamlit
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

# Title and description
st.title("Issuu Publication Scraper")
st.markdown("Upload a CSV file containing company names. The scraper will run 5 drivers concurrently and collect results.")

# File uploader for CSV
uploaded_file = st.file_uploader("Upload CSV file", type=["csv"])

# Helper to process batches of company names with concurrency=5
async def process_companies(companies, batch_size=5):
    results = []

    for i in range(0, len(companies), batch_size):
        batch = companies[i:i+batch_size]
        logger.info(f"Processing batch {i//batch_size + 1} with {len(batch)} companies")
        tasks = [scrape_issuu_results(company) for company in batch]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        for company, res in zip(batch, batch_results):
            if isinstance(res, Exception):
                logger.error(f"Error scraping {company}: {str(res)}")
                results.append({
                    "company": company,
                    "matching_results": [],
                    "non_matching_results": [],
                    "error": str(res)
                })
            else:
                matching, non_matching = res
                results.append({
                    "company": company,
                    "matching_results": matching,
                    "non_matching_results": non_matching,
                    "error": None
                })

    return results

# Process file on button click
if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)

    if "company_name" not in df.columns:
        st.error("CSV must contain a 'company_name' column.")
    else:
        company_names = df["company_name"].dropna().unique().tolist()

        if st.button("Scrape Companies", key="scrape_button"):
            st.info(f"Found {len(company_names)} companies to scrape")
            with st.spinner("Scraping Issuu... This may take a while."):
                try:
                    all_results = asyncio.run(process_companies(company_names, batch_size=5))

                    # Flatten results into a DataFrame for display
                    rows = []
                    for res in all_results:
                        company = res["company"]
                        if res["error"]:
                            rows.append({
                                "company": company,
                                "title": None,
                                "author_link": None,
                                "price": None,
                                "publication_link": None,
                                "match_type": "Error",
                                "error": res["error"]
                            })
                        else:
                            for item in res["matching_results"]:
                                rows.append({
                                    "company": company,
                                    "title": item["title"],
                                    "author_link": item["author_link"],
                                    "price": item["price"],
                                    "publication_link": item["publication_link"],
                                    "match_type": "Matching",
                                    "error": None
                                })
                            for item in res["non_matching_results"]:
                                rows.append({
                                    "company": company,
                                    "title": item["title"],
                                    "author_link": item["author_link"],
                                    "price": item["price"],
                                    "publication_link": item["publication_link"],
                                    "match_type": "Non-Matching",
                                    "error": None
                                })

                    results_df = pd.DataFrame(rows)

                    if not results_df.empty:
                        # Make links clickable
                        results_df['title'] = results_df.apply(
                            lambda row: f'<a href="{row["publication_link"]}" target="_blank">{row["title"]}</a>'
                            if row["publication_link"] else row["title"], axis=1
                        )
                        results_df['author_link'] = results_df['author_link'].apply(
                            lambda x: f'<a href="{x}" target="_blank">{x}</a>' if pd.notnull(x) else x
                        )

                        st.subheader("Scraped Results")
                        st.markdown(
                            results_df[['company', 'title', 'author_link', 'price', 'match_type']]
                            .to_html(escape=False, index=False),
                            unsafe_allow_html=True
                        )

                        # JSON download button
                        json_data = json.dumps(all_results, indent=2, ensure_ascii=False)
                        st.download_button(
                            label="Download All Results as JSON",
                            data=json_data,
                            file_name="issuu_results.json",
                            mime="application/json",
                            key="download_button"
                        )
                    else:
                        st.warning("No results found.")
                except Exception as e:
                    logger.error(f"Error during scraping in Streamlit: {str(e)}")
                    st.error(f"Error during scraping: {str(e)}")

# Footer
st.markdown("---")
st.markdown("Built with Streamlit, Playwright & AsyncIO. 🚀")
