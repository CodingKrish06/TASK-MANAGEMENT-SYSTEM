#!/usr/bin/env python
import django
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'taskmanager.settings')
django.setup()

from django.db import connection

cursor = connection.cursor()
cursor.execute("DESCRIBE accounts_userprofile")
print("Current accounts_userprofile schema:")
for row in cursor.fetchall():
    print(row)
