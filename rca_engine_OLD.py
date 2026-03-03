import requests
import json
import re
import time
from typing import Dict, List
from config import GROQ_API_KEY, GROQ_URL, FAST_MODEL, SMART_MODEL
from utils import safe_json_loads


class RCAAgent:

    def call_ai(self, model: str, prompt: str, json_mode: bool = False, max_retries: int = 3):
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.4,
            "max_tokens": 4000
        }

        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        for attempt in range(max_retries):
            try:
                print(f"   API call attempt {attempt + 1}/{max_retries}...")
                r = requests.post(GROQ_URL, headers=headers, json=payload, timeout=120)
                
                if r.status_code == 200:
                    response_text = r.json()["choices"][0]["message"]["content"]
                    print(f"   Received {len(response_text)} chars")
                    return response_text
                elif r.status_code == 429:
                    wait = int(r.headers.get('retry-after', 5))
                    print(f"   Rate limited, waiting {wait}s...")
                    time.sleep(wait)
                else:
                    print(f"   API error {r.status_code}: {r.text[:200]}")
                    
            except Exception as e:
                print(f"   Error: {str(e)[:100]}")
            
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

        print("   All retries failed")
        return None

    def extract_key_details(self, raw_text: str) -> Dict:
        details = {
            "incident_id": "",
            "systems": [],
            "teams": [],
            "times": [],
            "change_id": "",
            "is_change": False,
            "impact": "",
            "resolution": "",
            "description": ""
        }
        
        text = raw_text.replace('|', ' ').replace('  ', ' ')
        
        # Extract Incident ID
        inc_match = re.search(r'(INC\d{6,12})', text, re.IGNORECASE)
        if inc_match:
            details["incident_id"] = inc_match.group(1).upper()
        
        # Extract Change ID
        chg_match = re.search(r'(?:Change\s*(?:ID|#)?|CR)[#\s-]*(\d{5,})', text, re.IGNORECASE)
        if chg_match:
            details["change_id"] = chg_match.group(1).upper()
            details["is_change"] = True
        
        if not details["is_change"]:
            change_keywords = ['change number', 'change id', 'deployment', 'upgrade']
            for kw in change_keywords:
                if kw in text.lower():
                    nearby = re.search(rf'{kw}[:,\s]*(\d{{5,}}|CR\d+)', text, re.IGNORECASE)
                    if nearby:
                        details["change_id"] = nearby.group(1).upper()
                        details["is_change"] = True
                    break
        
        # Extract times
        time_patterns = [
            r'(\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM)?\s*(?:CT|ET|PT|UTC))',
            r'(\d{4}-\d{2}-\d{2}\s+\d{1,2}:\d{2})'
        ]
        for pattern in time_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            details["times"].extend([m.strip() for m in matches if m.strip()])
        details["times"] = list(dict.fromkeys(details["times"]))[:5]
        
        # Extract Teams
        team_matches = re.findall(r'([A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]+)?)\s+[Tt]eam\b', text)
        details["teams"] = list(dict.fromkeys([t.strip() for t in team_matches if len(t) > 2]))[:5]
        
        # Extract Systems
        system_contexts = []
        for keyword in ['system', 'service', 'platform', 'application']:
            matches = re.findall(r'([A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]+)?)\s+' + keyword, text, re.IGNORECASE)
            system_contexts.extend(matches)
        
        exclude = {'INC', 'THE', 'AND', 'FOR', 'WAS', 'NOT', 'BUT', 'ARE', 'FROM', 'THAT', 
                   'WITH', 'THIS', 'WERE', 'BEEN', 'HAVE', 'THEY', 'WILL', 'TYPE', 'STATUS',
                   'PRIORITY', 'SEVERITY', 'MIM', 'POD', 'ID', 'CT', 'ET', 'PT', 'CONFIG',
                   'HTTP', 'HTTPS', 'API', 'URL', 'SQL', 'CPU', 'RAM', 'SSD'}
        
        caps_in_context = re.findall(r'(?:fail|issue|error|problem|outage)[^.]*?\b([A-Z]{2,8})\b', text, re.IGNORECASE)
        
        all_systems = system_contexts + caps_in_context
        details["systems"] = []
        for sys in all_systems:
            sys_clean = sys.strip().upper()
            if sys_clean not in exclude and len(sys_clean) > 1:
                if sys_clean not in details["systems"]:
                    details["systems"].append(sys_clean)
        details["systems"] = details["systems"][:8]
        
        # Extract impact
        impact_patterns = [
            r'(?:impact|affect|unable|could not)(?::|[^.])*?([^.]+)',
            r'([^.]*(?:locations?|customers?|users?|offices?)[^.]*(?:unable|affect|down)[^.]*)'
        ]
        for pattern in impact_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                impact_text = match.group(1).strip()
                if len(impact_text) > 10:
                    details["impact"] = impact_text[:200]
                    break
        
        # Extract resolution
        resolution_keywords = ['restart', 'reboot', 'reset', 'update', 'rollback', 'revert', 
                              'fixed', 'resolved', 'restored', 'failover']
        resolution_sentences = []
        for kw in resolution_keywords:
            pattern = rf"[^.]*\b{kw}[^.]*\."
            matches = re.findall(pattern, text, re.IGNORECASE)
            resolution_sentences.extend(matches)
        if resolution_sentences:
            details["resolution"] = " ".join(resolution_sentences[:3])[:300]
        
        # Get description
        paragraphs = [p.strip() for p in text.split('\n\n') if len(p.strip()) > 50]
        if paragraphs:
            details["description"] = paragraphs[0][:500]
        
        return details

    def generate_heading(self, details: Dict, raw_text: str) -> str:
        inc_id = details.get("incident_id", "INC-Unknown")
        systems = details.get("systems", [])
        impact = details.get("impact", "")
        times = details.get("times", [])
        
        prompt = f"""Create a crisp incident heading in past tense.

RULES:
- Must be a complete sentence
- Past tense (Failed, Caused, Resulted in)
- Include affected system/technology
- Include customer/business impact
- Keep under 12 words
- No jargon like "Issue" or "Problem" - be specific

INCIDENT DATA:
ID: {inc_id}
Systems: {', '.join(systems[:3])}
Impact: {impact}
Time: {times[0] if times else 'recent'}

Return ONLY the heading text, no quotes:"""
        
        heading = self.call_ai(FAST_MODEL, prompt)
        
        if heading:
            heading = heading.strip().strip('"').strip("'")
            if not heading.endswith(('.', '!')):
                heading += '.'
            return f"{inc_id}: {heading}"
        
        system_str = systems[0] if systems else "Service"
        time_str = times[0] if times else ""
        
        if impact:
            return f"{inc_id}: {system_str} Failure Impacting {impact[:30]} at {time_str}"
        else:
            return f"{inc_id}: {system_str} Service Disruption ({time_str})"

    def generate_rca_questions(self, details: Dict, raw_text: str) -> Dict:
        inc_id = details.get("incident_id", "INC")
        systems = details.get("systems", [])
        teams = details.get("teams", [])
        is_change = details.get("is_change", False)
        change_id = details.get("change_id", "")
        times = details.get("times", [])
        impact = details.get("impact", "")
        
        system_list = ', '.join(systems[:3]) if systems else "the affected system"
        team_list = ', '.join(teams[:2]) if teams else "the support team"
        time_str = times[0] if times else "the incident start"
        
        # Build the prompt carefully
        prompt_lines = [
            "Generate specific RCA questions using 5-Whys methodology.",
            "",
            "=== INCIDENT CONTEXT (USE THESE EXACT DETAILS) ===",
            f"Incident ID: {inc_id}",
            f"Type: {'Change-Induced' if is_change else 'General'}",
            f"Change ID: {change_id if is_change else 'N/A'}",
            f"Systems: {system_list}",
            f"Teams: {team_list}",
            f"Start Time: {time_str}",
            f"Impact: {impact[:100] if impact else 'Service disruption to users'}",
            "",
            "=== QUESTION STRUCTURE ===",
            "",
            "1. 5-WHYS CHAIN (Deep Investigation):",
            "- Start with immediate technical cause",
            "- Progress to systemic/root causes",
            "- Each Why must reference specific systems/times",
            "- 5-6 questions total",
            "",
            "2. CORRECTIVE ACTIONS (Immediate Fixes):",
            f"- What immediate actions were taken by {team_list}?",
            "- What needs to be fixed now?",
            "- 2-3 questions",
            "",
            "3. PREVENTIVE ACTIONS (Long-term):",
            "- What automation/process changes needed?",
            f"- How to prevent recurrence in {system_list}?",
            "- 2-3 questions",
            "",
            "4. GAP IDENTIFICATION:",
            "- Why didn't monitoring catch this?",
            "- What process/procedure failed?",
            "- 2-3 questions",
        ]
        
        if is_change:
            prompt_lines.extend([
                "",
                "5. CHANGE-SPECIFIC QUESTIONS:",
                f"- Why was change {change_id} approved for production?",
                f"- What testing was performed before {change_id} deployment?",
                f"- Why didn't testing catch the impact on {system_list}?",
                f"- Was there a rollback plan for {change_id}?",
                f"- Will {change_id} be re-implemented? Under new CR?"
            ])
        
        prompt_lines.extend([
            "",
            "=== STRICT RULES ===",
            '1. NO generic questions like "Why did it fail?" or "What was the cause?"',
            f"2. EVERY question must use specific names: {system_list}, {team_list}, {time_str}",
            "3. Questions should be answerable only by investigating THIS incident",
            "4. Use past tense in questions where appropriate",
            "",
            "=== OUTPUT FORMAT (JSON) ===",
            '{',
            '  "probable_root_cause": "One sentence describing what failed",',
            '  "rca_questions": {',
            '    "five_whys": [',
            '      "Why did [specific system] fail at [time]?",',
            '      "Why did [specific component] not handle the failure?"',
            '    ],',
            '    "corrective_actions": [',
            f'      "What specific action did {team_list} take?"',
            '    ],',
            '    "preventive_actions": [',
            f'      "What must be implemented in {system_list}?"',
            '    ],',
            '    "gap_identification": [',
            '      "Why did monitoring not detect this?"',
            '    ]',
        ])
        
        if is_change:
            prompt_lines.append(f'    ,"change_specific": ["Change {change_id} specific questions"]')
        
        prompt_lines.extend([
            '  }',
            '}',
            "",
            f"Generate questions using: {system_list}, {team_list}, {time_str}"
        ])
        
        prompt = "\n".join(prompt_lines)
        
        raw = self.call_ai(SMART_MODEL, prompt, json_mode=True)
        parsed = safe_json_loads(raw) if raw else None
        
        if parsed:
            return parsed
        
        # Smart fallback
        five_whys = [
            f"Why did {system_list} experience a failure at {time_str}?",
            f"What specific component in {system_list} was the first point of failure?",
            f"Why did {team_list} need to intervene manually to restore service?",
            f"Why didn't monitoring detect the {system_list} degradation before user impact?",
            f"What underlying architectural weakness allowed this failure mode?"
        ]
        
        corrective = [
            f"What specific actions did {team_list} take to restore {system_list}?",
            "Why was manual intervention required instead of automated recovery?"
        ]
        
        preventive = [
            f"What must be implemented in {system_list} to prevent similar failures?",
            f"Why isn't {system_list} configuration validation automated?"
        ]
        
        gaps = [
            f"Why didn't monitoring alerts trigger for {system_list} before customer impact?",
            "What process gap allowed this issue to reach production?"
        ]
        
        change_qs = []
        if is_change:
            change_qs = [
                f"Why was change {change_id} approved without detecting the impact on {system_list}?",
                f"What testing was missing in {change_id} that would have caught this?",
                f"Why wasn't {change_id} rolled back immediately upon detection?"
            ]
        
        return {
            "probable_root_cause": f"Technical failure in {system_list} requiring manual intervention by {team_list}.",
            "rca_questions": {
                "five_whys": five_whys,
                "corrective_actions": corrective,
                "preventive_actions": preventive,
                "gap_identification": gaps,
                "change_specific": change_qs
            },
            "fallback_used": True
        }

    def process_incident(self, whiteboard_text: str, mir_text: str = None) -> Dict:
        print("Extracting incident details...")
        details = self.extract_key_details(whiteboard_text)
        
        if mir_text:
            mir_details = self.extract_key_details(mir_text)
            if mir_details.get("resolution"):
                details["mir_resolution"] = mir_details["resolution"]
        
        print(f"   Found: {details.get('incident_id', 'No ID')}, Change: {details.get('is_change', False)}")
        
        print("Generating crisp heading...")
        heading = self.generate_heading(details, whiteboard_text)
        print(f"   {heading[:80]}...")
        
        print("Generating RCA questions...")
        rca_result = self.generate_rca_questions(details, whiteboard_text)
        
        result = {
            "heading": heading,
            "probable_root_cause": rca_result.get("probable_root_cause", ""),
            "incident_classification": {
                "is_change": details.get("is_change", False),
                "change_id": details.get("change_id", ""),
                "type": "change-induced" if details.get("is_change") else "general"
            },
            "sections": {
                "five_whys": rca_result["rca_questions"]["five_whys"],
                "corrective_actions": rca_result["rca_questions"]["corrective_actions"],
                "preventive_actions": rca_result["rca_questions"]["preventive_actions"],
                "gap_identification": rca_result["rca_questions"]["gap_identification"],
                "change_specific": rca_result["rca_questions"].get("change_specific", [])
            },
            "incident_details": {
                "incident_id": details.get("incident_id", ""),
                "systems_affected": details.get("systems", []),
                "teams_involved": details.get("teams", []),
                "timeline": details.get("times", []),
                "impact": details.get("impact", ""),
                "change_id": details.get("change_id", "")
            },
            "raw_data": {
                "whiteboard": whiteboard_text[:2000],
                "mir": mir_text[:2000] if mir_text else None
            }
        }
        
        return result

    def improve_text(self, text: str, context: str = "heading") -> str:
        prompts = {
            "heading": f"""Improve this incident heading:
- Make it crisp and professional
- Ensure past tense
- Include specific impact
- Remove filler words

Original: {text}

Improved (return only the improved text):""",
            
            "question": f"""Improve this RCA question:
- Make it more specific and investigative
- Ensure it follows 5-whys methodology
- Remove ambiguity

Original: {text}

Improved:""",
            
            "root_cause": f"""Improve this root cause statement:
- Make it factual and specific
- Include what failed and why
- Remove vague terms

Original: {text}

Improved:"""
        }
        
        prompt = prompts.get(context, prompts["heading"])
        improved = self.call_ai(FAST_MODEL, prompt)
        
        return improved.strip() if improved else text

    def modify_rca(self, current_rca: Dict, user_request: str) -> Dict:
        prompt = f"""Modify this RCA based on user request.

CURRENT RCA:
Heading: {current_rca.get('heading', '')}
Root Cause: {current_rca.get('probable_root_cause', '')}
Questions: {json.dumps(current_rca.get('sections', {}), indent=2)}

USER REQUEST: {user_request}

Modify appropriately and return the complete updated JSON structure."""

        raw = self.call_ai(SMART_MODEL, prompt, json_mode=True)
        if raw:
            updated = safe_json_loads(raw)
            if updated:
                updated["incident_details"] = current_rca.get("incident_details", {})
                return updated
        
        return current_rca

    def answer_question(self, question: str, rca_data: Dict) -> str:
        details = rca_data.get("incident_details", {})
        q_lower = question.lower()
        
        if any(w in q_lower for w in ['which team', 'who resolved', 'who handled']):
            teams = details.get('teams_involved', [])
            return f"The incident was handled by: {', '.join(teams)}." if teams else "Team information not available."
        
        if any(w in q_lower for w in ['which system', 'what system', 'affected systems']):
            systems = details.get('systems_affected', [])
            return f"The affected systems were: {', '.join(systems[:3])}." if systems else "System information not available."
        
        if any(w in q_lower for w in ['when', 'what time', 'start']):
            times = details.get('timeline', [])
            return f"Incident started at: {times[0] if times else 'Time not recorded'}."
        
        if any(w in q_lower for w in ['change', 'cr#', 'deployment']):
            if details.get('change_id'):
                return f"This was related to change: {details['change_id']}."
            return "No change number was identified for this incident."
        
        context = f"""Incident: {details.get('incident_id')}
Systems: {', '.join(details.get('systems_affected', [])[:3])}
Teams: {', '.join(details.get('teams_involved', [])[:2])}
Impact: {details.get('impact', '')}"""
        
        prompt = f"""Answer this question about the incident:

Context:
{context}

Question: {question}

Provide a specific answer:"""
        
        answer = self.call_ai(FAST_MODEL, prompt)
        return answer.strip() if answer else "I don't have that specific information."