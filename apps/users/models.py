import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    user_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    role = models.CharField(
        max_length=50,
        choices=[('user', 'User'), ('reviewer', 'Reviewer'), ('operator', 'Operator')]
    )
    confidence_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)

    class Meta:
        db_table = 'user'
        indexes = [
            models.Index(fields=['username']),
            models.Index(fields=['email']),
        ]
