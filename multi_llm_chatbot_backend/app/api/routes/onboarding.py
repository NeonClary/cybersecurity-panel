# NEON AI (TM) SOFTWARE, Software Development Kit & Application Framework
# All Rights Reserved 2008-2025
# Licensed under the BSD 3-Clause License
# https://opensource.org/licenses/BSD-3-Clause
#
# Copyright (c) 2008-2025, Neongecko.com Inc.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
# 3. Neither the name of the copyright holder nor the names of its contributors
#    may be used to endorse or promote products derived from this software
#    without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.routes.user_profile import _is_field_filled, enrich_profile_from_user
from app.core.auth import get_current_active_user
from app.core.bootstrap import create_llm_client
from app.core.database import get_database
from app.core.onboarding_agent import OnboardingAgent, PROFILE_FIELDS
from app.models.user import User

LOG = logging.getLogger(__name__)

router = APIRouter()

ONBOARDING_COLLECTION = "onboarding_conversations"


class OnboardingMessage(BaseModel):
    user_input: str


def _progress(profile: Dict[str, Any]) -> int:
    filled = sum(1 for k, *_ in PROFILE_FIELDS if _is_field_filled(profile.get(k)))
    return int(filled / len(PROFILE_FIELDS) * 100)


def _next_missing_question(profile: Dict[str, Any]) -> Optional[str]:
    """Return the human-friendly question for the first unfilled field."""
    for key, question, _desc in PROFILE_FIELDS:
        if not _is_field_filled(profile.get(key)):
            return question
    return None


@router.get("/onboarding/start")
async def onboarding_start(
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    """Return conversation history (if any) and current progress.

    If the user has an in-progress conversation it is returned so the
    frontend can restore the chat.  Otherwise a fresh contextual welcome
    message is generated based on which fields are still missing.
    """
    db = get_database()
    doc = await db.user_profiles.find_one({"user_id": current_user.id})
    profile = enrich_profile_from_user(doc, current_user)
    progress = _progress(profile)

    if progress >= 100:
        await db[ONBOARDING_COLLECTION].delete_many({"user_id": current_user.id})
        return {
            "messages": [{"role": "agent",
                          "text": "Your profile is already complete! Feel free to update anything by chatting here."}],
            "progress": 100,
            "complete": True,
        }

    conv = await db[ONBOARDING_COLLECTION].find_one({"user_id": current_user.id})

    if conv and conv.get("messages"):
        return {
            "messages": conv["messages"],
            "progress": progress,
            "complete": False,
        }

    next_q = _next_missing_question(profile)
    if progress == 0:
        greeting = (
            f"Hey {current_user.firstName}! I'd like to learn a bit about your security background so "
            "your advisors can tailor depth and examples. "
            f"Let's start — {next_q.lower() if next_q else 'tell me about your role and goals!'}"
        )
    else:
        greeting = (
            f"Welcome back, {current_user.firstName}! You're {progress}% done. "
            f"Let's pick up where we left off — {next_q.lower() if next_q else 'what else can you tell me?'}"
        )

    messages = [{"role": "agent", "text": greeting}]
    await db[ONBOARDING_COLLECTION].update_one(
        {"user_id": current_user.id},
        {"$set": {"messages": messages, "updated_at": datetime.utcnow()},
         "$setOnInsert": {"user_id": current_user.id}},
        upsert=True,
    )

    return {"messages": messages, "progress": progress, "complete": False}


@router.post("/onboarding/chat")
async def onboarding_chat(
    msg: OnboardingMessage,
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    db = get_database()
    doc = await db.user_profiles.find_one({"user_id": current_user.id})
    profile = enrich_profile_from_user(doc, current_user)

    agent = OnboardingAgent(create_llm_client())
    result = await agent.chat(msg.user_input, current_user.id, profile)

    user_msg = {"role": "user", "text": msg.user_input}
    agent_msg = {"role": "agent", "text": result["reply"]}

    await db[ONBOARDING_COLLECTION].update_one(
        {"user_id": current_user.id},
        {"$push": {"messages": {"$each": [user_msg, agent_msg]}},
         "$set": {"updated_at": datetime.utcnow()},
         "$setOnInsert": {"user_id": current_user.id}},
        upsert=True,
    )

    if result.get("complete"):
        await db[ONBOARDING_COLLECTION].delete_many({"user_id": current_user.id})

    return result
