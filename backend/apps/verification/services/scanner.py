import json
import os
import requests
from typing import List, Dict, Any

VALID_CATEGORIES = {
    "AUTHENTICATION",
    "AUTHORIZATION",
    "INPUT_VALIDATION",
    "ERROR_HANDLING",
    "LOGGING",
    "RATE_LIMITING",
    "EDGE_CASES",
    "TESTS"
}

VALID_SEVERITIES = {
    "CRITICAL",
    "HIGH",
    "MEDIUM",
    "LOW",
    "INFO"
}


class NegativeSpaceScannerError(Exception):
    """Custom exception raised when negative-space scanning fails."""
    pass


class NegativeSpaceScannerService:
    """
    Service for running Negative-Space Scanning on PR diffs using an LLM.
    Analyzes code changes to identify omitted or missing security, validation,
    error handling, logging, rate limiting, edge case, or testing concerns.
    """

    @classmethod
    def scan(cls, verification_run) -> List[Dict[str, Any]]:
        """
        Performs a negative-space analysis on the given VerificationRun instance.
        Returns a list of structured finding dictionaries.
        
        Raises NegativeSpaceScannerError on LLM, network, or parsing failures.
        """
        api_key = os.getenv('LLM_API_KEY')
        if not api_key:
            raise NegativeSpaceScannerError("LLM_API_KEY environment variable is not configured.")

        model = os.getenv('LLM_MODEL', 'gpt-4o-mini')
        base_url = os.getenv('LLM_BASE_URL', 'https://api.openai.com/v1')

        ingested = verification_run.ingestion_data
        if not ingested or not isinstance(ingested, dict):
            raise NegativeSpaceScannerError("Verification run has no ingestion data to scan.")

        pr_info = ingested.get('pr', {})
        files_info = ingested.get('files', [])

        title = pr_info.get('title', 'N/A')
        description = pr_info.get('body', 'N/A')

        if not files_info:
            files_summary = "No changed files found in ingestion data."
        else:
            summaries = []
            for f in files_info:
                filename = f.get('filename', 'unknown')
                status = f.get('status', 'modified')
                patch = f.get('patch', '')
                summaries.append(f"File: {filename}\nStatus: {status}\nPatch:\n{patch}\n")
            files_summary = "\n---\n".join(summaries)

        system_prompt = (
            "You are ASEA Negative-Space Scanner, a security and quality code audit system. "
            "Analyze the provided Pull Request changes for missing, omitted, or inadequate implementations. "
            "You MUST ONLY inspect and report omitted concerns. Do NOT generate fixed code, modified code, or solutions. "
            "You MUST respond ONLY with a valid JSON array of objects. "
            "Each object MUST contain exactly four string fields:\n"
            "- \"category\": One of [\"AUTHENTICATION\", \"AUTHORIZATION\", \"INPUT_VALIDATION\", "
            "\"ERROR_HANDLING\", \"LOGGING\", \"RATE_LIMITING\", \"EDGE_CASES\", \"TESTS\"]\n"
            "- \"severity\": One of [\"CRITICAL\", \"HIGH\", \"MEDIUM\", \"LOW\", \"INFO\"]\n"
            "- \"description\": Detailed explanation of what safety/quality mechanism is missing.\n"
            "- \"reason\": Code evidence or contextual reasoning explaining why this issue exists.\n\n"
            "Output RAW JSON ONLY. No markdown formatting, no code fences."
        )

        user_prompt = (
            f"PR Title: {title}\n"
            f"PR Description: {description}\n\n"
            f"Diff and Files Changed:\n{files_summary}"
        )

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.2
        }

        endpoint = f"{base_url.rstrip('/')}/chat/completions"

        try:
            response = requests.post(endpoint, json=payload, headers=headers, timeout=30)
        except requests.RequestException as exc:
            raise NegativeSpaceScannerError(f"LLM API request connection error: {str(exc)}") from exc

        if response.status_code != 200:
            raise NegativeSpaceScannerError(
                f"LLM API request failed with status code {response.status_code}: {response.text}"
            )

        try:
            res_data = response.json()
            raw_content = res_data['choices'][0]['message']['content'].strip()
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise NegativeSpaceScannerError(f"Failed to extract content from LLM response: {str(exc)}") from exc

        # Strip markdown code blocks if LLM wrapped output in ```json ... ```
        if raw_content.startswith("```"):
            lines = raw_content.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            raw_content = "\n".join(lines).strip()

        try:
            findings = json.loads(raw_content)
        except json.JSONDecodeError as exc:
            raise NegativeSpaceScannerError(f"LLM returned invalid JSON output: {str(exc)}") from exc

        if not isinstance(findings, list):
            raise NegativeSpaceScannerError("LLM output must be a JSON list of finding objects.")

        validated_findings = []
        for index, item in enumerate(findings):
            if not isinstance(item, dict):
                raise NegativeSpaceScannerError(f"Finding at index {index} is not a valid JSON object.")

            category = str(item.get("category", "")).upper()
            severity = str(item.get("severity", "")).upper()
            description = item.get("description")
            reason = item.get("reason")

            if category not in VALID_CATEGORIES:
                raise NegativeSpaceScannerError(
                    f"Finding at index {index} has invalid category '{category}'. Must be one of {sorted(list(VALID_CATEGORIES))}."
                )

            if severity not in VALID_SEVERITIES:
                raise NegativeSpaceScannerError(
                    f"Finding at index {index} has invalid severity '{severity}'. Must be one of {sorted(list(VALID_SEVERITIES))}."
                )

            if not description or not isinstance(description, str):
                raise NegativeSpaceScannerError(f"Finding at index {index} is missing a valid 'description' string.")

            if not reason or not isinstance(reason, str):
                raise NegativeSpaceScannerError(f"Finding at index {index} is missing a valid 'reason' string.")

            validated_findings.append({
                "category": category,
                "severity": severity,
                "description": description.strip(),
                "reason": reason.strip()
            })

        return validated_findings
