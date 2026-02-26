"""
pytest configuration: suppress known third-party deprecation warnings
that cannot be fixed in project code.
"""
import warnings


def pytest_configure(config):  # noqa: ARG001
    # python-multipart internal import path changed
    warnings.filterwarnings(
        "ignore",
        message="Please use `import python_multipart` instead",
        category=PendingDeprecationWarning,
    )
    # google-genai internal async client inheritance
    warnings.filterwarnings(
        "ignore",
        category=DeprecationWarning,
    )
    # FastAPI uses deprecated asyncio.iscoroutinefunction (Python 3.12+)
    warnings.filterwarnings(
        "ignore",
        message="'asyncio.iscoroutinefunction' is deprecated",
        category=DeprecationWarning,
    )
    # FastAPI HTTP status constant renamed
    warnings.filterwarnings(
        "ignore",
        message="'HTTP_422_UNPROCESSABLE_ENTITY' is deprecated",
        category=DeprecationWarning,
    )
    # websockets legacy module deprecated in v14
    warnings.filterwarnings(
        "ignore",
        message="websockets.legacy is deprecated",
        category=DeprecationWarning,
    )
    # google-genai uses Python 3.14-deprecated typing internals
    warnings.filterwarnings(
        "ignore",
        message="'_UnionGenericAlias' is deprecated",
        category=DeprecationWarning,
    )
    # LangChain Pydantic V1 compat layer not supported on Python 3.14+
    warnings.filterwarnings(
        "ignore",
        message="Core Pydantic V1 functionality isn't compatible with Python 3.14",
        category=UserWarning,
    )
