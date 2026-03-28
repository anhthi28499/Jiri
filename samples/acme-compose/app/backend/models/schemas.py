from pydantic import BaseModel


class OrderItem(BaseModel):
    product_id: str
    quantity: int
    unit_price: float


class OrderIn(BaseModel):
    items: list[OrderItem]


class OrderOut(BaseModel):
    id: str
    items: list[OrderItem]
    status: str
    total: float = 0.0
