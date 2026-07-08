from pydantic import BaseModel, Field
from typing import List, Dict

class AnalyticalFramework(BaseModel):
    name: str = Field(description="The display name of the analytical framework")
    instructions: str = Field(description="The primary methodology and instructions for the framework")
    evidence_checklist: List[str] = Field(description="Key evidence points required for this framework")
    output_sections: List[str] = Field(description="Sections that must be present in the final report")

FRAMEWORKS: Dict[str, AnalyticalFramework] = {
    "SWOT": AnalyticalFramework(
        name="SWOT Analysis",
        instructions="Evaluate the target entity by identifying internal Strengths and Weaknesses, alongside external Opportunities and Threats.",
        evidence_checklist=[
            "Internal financial performance and resource availability",
            "Operational advantages or inefficiencies",
            "Macro-economic tailwinds or industry growth vectors",
            "Competitive actions, regulatory risks, or market contraction"
        ],
        output_sections=["Strengths", "Weaknesses", "Opportunities", "Threats", "Strategic Synthesis"]
    ),
    "PESTEL": AnalyticalFramework(
        name="PESTEL Analysis",
        instructions="Analyze the macro-environmental factors impacting the entity. Categorize findings strictly into Political, Economic, Social, Technological, Environmental, and Legal.",
        evidence_checklist=[
            "Pending legislation, trade tariffs, or political stability",
            "Inflation rates, interest rates, and GDP growth",
            "Demographic shifts and consumer behavior trends",
            "R&D investments and technological disruptions",
            "Climate impacts and sustainability regulations",
            "Antitrust, employment, and consumer protection laws"
        ],
        output_sections=["Political", "Economic", "Social", "Technological", "Environmental", "Legal", "Synthesis"]
    ),
    "PORTER": AnalyticalFramework(
        name="Porter's Five Forces",
        instructions="Evaluate the competitive intensity and market attractiveness of the entity's industry by analyzing the five forces.",
        evidence_checklist=[
            "Supplier concentration and pricing power",
            "Buyer switching costs and leverage",
            "Capital requirements and barriers to entry",
            "Viability of alternative products or services",
            "Intensity of existing market competition"
        ],
        output_sections=["Threat of New Entrants", "Bargaining Power of Suppliers", "Bargaining Power of Buyers", "Threat of Substitutes", "Industry Rivalry", "Synthesis"]
    ),
    "THEMATIC": AnalyticalFramework(
        name="Thematic Analysis",
        instructions="Scan the retrieved evidence for recurring narratives, market shifts, or semantic patterns that transcend standard categories.",
        evidence_checklist=[
            "Recurring keywords or product narratives",
            "Consumer sentiment outliers",
            "Uncategorized strategic pivots",
            "Historical parallels in the data"
        ],
        output_sections=["Primary Themes", "Supporting Evidence", "Anomalies", "Strategic Synthesis"]
    ),
    "CONCEPTUAL": AnalyticalFramework(
        name="Conceptual Synthesis",
        instructions="Abstract the specific data points into high-level business paradigms or first-principle models.",
        evidence_checklist=[
            "Core value propositions",
            "Disruptive technology impacts",
            "Business model viability",
            "Systemic market risks"
        ],
        output_sections=["Core Concepts", "Paradigm Shifts", "Systemic Risks", "Synthesis"]
    )
}

def get_framework(framework_key: str) -> AnalyticalFramework:
    """Retrieve an AnalyticalFramework definition. Raises ValueError if missing."""
    key_upper = framework_key.upper()
    if key_upper not in FRAMEWORKS:
        raise ValueError(f"Analytical framework '{framework_key}' is not defined. Available options: {list(FRAMEWORKS.keys())}")
    return FRAMEWORKS[key_upper]
