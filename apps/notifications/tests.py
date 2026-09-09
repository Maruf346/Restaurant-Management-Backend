import json

from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.test import TestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.notifications.services import NotificationService
from apps.notifications.models import NotificationType
from apps.users.models import User
from core.asgi import application


class NotificationWebSocketTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='notify@example.com',
            username='notify-user',
            password='StrongPass123',
            full_name='Notify User',
            is_staff=True,
        )

    def test_notification_websocket_connects_and_receives_unread_count(self):
        token = str(RefreshToken.for_user(self.user).access_token)
        communicator = WebsocketCommunicator(
            application,
            f'/ws/notifications/?token={token}',
            headers=[(b'origin', b'http://localhost:3000')],
        )

        connected = async_to_sync(communicator.connect)()
        self.assertTrue(connected)

        connection_message = json.loads(async_to_sync(communicator.receive_output)())
        self.assertEqual(connection_message['type'], 'connection_established')

        NotificationService.send_notification(
            user=self.user,
            notification_type=NotificationType.DAILY_SUMMARY,
            title='Test notification',
            body='This is a live notification test.',
            data={'source': 'websocket-test'},
        )

        notification_message = json.loads(async_to_sync(communicator.receive_output)())
        self.assertEqual(notification_message['type'], 'notification')
        self.assertEqual(notification_message['title'], 'Test notification')

        async_to_sync(communicator.disconnect)(1000)
