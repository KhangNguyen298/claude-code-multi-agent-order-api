from pydantic import BaseModel, ConfigDict, Field

# Simple format check (avoids the optional email-validator dependency).
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class CustomerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(max_length=254, pattern=EMAIL_PATTERN)


class Customer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
