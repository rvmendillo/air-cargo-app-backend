class PromptBuilder:
    def __init__(self, system_prompt: str):
        self.system_prompt = system_prompt

    def build(self, user_text: str) -> str:
        return f"""
{self.system_prompt}

TASK:
Analyze shipment for DGR compliance.

INPUT:
{user_text}
""".strip()