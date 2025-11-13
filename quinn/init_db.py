#!/usr/bin/env python3
"""
Initialize Quinn's SQLite database
Run this script to create the database tables
"""
from database.db import db

print("Initializing Quinn database...")
print(f"Database created at: {db.db_path}")
print("Tables created successfully!")
