import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base

class Centre(Base):
    __tablename__ = "centres"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    type = Column(String, nullable=False)  # "PHC" or "CHC"
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    population_served = Column(Integer, nullable=False)
    tier_classification = Column(String, nullable=False)  # "rural", "urban", "tribal"

    # Relationships
    stock_logs = relationship("StockLog", back_populates="centre")
    footfall_logs = relationship("FootfallLog", back_populates="centre")
    bed_statuses = relationship("BedStatus", back_populates="centre")
    staff_attendances = relationship("StaffAttendance", back_populates="centre")
    flags = relationship("Flag", back_populates="centre")
    users = relationship("User", back_populates="centre")


class Drug(Base):
    __tablename__ = "drugs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    unit = Column(String, nullable=False)  # e.g., "tablets", "vials", "bottles"
    safety_stock_level = Column(Integer, nullable=False)  # safety threshold for notifications

    # Relationships
    stock_logs = relationship("StockLog", back_populates="drug")
    transfers = relationship("Transfer", back_populates="drug")


class StockLog(Base):
    __tablename__ = "stock_logs"

    id = Column(Integer, primary_key=True, index=True)
    centre_id = Column(Integer, ForeignKey("centres.id", ondelete="CASCADE"), nullable=False)
    drug_id = Column(Integer, ForeignKey("drugs.id", ondelete="CASCADE"), nullable=False)
    quantity_change = Column(Integer, nullable=False)  # positive for additions, negative for consumption
    log_type = Column(String, nullable=False)  # "received", "consumed", "transferred"
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    source = Column(String, nullable=False)  # "manual", "voice", "whatsapp", "iot"
    reported_by = Column(String, nullable=False)  # username or reporter identifier

    # Relationships
    centre = relationship("Centre", back_populates="stock_logs")
    drug = relationship("Drug", back_populates="stock_logs")


class FootfallLog(Base):
    __tablename__ = "footfall_logs"

    id = Column(Integer, primary_key=True, index=True)
    centre_id = Column(Integer, ForeignKey("centres.id", ondelete="CASCADE"), nullable=False)
    count = Column(Integer, nullable=False)  # number of patients visited
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    source = Column(String, nullable=False)  # "manual", "voice", "whatsapp"
    reported_by = Column(String, nullable=False)

    # Relationships
    centre = relationship("Centre", back_populates="footfall_logs")


class BedStatus(Base):
    __tablename__ = "bed_status"

    id = Column(Integer, primary_key=True, index=True)
    centre_id = Column(Integer, ForeignKey("centres.id", ondelete="CASCADE"), nullable=False)
    total_beds = Column(Integer, nullable=False)
    occupied_beds = Column(Integer, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    centre = relationship("Centre", back_populates="bed_statuses")


class StaffAttendance(Base):
    __tablename__ = "staff_attendance"

    id = Column(Integer, primary_key=True, index=True)
    centre_id = Column(Integer, ForeignKey("centres.id", ondelete="CASCADE"), nullable=False)
    staff_role = Column(String, nullable=False)  # "doctor", "nurse", "pharmacist", etc.
    present = Column(Boolean, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    reported_by = Column(String, nullable=False)

    # Relationships
    centre = relationship("Centre", back_populates="staff_attendances")


class Transfer(Base):
    __tablename__ = "transfers"

    id = Column(Integer, primary_key=True, index=True)
    from_centre_id = Column(Integer, ForeignKey("centres.id", ondelete="CASCADE"), nullable=False)
    to_centre_id = Column(Integer, ForeignKey("centres.id", ondelete="CASCADE"), nullable=False)
    drug_id = Column(Integer, ForeignKey("drugs.id", ondelete="CASCADE"), nullable=False)
    quantity = Column(Integer, nullable=False)
    status = Column(String, nullable=False)  # "suggested", "approved", "completed"
    urgency_score = Column(Float, nullable=False)

    # Relationships
    from_centre = relationship("Centre", foreign_keys=[from_centre_id])
    to_centre = relationship("Centre", foreign_keys=[to_centre_id])
    drug = relationship("Drug", back_populates="transfers")


class Flag(Base):
    __tablename__ = "flags"

    id = Column(Integer, primary_key=True, index=True)
    centre_id = Column(Integer, ForeignKey("centres.id", ondelete="CASCADE"), nullable=False)
    flag_type = Column(String, nullable=False)  # "reliability", "adequacy", etc.
    triggering_metric = Column(String, nullable=False)  # e.g., "consumption_vs_footfall", "missing_reports"
    value = Column(Float, nullable=False)  # reported value
    threshold = Column(Float, nullable=False)  # threshold limit
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    resolved = Column(Boolean, default=False, nullable=False)

    # Relationships
    centre = relationship("Centre", back_populates="flags")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    role = Column(String, nullable=False)  # "field_staff", "asha_anm", "district_admin"
    centre_id = Column(Integer, ForeignKey("centres.id", ondelete="SET NULL"), nullable=True)
    phone_number = Column(String, unique=True, index=True, nullable=True)  # link to WhatsApp reporter

    # Relationships
    centre = relationship("Centre", back_populates="users")


class IntakeQueue(Base):
    __tablename__ = "intake_queue"

    id = Column(Integer, primary_key=True, index=True)
    sender = Column(String, nullable=False)
    message_body = Column(String, nullable=True)
    media_url = Column(String, nullable=True)
    status = Column(String, nullable=False, default="pending")  # "pending", "processed", "failed"
    retry_count = Column(Integer, nullable=False, default=0)
    error_message = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
