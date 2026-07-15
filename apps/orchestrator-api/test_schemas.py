import sys
import os
import asyncio
from dotenv import load_dotenv

# Force load .env from the current directory
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

sys.path.append(os.path.abspath("src"))
from graph.tools.financial_tools import company_overview, income_statement, balance_sheet, cash_flow, earnings
from graph.tools.macro_tools import data360_get_data
from graph.tools.trends_tools import interest_over_time, interest_by_region
from graph.tools.analytics_tools import get_schema

async def main():
    config = {"configurable": {"research_id": "00000000-0000-0000-0000-000000000000"}}
    symbol = "MSFT"
    
    # --- 1. Financial Artifacts ---
    print("\n[FINANCIAL] Testing company_overview...")
    await company_overview.ainvoke({"symbol": symbol}, config=config)
    print(await get_schema.ainvoke({"artifact_ids": [f"overview_{symbol.lower()}"]}))
    
    print("\n[FINANCIAL] Testing income_statement...")
    await income_statement.ainvoke({"symbol": symbol}, config=config)
    print(await get_schema.ainvoke({"artifact_ids": [f"income_statement_{symbol.lower()}"]}))

    print("\n[FINANCIAL] Testing balance_sheet...")
    await balance_sheet.ainvoke({"symbol": symbol}, config=config)
    print(await get_schema.ainvoke({"artifact_ids": [f"balance_sheet_{symbol.lower()}"]}))

    print("\n[FINANCIAL] Testing cash_flow...")
    await cash_flow.ainvoke({"symbol": symbol}, config=config)
    print(await get_schema.ainvoke({"artifact_ids": [f"cash_flow_{symbol.lower()}"]}))

    print("\n[FINANCIAL] Testing earnings...")
    await earnings.ainvoke({"symbol": symbol}, config=config)
    print(await get_schema.ainvoke({"artifact_ids": [f"earnings_{symbol.lower()}"]}))

    from graph.tools.financial_tools import earnings_calendar, ipo_calendar, listing_status
    print("\n[FINANCIAL] Testing earnings_calendar...")
    await earnings_calendar.ainvoke({"horizon": "3month"}, config=config)
    print(await get_schema.ainvoke({"artifact_ids": ["earnings_calendar"]}))

    print("\n[FINANCIAL] Testing ipo_calendar...")
    await ipo_calendar.ainvoke({}, config=config)
    print(await get_schema.ainvoke({"artifact_ids": ["ipo_calendar"]}))

    print("\n[FINANCIAL] Testing listing_status...")
    await listing_status.ainvoke({"state": "active"}, config=config)
    print(await get_schema.ainvoke({"artifact_ids": ["listing_status_active"]}))


    # --- 2. Macro Artifacts ---
    print("\n[MACRO] Testing data360_get_data (WDI GDP per capita)...")
    indicator = "NY.GDP.PCAP.CD" # WDI GDP per capita
    # Provide explicit years to avoid timeout/empty responses
    await data360_get_data.ainvoke({
        "database_id": "WDI", 
        "indicator_id": indicator, 
        "country_code": "USA;IND",
        "start_year": 2015,
        "end_year": 2023
    }, config=config)
    print(await get_schema.ainvoke({"artifact_ids": [indicator]}))

    # --- 3. Trends Artifacts ---
    query = "microsoft"
    print("\n[TRENDS] Testing interest_over_time...")
    await interest_over_time.ainvoke({"query": query, "date": "today 12-m", "geo": "US"}, config=config)
    print(await get_schema.ainvoke({"artifact_ids": [f"trends_time_{query}"]}))

    print("\n[TRENDS] Testing interest_by_region...")
    await interest_by_region.ainvoke({"query": query, "date": "today 12-m", "geo": "US"}, config=config)
    print(await get_schema.ainvoke({"artifact_ids": [f"trends_geo_{query}"]}))

if __name__ == "__main__":
    asyncio.run(main())
