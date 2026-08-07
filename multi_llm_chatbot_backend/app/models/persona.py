from app.llm.llm_client import LLMClient
from typing import List, Dict
import re

SENTINEL = "</END>"

# Shared compact formatting contract applied to all personas.
COMPACT_MARKDOWN_V1 = (
    "You must format your answer using GitHub-Flavored Markdown and exactly these three sections in this order:\n"
    "### Thought\n"
    "- 1–2 complete sentences of reasoning/context only. Do not put actions here.\n"
    "\n"
    "### What to do\n"
    "- Exactly 3 bullet points, one concrete action each. Use '-' as the bullet. Do not use unicode bullets.\n"
    "- Bullets must be actionable steps, not leftover reasoning from Thought.\n"
    "- If you would use an ordered list, keep text on the same line as the number (e.g., '1. Do X').\n"
    "\n"
    "### Next step\n"
    "- One imperative sentence only.\n"
    "- Must be distinct from every What-to-do bullet (do not copy or lightly rephrase the first bullet).\n"
    "- Prefer: the single most important action to start with right now, optionally with when/how.\n"
    "\n"
    "Rules: Use '###' for headings (never bold-as-heading). Insert a blank line between blocks. "
    "Do not include tables or code blocks unless explicitly requested. "
    "Do not include preambles or conclusions outside the three sections. "
    f"Finish your response with the sentinel token {SENTINEL}."
)

# Soft structure guidance per response_length
STRUCTURE_HINTS = {
    "short": "Keep it concise: Thought ≤ 2 short sentences; bullets ≤ 12 words; next step one short distinct sentence.",
    "medium": "Be clear: Thought 1–2 sentences; bullets ≤ 18 words; next step one distinct sentence.",
    "long": "Stay compact but complete: Thought up to 2 sentences; bullets ≤ 24 words; next step one distinct sentence.",
}

# Conservative token ceilings (kept close to prior behavior to avoid breaking changes)
MAX_TOKENS_MAP = {
    "short": 350,
    "medium": 600,
    "long": 900,
}

_HEADING_ALIASES = {
    "thought": "Thought",
    "tldr": "Thought",
    "tl;dr": "Thought",
    "reasoning": "Thought",
    "context": "Thought",
    "what to do": "What to do",
    "what-to-do": "What to do",
    "actions": "What to do",
    "action items": "What to do",
    "recommendations": "What to do",
    "next step": "Next step",
    "next steps": "Next step",
    "immediate next step": "Next step",
}


def _cut_at_sentinel(text: str) -> str:
    if not text:
        return ""
    idx = text.find(SENTINEL)
    return text[:idx] if idx != -1 else text


def _normalize_eols(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _rstrip_lines(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.split("\n"))


def _convert_bold_headers_to_atx(lines: List[str]) -> List[str]:
    out = []
    for l in lines:
        # Full-line **Heading** or **Heading**: becomes '### Heading'
        m = re.match(r"^\s*\*\*(.+?)\*\*\s*:?\s*$", l)
        if m:
            out.append(f"### {m.group(1).strip()}")
        else:
            out.append(l)
    return out


def _convert_unicode_bullets(lines: List[str]) -> List[str]:
    out = []
    for l in lines:
        out.append(re.sub(r"^\s*[•●▪◦]\s+", "- ", l))
    return out


def _merge_orphan_numbered_items(lines: List[str]) -> List[str]:
    out = []
    i = 0
    while i < len(lines):
        cur = lines[i]
        m = re.match(r"^\s*(\d+)\.\s*$", cur)
        if m:
            # find next non-empty line and merge
            j = i + 1
            while j < len(lines) and lines[j].strip() == "":
                j += 1
            if j < len(lines):
                out.append(f"{m.group(1)}. {lines[j].strip()}")
                i = j + 1
                continue
        out.append(cur)
        i += 1
    return out


def _collapse_blank_runs(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _truncate_words(s: str, limit: int) -> str:
    words = s.strip().split()
    if len(words) <= limit:
        return s.strip()
    return " ".join(words[:limit]) + "…"


def _first_n_sentences(text: str, n: int, max_words: int) -> str:
    parts = [p.strip() for p in re.split(r"(?<=[\.!?])\s+", text.strip()) if p.strip()]
    if not parts:
        return _truncate_words(text, max_words)
    joined = " ".join(parts[: max(1, n)])
    return _truncate_words(joined, max_words)


def _normalize_heading_label(raw: str) -> str | None:
    label = re.sub(r"^#+\s*", "", (raw or "").strip()).strip().rstrip(":").lower()
    label = re.sub(r"\s+", " ", label)
    return _HEADING_ALIASES.get(label)


def _match_section_heading(line: str) -> str | None:
    s = line.strip()
    if not s:
        return None
    # ### Heading / ## Heading
    m = re.match(r"^#{1,6}\s+(.+?)\s*$", s)
    if m:
        return _normalize_heading_label(m.group(1))
    # **Heading** or **Heading:**
    m = re.match(r"^\*\*(.+?)\*\*\s*:?\s*$", s)
    if m:
        return _normalize_heading_label(m.group(1))
    # Heading: alone on a line
    m = re.match(r"^(Thought|What to do|Next step|Actions|Next steps)\s*:?\s*$", s, re.I)
    if m:
        return _normalize_heading_label(m.group(1))
    return None


def _extract_heading_blocks(lines: List[str]) -> Dict[str, List[str]]:
    sections = {"Thought": [], "What to do": [], "Next step": []}
    current = None
    for l in lines:
        headed = _match_section_heading(l)
        if headed:
            current = headed
            continue
        if current:
            sections[current].append(l)
    return sections


def _extract_bullets(lines: List[str]) -> List[str]:
    bullets = []
    for l in lines:
        s = l.strip()
        if s.startswith("- "):
            bullets.append(s[2:].strip())
        elif s.startswith("* "):
            bullets.append(s[2:].strip())
        else:
            m = re.match(r"^(\d+)\.\s+(.*)$", s)
            if m and m.group(2).strip():
                bullets.append(m.group(2).strip())
    return bullets


def _is_action_like(text: str) -> bool:
    s = (text or "").strip()
    if not s:
        return False
    if re.match(r"^(-|\*|\d+\.)\s+", s):
        return True
    return bool(
        re.match(
            r"^(do|enable|disable|install|update|set|check|verify|review|turn|change|"
            r"open|close|reset|remove|add|configure|run|use|start|stop|contact|"
            r"document|backup|export|import|scan|patch)\b",
            s,
            re.I,
        )
    )


def _split_thought_and_actions(thought_lines: List[str]) -> tuple[str, List[str]]:
    """Keep reasoning prose in Thought; move bullet/action lines to What to do."""
    prose: List[str] = []
    actions: List[str] = []
    for l in thought_lines:
        s = l.strip()
        if not s:
            continue
        if _extract_bullets([l]):
            actions.extend(_extract_bullets([l]))
        elif _is_action_like(s) and len(s.split()) <= 24:
            actions.append(s)
        else:
            prose.append(s)
    return " ".join(prose).strip(), actions


def _synthesize_bullets_from_text(text: str, max_items: int, per_bullet_words: int) -> List[str]:
    # Prefer imperative-looking sentences when inventing actions
    sentences = re.split(r"(?<=[\.!?])\s+", text.strip())
    items = []
    for s in sentences:
        s_clean = s.strip("-•* ").strip()
        if not s_clean:
            continue
        if not _is_action_like(s_clean) and len(items) > 0:
            continue
        items.append(_truncate_words(s_clean, per_bullet_words))
        if len(items) >= max_items:
            break
    if len(items) < max_items:
        for s in sentences:
            s_clean = s.strip("-•* ").strip()
            if not s_clean:
                continue
            cand = _truncate_words(s_clean, per_bullet_words)
            if cand not in items:
                items.append(cand)
            if len(items) >= max_items:
                break
    return items[:max_items]


def _norm_compare(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def _distinct_next_step(candidate: str, bullets: List[str], fallback: str, max_words: int) -> str:
    """Ensure Next step is not a duplicate of a What-to-do bullet."""
    cand = _truncate_words(_first_n_sentences(candidate or "", 1, max_words), max_words)
    norms = {_norm_compare(b) for b in bullets if b}
    if cand and _norm_compare(cand) not in norms:
        # Also reject near-duplicates (prefix overlap)
        cn = _norm_compare(cand)
        if not any(cn and (cn.startswith(b[: max(8, len(b) // 2)]) or b.startswith(cn[: max(8, len(cn) // 2)])) for b in norms if b):
            return cand
    # Prefer a later bullet phrased as "Start with …" without copying verbatim
    for b in bullets[1:]:
        phrased = _truncate_words(f"Start now: {b}", max_words)
        if _norm_compare(phrased) not in norms:
            return phrased
    if bullets:
        first = bullets[0]
        # Rephrase so it is clearly the priority call-to-action, not a bullet clone
        phrased = _truncate_words(f"Begin with this first: {first}", max_words)
        return phrased
    return _truncate_words(fallback or "Proceed with the most actionable item.", max_words)


def _ensure_compact_shape(text: str, response_length: str) -> str:
    # Normalize and coerce into the 3-section compact shape.
    per_bullet_words = 12 if response_length == "short" else 18 if response_length == "medium" else 24
    sentence_words = 28 if response_length == "short" else 40 if response_length == "medium" else 52

    t = _cut_at_sentinel(_rstrip_lines(_normalize_eols(text)))
    lines = t.split("\n")
    lines = _convert_bold_headers_to_atx(lines)
    lines = _convert_unicode_bullets(lines)
    lines = _merge_orphan_numbered_items(lines)
    t = _collapse_blank_runs("\n".join(lines))
    lines = t.split("\n")

    sections = _extract_heading_blocks(lines)
    thought_text, thought_actions = _split_thought_and_actions(sections["Thought"])
    bullets = _extract_bullets(sections["What to do"])
    bullets = thought_actions + bullets
    next_body = " ".join([l.strip() for l in sections["Next step"] if l.strip()])

    have_thought = bool(thought_text.strip())
    have_actions = len(bullets) > 0
    have_next = bool(next_body.strip())
    have_all = have_thought and have_actions and have_next

    if not have_all:
        # Build compact output from scratch using best-effort extraction
        raw_plain = " ".join([l for l in lines if not l.strip().startswith("#")]).strip()
        if not thought_text:
            thought_text = _first_n_sentences(raw_plain, 2, sentence_words) if raw_plain else ""
        if len(bullets) < 3:
            extra = _extract_bullets(lines)
            for b in extra:
                if b not in bullets:
                    bullets.append(b)
            if len(bullets) < 3:
                filler = _synthesize_bullets_from_text(raw_plain, 3 - len(bullets), per_bullet_words)
                for b in filler:
                    if b not in bullets:
                        bullets.append(b)
        bullets = [_truncate_words(b, per_bullet_words) for b in bullets[:3]]
        while len(bullets) < 3:
            bullets.append(
                [
                    "Identify the key task.",
                    "Decide the immediate next action.",
                    "Verify prerequisites and proceed.",
                ][len(bullets)]
            )
        next_final = _distinct_next_step(next_body, bullets, thought_text, sentence_words)
        tldr_final = _first_n_sentences(thought_text, 2, sentence_words) if thought_text else "Concise summary unavailable."

        parts = [
            "### Thought",
            tldr_final,
            "",
            "### What to do",
        ]
        for b in bullets[:3]:
            parts.append(f"- {b}")
        parts.extend(["", "### Next step", next_final])
        return "\n".join(parts).strip()

    # Sections exist — normalize without dumping Thought remainder into actions
    tldr_final = _first_n_sentences(thought_text, 2, sentence_words) if thought_text else "Concise summary unavailable."

    bullets = [_truncate_words(b, per_bullet_words) for b in bullets if b]
    # Prefer true action bullets; only pad from What-to-do prose if short
    if len(bullets) < 3:
        wtd_plain = " ".join([l.strip() for l in sections["What to do"] if l.strip() and not l.strip().startswith(("-", "*", "#"))])
        filler = _synthesize_bullets_from_text(wtd_plain, 3 - len(bullets), per_bullet_words) if wtd_plain else []
        for b in filler:
            if b not in bullets:
                bullets.append(b)
    while len(bullets) < 3:
        bullets.append(
            [
                "Identify the key task.",
                "Decide the immediate next action.",
                "Verify prerequisites and proceed.",
            ][len(bullets)]
        )
    bullets = bullets[:3]

    next_final = _distinct_next_step(next_body, bullets, tldr_final, sentence_words)

    parts = [
        "### Thought",
        tldr_final,
        "",
        "### What to do",
    ]
    for b in bullets[:3]:
        parts.append(f"- {b}")
    parts.extend(["", "### Next step", next_final])

    return "\n".join(parts).strip()


class Persona:
    def __init__(
        self,
        id: str,
        name: str,
        system_prompt: str,
        llm: LLMClient,
        temperature: int = 5,
        role: str = "",
        summary: str = "",
    ):
        self.id = id
        self.name = name
        self.system_prompt = system_prompt
        self.llm = llm
        self.temperature = temperature
        # Short descriptors used for routing prompts (kept tiny on purpose).
        self.role = role
        self.summary = summary

    async def respond(self, context: List[Dict], response_length: str = "medium") -> str:
        """Generate a compact, well-formed Markdown response suitable for the UI.
        Returns the compact Markdown string (backward compatible with previous callers).
        """
        max_tokens = MAX_TOKENS_MAP.get(response_length, 600)
        structure_hint = STRUCTURE_HINTS.get(response_length, STRUCTURE_HINTS["medium"])
        temp_scaled = round(self.temperature / 10, 2)

        full_prompt = (
            f"{self.system_prompt}\n\n"
            f"{COMPACT_MARKDOWN_V1}\n\n"
            f"{structure_hint}"
        )

        raw_text = await self.llm.generate(
            system_prompt=full_prompt,
            context=context,
            temperature=temp_scaled,
            max_tokens=max_tokens,
        )

        compact = _ensure_compact_shape(raw_text or "", response_length)

        # Final safety: cap extreme length by trimming bullet lines further if necessary
        # (We keep this conservative to avoid changing behavior unnecessarily)
        if len(compact) > 4000:  # very generous; UI should stay well below this
            # Trim bullets to even fewer words
            compact = _ensure_compact_shape(compact, "short")

        return compact
