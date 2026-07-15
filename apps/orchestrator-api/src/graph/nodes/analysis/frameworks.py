"""
Business and Research Frameworks for the Qualitative Analysis Agent.
"""

FRAMEWORKS = {
    "SWOT": {
        "instructions": "Evaluate the subject by identifying its Strengths, Weaknesses, Opportunities, and Threats.",
        "checklist": [
            "Internal strengths (advantages, resources, capabilities)",
            "Internal weaknesses (limitations, vulnerabilities)",
            "External opportunities (market trends, gaps, macro factors)",
            "External threats (competitors, regulations, risks)"
        ],
        "schema": {
            "Strengths": ["..."],
            "Weaknesses": ["..."],
            "Opportunities": ["..."],
            "Threats": ["..."]
        }
    },
    "PESTEL": {
        "instructions": "Analyze the macro-environmental factors impacting the subject: Political, Economic, Social, Technological, Environmental, and Legal.",
        "checklist": [
            "Political factors (government policy, stability, trade tariffs)",
            "Economic factors (growth, exchange rates, inflation, interest rates)",
            "Social factors (cultural trends, demographics, attitudes)",
            "Technological factors (innovation, automation, R&D)",
            "Environmental factors (climate change, sustainability, carbon footprint)",
            "Legal factors (employment laws, consumer protection, health and safety)"
        ],
        "schema": {
            "Political": ["..."],
            "Economic": ["..."],
            "Social": ["..."],
            "Technological": ["..."],
            "Environmental": ["..."],
            "Legal": ["..."]
        }
    },
    "PORTER": {
        "instructions": "Analyze the competitive environment using Porter's Five Forces methodology.",
        "checklist": [
            "Threat of new entrants (barriers to entry, economies of scale)",
            "Bargaining power of suppliers (number of suppliers, switching costs)",
            "Bargaining power of buyers (customer concentration, price sensitivity)",
            "Threat of substitute products or services (alternatives, price-performance tradeoff)",
            "Rivalry among existing competitors (industry concentration, growth rate)"
        ],
        "schema": {
            "Threat of New Entrants": ["..."],
            "Bargaining Power of Suppliers": ["..."],
            "Bargaining Power of Buyers": ["..."],
            "Threat of Substitutes": ["..."],
            "Competitive Rivalry": ["..."]
        }
    },
    "THEMATIC": {
        "instructions": "Perform thematic analysis by identifying patterns, recurring concepts, and major themes across the evidence.",
        "checklist": [
            "Core recurring themes across multiple sources",
            "Contradictory evidence or conflicting perspectives",
            "Outlier data points or weak signals",
            "Evolution of themes over time"
        ],
        "schema": {
            "Primary Themes": [{"theme": "...", "evidence": ["..."]}],
            "Conflicting Perspectives": ["..."],
            "Emerging Trends": ["..."]
        }
    },
    "CONCEPTUAL": {
        "instructions": "Perform conceptual analysis by defining key terms, mapping their relationships, and evaluating their application in the current context.",
        "checklist": [
            "Definition of core concepts",
            "Relationships and dependencies between concepts",
            "Contextual application of concepts in the provided evidence",
            "Theoretical gaps or ambiguities"
        ],
        "schema": {
            "Core Concepts": [{"concept": "...", "definition": "..."}],
            "Relationships": ["..."],
            "Application & Gaps": ["..."]
        }
    }
}

def get_framework_instructions(framework_names: list[str]) -> str:
    """Returns a formatted string containing instructions for the selected frameworks."""
    output = ""
    for name in framework_names:
        name_upper = name.strip().upper()
        if name_upper in FRAMEWORKS:
            fw = FRAMEWORKS[name_upper]
            output += f"\n### Framework: {name_upper}\n"
            output += f"**Instructions:** {fw['instructions']}\n"
            output += "**Evidence Checklist:**\n"
            for item in fw['checklist']:
                output += f"- {item}\n"
            output += f"**Expected Output Schema Structure:**\n{fw['schema']}\n"
        else:
            output += f"\n### Framework: {name} (Unknown)\n"
            output += "Analyze the evidence organically based on the requested framework.\n"
    return output
