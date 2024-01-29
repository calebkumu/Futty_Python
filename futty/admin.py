from django.contrib import admin

# Register your models here.
from .models import Fields, End_points, Users
admin.site.register(Fields)
admin.site.register(End_points)
admin.site.register(Users)

