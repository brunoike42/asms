from ..providers.console import ConsoleProvider


def test_console_provider_always_succeeds_and_returns_unique_ids():
    provider = ConsoleProvider()

    result_a = provider.send("+256712345678", "hello")
    result_b = provider.send("+256712345678", "hello")

    assert result_a.status == "Success"
    assert result_a.message_id != result_b.message_id
