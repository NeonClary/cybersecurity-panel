from typing import Dict, List, Optional

import logging
import re

from app.llm.llm_client import LLMClient
from app.config import get_settings

logger = logging.getLogger(__name__)

CONTEXT_SUMMARY_SYSTEM = (
    "You are a concise summarizer. Condense the following conversation into a short summary "
    "that preserves the key topics discussed, any conclusions reached, important facts shared, "
    "and the overall tone. Keep it under 300 words. Write in third person narrative form."
)


def _conversation_role_label(role: str, persona_names: Optional[Dict[str, str]] = None) -> str:
    if role == "user":
        return "User"
    if role == "assistant":
        return "Assistant"
    if persona_names and role in persona_names:
        return persona_names[role]
    return role.replace("_", " ").title()


async def generate_conversation_context_summary(
    messages: List[dict],
    llm: LLMClient,
    persona_names: Optional[Dict[str, str]] = None,
    max_tokens: int = 1024,
) -> str:
    """Summarize chat history for LLM context when the transcript exceeds the token budget."""
    transcript_lines = []
    for msg in messages:
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        label = _conversation_role_label(msg.get("role", "user"), persona_names)
        transcript_lines.append(f"{label}: {content}")

    if not transcript_lines:
        return ""

    transcript = "\n".join(transcript_lines)
    try:
        summary = await llm.generate(
            system_prompt=CONTEXT_SUMMARY_SYSTEM,
            context=[{"role": "user", "content": transcript}],
            temperature=0.3,
            max_tokens=max_tokens,
        )
        return (summary or "").strip()
    except Exception as exc:
        logger.error("Conversation context summary failed: %s", exc)
        return ""

async def generate_summary_from_messages(messages: List[dict], llm: LLMClient, max_tokens: int = 800) -> str:
    """
    Summarize the conversation using the given LLM client.
    """
    try:
        app_title = get_settings().app.title
        full_text = "\n\n".join([f"{m['role']}:\n{m['content']}" for m in messages])

        system_prompt = (
            f"You are an assistant for {app_title}. Summarize the following chat conversation "
            "into a well-formatted summary with clear bullet points. "
            "Please format your response as follows:\n"
            "- Use bullet points (starting with *) for key insights\n"
            "- Put each bullet point on a separate line\n"
            "- Include section headings if appropriate (formatted as **Section Name:**)\n"
            "- Focus on insights, questions, and actionable advice\n"
            "- Maximum 10 bullet points\n\n"
            "Example format:\n"
            "**Key Insights:**\n"
            "* First main point about the conversation\n"
            "* Second important insight\n"
            "* Third key takeaway\n\n"
            "**Recommendations:**\n"
            "* First actionable recommendation\n"
            "* Second suggestion"
        )

        context = [{"role": "user", "content": f"Chat Log:\n{full_text}"}]

        summary = await llm.generate(
            system_prompt=system_prompt,
            context=context,
            temperature=0.4,
            max_tokens=max_tokens
        )

        # Post-process the summary to ensure proper formatting
        formatted_summary = _format_summary_text(summary.strip())
        return formatted_summary

    except Exception as e:
        logger.error(f"Error generating summary: {str(e)}")
        return "Summary generation failed. Please try again later."


def _format_summary_text(summary_text: str) -> str:
    """
    Post-process the summary text to ensure proper bullet point formatting.
    """
    # Fix common formatting issues
    
    # Add line breaks before bullet points that don't have them
    summary_text = re.sub(r'(?<!\n)([*•] )', r'\n\1', summary_text)
    
    # Add line breaks before numbered lists that don't have them
    summary_text = re.sub(r'(?<!\n)(\d+\.\s+)', r'\n\1', summary_text)
    
    # Add line breaks after periods followed by capital letters (likely new sentences)
    summary_text = re.sub(r'(?<=[.!?])(?=\s*[*•]\s)', '\n', summary_text)
    
    # Clean up multiple consecutive newlines
    summary_text = re.sub(r'\n{3,}', '\n\n', summary_text)
    
    # Ensure bullet points are properly spaced
    summary_text = re.sub(r'\n([*•] )', r'\n\n\1', summary_text)
    
    # Fix section headings that might be run together
    summary_text = re.sub(r'([.!?])\s*(\*\*[^*]+\*\*)', r'\1\n\n\2', summary_text)
    
    return summary_text.strip()


def parse_summary_to_blocks(summary_text: str) -> List[Dict]:
    """
    Parse summary text into structured blocks for better formatting.
    """
    # First, ensure proper formatting
    summary_text = _format_summary_text(summary_text)
    
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

        # Match section headings (e.g. **Title:** or **Title**)
        heading_match = re.match(r'^\*\*(.+?)\*\*:?$', line)
        if heading_match:
            flush_current_block()
            current_block = {"type": "heading", "text": heading_match.group(1).strip()}
            flush_current_block()
            current_block = None
            continue

        # Match bullet list items (*, •, or -)
        bullet_match = re.match(r'^[*•-]\s+(.+)', line)
        if bullet_match:
            if current_block is None or current_block["type"] != "list" or current_block.get("style") != "bullet":
                flush_current_block()
                current_block = {"type": "list", "style": "bullet", "items": []}
            current_block["items"].append(bullet_match.group(1).strip())
            continue

        # Match numbered list items
        number_match = re.match(r'^\d+\.\s+(.+)', line)
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

    # Debug output to help troubleshoot
    logger.info(f"[DEBUG] Parsed {len(blocks)} blocks from summary")
    for i, block in enumerate(blocks):
        if block["type"] == "list":
            logger.info(f"Block {i}: {block['type']} ({block['style']}) with {len(block['items'])} items")
        else:
            logger.info(f"Block {i}: {block['type']}")
    
    return blocks


def format_summary_for_text_export(summary_text: str) -> str:
    """
    Format summary text specifically for TXT and DOCX exports with proper line breaks.
    """
    formatted_text = _format_summary_text(summary_text)
    
    # Add extra spacing for better readability in text formats
    lines = formatted_text.split('\n')
    formatted_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Add extra space before section headings
        if re.match(r'^\*\*(.+?)\*\*:?$', line):
            if formatted_lines:  # Don't add space before first heading
                formatted_lines.append('')
            formatted_lines.append(line)
            formatted_lines.append('')  # Space after heading
        # Add space before bullet points (but group them together)
        elif re.match(r'^[*•-]\s+', line):
            # Check if previous line was also a bullet point
            if formatted_lines and not re.match(r'^[*•-]\s+', formatted_lines[-1]):
                formatted_lines.append('')  # Space before first bullet in group
            formatted_lines.append(line)
        else:
            # Regular paragraph
            if formatted_lines:
                formatted_lines.append('')
            formatted_lines.append(line)
    
    return '\n'.join(formatted_lines)