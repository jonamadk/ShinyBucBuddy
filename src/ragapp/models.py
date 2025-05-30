from extensions import db
from datetime import datetime


class ChatHistory(db.Model):
    __tablename__ = "chat_history"

    historyid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    conversationid = db.Column(db.Integer, db.ForeignKey(
        'chat_conversations.conversationid'), nullable=False)  # Link to ChatConversation
    useremail = db.Column(db.String(120), db.ForeignKey(
        'users.email'), nullable=False)
    userquery = db.Column(db.Text, nullable=False)
    llmresponse = db.Column(db.Text, nullable=False)
    top_n_document = db.Column(db.JSON, nullable=True)
    citation_data = db.Column(db.JSON, nullable=True)
    timestamp = db.Column(db.DateTime, nullable=False)

    def to_dict(self):
        return {
            "historyid": self.historyid,
            "conversationid": self.conversationid,
            "useremail": self.useremail,
            "userquery": self.userquery,
            "llmresponse": self.llmresponse,
            "top_n_document": self.top_n_document,
            "citation_data": self.citation_data,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }


class ChatConversation(db.Model):
    __tablename__ = "chat_conversations"

    conversationid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    useremail = db.Column(db.String(120), db.ForeignKey('users.email'), nullable=False)
    title = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationship to ChatHistory
    chat_history = db.relationship('ChatHistory', backref='conversation', lazy=True)

    def to_dict(self):
        return {
            "conversationid": self.conversationid,
            "useremail": self.useremail,
            "title": self.title,
            "created_at": self.created_at.isoformat(),
            "chat_history": [history.to_dict() for history in self.chat_history]
        }


class UnauthenticatedSession(db.Model):
    __tablename__ = "unauthenticated_sessions"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # Unique identifier for each row
    session_id = db.Column(db.String(255), nullable=False)  # Unique session ID
    conversation_id = db.Column(db.Integer, nullable=False)  # Conversation ID
    userquery = db.Column(db.Text, nullable=False)  # User query
    llmresponse = db.Column(db.Text, nullable=False)  # LLM response
    top_n_document = db.Column(db.JSON, nullable=True)  # Top N documents
    citation_data = db.Column(db.JSON, nullable=True)  # Citation data
    history_userquery = db.Column(db.JSON, nullable=True)  # History of user queries
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)  # Timestamp of the interaction

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "conversation_id": self.conversation_id,
            "userquery": self.userquery,
            "llmresponse": self.llmresponse,
            "top_n_document": self.top_n_document,
            "citation_data": self.citation_data,
            "history_userquery": self.history_userquery,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }
