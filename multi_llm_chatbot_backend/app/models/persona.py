from app.llm.llm_client import LLMClient
from typing import AsyncIterator, Dict, List
import re

SENTINEL = "</END>"

# Shared compact formatting contract applied to all personas.
# Headings are a product format; content inside them must still be role-specific.
COMPACT_MARKDOWN_V1 = (
    "You must format your answer using GitHub-Flavored Markdown and exactly these three sections in this order:\n"
    "### Thought\n"
    "- 1–2 complete sentences of YOUR specialist reasoning only. Do not put actions here.\n"
    "- Finish each sentence; never cut a sentence short mid-phrase.\n"
    "- Do not open by restating the user question as 'To [verb] …' or 'Here's a step-by-step approach…'.\n"
    "\n"
    "### What to do\n"
    "- Exactly 3 bullet points, one concrete action each. Use '-' as the bullet. Do not use unicode bullets.\n"
    "- Write each bullet as a complete imperative sentence (plain text, no bold title prefixes).\n"
    "- Bullets must be artifacts of YOUR specialty, not leftover reasoning and not a shared curriculum "
    "(not Purpose/Scope/Basics, not Research/Plan/Write) unless that is truly your job.\n"
    "- If you would use an ordered list, keep text on the same line as the number (e.g., '1. Do X').\n"
    "\n"
    "### Next step\n"
    "- One imperative sentence only — the next action YOUR role would assign.\n"
    "- Must be distinct from every What-to-do bullet (do not copy or lightly rephrase the first bullet).\n"
    "- Prefer: the single most important action to start with right now, optionally with when/how.\n"
    "\n"
    "Rules: Use '###' for headings (never bold-as-heading). Insert a blank line between blocks. "
    "Do not include tables or code blocks unless explicitly requested. "
    "Do not include preambles or conclusions outside the three sections. "
    "Never truncate with ellipsis (... or …); always finish the sentence or bullet. "
    "Stay short and sharp; do not pad to match other advisors. "
    f"Finish your response with the sentinel token {SENTINEL}."
)

# Applied at generation time so parallel advisors do not echo one outline.
ANTI_ECHO_CONTRACT = (
    "You are one specialist on a panel. Other advisors answer the SAME question in parallel.\n"
    "Answer from YOUR role only. Do not write a generic training syllabus, course outline, "
    "or purpose/scope/steps plan unless that is genuinely your specialty.\n"
    "Do not copy a shared opener. Start Thought with what YOU notice from your domain.\n"
    "If the ask is fiction, a novel, worldbuilding, or a creative project, still apply YOUR "
    "professional lens (coaching vs threat model vs architecture vs IR vs compliance vs career "
    "mechanics) — do not all invent the same training program.\n"
    "What-to-do and Next step must be the kinds of actions YOUR specialty produces."
)

# Recency-winning fill hints (appended last). Keys match persona YAML ids.
PERSONA_SLOT_HINTS = {
    "jerry_huaute": (
        "Fill slots as intake lead: Thought names their real need in a mentoring voice; "
        "What-to-do is clarify the ask + one lived-experience insight + encouragement with a "
        "constraint; Next step is one grounding or clarifying action. Never dump a training curriculum."
    ),
    "threat_modeler": (
        "Fill slots as threat modeler: Thought names assets, adversary, and an assumption; "
        "What-to-do is STRIDE, abuse cases, attack surfaces, or a tabletop inject; "
        "Next step is one threat-model artifact. Never a training-program outline."
    ),
    "security_architect": (
        "Fill slots as architect: Thought names trust boundaries, controls, or layers of the "
        "system (including an in-world fictional system); What-to-do is design moves "
        "(zones, identity, logging, sequencing); Next step is one design artifact. "
        "Never Purpose/Scope/Basics or a writing/training syllabus."
    ),
    "incident_responder": (
        "Fill slots as IR: Thought is severity and containment posture; What-to-do is ordered "
        "first-hour actions; Next step is the single stop-the-bleeding move. Not a training syllabus."
    ),
    "security_mentor": (
        "Fill slots as career mentor: certs, labs, interviews, or weekly effort for this person "
        "or character; Next step is one study or portfolio action. Not a corporate awareness syllabus "
        "unless they asked for that job."
    ),
    "compliance_officer": (
        "Fill slots as compliance: framework mapping, evidence, or questionnaires; Next step is "
        "one control or evidence artifact. Not a training syllabus."
    ),
    "smb_advisor": (
        "Fill slots as SMB advisor: ranked cheap controls in priority order; Next step is the "
        "highest-ROI action this week. Not a training syllabus."
    ),
    "ai_security_strategist": (
        "Fill slots as AI strategist: Secure / Defend / Thwart in business language; Next step is "
        "one decision a sponsor can make. Not a training syllabus."
    ),
}


def _as_text(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def panel_lens_reminder(name: str = "", role: str = "") -> str:
    """Per-turn overlay so parallel advisors keep distinct voices."""
    name = _as_text(name)
    role = _as_text(role)
    if not name:
        return ""
    role_bit = role or "your specialty"
    return (
        f"PANEL ROLE: You are {name} ({role_bit}). Other advisors are answering "
        "this same question in parallel. Do not write the same outline they would. "
        "Lead with your specialty. If the ask is fiction or worldbuilding, still "
        "apply your professional lens — do not all produce a training syllabus."
    )


def compose_response_system_prompt(
    system_prompt: str,
    response_length: str = "medium",
    *,
    name: str = "",
    role: str = "",
    persona_id: str = "",
) -> str:
    """Assemble the generation-time system prompt.

    Shared format instructions come first; identity and slot hints are last so
    recency favors the persona lens over the common template.
    """
    structure_hint = STRUCTURE_HINTS.get(response_length, STRUCTURE_HINTS["medium"])
    name = _as_text(name)
    role = _as_text(role)
    persona_id = _as_text(persona_id)
    identity_lines = []
    if name or role:
        who = name or "this advisor"
        identity_lines.append(
            f"You are answering as {who}" + (f" ({role})" if role else "") + "."
        )
    slot_hint = PERSONA_SLOT_HINTS.get(persona_id, "")
    if slot_hint:
        identity_lines.append(slot_hint)
    identity_block = "\n".join(identity_lines)
    parts = [
        (system_prompt or "").strip(),
        COMPACT_MARKDOWN_V1,
        structure_hint,
        ANTI_ECHO_CONTRACT,
    ]
    if identity_block:
        parts.append(identity_block)
    return "\n\n".join(p for p in parts if p).strip()

# Soft structure guidance per response_length
STRUCTURE_HINTS = {
    "short": "Keep it concise: Thought ≤ 2 short complete sentences; bullets complete and ≤ ~16 words; next step one short distinct sentence. No ellipsis.",
    "medium": "Be clear: Thought 1–2 complete sentences; bullets complete and ≤ ~22 words; next step one distinct sentence. No ellipsis.",
    "long": "Stay compact but complete: Thought up to 2 full sentences; bullets complete and ≤ ~30 words; next step one distinct sentence. No ellipsis.",
}

# Enough headroom so compact sections finish sentences (models were cutting mid-bullet at 600).
MAX_TOKENS_MAP = {
    "short": 500,
    "medium": 850,
    "long": 1200,
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


_DANGLING_TAIL = re.compile(
    r"(?i)\b(a|an|the|and|or|of|to|for|with|from|into|onto|by|as|at|in|on|is|are|be|than|that|which|your|my|our|,|;|:|-|—)$"
)


def _strip_md_noise(s: str) -> str:
    """Normalize for compare / cleanup: drop bold markers and excess spaces."""
    t = re.sub(r"\*+", "", (s or "").strip())
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _soft_limit_words(s: str, limit: int) -> str:
    """Prefer complete text. Never append ellipsis; drop whole trailing clauses instead."""
    text = _strip_md_noise(s)
    if not text:
        return ""
    words = text.split()
    if len(words) <= limit:
        return text
    # Prefer keeping a complete first sentence that fits (or the whole first sentence if longer)
    parts = [p.strip() for p in re.split(r"(?<=[\.!?])\s+", text) if p.strip()]
    if parts:
        kept: List[str] = []
        count = 0
        for p in parts:
            w = len(p.split())
            if kept and count + w > limit:
                break
            if not kept and w > limit:
                return p  # never mid-sentence cut; keep full first sentence
            kept.append(p)
            count += w
            if count >= limit:
                break
        if kept:
            return " ".join(kept)
    # No sentence breaks — keep full text rather than clipping with "…"
    return text


def _first_n_sentences(text: str, n: int, max_words: int) -> str:
    cleaned = _strip_md_noise(text)
    parts = [p.strip() for p in re.split(r"(?<=[\.!?])\s+", cleaned) if p.strip()]
    if not parts:
        return _soft_limit_words(cleaned, max_words)
    chosen: List[str] = []
    word_count = 0
    for p in parts[: max(1, n)]:
        w = len(p.split())
        if chosen and word_count + w > max_words:
            break
        if not chosen and w > max_words:
            return p  # complete over-budget sentence beats an ellipsis clip
        chosen.append(p)
        word_count += w
    return " ".join(chosen) if chosen else parts[0]


def _looks_incomplete(s: str) -> bool:
    t = (s or "").strip()
    if not t:
        return True
    if _DANGLING_TAIL.search(t.rstrip(".!?")):
        return True
    if t[-1] in ",;:":
        return True
    return False


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
        s_clean = _strip_md_noise(s.strip("-•* ").strip())
        if not s_clean:
            continue
        if not _is_action_like(s_clean) and len(items) > 0:
            continue
        items.append(_soft_limit_words(s_clean, per_bullet_words))
        if len(items) >= max_items:
            break
    if len(items) < max_items:
        for s in sentences:
            s_clean = _strip_md_noise(s.strip("-•* ").strip())
            if not s_clean:
                continue
            cand = _soft_limit_words(s_clean, per_bullet_words)
            if cand not in items:
                items.append(cand)
            if len(items) >= max_items:
                break
    return items[:max_items]


def _norm_compare(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", _strip_md_noise(s).lower())


def _is_near_duplicate(a: str, b: str) -> bool:
    an, bn = _norm_compare(a), _norm_compare(b)
    if not an or not bn:
        return False
    if an == bn:
        return True
    # Shared significant prefix (handles "Disconnect X" vs "Immediately disconnect X")
    n = max(10, min(len(an), len(bn)) // 2)
    if an.startswith(bn[:n]) or bn.startswith(an[:n]):
        return True
    # High token overlap
    aw, bw = set(re.findall(r"[a-z0-9]{3,}", _strip_md_noise(a).lower())), set(
        re.findall(r"[a-z0-9]{3,}", _strip_md_noise(b).lower())
    )
    if not aw or not bw:
        return False
    overlap = len(aw & bw) / max(1, min(len(aw), len(bw)))
    return overlap >= 0.72


def _distinct_next_step(candidate: str, bullets: List[str], fallback: str, max_words: int) -> str:
    """Ensure Next step is not a duplicate of a What-to-do bullet."""
    cand = _first_n_sentences(candidate or "", 1, max_words)
    clean_bullets = [_strip_md_noise(b) for b in bullets if b]

    def _ok(text: str) -> bool:
        if not text or _looks_incomplete(text):
            return False
        return not any(_is_near_duplicate(text, b) for b in clean_bullets)

    if _ok(cand):
        return cand
    # Prefer a later bullet framed as priority timing — still must not equal that bullet text alone
    for b in clean_bullets[1:]:
        phrased = _soft_limit_words(f"Start now by doing this next: {b}", max_words)
        # Reject if it collapses to the same action fingerprint as bullet 1
        if clean_bullets and _is_near_duplicate(phrased, clean_bullets[0]):
            continue
        if phrased and not _looks_incomplete(phrased):
            # Distinct enough from bullet text alone (has priority framing)
            if _norm_compare(phrased) != _norm_compare(b):
                return phrased
    # Never echo bullet 1 verbatim; give a priority CTA that points at the list
    if clean_bullets:
        return "Begin with the first What-to-do action, then continue down the list."
    return _soft_limit_words(fallback or "Proceed with the most actionable item.", max_words)


def _ensure_compact_shape(text: str, response_length: str) -> str:
    # Normalize and coerce into the 3-section compact shape.
    # Soft budgets: keep full sentences/bullets (no ellipsis clipping).
    per_bullet_words = 18 if response_length == "short" else 28 if response_length == "medium" else 36
    sentence_words = 40 if response_length == "short" else 60 if response_length == "medium" else 80

    t = _cut_at_sentinel(_rstrip_lines(_normalize_eols(text)))
    lines = t.split("\n")
    lines = _convert_bold_headers_to_atx(lines)
    lines = _convert_unicode_bullets(lines)
    lines = _merge_orphan_numbered_items(lines)
    t = _collapse_blank_runs("\n".join(lines))
    lines = t.split("\n")

    sections = _extract_heading_blocks(lines)
    thought_text, thought_actions = _split_thought_and_actions(sections["Thought"])
    bullets = [_strip_md_noise(b) for b in _extract_bullets(sections["What to do"])]
    bullets = [_strip_md_noise(b) for b in (thought_actions + bullets)]
    next_body = " ".join([_strip_md_noise(l) for l in sections["Next step"] if l.strip()])

    have_thought = bool(thought_text.strip())
    have_actions = len(bullets) > 0
    have_next = bool(next_body.strip())
    have_all = have_thought and have_actions and have_next

    def _finalize_bullets(src: List[str]) -> List[str]:
        cleaned = []
        for b in src:
            b2 = _soft_limit_words(b, per_bullet_words)
            # Drop mid-cut model fragments (e.g. ending in "of" / "to") instead of ellipsis
            if b2 and not _looks_incomplete(b2):
                cleaned.append(b2)
        return cleaned

    if not have_all:
        # Build compact output from scratch using best-effort extraction
        raw_plain = " ".join([l for l in lines if not l.strip().startswith("#")]).strip()
        if not thought_text:
            thought_text = _first_n_sentences(raw_plain, 2, sentence_words) if raw_plain else ""
        if len(bullets) < 3:
            extra = [_strip_md_noise(b) for b in _extract_bullets(lines)]
            for b in extra:
                if b not in bullets:
                    bullets.append(b)
            if len(bullets) < 3:
                filler = _synthesize_bullets_from_text(raw_plain, 3 - len(bullets), per_bullet_words)
                for b in filler:
                    if b not in bullets:
                        bullets.append(b)
        bullets = _finalize_bullets(bullets)[:3]
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

    bullets = _finalize_bullets(bullets)
    # Prefer true action bullets; only pad from What-to-do prose if short
    if len(bullets) < 3:
        wtd_plain = " ".join([l.strip() for l in sections["What to do"] if l.strip() and not l.strip().startswith(("-", "*", "#"))])
        filler = _synthesize_bullets_from_text(wtd_plain, 3 - len(bullets), per_bullet_words) if wtd_plain else []
        for b in filler:
            if b not in bullets:
                bullets.append(b)
        bullets = _finalize_bullets(bullets)
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
        *[f"- {b}" for b in bullets[:3]],
        "",
        "### Next step",
        next_final,
    ]

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
        temp_scaled = round(self.temperature / 10, 2)

        full_prompt = compose_response_system_prompt(
            self.system_prompt,
            response_length,
            name=self.name,
            role=self.role,
            persona_id=self.id,
        )

        raw_text = await self.llm.generate(
            system_prompt=full_prompt,
            context=context,
            temperature=temp_scaled,
            max_tokens=max_tokens,
        )

        compact = _finalize_compact(raw_text or "", response_length)
        return compact

    async def respond_stream(
        self, context: List[Dict], response_length: str = "medium"
    ) -> AsyncIterator[str]:
        """Yield token/text chunks, then stop. Caller applies compact shape on the join."""
        max_tokens = MAX_TOKENS_MAP.get(response_length, 600)
        temp_scaled = round(self.temperature / 10, 2)

        full_prompt = compose_response_system_prompt(
            self.system_prompt,
            response_length,
            name=self.name,
            role=self.role,
            persona_id=self.id,
        )

        async for chunk in self.llm.generate_stream(
            system_prompt=full_prompt,
            context=context,
            temperature=temp_scaled,
            max_tokens=max_tokens,
        ):
            if chunk:
                yield chunk


def _finalize_compact(raw_text: str, response_length: str) -> str:
    compact = _ensure_compact_shape(raw_text or "", response_length)
    if len(compact) > 4000:
        compact = _ensure_compact_shape(compact, "short")
    return compact
