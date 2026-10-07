import json
import os
import re
import requests
from typing import List, Dict, Any

VALID_CATEGORIES = {
    "MODULE_ORGANIZATION",
    "NAMING_CONVENTIONS",
    "DESIGN_PATTERNS",
    "API_STRUCTURE",
    "ERROR_HANDLING",
    "DEPENDENCY_USAGE",
    "TEST_CONVENTIONS"
}

VALID_SEVERITIES = {
    "CRITICAL",
    "HIGH",
    "MEDIUM",
    "LOW",
    "INFO"
}


class ArchitectureCheckerError(Exception):
    """Custom exception raised when Architecture Fit Checking fails."""
    pass


class ArchitectureCheckerService:
    """
    Service for evaluating PR changes against codebase architectural structure and design patterns.
    Combines rule-based static analysis checks with LLM architectural pattern comparison.
    """

    @classmethod
    def check(cls, verification_run) -> List[Dict[str, Any]]:
        """
        Performs architecture fit analysis on the given VerificationRun instance.
        Returns a list of structured finding dictionaries.
        
        Raises ArchitectureCheckerError on analysis, network, or LLM failures.
        """
        ingested = verification_run.ingestion_data
        if not ingested or not isinstance(ingested, dict):
            raise ArchitectureCheckerError("Verification run has no ingestion data to analyze.")

        pr_info = ingested.get('pr', {})
        files_info = ingested.get('files', [])

        # 1. Rule-Based Static Analysis Checks
        static_findings = cls._run_static_rule_checks(files_info)

        # 2. LLM Architectural Comparison Checks
        llm_findings = cls._run_llm_architecture_check(pr_info, files_info)

        # 3. Combine findings
        all_findings = static_findings + llm_findings
        return all_findings

    @classmethod
    def _run_static_rule_checks(cls, files_info: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        findings = []
        has_test_files = False
        has_feature_files = False

        for f in files_info:
            filename = f.get('filename', '')
            patch = f.get('patch', '')

            # Track test presence vs feature files
            if 'test' in filename.lower():
                has_test_files = True
            elif filename.endswith('.py') and not filename.endswith('__init__.py'):
                has_feature_files = True

            # Check Naming Conventions
            if 'views' in filename and filename.endswith('.py'):
                # Extract class names in patch
                class_matches = re.findall(r'\+class\s+([A-Za-z0-9_]+)', patch)
                for class_name in class_matches:
                    if not class_name.endswith('View') and not class_name.endswith('TestCase') and not class_name.endswith('Test'):
                        findings.append({
                            "category": "NAMING_CONVENTIONS",
                            "severity": "LOW",
                            "description": f"View class '{class_name}' in {filename} does not follow standard naming convention ending with 'View'.",
                            "evidence": f"Class declaration: class {class_name}"
                        })

            if 'serializers' in filename and filename.endswith('.py'):
                class_matches = re.findall(r'\+class\s+([A-Za-z0-9_]+)', patch)
                for class_name in class_matches:
                    if not class_name.endswith('Serializer'):
                        findings.append({
                            "category": "NAMING_CONVENTIONS",
                            "severity": "LOW",
                            "description": f"Serializer class '{class_name}' in {filename} does not follow standard naming convention ending with 'Serializer'.",
                            "evidence": f"Class declaration: class {class_name}"
                        })

            if 'services' in filename and filename.endswith('.py'):
                class_matches = re.findall(r'\+class\s+([A-Za-z0-9_]+)', patch)
                for class_name in class_matches:
                    if not class_name.endswith('Service') and not class_name.endswith('Error'):
                        findings.append({
                            "category": "NAMING_CONVENTIONS",
                            "severity": "LOW",
                            "description": f"Service class '{class_name}' in {filename} does not follow standard naming convention ending with 'Service'.",
                            "evidence": f"Class declaration: class {class_name}"
                        })

            # Check Error Handling Patterns (bare except or pass swallowing errors)
            if re.search(r'\+.*except\s*:\s*pass', patch) or re.search(r'\+.*except\s+Exception\s*:\s*pass', patch):
                findings.append({
                    "category": "ERROR_HANDLING",
                    "severity": "HIGH",
                    "description": f"Silent exception swallowing detected in {filename}.",
                    "evidence": "Broad except block with pass statement found in patch."
                })

            # Check Module Organization
            if filename.startswith('backend/') and not re.match(r'^backend/(apps|config|venv|\.[^/]+|[^/]+\.py)', filename):
                findings.append({
                    "category": "MODULE_ORGANIZATION",
                    "severity": "MEDIUM",
                    "description": f"File '{filename}' placed outside standard project modular structure ('apps/', 'config/').",
                    "evidence": f"File path: {filename}"
                })

        # Check Test Conventions across PR
        if has_feature_files and not has_test_files:
            findings.append({
                "category": "TEST_CONVENTIONS",
                "severity": "MEDIUM",
                "description": "PR includes new or modified feature code but does not include updated or new test files.",
                "evidence": "No files matching '*test*' were modified in this PR."
            })

        return findings

    @classmethod
    def _run_llm_architecture_check(cls, pr_info: Dict[str, Any], files_info: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        api_key = os.getenv('LLM_API_KEY')
        if not api_key:
            raise ArchitectureCheckerError("LLM_API_KEY environment variable is not configured.")

        model = os.getenv('LLM_MODEL', 'gpt-4o-mini')
        base_url = os.getenv('LLM_BASE_URL', 'https://api.openai.com/v1')

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
            "You are ASEA Architecture Fit Checker, an expert software architecture auditor. "
            "Analyze the provided Pull Request code diffs for alignment with codebase architectural patterns. "
            "Inspect: module/file organization, naming conventions, design patterns, API structure, "
            "error handling patterns, dependency usage, and test conventions. "
            "You are read-only: NEVER generate fixed code or modify code. Only report architectural findings. "
            "You MUST respond ONLY with a valid JSON array of objects. "
            "Each object MUST contain exactly four string fields:\n"
            "- \"category\": One of [\"MODULE_ORGANIZATION\", \"NAMING_CONVENTIONS\", \"DESIGN_PATTERNS\", "
            "\"API_STRUCTURE\", \"ERROR_HANDLING\", \"DEPENDENCY_USAGE\", \"TEST_CONVENTIONS\"]\n"
            "- \"severity\": One of [\"CRITICAL\", \"HIGH\", \"MEDIUM\", \"LOW\", \"INFO\"]\n"
            "- \"description\": Clear explanation of the architectural discrepancy or pattern deviation.\n"
            "- \"evidence\": Specific code snippet, class name, or file path demonstrating the architectural issue.\n\n"
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
            raise ArchitectureCheckerError(f"LLM API connection error during architecture check: {str(exc)}") from exc

        if response.status_code != 200:
            raise ArchitectureCheckerError(
                f"LLM API architecture check failed with status code {response.status_code}: {response.text}"
            )

        try:
            res_data = response.json()
            raw_content = res_data['choices'][0]['message']['content'].strip()
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise ArchitectureCheckerError(f"Failed to extract content from LLM response: {str(exc)}") from exc

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
            raise ArchitectureCheckerError(f"LLM returned invalid JSON output for architecture check: {str(exc)}") from exc

        if not isinstance(findings, list):
            raise ArchitectureCheckerError("LLM architecture check output must be a JSON list of finding objects.")

        validated_findings = []
        for index, item in enumerate(findings):
            if not isinstance(item, dict):
                raise ArchitectureCheckerError(f"LLM finding at index {index} is not a JSON object.")

            category = str(item.get("category", "")).upper()
            severity = str(item.get("severity", "")).upper()
            description = item.get("description")
            evidence = item.get("evidence")

            if category not in VALID_CATEGORIES:
                raise ArchitectureCheckerError(
                    f"LLM finding at index {index} has invalid category '{category}'. Must be one of {sorted(list(VALID_CATEGORIES))}."
                )

            if severity not in VALID_SEVERITIES:
                raise ArchitectureCheckerError(
                    f"LLM finding at index {index} has invalid severity '{severity}'. Must be one of {sorted(list(VALID_SEVERITIES))}."
                )

            if not description or not isinstance(description, str):
                raise ArchitectureCheckerError(f"LLM finding at index {index} missing 'description' string.")

            if not evidence or not isinstance(evidence, str):
                raise ArchitectureCheckerError(f"LLM finding at index {index} missing 'evidence' string.")

            validated_findings.append({
                "category": category,
                "severity": severity,
                "description": description.strip(),
                "evidence": evidence.strip()
            })

        return validated_findings
