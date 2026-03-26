# -*- coding: utf-8 -*-
"""
This script uses the Google Gemini API to generate a curated list of early-stage
startups in a specific sector and geographical location. It performs a multi-step
process of discovery, classification, and filtering, followed by advanced
post-processing, rationalization, and analysis.
"""

import json
import logging
import os
import random
import re
import time
from collections import defaultdict
from typing import List, Dict, Tuple, Type, Any

from dotenv import load_dotenv
from google.api_core import exceptions
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import google.generativeai as genai
from pydantic import BaseModel, ValidationError

# --- Configuration ---

# Configure logging for detailed output.
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Load environment variables from a .env file.
load_dotenv()


# --- Pydantic Models for Structured & Validated Output ---

class SimilarResponse(BaseModel):
    """Defines the structure for the similar businesses API response."""
    similar_business: List[str]


class StartupsResponse(BaseModel):
    """Defines the structure for the startup list API response."""
    startups: List[str]


class Classification(BaseModel):
    """Defines the structure for a single company classification."""
    company_name: str
    primary_sector: str


class ClassificationsResponse(BaseModel):
    """Defines the structure for a batch of company classifications."""
    classifications: List[Classification]


class RationalizedName(BaseModel):
    """Structure for a single rationalized entity."""
    original_names: List[str]
    rationalized_name: str


class RationalizationResponse(BaseModel):
    """Structure for the response containing rationalized entities."""
    rationalized_entities: List[RationalizedName]


class CorrelationScore(BaseModel):
    """Structure for a sector's correlation score."""
    sector: str
    correlation_score: float


class CorrelationResponse(BaseModel):
    """Structure for the response containing multiple correlation scores."""
    correlations: List[CorrelationScore]


# --- Helper Functions ---

def salvage_startup_names(raw_text: str) -> List[str]:
    """
    Attempts to extract a list of startup names from a potentially malformed or
    truncated JSON string using regular expressions.
    """
    names = re.findall(r'"([^"]+)"', raw_text)
    names = [name for name in names if name not in ("startups", "company_name", "primary_sector", "classifications")]
    if names:
        logging.warning(f"Salvaged {len(names)} names from a malformed JSON response.")
    else:
        logging.error("Failed to salvage any names from the malformed JSON response.")
    return names


def salvage_classifications(raw_text: str) -> List[Classification]:
    """
    Attempts to extract a list of classification objects from a potentially malformed
    or truncated JSON string using regular expressions.
    """
    pattern = r'\{\s*"company_name"\s*:\s*"([^"]+)"\s*,\s*"primary_sector"\s*:\s*"([^"]+)"\s*\}'
    matches = re.findall(pattern, raw_text)
    salvagged_data = []
    if matches:
        for company_name, primary_sector in matches:
            try:
                salvagged_data.append(Classification(company_name=company_name, primary_sector=primary_sector))
            except ValidationError:
                logging.warning(f"Skipped a salvaged item that failed validation: {company_name}")
    if salvagged_data:
        logging.warning(f"Salvaged {len(salvagged_data)} classifications from a malformed JSON response.")
    else:
        logging.error("Failed to salvage any classifications from the malformed JSON response.")
    return salvagged_data


# --- Core API Interaction Logic ---

def call_gemini_api_with_retry(
        model_name: str,
        prompt: str,
        response_model: Type[BaseModel],
        max_retries: int = 3,
        initial_delay: int = 5,
) -> Tuple[bool, BaseModel | str]:
    """
    Calls the Gemini API with a given prompt and handles retries with exponential backoff.
    If a JSON parsing error occurs, it attempts to salvage partial data.
    """
    api_key = "AIzaSyD9DVWRDtCOzk73XGFwvLj3x5ncq5jZuZA"
    # api_key = os.getenv("GEMINI_API_KEY", "your_default_api_key_here")  # Use env var, provide a placeholder
    if not api_key or "your_default_api_key_here" in api_key:
        return False, "GEMINI_API_KEY not found or not set in .env file."

    genai.configure(api_key=api_key)
    delay = initial_delay
    generation_config = {"temperature": 0.2, "top_p": 1, "top_k": 1, "max_output_tokens": 32768,
                         "response_mime_type": "application/json"}

    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    }

    model = genai.GenerativeModel(
        model_name=model_name,
        generation_config=generation_config,
        safety_settings=safety_settings,
        system_instruction="You are an expert market analyst. Your responses must strictly be valid JSON objects that conform to the user's requested structure. Do not add any text before or after the JSON."
    )

    for attempt in range(max_retries):
        try:
            logging.info(f"Sending prompt to Gemini API (Attempt {attempt + 1}/{max_retries})...")
            response = model.generate_content(prompt)

            if not response.parts:
                finish_reason_name = "UNKNOWN"
                try:
                    finish_reason_name = response.candidates[0].finish_reason.name
                except (IndexError, AttributeError):
                    pass
                error_msg = f"Response was blocked or empty. Finish Reason: {finish_reason_name}."
                logging.error(error_msg)
                return False, error_msg

            return True, response_model.model_validate_json(response.text)

        except (exceptions.ResourceExhausted, exceptions.ServiceUnavailable) as e:
            logging.warning(f"API rate limit or server error: {e}. Retrying in {delay}s...")
            time.sleep(delay)
            delay *= 2
        except (ValidationError, json.JSONDecodeError) as e:
            error_msg = f"Failed to parse API response: {e}"
            logging.error(f"{error_msg}\nRaw Text: {response.text}")
            if response_model == StartupsResponse:
                if salvaged := salvage_startup_names(response.text): return True, StartupsResponse(startups=salvaged)
            elif response_model == ClassificationsResponse:
                if salvaged := salvage_classifications(response.text): return True, ClassificationsResponse(
                    classifications=salvaged)
            return False, error_msg
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}", exc_info=True)
            return False, str(e)
    return False, "Max retries exceeded for API call."


def call_grok_api_mock(prompt: str) -> Dict[str, Any]:
    """
    MOCK function to simulate a call to the Grok API.
    """
    logging.info("--- MOCK GROK API CALL ---")
    logging.info(f"PROMPT (first 200 chars): {prompt[:200]}...")
    if "validate the classification" in prompt:
        return {"status": "success", "response": {"changes": [{"company": "FarEye", "new_sector": "Other"}]}}
    if "re-classify the following companies" in prompt:
        return {"status": "success", "response": {
            "changes": [{"company": "Falcon Autotech", "new_sector": "Procurement Technology (Procure-to-Pay)"}]}}
    return {"status": "success", "response": {"changes": []}}


# --- Main Workflow Functions ---

def get_similar_business(sector: str, geo: str, model_name: str) -> Tuple[bool, List[str] | str]:
    """Finds sectors similar to a target sector using the Gemini API."""
    prompt = f'You are an expert analyst on startups in business sector {sector} in {geo}. Identify business sectors similar to "{sector}" in "{geo}". Your response MUST be a JSON object with one key, "similar_business", an array of strings. Example: {{"similar_business": ["Battery Technology"]}}. You can identify upto 10 sectors that are similar.'
    success, result = call_gemini_api_with_retry(model_name, prompt, SimilarResponse)
    if success:
        logging.info(f"Successfully found {len(result.similar_business)} similar sectors.")
        return True, result.similar_business
    return False, result


def build_startup_prompt_with_exclusions(area: str, geo: str, num_to_request: int, master_startup_list: set) -> str:
    """Builds a more robust prompt to reduce hallucinations and improve factual accuracy."""
    paging_instruction = f"I have already identified {len(master_startup_list)} companies from the above business sector in {geo}. Some of these are {list(master_startup_list)}. Provide the next, different batch of {num_to_request} companies." if master_startup_list else f"Your task is to list the top {num_to_request} startups."

    exclusion_prompt = ""
    # if master_startup_list:
    #     startup_list_for_sampling = list(master_startup_list)
    #     num_to_sample = min(len(startup_list_for_sampling), 90)
    #     exclusions = random.sample(startup_list_for_sampling, num_to_sample)
    #     exclusions_str = json.dumps(exclusions)
    #     exclusion_prompt = f"To prevent repetition, DO NOT include any names from this existing JSON list: {exclusions_str}."

    prompt = f"""
    You are a meticulous market research analyst tasked with identifying VERIFIABLE early-stage companies. Your primary goal is accuracy.

    The sector is '{area}' within '{geo}'.

    {paging_instruction}

    CRITICAL INSTRUCTIONS FOR ACCURACY:
    1.  **VERIFY EXISTENCE:** Only include companies that have a valid CIN,
    2.  **OFFICIAL COMPANY NAMES ONLY:** You MUST provide the official registered or legal name of the company, not product names. For example, provide "Alphabet Inc." not "Google".
    3.  **NO FICTITIOUS NAMES:** Do not invent or create company names. If you cannot find real companies, return an empty list.
    4.  **FUNDING STATUS:** Focus on companies that have verifiably received at least seed funding. This information could be available on the company's website, or on other sites like traxn.com, pvtcircle.com, etc

    STRICT EXCLUSION CRITERIA:
    Do NOT include any companies that are: publicly listed, government-owned, banks, small finance banks, NGOs, majority foreign-owned, or older than 20 years.

    {exclusion_prompt}

    Your response MUST be a JSON object with one key, "startups", containing an array of strings (the official company names).
    Example: {{"startups": ["Official Company Name Inc.", "Real Startup Solutions Pvt. Ltd."]}}
    """
    return prompt


def find_seed_startups_workflow(area: str, geo: str, total_required: int, model_name: str) -> Tuple[
    bool, List[str] | str]:
    """Orchestrates the iterative process of finding and rationalizing a large list of startups."""
    master_startup_list = set()
    no_new_found_counter = 0
    max_consecutive_failures = 3
    startups_per_loop = 150
    last_rationalization_milestone = 0

    while len(master_startup_list) < total_required and no_new_found_counter < max_consecutive_failures:
        num_to_request = min(startups_per_loop, total_required - len(master_startup_list) + 25)

        prompt = build_startup_prompt_with_exclusions(area, geo, num_to_request, master_startup_list)
        success, result = call_gemini_api_with_retry(model_name, prompt, StartupsResponse)

        if success:
            new_additions = set(result.startups) - master_startup_list
            if new_additions:
                logging.info(f"Adding {len(new_additions)} new startups to the master list.")
                master_startup_list.update(new_additions)
                no_new_found_counter = 0
            else:
                logging.warning("API call returned no new companies.")
                no_new_found_counter += 1
        else:
            logging.error(f"API call failed. Reason: {result}")
            no_new_found_counter += 1

        logging.info(f"Total unique startups found: {len(master_startup_list)}/{total_required}")

        current_milestone = len(master_startup_list) // 200
        if current_milestone > last_rationalization_milestone:
            logging.info(f"--- Rationalizing startup list at {len(master_startup_list)} entries ---")
            master_startup_list = rationalize_simple_list(master_startup_list, model_name)
            last_rationalization_milestone = current_milestone
            logging.info(f"--- List rationalized to {len(master_startup_list)} entries ---")

        time.sleep(30)

    if len(master_startup_list) >= total_required:
        logging.info(f"--- Target of {total_required} met. Performing final rationalization pass. ---")
        master_startup_list = rationalize_simple_list(master_startup_list, model_name)
        logging.info(f"--- Final list rationalized to {len(master_startup_list)} entries. ---")

    if not master_startup_list: return False, "Could not find any startups."
    return True, sorted(list(master_startup_list))


def filter_startups_by_sector_workflow(startup_list: List[str], target_sector: str, similar_sectors: List[str],
                                       final_count: int, model_name: str) -> Tuple[List[str], Dict[str, List[str]]]:
    """
    Filters a startup list by classifying each company, ensuring all companies are processed
    even with partial API responses.
    """
    logging.info(f"--- Starting Filtering: Goal is {final_count} startups from {len(startup_list)} candidates. ---")
    filtered_list, all_classifications = [], defaultdict(list)
    batch_size = 100
    all_sectors = [target_sector] + similar_sectors

    unclassified_companies = startup_list[:]

    while unclassified_companies:
        batch_names = unclassified_companies[:batch_size]
        logging.info(f"Classifying batch of {len(batch_names)}. Remaining: {len(unclassified_companies)}")

        prompt = f'You are a precise classification engine. For each company in this list: {json.dumps(batch_names)}, identify its primary sector. The sector MUST be one of {json.dumps(all_sectors)}, or "Other". Your response MUST be a JSON object with a key "classifications", an array of objects. Each object must have "company_name" and "primary_sector".'
        success, result = call_gemini_api_with_retry(model_name, prompt, ClassificationsResponse)

        processed_in_batch = set()

        if success:
            classifications_dict = {item.company_name: item.primary_sector for item in result.classifications}

            for company_name, classification in classifications_dict.items():
                if company_name in batch_names:
                    all_classifications[classification].append(company_name)
                    if classification == target_sector and len(filtered_list) < final_count:
                        filtered_list.append(company_name)
                    processed_in_batch.add(company_name)

            unresponsive_in_batch = set(batch_names) - processed_in_batch
            if unresponsive_in_batch:
                logging.warning(
                    f"{len(unresponsive_in_batch)} companies from the batch were not in the response and will be retried.")

        else:
            logging.error(f"Failed to classify batch. Will retry. Error: {result}")
            time.sleep(30)
            continue

        unclassified_companies = [c for c in unclassified_companies if c not in processed_in_batch]

        if len(filtered_list) >= final_count:
            logging.info(f"Reached target of {final_count} startups. Halting filtering.")
            unclassified_companies = []

        time.sleep(30)

    if unclassified_companies:
        logging.warning(f"Adding {len(unclassified_companies)} companies that could not be classified to 'Other'.")
        for company in unclassified_companies:
            all_classifications["Other"].append(company)

    return filtered_list, dict(all_classifications)


# --- Post-Processing Functions ---

def rationalize_simple_list(startup_names: set, model_name: str) -> set:
    """
    Rationalizes a set of startup names using a rule-based approach followed by an LLM call
    that processes the list in batches to avoid token limits.
    """
    first_word_map = {}
    for name in sorted(list(startup_names)):
        first_word = name.split()[0].lower()
        if first_word not in first_word_map:
            first_word_map[first_word] = name

    rule_based_rationalized = set(first_word_map.values())
    logging.info(
        f"Rule-based rationalization reduced list from {len(startup_names)} to {len(rule_based_rationalized)}.")

    if len(rule_based_rationalized) < 2:
        return rule_based_rationalized

    companies_to_process = sorted(list(rule_based_rationalized))
    final_rationalized_entities = []
    batch_size = 100

    for i in range(0, len(companies_to_process), batch_size):
        batch = companies_to_process[i:i + batch_size]
        logging.info(
            f"Performing LLM rationalization on batch {i // batch_size + 1} of {-(len(companies_to_process) // -batch_size)}...")

        prompt = f'Analyze this list of company names: {json.dumps(batch)}. Identify groups that refer to the same entity (e.g., "Innovate Inc.", "Innovate"). For each group, choose the most official name as "rationalized_name". Your response must be a JSON object with a key "rationalized_entities", a list of objects, each with "original_names" (a list) and "rationalized_name" (a string). Example: {{"rationalized_entities": [{{"original_names": ["Innovate Inc.", "Innovate"], "rationalized_name": "Innovate Inc."}}]}}'

        success, result = call_gemini_api_with_retry(model_name, prompt, RationalizationResponse)

        if success:
            final_rationalized_entities.extend(result.rationalized_entities)
        else:
            logging.error(f"Failed to rationalize batch. These companies will be kept as is: {batch}")
            for name in batch:
                final_rationalized_entities.append(RationalizedName(original_names=[name], rationalized_name=name))

        time.sleep(30)

    processed_names = {name for entity in final_rationalized_entities for name in entity.original_names}
    new_company_list = [entity.rationalized_name for entity in final_rationalized_entities]
    new_company_list.extend([name for name in companies_to_process if name not in processed_names])

    final_set = set(new_company_list)
    logging.info(f"LLM rationalization resulted in {len(final_set)} unique companies.")
    return final_set


def validate_classifications_with_grok(all_classified: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """Uses a mock Grok call to validate company classifications."""
    logging.info("--- Step 5: Validating Classifications with Grok (Mock) ---")
    validated_classifications = defaultdict(list, {k: v[:] for k, v in all_classified.items()})
    for sector, companies in all_classified.items():
        if sector == "Other" or not companies: continue
        prompt = f"Validate the classification of these companies for the '{sector}' sector. List any misclassified. Companies: {json.dumps(companies)}"
        response = call_grok_api_mock(prompt)
        if response.get("status") == "success" and response["response"].get("changes"):
            for change in response["response"]["changes"]:
                company_to_move = change.get("company")
                if company_to_move in validated_classifications[sector]:
                    validated_classifications[sector].remove(company_to_move)
                    validated_classifications["Other"].append(company_to_move)
                    logging.info(f"GROK VALIDATION: Moved '{company_to_move}' from '{sector}' to 'Other'.")
    return dict(validated_classifications)


def get_sector_correlations(search_area: str, similar_sectors: List[str], model_name: str) -> Dict[str, float]:
    """Calculates a correlation score for each sector relative to the main search area."""
    logging.info("--- Step 6: Calculating Sector Correlation Scores ---")
    prompt = f'For the primary sector "{search_area}", calculate a correlation score (0.0 to 1.0) for each of these sectors: {json.dumps(similar_sectors)}. Your response MUST be a JSON object with a key "correlations", a list of objects, each with "sector" and "correlation_score". Example: {{"correlations": [{{"sector": "Battery Technology", "correlation_score": 0.8}}]}}'
    success, result = call_gemini_api_with_retry(model_name, prompt, CorrelationResponse)
    if success:
        scores = {item.sector: item.correlation_score for item in result.correlations}
        scores[search_area] = 1.0
        return scores
    logging.error("Failed to calculate correlation scores. Defaulting scores to 0.0.")
    return {sector: 0.0 for sector in similar_sectors}


def reclassify_others_with_grok(all_classified: Dict[str, List[str]], all_sectors: List[str]) -> Dict[str, List[str]]:
    """Uses a mock Grok call to re-classify companies from the 'Other' category."""
    logging.info("--- Step 7: Re-classifying 'Other' Category with Grok (Mock) ---")
    reclassified_data = defaultdict(list, {k: v[:] for k, v in all_classified.items()})
    others_list = reclassified_data.get("Other", [])
    if not others_list: return dict(reclassified_data)
    prompt = f"Re-classify these companies into one of the provided sectors if applicable. If a company does not fit, classify it as 'Other'. Sectors: {json.dumps(all_sectors)}. Companies: {json.dumps(others_list)}"
    response = call_grok_api_mock(prompt)
    if response.get("status") == "success" and response["response"].get("changes"):
        for change in response["response"]["changes"]:
            company, new_sector = change.get("company"), change.get("new_sector")
            if company in reclassified_data["Other"] and new_sector in all_sectors:
                reclassified_data["Other"].remove(company)
                reclassified_data[new_sector].append(company)
                logging.info(f"GROK RE-CLASSIFICATION: Moved '{company}' from 'Other' to '{new_sector}'.")
    return dict(reclassified_data)


# --- Main Execution Block ---

if __name__ == "__main__":
    # --- Configuration ---
    search_area = "Supply-Chain Finance"
    search_geo = "India"
    initial_target = 500
    final_target = 150
    model = "gemini-2.5-pro"
    grokEnabled = False

    # --- Step 1: Get Similar Business Sectors ---
    logging.info(f"--- Step 1: Finding sectors similar to '{search_area}' ---")
    sim_success, similar_businesses = get_similar_business(search_area, search_geo, model)
    if not sim_success:
        logging.error(f"Could not retrieve similar business sectors. Aborting. Reason: {similar_businesses}")
    else:
        print(f"\nFound similar sectors: {', '.join(similar_businesses)}")
        all_sectors = [search_area] + similar_businesses
        time.sleep(30)

        # --- Step 2: Find Initial Startup Candidates ---
        logging.info(f"\n--- Step 2: Finding {initial_target} initial startup candidates ---")
        find_success, initial_startups = find_seed_startups_workflow(search_area, search_geo, initial_target, model)

        if find_success and initial_startups:
            print(f"\nSuccessfully found {len(initial_startups)} initial candidates.")

            # --- Step 3: Filter and Classify Startups ---
            final_list, all_classified = filter_startups_by_sector_workflow(initial_startups, search_area,
                                                                            similar_businesses, final_target, model)

            # --- Post-Processing Workflow ---
            validated_classified = all_classified
            final_classifications = all_classified

            if grokEnabled:
                validated_classified = validate_classifications_with_grok(all_classified)
                final_classifications = reclassify_others_with_grok(validated_classified, all_sectors)

            correlation_scores = get_sector_correlations(search_area, similar_businesses, model)

            sorted_sectors = sorted(correlation_scores.keys(), key=lambda s: correlation_scores.get(s, -1),
                                    reverse=True)
            if "Other" in final_classifications and "Other" not in sorted_sectors:
                sorted_sectors.append("Other")

            print("\n" + "=" * 50)
            print("--- Final, Filtered List of Startups ---")
            print("=" * 50)
            for i, name in enumerate(final_list): print(f"{i + 1}. {name}")
            print(f"\nProcess complete. Final list contains {len(final_list)} startups.")

            print("\n" + "=" * 50)
            print("--- Final Rationalized & Validated Sector Breakdown ---")
            print("=" * 50)
            for sector in sorted_sectors:
                if sector in final_classifications and final_classifications[sector]:
                    companies = sorted(final_classifications[sector])
                    score_str = f"(Correlation: {correlation_scores.get(sector):.2f})" if sector in correlation_scores else ""
                    print(f"\nSector: {sector} {score_str} ({len(companies)} companies)")
                    print(json.dumps(companies, indent=2))
        else:
            print(f"\n--- Process Failed During Startup Search ---")
            print(f"Error: {initial_startups}")
