from pydantic import BaseModel


class PaperTradingStartRequest(BaseModel):
    strategy: str = "CryptoInvestorV1"


class PaperTradingStatusResponse(BaseModel):
    running: bool
    strategy: str | None = None
    pid: int | None = None
    started_at: str | None = None
    uptime_seconds: int = 0
    exit_code: int | None = None


class PaperTradingActionResponse(BaseModel):
    status: str
    strategy: str | None = None
    pid: int | None = None
    started_at: str | None = None
    error: str | None = None
