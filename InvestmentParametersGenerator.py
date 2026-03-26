import os
import json
import google.generativeai as genai

# You can place your API key here as a fallback, similar to the other script.
# It's recommended to handle API keys via environment variables for security.
GEMINI_API_KEY = "XXXXXXXXXXX"  # Replace with your key if not using .env


def get_investment_parameters(api_key: str, startup_list: list[str], area: str, geo: str, model_name: str, nParameters : str | int = "40") -> tuple[
    bool, list[str] | str]:
    """
    Calls the Gemini API to get a list of investment evaluation parameters.

    Args:
        api_key: The Google Gemini API key.
        startup_list: A list of startup names to provide context.
        area: The business line or sector for context.
        geo: The geographical region for context.
        model_name: The Gemini model name to use.
        nParameters: The number of investment parameters that is required as output.

    Returns:
        A tuple containing a success boolean and either a list of parameters or an error message.
        :param api_key:
        :param startup_list:
        :param area:
        :param geo:
        :param model_name:
        :param nParameters:
    """

    try:
        if (api_key is not None) and (api_key != ""):
            genai.configure(api_key=api_key)
        else:
            genai.configure(api_key=GEMINI_API_KEY)

        # Define the generation config to request a JSON response
        generation_config = {
            "temperature": 0.3,
            "response_mime_type": "application/json",
        }

        model = genai.GenerativeModel(
            # model_name="gemini-2.0-flash",
            model_name=model_name,
            generation_config=generation_config,
        )

        # Convert the list of startups into a comma-separated string for the prompt
        startup_examples = ", ".join(startup_list)

        prompt = f"""
        For startups in the '{area}' sector in '{geo}', like {startup_examples}, generate a detailed list of exactly {nParameters} parameters.
        These parameters should be the key criteria a Venture Capital or Private Equity fund uses to evaluate a company for a potential investment.
        Include criteria covering financial health, market position, product, team, and scalability.

        Here are some examples of the kind of parameters I'm looking for (Note that these are merely examples and your set could be completely different from these):
        - Market Share & Growth Rate
        - Compound Annual Growth Rate (CAGR) projections
        - Annual Recurring Revenue (ARR) & Revenue Growth
        - Fund-raising history
        - Product offerings
        - Expansion plans into other products and / or geos
        - Nuances like understanding of the broader market and niches therein
        - Robustness, timeline, and variation of the process of Lead generation to sales cycle
        - Robustness, timeline, and variation of the order to cash cycle
        - EBITDA & Profitability Path
        - Technology Stack & IP Defensibility
        - Breadth and Depth of Product Offerings
        - Comprehensive Fund Raising History (Seed, Series A, etc.)
        - Employee Count & Talent Density
        - Future Growth Strategy & Investment Focus
        - Customer Retention Rate (CRR) & Churn
        - Customer Acquisition Cost (CAC)
        - Customer Lifetime Value (CLTV)
        - Free Cash Flow & Burn Rate
        - Scalability of Product, Operations, and Market
        - Founder's Execution Excellence & Track Record
        - Identified Risk Factors & Mitigation Strategies
        - Potential Exit Opportunities (M&A, IPO)
        - Barriers to Entry for New Competitors
        - Unique Value Proposition (UVP)
        - Moat / Defensibility of the business
        - Passion & Resilience of Founding Team
        - "Gross Transaction Value (GTV) Financed & Growth Rate",
        - "Net Revenue Take Rate (as a % of GTV)",
        - "Annual Recurring Revenue (ARR) & Revenue Growth"
        - "EBITDA Margin & Path to Profitability",
        - "Loan Book Size & Quality (Gross & Net NPA %)",
        - "Cost of Capital and Diversity of Funding Sources (Banks, NBFCs, Debt Funds)",
        - "Customer Acquisition Cost (CAC) for both Anchor Corporates and MSME Vendors",
        - "Customer Lifetime Value (CLTV) to CAC Ratio",
        - "Monthly Burn Rate & Cash Runway",
        - "Unit Economics per Transaction",
        - "Capital Adequacy & Leverage Ratios (if NBFC licensed)",
        - "Total Addressable Market (TAM) Penetration in India's SCF space",
        - "Market Share within specific segments (e.g., TReDS, Dynamic Discounting)",
        - "Strength and Stickiness of Anchor Corporate Portfolio",
        - "MSME Vendor Ecosystem Size and Engagement Rate",
        - "Regulatory Moat (TReDS license, NBFC license, etc.) & Compliance Record",
        - "Competitive Landscape Analysis vs. Banks and other FinTechs",
        - "Partnership Ecosystem with Financial Institutions and Technology Providers",
        - "Geographic Penetration across Tier 1, 2, and 3 cities in India",
        - "Brand Equity and Reputation among Corporates and MSMEs",
        - "Technology Stack Scalability, Security, and Proprietary IP",
        - "Sophistication of AI/ML-based Credit Underwriting & Risk Modeling",
        - "Breadth and Depth of Product Offerings (e.g., Invoice Discounting, PO Financing, Vendor Financing)",
        - "Seamlessness of ERP & Accounting Software Integration Capabilities",
        - "User Experience (UX) and Onboarding Efficiency for all stakeholders",
        - "Product Roadmap and Innovation Pipeline", "Data Analytics Capabilities for providing insights to clients",
        - "Network Effects derived from the platform's ecosystem of buyers, suppliers, and financiers",
        - "Founder's Domain Expertise (Finance, Tech, Supply Chain) & Execution Track Record",
        - "Strength and Completeness of the Senior Management Team",
        - "Talent Density & Employee Retention Rate (especially in tech and credit)",
        - "Sales & Distribution Strategy and Efficiency",
        - "Operational Efficiency in Loan Disbursal and Collection Processes",
        - "Corporate Governance Structure and Board Composition",
        - "Customer Retention Rate (CRR) & Churn (for both Anchors and MSMEs)",
        - "Capital Efficiency (Revenue / Total Capital Raised)",
        - "Comprehensive Fundraising History & Cap Table Structure",
        - "Clarity of Future Growth Strategy & Use of Investment Proceeds",
        - "Identified Risk Factors (Credit, Operational, Regulatory) & Mitigation Strategies",
        - "Potential Exit Opportunities (Strategic M&A, IPO) and Timeline"

        It is very important for you to understand that the above parameters are only directional in nature. 
        They may or may not apply to specific areas and geos. You, as the expert who is advising me, need to properly research this area to find the best set of investment parameters, 
        and may therefore, come up with a completely different set of parameters that help much better in taking investment decisions.
        
        Since you are the expert, do the background research necessary to figure out the relative importance of the investment parameters for decision making, and 
        order them in descending order of importance. Hence, the most important criteria should be in the first column after the startup names, followed by the next
        most important criteria, and son on.
        
        Your response MUST be a single, valid JSON object.
        This JSON object must contain one key: "parameters".
        The value of "parameters" must be an array of {nParameters} strings.
        Do not include any text or markdown formatting outside of the JSON object.
        """

        response = model.generate_content(prompt)
        # --- SAFETY CHECK ---
        # Check if the response has content before trying to access it.
        if not response.parts:
            block_reason = response.prompt_feedback.block_reason
            return False, f"Error: The response was blocked. Reason: {block_reason.name if block_reason else 'Unknown'}."

        data = json.loads(response.text)
        parameters = data.get("parameters")

        if isinstance(parameters, list) and len(parameters) > 0:
            return True, parameters
        else:
            return False, "Error: JSON response did not contain a valid list of 'parameters'."

    except Exception as e:
        return False, f"An API or JSON parsing error occurred: {e}"


# --- MAIN EXECUTION BLOCK FOR TESTING ---
# if __name__ == "__main__":
#     print("--- Running Test for get_investment_parameters ---")
#
#     # 1. This is a sample JSON output from the first script (gemini_startup_finder.py)
#     mock_startup_data = {
#         "startups": [
#             "KredX",
#             "Cashflo",
#             "CredAble",
#             "Vayana Network",
#             "RXIL (Receivables Exchange of India)",
#             "M1xchange",
#             "Invoicemart",
#             "FinAGG",
#             "Mintifi",
#             "Progcap",
#             "Indifi",
#             "Lendingkart",
#             "Aye Finance",
#             "FlexiLoans",
#             "OfBusiness"
#         ]
#     }
#
#     # 2. Extract the list of names
#     startups = mock_startup_data.get("startups")
#
#     # 3. Define the context
#     business_area = "supply-chain finance"
#     geography = "India"
#
#     # 4. Get the API key (replace with your actual key or set it as an environment variable)
#     my_api_key = os.getenv("GEMINI_API_KEY", GEMINI_API_KEY)
#     # if my_api_key == "YOUR_GEMINI_API_KEY_HERE":
#     #     print("\nWARNING: Using a placeholder API key.")
#     #     print("Please replace 'YOUR_GEMINI_API_KEY_HERE' in the script or set a GEMINI_API_KEY environment variable.\n")
#
#     # 5. Call the function
#     if startups:
#         success, result = get_investment_parameters(my_api_key, startups, business_area, geography)
#
#         # 6. Print the results
#         if success:
#             print(f"Successfully generated {len(result)} investment parameters:")
#             # Pretty print the JSON
#             print(json.dumps(result, indent=2))
#         else:
#             print("Failed to get investment parameters.")
#             print("Error:", result)
#     else:
#         print("Could not find a list of startups in the mock data.")
