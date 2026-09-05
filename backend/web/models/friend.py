from django.db import models
from django.utils.timezone import now, localtime

from web.models.character import Character
from web.models.user import UserProfile


class Friend(models.Model):
    me = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    character = models.ForeignKey(Character, on_delete=models.CASCADE)
    memory = models.TextField(default="",max_length=5000,blank=True,null=True)
    create_time = models.DateTimeField(default=now)
    update_time = models.DateTimeField(default=now)
    def __str__(self):
        return f"{self.character.name}-{self.me.user.username}-{localtime(self.create_time).strftime('%Y/%m/%d %H:%M:%S')}"

class Message(models.Model):
    friend = models.ForeignKey(Friend, on_delete=models.CASCADE)
    user_message = models.TextField(max_length=5000)#用户的消息
    input= models.TextField(max_length=10000)#用户的消息被优化的消息
    output = models.TextField(max_length=5000)
    create_time = models.DateTimeField(default=now)
    input_tokens = models.IntegerField(default=0)
    output_tokens = models.IntegerField(default=0)
    total_tokens = models.IntegerField(default=0)
    create_time = models.DateTimeField(default=now)


    def __str__(self):
        return f"{self.friend.character.name}-{self.friend.me.user.username}-{self.user_message[:50]}-{localtime(self.create_time).strftime('%Y/%m/%d %H:%M:%S')}"