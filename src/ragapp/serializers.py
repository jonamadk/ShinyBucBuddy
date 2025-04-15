from marshmallow import Schema, fields


class ChatHistorySchema(Schema):
    historyid = fields.Int(dump_only=True)
    useremail = fields.Str(required=True)
    userquery = fields.Str(required=True)  # Renamed from query to userquery
    llmresponse = fields.Str(required=True)
    top_n_document = fields.Raw(required=False)
    citation_data = fields.Raw(required=False)
    timestamp = fields.DateTime(required=True)
