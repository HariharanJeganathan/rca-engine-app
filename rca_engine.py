import re
import json
from typing import Dict, Optional
from datetime import datetime
from openai import AzureOpenAI

from config import (
    AZURE_OPENAI_KEY,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_DEPLOYMENT,
    SMART_MODEL,
    FAST_MODEL
)


class RCAAgent:
    def __init__(self):
        # Azure OpenAI Client
        self.client = AzureOpenAI(
            api_key=AZURE_OPENAI_KEY,
            api_version="2024-02-15-preview",
            azure_endpoint=AZURE_OPENAI_ENDPOINT
        )

    # -------------------------------------------------
    # AI CALL
    # -------------------------------------------------
    def call_ai(self, prompt: str, max_tokens: int = 2000, model: str = None) -> Optional[str]:
        if not model:
            model = SMART_MODEL

        try:
            response = self.client.chat.completions.create(
                model=AZURE_OPENAI_DEPLOYMENT,  # deployment name (gpt-4o)
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert Root Cause Analysis investigator for enterprise IT incidents."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=max_tokens
            )

            return response.choices[0].message.content

        except Exception as e:
            print("AI Call Error:", e)
            return None

    # -------------------------------------------------
    # EXTRACT DETAILS
    # -------------------------------------------------
    def extract_incident_details(self, text: str) -> Dict:
        details = {
            "incident_id": "",
            "systems": [],
            "teams": [],
            "times": [],
            "change_id": "",
            "is_change": False,
            "impact": "",
        }

        inc_match = re.search(r'(INC\d{6,12})', text, re.IGNORECASE)
        if inc_match:
            details["incident_id"] = inc_match.group(1).upper()

        teams = re.findall(r'([A-Z][a-zA-Z]+)\s+[Tt]eam', text)
        details["teams"] = list(set(teams))[:3]

        systems = re.findall(r'(?:system|service|platform)\s+([A-Z][a-zA-Z]+)', text)
        details["systems"] = list(set(systems))[:5]

        return details

    # -------------------------------------------------
    # HEADING
    # -------------------------------------------------
    def generate_heading(self, details: Dict, text: str) -> str:
        inc_id = details.get("incident_id", "INC-Unknown")

        prompt = f"""
Generate a crisp incident heading in past tense.
Max 10 words. Mention system + impact.

Incident ID: {inc_id}
Systems: {details.get('systems')}
Impact: {details.get('impact')}

Return only heading sentence.
"""

        heading = self.call_ai(prompt, max_tokens=100, model=FAST_MODEL)

        if heading:
            heading = heading.strip().replace('"', '')
            return f"{inc_id}: {heading}"

        return f"{inc_id}: Service Disruption Occurred"

    # -------------------------------------------------
    # QUESTIONS (NO RAG)
    # -------------------------------------------------
    def generate_rca_questions(self, details: Dict, text: str, is_final: bool = False) -> Dict:
        """Generate specific RCA questions using AI only (No RAG)"""

        system_list = ', '.join(details.get('systems', ['affected system']))
        team_list = ', '.join(details.get('teams', ['support team']))
        time_str = details['times'][0] if details.get('times') else 'incident start'

        prompt = f"""Generate detailed RCA investigation questions for this incident.

Incident Context:
Systems: {system_list}
Teams: {team_list}
Time: {time_str}
Impact: {details.get('impact', 'Service disruption')}

Text Sample:
{text[:1200]}

Generate:
1. FIVE WHYS – 5 questions
2. CORRECTIVE ACTIONS – 3 questions
3. PREVENTIVE ACTIONS – 3 questions
4. GAP IDENTIFICATION – 3 questions

Rules:
- Questions must be specific to THIS incident
- Use actual system names
- Use actual team names
- No generic questions like "Why did system fail?"
- Questions should sound like real enterprise RCA investigation
- No explanations, only questions
- Return ONLY JSON

Return JSON:
{{
"probable_root_cause": "one clear technical sentence",
"five_whys": [],
"corrective_actions": [],
"preventive_actions": [],
"gap_identification": []
}}
"""

        response = self.call_ai(prompt, max_tokens=2200, model=SMART_MODEL)

        if response:
            try:
                response = response.strip()

                if response.startswith("```json"):
                    response = response[7:]
                if response.endswith("```"):
                    response = response[:-3]

                parsed = json.loads(response.strip())

                return {
                    "probable_root_cause": parsed.get("probable_root_cause", f"Issue detected in {system_list}"),
                    "five_whys": parsed.get("five_whys", [])[:5],
                    "corrective_actions": parsed.get("corrective_actions", [])[:3],
                    "preventive_actions": parsed.get("preventive_actions", [])[:3],
                    "gap_identification": parsed.get("gap_identification", [])[:3],
                    "change_specific": []
                }

            except Exception as e:
                print("JSON Parse Failed:", e)

        # Soft fallback
        return {
            "probable_root_cause": f"Service disruption occurred in {system_list}.",
            "five_whys": [
                f"Why did {system_list} fail at {time_str}?",
                f"Why did {team_list} not detect earlier?",
                "Why did monitoring not alert?",
                "Why did the failure impact users?",
                "Why was prevention missing?"
            ],
            "corrective_actions": [
                f"What immediate action did {team_list} take?",
                "What configuration or service was restored?",
                "What rollback or restart was done?"
            ],
            "preventive_actions": [
                "What monitoring improvement is needed?",
                "What redundancy or automation should be added?",
                "What validation checks should be enforced?"
            ],
            "gap_identification": [
                "Which alert failed?",
                "Which escalation step was delayed?",
                "What process gap allowed this?"
            ],
            "change_specific": []
        }

    # -------------------------------------------------
    # MAIN PROCESS
    # -------------------------------------------------
    def process_incident(self, whiteboard_text: str, mir_text: str = None, is_draft: bool = True) -> Dict:

        full_text = whiteboard_text or ""
        if mir_text:
            full_text += "\n" + mir_text

        details = self.extract_incident_details(full_text)

        heading = self.generate_heading(details, full_text)
        questions = self.generate_rca_questions(details, full_text)

        return {
            "heading": heading,
            "probable_root_cause": questions["probable_root_cause"],
            "sections": {
                "five_whys": questions["five_whys"],
                "corrective_actions": questions["corrective_actions"],
                "preventive_actions": questions["preventive_actions"],
                "gap_identification": questions["gap_identification"]
            },
            "incident_details": details,
            "created_at": datetime.utcnow().isoformat()
        }