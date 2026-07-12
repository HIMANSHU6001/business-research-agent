import asyncio
import os
import sys

# Add src to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from dotenv import load_dotenv
load_dotenv()

from context.knowledge import KnowledgeManager

report_1 = """## Macro Economic Intelligence Report

### Indicator Fetched:

* GDP per capita (current US$)
* Database: World Development Indicators (WDI)
* Country: India
* Year Range: 2020-2026

### Artifact IDs Created:

* Artifact ID: WB_WDI_NY_GDP_PCAP_CD

### Statistical Highlights:

* Mean GDP per capita: $2359.26
* Median GDP per capita: $2357.21
* Maximum GDP per capita: $2702.48 (2025)
* Minimum GDP per capita: $1907.04 (2020)
* Trend: Increasing

### Gaps:

* None

Note: The data collection was successful, and the required data was fetched from the World Bank Data360 database."""


report_2 = """**Macro Economic Intelligence Report**

**Indicator:** Unemployment Rate
**Database:** Gender Statistics (WB_GS)
**Country:** India
**Year Range:** 2020-2026

**Artifact ID:** WB_GS_SL_UEM_ZS

**Summary:** The unemployment rate for India has been decreasing over the years, with the latest available data showing a rate of 4.668% in 2023.

**Highlights:**

* The unemployment rate for India has been decreasing over the years.
* The latest available data shows a rate of 4.668% in 2023.
* The data is available for both males and females, as well as for different age groups.

**Gaps:** None

**Conclusion:** The unemployment rate for India has been decreasing over the years, with the latest available data showing a rate of 4.668% in 2023."""


report_3 = """## Data Collection Report

### Introduction:
This report synthesizes the findings from two macroeconomic intelligence reports, focusing on GDP per capita and unemployment rate in India, from 2020 to 2026. The data was collected from the World Development Indicators (WDI) and Gender Statistics (WB_GS) databases.

### Key Findings:

1. **GDP per capita:**
   - The mean GDP per capita for India from 2020 to 2026 was $2359.26.
   - The median GDP per capita was $2357.21.
   - The maximum GDP per capita was $2702.48, recorded in 2025.
   - The minimum GDP per capita was $1907.04, recorded in 2020.
   - The trend indicates an increase in GDP per capita over the years.

2. **Unemployment Rate:**
   - The unemployment rate in India has been decreasing over the years.
   - The latest available data (2023) shows an unemployment rate of 4.668%.
   - Data is available for both males and females, as well as for different age groups.

### Artifact IDs:
- For GDP per capita: WB_WDI_NY_GDP_PCAP_CD
- For Unemployment Rate: WB_GS_SL_UEM_ZS

### Statistical Highlights:
- The data shows a positive trend in GDP per capita and a decreasing trend in unemployment rates, indicating economic growth and improvement in the labor market.

### Gaps:
No gaps were reported in the data collection process for either indicator.

### Conclusion:
The data collection was successful, providing insights into India's economic performance from 2020 to 2026. The increasing GDP per capita and decreasing unemployment rate suggest a positive economic trajectory. These findings can be useful for policymakers, economists, and stakeholders interested in India's macroeconomic trends."""

async def main():
    import uuid
    km = KnowledgeManager()
    research_id = str(uuid.uuid4())
    
    print("Inserting Report 1...")
    await km.store_context(research_id, "macro_agent", "Collect GDP data", report_1)
    print("Inserting Report 2...")
    await km.store_context(research_id, "macro_agent", "Collect Unemployment data", report_2)
    print("Inserting Report 3...")
    await km.store_context(research_id, "collection_supervisor", "Synthesize Data Collection Report", report_3)
    
    print("Done! All test reports inserted.")
    print(f"Research ID for querying is: {research_id}")

if __name__ == "__main__":
    asyncio.run(main())
