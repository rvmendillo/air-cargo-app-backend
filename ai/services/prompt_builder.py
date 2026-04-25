class PromptBuilder:
    def __init__(self, system_prompt: str):
        self.system_prompt = system_prompt

    def build(self, user_text: str, context: str = None) -> str:
        context_block = ""
        if context:
            context_block = f"""
SHIPMENT/AWB CONTEXT DATA (use this to answer user questions about their specific shipment):
{context}
"""
        return f"""
{self.system_prompt}
{context_block}
TASK:
Analyze and respond to the user's query. If shipment context data is provided, use it to give specific answers.

USER QUERY:
{user_text}
""".strip()