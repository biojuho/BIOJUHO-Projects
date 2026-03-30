"""Basic tests for Instagram automation models."""

from models import DMTriggerRule, InstagramPost, PostInsights, PostStatus, PostType


def test_instagram_post_full_caption():
    post = InstagramPost(
        caption="Test caption",
        hashtags="#test #automation",
    )
    assert post.full_caption == "Test caption\n\n#test #automation"


def test_instagram_post_full_caption_no_hashtags():
    post = InstagramPost(caption="Just caption")
    assert post.full_caption == "Just caption"


def test_post_insights_engagement_rate():
    insights = PostInsights(
        media_id="123",
        reach=1000,
        engagement=50,
    )
    assert insights.engagement_rate == 5.0


def test_post_insights_zero_reach():
    insights = PostInsights(media_id="123", reach=0, engagement=10)
    assert insights.engagement_rate == 0.0


def test_post_defaults():
    post = InstagramPost(caption="hi")
    assert post.post_type == PostType.IMAGE
    assert post.status == PostStatus.DRAFT
    assert post.media_id is None


def test_dm_trigger_rule():
    rule = DMTriggerRule(
        keyword="price",
        response_template="Here is our price list...",
    )
    assert rule.enabled is True
    assert rule.is_llm_response is False
