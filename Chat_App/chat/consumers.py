import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from .models import Message
from django.utils import timezone


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        # Create a personal channel for the user
        self.personal_group = f'user_{self.user.username}'

        # Join personal channel
        await self.channel_layer.group_add(
            self.personal_group,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        # Leave personal channel
        await self.channel_layer.group_discard(
            self.personal_group,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data['message']
        receiver_username = data['receiver']

        # Save message to database
        message_obj = await self.save_message(
            sender=self.user,
            receiver_username=receiver_username,
            content=message
        )

        # Send to sender's channel
        await self.channel_layer.group_send(
            f'user_{self.user.username}',
            {
                'type': 'chat_message',
                'message': message,
                'sender': self.user.username,
                'receiver': receiver_username,
                'timestamp': message_obj.timestamp.strftime('%H:%M'),
                'message_id': message_obj.id,
                'is_sent': True
            }
        )

        # Send to receiver's channel
        await self.channel_layer.group_send(
            f'user_{receiver_username}',
            {
                'type': 'chat_message',
                'message': message,
                'sender': self.user.username,
                'receiver': receiver_username,
                'timestamp': message_obj.timestamp.strftime('%H:%M'),
                'message_id': message_obj.id,
                'is_sent': False
            }
        )

    async def chat_message(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'sender': event['sender'],
            'receiver': event['receiver'],
            'timestamp': event['timestamp'],
            'message_id': event['message_id'],
            'is_sent': event.get('is_sent', False)
        }))

    async def message_read(self, event):
        # Forward read receipt to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'message_read',
            'message_id': event['message_id']
        }))

    @database_sync_to_async
    def save_message(self, sender, receiver_username, content):
        receiver = User.objects.get(username=receiver_username)
        return Message.objects.create(
            sender=sender,
            receiver=receiver,
            content=content,
            timestamp=timezone.now()
        )