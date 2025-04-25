# filepath: /Users/manojadhikari/Documents/Capstone/Shiny-BucBuddy/ShinyBucBuddy/src/user/serializers.py
from marshmallow import Schema, fields
from marshmallow import Schema, fields, ValidationError, validates
from .models import User
import re

class UserSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True, load_only=True)
    confirm_password = fields.Str(load_only=True, required=False)  
    firstname = fields.Str(required=True)
    lastname = fields.Str(required=True)

    @validates('email')
    def validate_email(self, value, **kwargs):
        if User.query.filter_by(email=value).first():
            raise ValidationError('Email already exists')

    @validates('password')
    def validate_password(self, value, **kwargs):
        if len(value) < 8:
            raise ValidationError('Password must be at least 8 characters long')
        if not re.search(r'[A-Z]', value):
            raise ValidationError('Password must contain at least one uppercase letter')
        if not re.search(r'[0-9]', value):
            raise ValidationError('Password must contain at least one number')