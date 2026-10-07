from typing import Dict, Any, List, Tuple

SEVERITY_PENALTIES = {
    "CRITICAL": 25,
    "HIGH": 15,
    "MEDIUM": 8,
    "LOW": 3,
    "INFO": 1
}


class ConfidenceScoringError(Exception):
    """Custom exception raised when confidence scoring fails."""
    pass


class ConfidenceScoringService:
    """
    Service for calculating a deterministic, explainable confidence score (0-100)
    for a VerificationRun based on Module 3 (Negative-Space Scanner) and Module 4 (Architecture Fit Checker) findings.
    """

    @classmethod
    def calculate_score(cls, verification_run) -> Tuple[int, str, List[Dict[str, Any]]]:
        """
        Calculates confidence score, explanation narrative, and penalty breakdown.
        Returns a tuple: (score: int, explanation: str, breakdown: list).
        """
        try:
            negative_findings = verification_run.findings or []
            architecture_findings = verification_run.architecture_findings or []
        except Exception as exc:
            raise ConfidenceScoringError(f"Failed to access verification run findings: {str(exc)}") from exc

        base_score = 100
        breakdown = []
        severity_counts = {
            "CRITICAL": 0,
            "HIGH": 0,
            "MEDIUM": 0,
            "LOW": 0,
            "INFO": 0
        }
        total_penalties = 0

        # Process Module 3 Findings
        for finding in negative_findings:
            if not isinstance(finding, dict):
                continue
            severity = str(finding.get("severity", "INFO")).upper()
            penalty = SEVERITY_PENALTIES.get(severity, 1)
            total_penalties += penalty
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

            breakdown.append({
                "source": "Module 3 (Negative-Space Scanner)",
                "category": finding.get("category", "UNKNOWN"),
                "severity": severity,
                "deduction": penalty,
                "description": finding.get("description", ""),
                "reason": finding.get("reason", "")
            })

        # Process Module 4 Findings
        for finding in architecture_findings:
            if not isinstance(finding, dict):
                continue
            severity = str(finding.get("severity", "INFO")).upper()
            penalty = SEVERITY_PENALTIES.get(severity, 1)
            total_penalties += penalty
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

            breakdown.append({
                "source": "Module 4 (Architecture Fit Checker)",
                "category": finding.get("category", "UNKNOWN"),
                "severity": severity,
                "deduction": penalty,
                "description": finding.get("description", ""),
                "evidence": finding.get("evidence", "")
            })

        final_score = max(0, min(100, base_score - total_penalties))

        # Generate Explanation
        total_findings = len(breakdown)
        if total_findings == 0:
            explanation = (
                "Base confidence score of 100/100. "
                "No negative-space or architectural concerns identified across all modules. "
                "High confidence for deployment."
            )
        else:
            summary_parts = []
            for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
                cnt = severity_counts.get(sev, 0)
                if cnt > 0:
                    pts = cnt * SEVERITY_PENALTIES[sev]
                    summary_parts.append(f"{cnt} {sev} (-{pts} pts)")

            breakdown_text = ", ".join(summary_parts)
            explanation = (
                f"Base confidence score of 100 reduced by {total_penalties} penalty points across {total_findings} total finding(s) "
                f"({breakdown_text}). Final confidence score evaluated to {final_score}/100."
            )

        return final_score, explanation, breakdown
