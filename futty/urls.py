from django.urls import path, include
from futty import loginview, originalview

urlpatterns = [
    path('futtyai/', originalview.futty, name = "futty"),
    path('futtyai2/', loginview.futty, name = 'futty2'), #If you want to create separate space for each user.
]