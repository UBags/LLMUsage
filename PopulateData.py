import os
import json
import re
import time
import google.generativeai as genai
import tkinter as tk

# It's recommended to handle API keys via environment variables for security.
GEMINI_API_KEY = "XXXXXXXXXX"  # Replace with your key if not using .env


def _log(message: str, log_widget=None):
    """Helper function to print to console and optionally update a Tkinter widget."""
    print(message)
    if log_widget:
        # Use after() to schedule the update on the main GUI thread
        log_widget.after(0, lambda: log_widget.insert(tk.END, message + "\n"))
        log_widget.after(0, log_widget.see, tk.END)  # Auto-scroll


def save_to_html(batch_data: dict, parameter_list: list[str]) -> str:
    """
    Generates a clean HTML file with data in a table, returning the raw HTML string.
    """
    # --- HTML Structure Start ---
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <style>
            body { font-family: sans-serif; }
            table { border-collapse: collapse; width: 100%; }
            th, td { border: 1px solid #dddddd; padding: 8px; text-align: left; vertical-align: top; }
            th {
                background-color: black;
                color: white;
                text-align: center;
                vertical-align: middle;
            }
            td:not(:first-child) {
                width: 350px;
                min-width: 350px;
                word-wrap: break-word;
            }
            tbody tr td:first-child {
                background-color: #f2f2f2;
                color: blue;
                text-align: center;
                vertical-align: middle;
                font-weight: bold;
            }
        </style>
    </head>
    <body>
        <table>
            <thead>
                <tr>
                    <th>Startup Name</th>
    """
    for param in parameter_list:
        html_content += f"<th>{param}</th>"
    html_content += "</tr></thead><tbody>"

    for startup_name, params in batch_data.items():
        html_content += f"<tr><td>{startup_name}</td>"
        if "error" in params:
            html_content += f'<td colspan="{len(parameter_list)}">{params["error"]}</td>'
        else:
            for param_name in parameter_list:
                details = params.get(param_name, {})
                summary = details.get("summary", "N/A")
                sources_list = details.get("sources", [])
                sources_html = ""
                if isinstance(sources_list, list) and sources_list:
                    links = [f'<a href="{url}" target="_blank">Source {i}</a>' for i, url in enumerate(sources_list, 1)]
                    sources_html = "<br>".join(links)
                cell_content = f"{summary}<br><br>{sources_html if sources_html else ''}"
                html_content += f"<td>{cell_content}</td>"
        html_content += "</tr>"

    html_content += "</tbody></table></body></html>"
    return html_content


def merge_html_files(output_dir: str, safe_area: str, safe_geo: str, num_files: int, log_widget=None):
    """
    Merges batched _debug.html files into a single master HTML file and cleans up the temp files.
    """
    if num_files < 1:
        return

    _log("\n--- Merging HTML files ---", log_widget)
    final_filename = os.path.join(output_dir, f"{safe_area}_{safe_geo}.html")
    first_file_path = os.path.join(output_dir, f"{safe_area}_{safe_geo}_1_debug.html")

    try:
        with open(first_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            header_end_index = content.find("<tbody>") + len("<tbody>")
            header = content[:header_end_index]
            footer = content[content.find("</tbody>"):]
    except Exception as e:
        _log(f"  - ERROR: Could not read the first debug file. Aborting merge. Reason: {e}", log_widget)
        return

    all_rows = ""
    temp_files_to_delete = []
    for i in range(1, num_files + 1):
        temp_filename = os.path.join(output_dir, f"{safe_area}_{safe_geo}_{i}_debug.html")
        temp_files_to_delete.append(temp_filename)
        try:
            with open(temp_filename, 'r', encoding='utf-8') as f:
                content = f.read()
                start = content.find("<tbody>") + len("<tbody>")
                end = content.find("</tbody>")
                all_rows += content[start:end]
        except Exception as e:
            _log(f"  - WARNING: Could not read {temp_filename}. It will be skipped. Reason: {e}", log_widget)

    final_html = header + all_rows + footer
    try:
        with open(final_filename, 'w', encoding='utf-8') as f:
            f.write(final_html)
        _log(f"  - Successfully created merged file: '{final_filename}'", log_widget)
    except Exception as e:
        _log(f"  - ERROR: Could not save the final merged HTML file. Reason: {e}", log_widget)
        return

    _log("  - Cleaning up temporary files...", log_widget)
    for f_path in temp_files_to_delete:
        try:
            os.remove(f_path)
        except Exception as e:
            _log(f"  - WARNING: Could not delete temp file {f_path}. Reason: {e}", log_widget)


def populate_data(api_key: str, startup_list: list[str], parameter_list: list[str], area: str, geo: str,
                  model_name : str, log_widget=None) -> tuple[
    bool, dict | str]:
    """
    Iteratively calls the Gemini API and saves results, logging progress to a widget.
    """
    try:
        if (api_key is not None) and (api_key != ""):
            genai.configure(api_key=api_key)
        else:
            genai.configure(api_key=GEMINI_API_KEY)

        generation_config = {"temperature": 0.4, "response_mime_type": "application/json"}
        model = genai.GenerativeModel(model_name=model_name, generation_config=generation_config)

        all_startup_data, batch_data = {}, {}
        file_counter = 1
        output_dir = "Output Data"
        os.makedirs(output_dir, exist_ok=True)

        _log(f"Starting data population for {len(startup_list)} startups...", log_widget)

        for i, startup_name in enumerate(startup_list):
            _log(f"({i + 1}/{len(startup_list)}) Researching: {startup_name}...", log_widget)

            parameters_str = ", ".join(f'"{p}"' for p in parameter_list)
            prompt = f"""
            Based on publicly available information as of late 2023 / early 2024, perform deep research and populate the following parameters for the startup: "{startup_name}". The context is the '{area}' sector in '{geo}'.
            Parameters to populate: [{parameters_str}]
            For each parameter, provide a data object with two keys: "summary" and "sources".
            The "summary" MUST be a concise, data-oriented string up to 50 words.
            The "sources" MUST be an array of valid URL strings.
            Your response MUST be a single, valid JSON object. The keys of this object should be the parameter names.
            """

            try:
                response = model.generate_content(prompt)

                # --- SAFETY CHECK ---
                # Check if the response has content before trying to access it.
                if not response.parts:
                    block_reason = response.prompt_feedback.block_reason
                    error_message = f"Failed to process {startup_name}. Error: {block_reason}"
                    _log(f"  - WARNING: {error_message}", log_widget)
                    all_startup_data[startup_name] = {"error": error_message}
                    batch_data[startup_name] = {"error": error_message}

                else:
                    raw_text = response.text.replace('\\u20b9', 'Rs. ')
                    match = re.search(r'```(json)?\s*({.*})\s*```', raw_text, re.DOTALL)
                    json_text = match.group(2) if match else raw_text[raw_text.find('{'):raw_text.rfind('}') + 1]

                    try:
                        data = json.loads(json_text)
                    except json.JSONDecodeError as e:
                        # Attempt to fix common JSON errors from the LLM
                        error_str = str(e).lower()
                        if "invalid \\escape" in error_str:
                            _log("  - INFO: Attempting to fix invalid backslash escapes...", log_widget)
                            # Find backslashes that are NOT part of a valid JSON escape sequence and replace them
                            corrected_text = re.sub(r'\\(?![\\"/bfnrtu])', r'\\\\', json_text)
                            data = json.loads(corrected_text)
                            _log("  - INFO: Backslash fix successful.", log_widget)
                        elif "expecting property name enclosed in double quotes" in error_str:
                            _log("  - INFO: Attempting to fix single quotes in keys...", log_widget)
                            corrected_text = re.sub(r"(\s*|{\s*|,\s*)'([^']+)':", r'\1"\2":', json_text)
                            data = json.loads(corrected_text)
                            _log("  - INFO: Single quote fix successful.", log_widget)
                        else:
                            # If it's a different, unhandled error, re-raise it
                            raise e

                    all_startup_data[startup_name] = data
                    batch_data[startup_name] = data

            except Exception as e:
                error_message = f"Failed to process {startup_name}. Error: {e}"
                _log(f"  - WARNING: {error_message}", log_widget)
                all_startup_data[startup_name] = {"error": error_message}
                batch_data[startup_name] = {"error": error_message}

            if (i + 1) % 4 == 0 or (i + 1) == len(startup_list):
                if batch_data:
                    safe_area = "".join(c for c in area if c.isalnum() or c == ' ').rstrip().replace(' ', '_')
                    safe_geo = "".join(c for c in geo if c.isalnum() or c == ' ').rstrip().replace(' ', '_')
                    temp_html_filename = os.path.join(output_dir, f"{safe_area}_{safe_geo}_{file_counter}_debug.html")

                    html_content = save_to_html(batch_data, parameter_list)
                    try:
                        with open(temp_html_filename, 'w', encoding='utf-8') as f:
                            f.write(html_content)
                        _log(f"  - Saved intermediate HTML to '{temp_html_filename}'", log_widget)
                    except Exception as e:
                        _log(f"  - WARNING: Could not save intermediate HTML file. Reason: {e}", log_widget)
                        continue

                    file_counter += 1
                    batch_data = {}

                _log(f"Sleeping between batches to conserve TPM, RPM, and RPD", log_widget)
                if not ((i + 1) == len(startup_list)):
                    time.sleep(120)

            time.sleep(5)

        safe_area = "".join(c for c in area if c.isalnum() or c == ' ').rstrip().replace(' ', '_')
        safe_geo = "".join(c for c in geo if c.isalnum() or c == ' ').rstrip().replace(' ', '_')
        merge_html_files(output_dir, safe_area, safe_geo, file_counter - 1, log_widget)
        _log("--- Data population complete ---", log_widget)
        return True, {"startup_data": all_startup_data}

    except Exception as e:
        return False, f"An unexpected API or processing error occurred: {e}"

