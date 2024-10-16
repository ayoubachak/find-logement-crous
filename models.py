from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Alert(db.Model):
    __tablename__ = 'alerts'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # New name attribute
    city = db.Column(db.String(100), nullable=False)   # Keeping city as it is
    price = db.Column(db.Float, nullable=False)
    emails = db.Column(db.Text, nullable=False)  # Store emails as a comma-separated string
    bounds = db.Column(db.String(255), nullable=True)  # New bounds attribute
    status = db.Column(db.Boolean, default=True)  # Active (True) or Inactive (False)
    interval = db.Column(db.Integer, default=300)  # Refresh duration in seconds
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Alert {self.name} - {self.city} - {self.price} EUR>"

class AlertLog(db.Model):
    __tablename__ = 'alert_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    alert_id = db.Column(db.Integer, db.ForeignKey('alerts.id'), nullable=False)
    log = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    alert = db.relationship('Alert', backref='logs')

    def __repr__(self):
        return f"<Log for Alert {self.alert_id}>"
