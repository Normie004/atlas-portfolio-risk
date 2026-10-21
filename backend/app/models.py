from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field, field_validator

AssetClass = Literal['Equity', 'Bond', 'ETF', 'Cash']
Currency = Literal['CAD', 'USD']

class Holding(BaseModel):
    symbol: str = Field(min_length=1, max_length=24)
    name: str = Field(min_length=1, max_length=120)
    asset_class: AssetClass
    currency: Currency
    quantity: Decimal = Field(ge=0)
    price: Decimal = Field(ge=0)

    @field_validator('symbol', 'name')
    @classmethod
    def not_whitespace(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError('Must not be blank')
        return value

class Scenario(BaseModel):
    equities_pct: Decimal = Field(default=Decimal('-5'), ge=-100, le=100)
    bonds_pct: Decimal = Field(default=Decimal('-2'), ge=-100, le=100)
    usd_fx_pct: Decimal = Field(default=Decimal('-3'), ge=-100, le=100)

class AnalyzeRequest(BaseModel):
    holdings: list[Holding] = Field(min_length=1, max_length=500)
    usd_to_cad: Decimal = Field(default=Decimal('1.37'), gt=0, le=10)
    scenario: Scenario = Field(default_factory=Scenario)
    source_label: str = Field(default='Demo portfolio', max_length=60)
