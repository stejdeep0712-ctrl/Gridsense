

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Text,
    ForeignKey
)
from sqlalchemy.orm import relationship

from database.db import Base


class Feeder(Base):
    __tablename__ = "feeders"

    id = Column(Integer, primary_key=True, index=True)
    feeder_id = Column(String, unique=True, index=True, nullable=False)

    peak_load = Column(Float)
    min_load = Column(Float)
    transformer_rating = Column(Float)
    existing_solar = Column(Float)

    voltage = Column(Float)
    nominal_voltage = Column(Float)

    voltage_unbalance = Column(Float)
    thd = Column(Float)
    power_factor = Column(Float)

    line_resistance = Column(Float)
    line_reactance = Column(Float)

    hosting_capacity = Column(Float)
    pq_incident = Column(Integer)

    assessments = relationship(
        "AssessmentHistory",
        back_populates="feeder"
    )


class AssessmentHistory(Base):
    __tablename__ = "assessment_history"

    id = Column(Integer, primary_key=True, index=True)

    feeder_id = Column(
        Integer,
        ForeignKey("feeders.id"),
        nullable=True,
        index=True
    )

    feeder_code = Column(String, nullable=False, index=True)
    assessment_type = Column(String, nullable=False)
    status = Column(String, nullable=False)

    input_data = Column(Text, nullable=False)
    result_data = Column(Text, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    feeder = relationship(
        "Feeder",
        back_populates="assessments"
    )
