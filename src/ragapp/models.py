from extensions import db



class ChatHistory(db.Model):
    __tablename__ = "chat_history"

    # Renamed from id to historyid
    historyid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    useremail = db.Column(db.String(120), db.ForeignKey(
        'users.email'), nullable=False)
    userquery = db.Column(db.Text, nullable=False)  # Renamed from query to userquery
    llmresponse = db.Column(db.Text, nullable=False)
    top_n_document = db.Column(db.JSON, nullable=True)
    citation_data = db.Column(db.JSON, nullable=True)
    timestamp = db.Column(db.DateTime, nullable=False)

    def to_dict(self):
        return {
            "historyid": self.historyid,
            "useremail": self.useremail,
            "userquery": self.userquery,  # Updated field name
            "llmresponse": self.llmresponse,
            "top_n_document": self.top_n_document,
            "citation_data": self.citation_data,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }
