# filepath: /Users/manojadhikari/Documents/Capstone/Shiny-BucBuddy/ShinyBucBuddy/src/user/serializers.py
from marshmallow import Schema, fields


class UserSchema(Schema):
    """Serializer for the User model."""
    email = fields.Email(required=True)
    password = fields.Str(load_only=True, required=True)
    firstname = fields.Str(required=False, allow_none=True)
    lastname = fields.Str(required=False, allow_none=True)
    signinstatus = fields.Bool(required=False)
