"""models.py 테스트: 데이터 구조, 자동 계산, 직렬화."""

import unittest

from models import (
    GeneratedThread,
    GeneratedTweet,
    MultiSourceContext,
    RunResult,
    TrendCluster,
    TweetBatch,
)


class TestGeneratedTweet(unittest.TestCase):
    """트윗 자동 글자수 계산."""

    def test_char_count_auto(self):
        tweet = GeneratedTweet(tweet_type="공감 유도형", content="안녕하세요!")
        self.assertEqual(tweet.char_count, 6)

    def test_empty_content(self):
        tweet = GeneratedTweet(tweet_type="test", content="")
        self.assertEqual(tweet.char_count, 0)

    def test_content_type_default(self):
        tweet = GeneratedTweet(tweet_type="test", content="hi")
        self.assertEqual(tweet.content_type, "short")

    def test_long_content_type(self):
        tweet = GeneratedTweet(tweet_type="딥다이브", content="x" * 2000, content_type="long")
        self.assertEqual(tweet.content_type, "long")
        self.assertEqual(tweet.char_count, 2000)


class TestMultiSourceContext(unittest.TestCase):
    """멀티소스 컨텍스트 결합."""

    def test_combined_all(self):
        ctx = MultiSourceContext(
            twitter_insight="X 반응",
            reddit_insight="Reddit 토론",
            news_insight="뉴스 헤드라인",
        )
        combined = ctx.to_combined_text()
        self.assertIn("[X 실시간 반응]", combined)
        self.assertIn("[Reddit 커뮤니티]", combined)
        self.assertIn("[뉴스 헤드라인]", combined)

    def test_combined_partial(self):
        ctx = MultiSourceContext(twitter_insight="only twitter")
        combined = ctx.to_combined_text()
        self.assertIn("only twitter", combined)
        self.assertNotIn("Reddit", combined)

    def test_combined_empty(self):
        ctx = MultiSourceContext()
        self.assertEqual(ctx.to_combined_text(), "")


class TestTweetBatch(unittest.TestCase):
    """배치 구조 검증."""

    def test_empty_batch(self):
        batch = TweetBatch(topic="테스트")
        self.assertEqual(len(batch.tweets), 0)
        self.assertEqual(len(batch.long_posts), 0)
        self.assertEqual(len(batch.threads_posts), 0)
        self.assertIsNone(batch.thread)

    def test_batch_with_all_types(self):
        batch = TweetBatch(
            topic="테스트 키워드",
            tweets=[GeneratedTweet(tweet_type="공감", content="내용1")],
            long_posts=[GeneratedTweet(tweet_type="딥다이브", content="긴글", content_type="long")],
            threads_posts=[GeneratedTweet(tweet_type="훅", content="Threads글", content_type="threads")],
            thread=GeneratedThread(tweets=["1", "2", "3"]),
        )
        self.assertEqual(len(batch.tweets), 1)
        self.assertEqual(len(batch.long_posts), 1)
        self.assertEqual(len(batch.threads_posts), 1)
        self.assertEqual(len(batch.thread.tweets), 3)


class TestTrendCluster(unittest.TestCase):
    """트렌드 클러스터."""

    def test_cluster_creation(self):
        cluster = TrendCluster(
            representative="AI 규제",
            members=["AI 규제", "ChatGPT 규제"],
        )
        self.assertEqual(cluster.representative, "AI 규제")
        self.assertEqual(len(cluster.members), 2)

    def test_cluster_no_context(self):
        cluster = TrendCluster(representative="test")
        self.assertIsNone(cluster.merged_context)


class TestRunResult(unittest.TestCase):
    """실행 결과."""

    def test_default_values(self):
        run = RunResult(run_id="test-123")
        self.assertEqual(run.trends_collected, 0)
        self.assertEqual(run.tweets_generated, 0)
        self.assertEqual(run.errors, [])
        self.assertIsNone(run.finished_at)


if __name__ == "__main__":
    unittest.main()
