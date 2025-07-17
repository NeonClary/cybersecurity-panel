from typing import List
from app.llm.llm_client import LLMClient
import logging
import re
from typing import List, Dict

logger = logging.getLogger(__name__)

async def generate_summary_from_messages(messages: List[dict], llm: LLMClient, max_tokens: int = 800) -> str:
    """
    Summarize the conversation using the given LLM client.
    """
    try:
        full_text = "\n\n".join([f"{m['role']}:\n{m['content']}" for m in messages])

        system_prompt = (
            "You are an academic assistant. Summarize the following PhD chat conversation "
            "into concise bullet points (max 10) or short paragraphs. Focus on insights, questions, and advice."
        )

        context = [{"role": "user", "content": f"Chat Log:\n{full_text}"}]

        summary = await llm.generate(
            system_prompt=system_prompt,
            context=context,
            temperature=0.4,
            max_tokens=max_tokens
        )

        return summary.strip()

    except Exception as e:
        logger.error(f"Error generating summary: {str(e)}")
        return "Summary generation failed. Please try again later."

def parse_summary_to_blocks(summary_text: str) -> List[Dict]:
    #summary_text = re.sub(r'(?<!\n)([*•] )', r'\n\1', summary_text)
    #summary_text = re.sub(r'(?<!\n)(\d+\.\s+)', r'\n\1', summary_text)
    #summary_text = re.sub(r'(?<=[.!?])(?=\S)', ' ', summary_text)

    lines = summary_text.strip().splitlines()
    blocks = []
    current_block = None

    def flush_current_block():
        if current_block:
            blocks.append(current_block.copy())

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Match section headings (e.g. **Title:**) as heading block
        heading_match = re.match(r'^\*\*(.+?)\*\*:?$', line)
        if heading_match:
            flush_current_block()
            current_block = {"type": "heading", "text": heading_match.group(1).strip()}
            flush_current_block()
            current_block = None
            continue

        # Match bullet list
        if line.startswith("* "):
            if current_block is None or current_block["type"] != "list" or current_block.get("style") != "bullet":
                flush_current_block()
                current_block = {"type": "list", "style": "bullet", "items": []}
            current_block["items"].append(line[2:].strip())
            continue

        # Match numbered list
        number_match = re.match(r'^\d+\.\s+(.*)', line)
        if number_match:
            if current_block is None or current_block["type"] != "list" or current_block.get("style") != "numbered":
                flush_current_block()
                current_block = {"type": "list", "style": "numbered", "items": []}
            current_block["items"].append(number_match.group(1).strip())
            continue

        # Default: treat as paragraph
        flush_current_block()
        current_block = {"type": "paragraph", "text": line}
        flush_current_block()
        current_block = None

    flush_current_block()

    import pprint
    print("[DEBUG] Summary Blocks:")
    pprint.pprint(blocks)
    return blocks

