from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import Message


@login_required
def home(request):
    users = User.objects.exclude(username=request.user.username)
    # Get latest messages for each user
    user_messages = {}
    for user in users:
        latest_message = Message.objects.filter(
            Q(sender=request.user, receiver=user) |
            Q(sender=user, receiver=request.user)
        ).order_by('-timestamp').first()
        user_messages[user.id] = latest_message

    return render(request, 'chat/home.html', {
        'users': users,
        'user_messages': user_messages
    })


@login_required
def room(request, username):
    other_user = User.objects.get(username=username)
    users = User.objects.exclude(username=request.user.username)

    # Get messages between current user and other user
    messages = Message.objects.filter(
        Q(sender=request.user, receiver=other_user) |
        Q(sender=other_user, receiver=request.user)
    ).order_by('timestamp')

    # Mark received messages as read
    Message.objects.filter(
        sender=other_user,
        receiver=request.user,
        is_read=False
    ).update(is_read=True)

    # Get latest message for each user in the sidebar
    user_messages = {}
    for user in users:
        latest_message = Message.objects.filter(
            Q(sender=request.user, receiver=user) |
            Q(sender=user, receiver=request.user)
        ).order_by('-timestamp').first()
        user_messages[user.id] = latest_message

    return render(request, 'chat/room.html', {
        'other_user': other_user,
        'users': users,
        'messages': messages,
        'user_messages': user_messages
    })

@require_POST
@login_required
def mark_message_read(request, message_id):
    Message.objects.filter(
        id=message_id,
        receiver=request.user,
        is_read=False
    ).update(is_read=True)
    return JsonResponse({'status': 'ok'})

def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Registration successful!')
            return redirect('home')
        else:
            messages.error(request, 'Registration failed. Please correct the errors.')
    else:
        form = UserCreationForm()
    return render(request, 'chat/register.html', {'form': form})


@require_POST
@login_required
def mark_message_read(request, message_id):
    message = Message.objects.filter(
        id=message_id,
        receiver=request.user,
        is_read=False
    ).first()

    if message:
        message.is_read = True
        message.save()

        # Get channel layer and send to sender's group
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'user_{message.sender.username}',
            {
                'type': 'message_read',
                'message_id': message_id
            }
        )

    return JsonResponse({'status': 'ok'})