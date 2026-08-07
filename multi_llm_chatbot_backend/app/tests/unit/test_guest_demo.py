"""Unit tests for guest demo persona resolution (no DB)."""

from app.core.guest_demo import resolve_persona, derive_guest_label


def test_resolve_personal_choice():
    assert resolve_persona("personal") == "personal"
    assert resolve_persona("individual") == "personal"


def test_resolve_business_choice():
    assert resolve_persona("business") == "business"
    assert resolve_persona("organization") == "business"


def test_resolve_other_with_free_text():
    assert resolve_persona("other", "I want to study for Security+") == "other"


def test_infer_business_from_free_text():
    assert resolve_persona("other", "Need help with SOC 2 for our company") == "business"


def test_derive_guest_label_personal_business():
    assert derive_guest_label("personal") == "Personal"
    assert derive_guest_label("business") == "Business"


def test_derive_guest_label_from_free_text():
    assert derive_guest_label("other", "Preparing for a Security+ exam") == "Preparing"
    assert derive_guest_label("other", "ransomware readiness review") == "Ransomware"
    assert derive_guest_label("other", "") == "Custom"
