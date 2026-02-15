from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session, get_session
from app.services.exchange import ExchangeService
from app.services.job import JobService
from app.services.job_runner import JobRunner
from app.services.market import MarketService
from app.services.portfolio import PortfolioService
from app.services.paper_trading import PaperTradingService
from app.services.trading import TradingService

SessionDep = Annotated[AsyncSession, Depends(get_session)]

# Singleton job runner (shared across requests)
_job_runner: JobRunner | None = None


def get_job_runner() -> JobRunner:
    global _job_runner
    if _job_runner is None:
        _job_runner = JobRunner(async_session, max_workers=settings.max_job_workers)
    return _job_runner


JobRunnerDep = Annotated[JobRunner, Depends(get_job_runner)]


async def get_exchange_service() -> AsyncGenerator[ExchangeService, None]:
    service = ExchangeService()
    try:
        yield service
    finally:
        await service.close()


ExchangeServiceDep = Annotated[ExchangeService, Depends(get_exchange_service)]


def get_portfolio_service(session: SessionDep) -> PortfolioService:
    return PortfolioService(session)


def get_market_service(
    session: SessionDep, exchange: ExchangeServiceDep
) -> MarketService:
    return MarketService(session, exchange)


def get_trading_service(
    session: SessionDep, exchange: ExchangeServiceDep
) -> TradingService:
    return TradingService(session, exchange)


def get_job_service(session: SessionDep, runner: JobRunnerDep) -> JobService:
    return JobService(session, runner)


# Singleton paper trading service (manages subprocess)
_paper_trading_service: PaperTradingService | None = None


def get_paper_trading_service() -> PaperTradingService:
    global _paper_trading_service
    if _paper_trading_service is None:
        _paper_trading_service = PaperTradingService()
    return _paper_trading_service


PaperTradingServiceDep = Annotated[
    PaperTradingService, Depends(get_paper_trading_service)
]
PortfolioServiceDep = Annotated[PortfolioService, Depends(get_portfolio_service)]
MarketServiceDep = Annotated[MarketService, Depends(get_market_service)]
TradingServiceDep = Annotated[TradingService, Depends(get_trading_service)]
JobServiceDep = Annotated[JobService, Depends(get_job_service)]
