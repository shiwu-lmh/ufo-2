import unittest

from ufo.client.action_retry import execute_with_retries


class ActionRetryTests(unittest.IsolatedAsyncioTestCase):
    async def test_retries_a_failed_ui_action_twice_before_success(self):
        attempts = 0
        refresh_attempts = []

        async def operation():
            nonlocal attempts
            attempts += 1
            return attempts == 3

        async def refresh(retry_number):
            refresh_attempts.append(retry_number)

        result = await execute_with_retries(
            operation,
            max_retries=2,
            is_success=lambda value: value is True,
            before_retry=refresh,
        )

        self.assertTrue(result)
        self.assertEqual(attempts, 3)
        self.assertEqual(refresh_attempts, [1, 2])

    async def test_stops_after_two_retries_when_action_keeps_failing(self):
        attempts = 0

        async def operation():
            nonlocal attempts
            attempts += 1
            return False

        result = await execute_with_retries(
            operation,
            max_retries=2,
            is_success=lambda value: value is True,
        )

        self.assertFalse(result)
        self.assertEqual(attempts, 3)


if __name__ == "__main__":
    unittest.main()
