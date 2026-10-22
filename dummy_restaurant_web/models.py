from pydantic import BaseModel, Field
from typing import Optional, List

class ReservationCreate(BaseModel):
    customer_name: str = Field(..., min_length=2, description="Nama lengkap pemesan")
    phone: str = Field(..., min_length=8, description="Nomor telepon / WhatsApp")
    email: Optional[str] = Field(None, description="Alamat email pemesan")
    reservation_date: str = Field(..., description="Format: YYYY-MM-DD")
    reservation_time: str = Field(..., description="Format: HH:MM (contoh: 18:30)")
    guest_count: int = Field(..., ge=1, le=50, description="Jumlah tamu (1-50 orang)")
    table_area: str = Field(default="Indoor AC", description="Indoor AC, Outdoor Garden, VIP Room, Rooftop Lounge")
    special_notes: Optional[str] = Field(None, description="Catatan permintaan khusus")

class ReservationStatusUpdate(BaseModel):
    status: str = Field(..., description="Confirmed, Completed, Cancelled, Pending")

class MenuItemCreate(BaseModel):
    name: str
    category: str
    price: int
    description: Optional[str] = ""
    image_url: Optional[str] = ""
    is_available: int = 1
    is_favorite: int = 0
    spicy_level: int = 0
    tags: Optional[str] = ""

class MenuItemUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    price: Optional[int] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    is_available: Optional[int] = None
    is_favorite: Optional[int] = None
    spicy_level: Optional[int] = None
    tags: Optional[str] = None

class RestaurantInfoUpdate(BaseModel):
    name: Optional[str] = None
    tagline: Optional[str] = None
    description: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    email: Optional[str] = None
    open_time: Optional[str] = None
    close_time: Optional[str] = None
