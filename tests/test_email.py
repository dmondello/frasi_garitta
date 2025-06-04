import os
import importlib
import sys
import unittest
from unittest.mock import patch, MagicMock


class TestSendConfirmationEmail(unittest.TestCase):
    def setUp(self):
        self.env = {
            'EMAIL_HOST': 'smtp.test.com',
            'EMAIL_PORT': '2525',
            'EMAIL_USER': 'user@test.com',
            'EMAIL_PASSWORD': 'secret',
            'EMAIL_FROM': 'noreply@test.com',
            'SITE_URL': 'http://testserver'
        }

    def test_send_confirmation_email_uses_env_vars(self):
        with patch.dict(os.environ, self.env), \
             patch.dict(sys.modules, {'flask': MagicMock()}):
            app = importlib.import_module('app')
            importlib.reload(app)
            with patch('smtplib.SMTP') as mock_smtp:
                result = app.send_confirmation_email('dest@test.com', 'token', 'Test User')

                mock_smtp.assert_called_with(self.env['EMAIL_HOST'], int(self.env['EMAIL_PORT']))
                instance = mock_smtp.return_value
                instance.starttls.assert_called_once()
                instance.login.assert_called_once_with(self.env['EMAIL_USER'], self.env['EMAIL_PASSWORD'])
                instance.send_message.assert_called_once()
                instance.quit.assert_called_once()
                self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()
