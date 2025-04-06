# filepath: /Users/manojadhikari/Documents/Capstone/Shiny-BucBuddy/ShinyBucBuddy/src/user/serializers.py
from marshmallow import Schema, fields


class UserSchema(Schema):
    """Serializer for the User model."""
    id = fields.Int(dump_only=True)
    username = fields.Str(required=True)
    email = fields.Email(required=True)
    password = fields.Str(load_only=True, required=True)
