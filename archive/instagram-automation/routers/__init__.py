"""Instagram Automation API Routers.

Organized by functional domain:
- webhook: Meta webhook verification and event handling
- posts: Post generation, queuing, and publishing
- insights: Analytics and performance metrics
- dm: DM automation and rules
- calendar: Content calendar management
- hashtags: Hashtag optimization
- ab_testing: A/B experiment management
- external: External trigger API
- monitoring: Health checks, dashboard, alerts
"""

from . import (
    ab_testing,
    calendar,
    dm,
    external,
    hashtags,
    insights,
    monitoring,
    posts,
    webhook,
)

__all__ = [
    "webhook",
    "posts",
    "insights",
    "dm",
    "calendar",
    "hashtags",
    "ab_testing",
    "external",
    "monitoring",
]
