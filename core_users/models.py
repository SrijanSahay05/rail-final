from django.db import models
from django.contrib.auth.models import AbstractUser

class CustomUser(AbstractUser):
    USER_TYPE_CHOICES = [
        ('PASSENGER', 'Passenger'),
        ('STAFF', 'Railway Staff'),
    ]
    
    user_type = models.CharField(
        max_length=10, 
        choices=USER_TYPE_CHOICES, 
        default='PASSENGER'
    )
    is_railway_staff = models.BooleanField(default=False)
    migration_fix = models.CharField(default='fixed')    

    def __str__(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username
    
    @property
    def is_passenger(self):
        return self.user_type == 'PASSENGER'
    
    @property
    def is_staff_member(self):
        return self.user_type == 'STAFF' or self.is_railway_staff
    
    def save(self, *args, **kwargs):
        if self.user_type == 'STAFF':
            self.is_railway_staff = True
        elif self.user_type == 'PASSENGER':
            self.is_railway_staff = False

        if not self.username:
            self.username = f"{self.email}"
        super().save(*args, **kwargs)


    


