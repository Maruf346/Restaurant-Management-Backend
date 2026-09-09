from asgiref.sync import async_to_sync, sync_to_async
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.notifications.models import NotificationType
from apps.notifications.services import NotificationService
from apps.users.models import User
from core.asgi import application


class NotificationWebSocketTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='notify@example.com',
            username='notify-user',
            password='StrongPass123',
            full_name='Notify User',
            is_staff=True,
        )

    def test_notification_websocket_connects_and_receives_unread_count(self):
        # Create token synchronously before entering async context
        token = str(RefreshToken.for_user(self.user).access_token)

        async def run_test():
            communicator = WebsocketCommunicator(
                application,
                f'/ws/notifications/?token={token}',
                headers=[(b'origin', b'http://localhost:3000')],
            )

            connected, _ = await communicator.connect()
            self.assertTrue(connected)

            connection_message = await communicator.receive_json_from()
            self.assertEqual(connection_message['type'], 'connection_established')

            # send_notification is synchronous ORM operation -> wrap in sync_to_async
            await sync_to_async(NotificationService.send_notification)(
                user=self.user,
                notification_type=NotificationType.DAILY_SUMMARY,
                title='Test notification',
                body='This is a live notification test.',
                data={'source': 'websocket-test'},
            )

            notification_message = await communicator.receive_json_from()
            self.assertEqual(notification_message['type'], 'notification')
            self.assertEqual(notification_message['title'], 'Test notification')

            await communicator.disconnect(1000)

        async_to_sync(run_test)()
