from django.db import models
# Create your models here.

class End_points(models.Model):
    api_address = models.CharField(max_length = 500, blank = False, null = False)
    description = models.CharField(max_length = 500, blank = False, null = False)

    def __str__(self):
        return self.api_address

class Fields(models.Model):
    api_address = models.ForeignKey(End_points,  on_delete=models.PROTECT)
    field_name = models.CharField(max_length = 150, blank = False, null = False)
    field_type = models.CharField(max_length = 150, blank = False, null = False)
    required = models.BooleanField(default = False)
    default_value = models.CharField(max_length = 500, blank = True, null = True)
    description = models.CharField(max_length = 500, blank = False, null = False)
    csv_file = models.FileField(upload_to='csv_files/', null=True, blank=True)

    def __str__(self):
        return self.field_name

class Users(models.Model):
    email = models.EmailField(max_length = 245)
    chat_history = models.JSONField(default=list)
    final_searched_player = models.CharField(max_length = 245, default = "FOOTY")
    final_api_address =  models.CharField(max_length = 250, null = True, blank = True)
    last_query = models.CharField(max_length = 250, null = True, blank = True)
    need_history = models.JSONField(default=list)
    cleared = models.BooleanField(default = True)
    def __str__(self):
        return self.email

    def append_data(self, new_item):
        conversation_data = self.chat_history
        conversation_data.append(new_item)
        self.chat_history = conversation_data
        self.save()
    
    def extend_data(self, new_item):
        conversation_data = self.chat_history
        conversation_data.extend(new_item)
        self.chat_history = conversation_data
        self.save()

    def remove_data(self):
        conversation_data = self.data
        if len(conversation_data) > 1:  
            self.chat_history = [conversation_data[0]]  
            self.save()
