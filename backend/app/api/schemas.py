from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

# ----------------------------------------------------
# Centre Schemas
# ----------------------------------------------------
class CentreBase(BaseModel):
    name: str
    type: str  # "PHC" or "CHC"
    lat: float
    lng: float
    population_served: int
    tier_classification: str  # "rural", "urban", "tribal"

class CentreCreate(CentreBase):
    pass

class CentreResponse(CentreBase):
    id: int

    class Config:
        from_attributes = True

# ----------------------------------------------------
# Drug Schemas
# ----------------------------------------------------
class DrugBase(BaseModel):
    name: str
    unit: str
    safety_stock_level: int

class DrugCreate(DrugBase):
    pass

class DrugResponse(DrugBase):
    id: int

    class Config:
        from_attributes = True

# ----------------------------------------------------
# Stock Log Schemas
# ----------------------------------------------------
class StockLogBase(BaseModel):
    centre_id: int
    drug_id: int
    quantity_change: int
    log_type: str  # "received", "consumed", "transferred"
    source: str  # "manual", "voice", "whatsapp", "iot"
    reported_by: str

class StockLogCreate(StockLogBase):
    timestamp: Optional[datetime] = None

class StockLogResponse(StockLogBase):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True

# ----------------------------------------------------
# Footfall Log Schemas
# ----------------------------------------------------
class FootfallLogBase(BaseModel):
    centre_id: int
    count: int
    source: str
    reported_by: str

class FootfallLogCreate(FootfallLogBase):
    timestamp: Optional[datetime] = None

class FootfallLogResponse(FootfallLogBase):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True

# ----------------------------------------------------
# Bed Status Schemas
# ----------------------------------------------------
class BedStatusBase(BaseModel):
    centre_id: int
    total_beds: int
    occupied_beds: int

class BedStatusCreate(BedStatusBase):
    timestamp: Optional[datetime] = None

class BedStatusResponse(BedStatusBase):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True

# ----------------------------------------------------
# Staff Attendance Schemas
# ----------------------------------------------------
class StaffAttendanceBase(BaseModel):
    centre_id: int
    staff_role: str
    present: bool
    reported_by: str

class StaffAttendanceCreate(StaffAttendanceBase):
    timestamp: Optional[datetime] = None

class StaffAttendanceResponse(StaffAttendanceBase):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True

# ----------------------------------------------------
# Transfer Schemas
# ----------------------------------------------------
class TransferBase(BaseModel):
    from_centre_id: int
    to_centre_id: int
    drug_id: int
    quantity: int
    status: str  # "suggested", "approved", "completed"
    urgency_score: float

class TransferCreate(TransferBase):
    pass

class TransferResponse(TransferBase):
    id: int

    class Config:
        from_attributes = True

# ----------------------------------------------------
# Flag Schemas
# ----------------------------------------------------
class FlagBase(BaseModel):
    centre_id: int
    flag_type: str
    triggering_metric: str
    value: float
    threshold: float
    resolved: bool = False

class FlagCreate(FlagBase):
    timestamp: Optional[datetime] = None

class FlagResponse(FlagBase):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True

# ----------------------------------------------------
# User Schemas
# ----------------------------------------------------
class UserBase(BaseModel):
    name: str
    role: str
    centre_id: Optional[int] = None
    phone_number: Optional[str] = None

class UserCreate(UserBase):
    pass

class UserResponse(UserBase):
    id: int

    class Config:
        from_attributes = True

# ----------------------------------------------------
# Unified Report Submission Schema
# ----------------------------------------------------
class ReportSubmitRequest(BaseModel):
    centre_id: int
    report_type: str  # "stock", "footfall", "bed", "attendance"
    source: str  # "manual", "whatsapp", "voice", "iot"
    reported_by: str
    data: dict = Field(..., description="Details of the report (e.g., {'drug_id': 1, 'quantity_change': -50} for stock)")

# ----------------------------------------------------
# Risk State Response Schema
# ----------------------------------------------------
class StockForecastItem(BaseModel):
    drug_id: int
    drug_name: str
    current_stock: int
    safety_stock_level: int
    predicted_days_to_stockout: float
    uncertainty_lower: float
    uncertainty_upper: float
    reasoning: str

class CentreRiskStateResponse(BaseModel):
    centre_id: int
    centre_name: str
    data_reliability_score: float  # 0 to 100
    resource_adequacy_score: float  # 0 to 100
    reliability_reasons: List[str]
    adequacy_reasons: List[str]
    stock_forecasts: List[StockForecastItem]
    predicted_footfall_next_7_days: List[float]
    predicted_bed_demand_next_7_days: List[float]
    active_flags: List[FlagResponse]
