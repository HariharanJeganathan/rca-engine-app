from memory_store import RCAStore

store = RCAStore()

def get_rca_context(limit: int = 5) -> str:
    """Fetch recent finalized RCAs for AI context"""
    rows = store.find_recent_final(limit)
    
    if not rows:
        return "No historical RCA data available."
    
    context_blocks = []
    for r in rows:
        block = f"""
INCIDENT: {r["incident_id"]}
ROOT CAUSE: {r["final_root_cause"]}
CORRECTIVE: {r["corrective_actions"]}
PREVENTIVE: {r["preventive_actions"]}
"""
        context_blocks.append(block.strip())
    
    return "\n\n---\n\n".join(context_blocks)