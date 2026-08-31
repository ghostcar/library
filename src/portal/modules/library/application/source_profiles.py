"""Product-facing source profiles for guided catalog onboarding."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GuidedSourceProfile:
    id: str
    title: str
    mode: str
    enabled: bool
    reason: str = ""
    url_hint: str = "https://example.com/author"


AUTHOR_SOURCE_PROFILES = (
    GuidedSourceProfile(
        id="author_today",
        title="Author.Today — автоматическое наблюдение",
        mode="watch",
        enabled=True,
        url_hint="https://author.today/u/имя",
    ),
    GuidedSourceProfile(
        id="website_link",
        title="Другой сайт — сохранить ссылку",
        mode="link",
        enabled=True,
    ),
    GuidedSourceProfile(
        id="litnet",
        title="Litnet",
        mode="disabled",
        enabled=False,
        reason=(
            "автоматический сбор не включён; "  # noqa: RUF001
            "страницу можно сохранить как обычную ссылку"
        ),
        url_hint="https://litnet.com/ru/имя",
    ),
)


def get_author_source_profile(profile_id: str) -> GuidedSourceProfile | None:
    return next((profile for profile in AUTHOR_SOURCE_PROFILES if profile.id == profile_id), None)
