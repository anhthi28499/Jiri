from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from .auth import get_current_user

router = APIRouter(prefix="/orders", tags=["orders"])


class OrderIn(BaseModel):
    items: list[dict]


class OrderOut(BaseModel):
    id: str
    items: list[dict]
    status: str


@router.post("/", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def create_order(body: OrderIn, user=Depends(get_current_user)):
    # TODO: persist to database
    return OrderOut(id="order-stub", items=body.items, status="pending")


@router.get("/{order_id}", response_model=OrderOut)
async def get_order(order_id: str, user=Depends(get_current_user)):
    return OrderOut(id=order_id, items=[], status="pending")
