### Modified from the tutorial below
# https://www.slingacademy.com/article/ways-to-implement-pagination-in-fastapi/

from typing import Any, Dict, Optional, Sequence, TypeVar

from fastapi import Query
from pydantic import BaseModel

from routes.v1.schemas import Simulation, User

T = TypeVar("T", bound=BaseModel)


class PaginationParams(BaseModel):
    page: Optional[int] = None
    per_page: Optional[int] = None


class SortParams(BaseModel):
    sort_order: Optional[str] = None
    sort_by: Optional[str] = None


class UserFilterParams(BaseModel):
    isadmin: Optional[int] = None


class SimulationFilterParams(BaseModel):
    theta: Optional[float] = None
    status: Optional[str] = None
    equation: Optional[str] = None
    user: Optional[str] = None


def get_pagination_params(
    page: int = Query(1, gt=0), per_page: int = Query(10, gt=0)
) -> PaginationParams:
    return PaginationParams(page=page, per_page=per_page)


def get_admin_pagination_params(
    page: Optional[int] = Query(None, gt=0),
    per_page: Optional[int] = Query(None, gt=0),
) -> PaginationParams:
    return PaginationParams(page=page, per_page=per_page)


def get_user_sort_params(
    sort_by: Optional[str] = Query("id", pattern="^(id|username|isadmin)$"),
    sort_order: Optional[str] = Query("asc", pattern="^(asc|desc)$"),
) -> SortParams:
    return SortParams(sort_order=sort_order, sort_by=sort_by)


def get_user_filter_params(
    isadmin: Optional[int] = Query(None, ge=0, le=1),
) -> UserFilterParams:
    return UserFilterParams(isadmin=isadmin)


def get_simulation_sort_params(
    sort_by: Optional[str] = Query(
        None,
        pattern="^(simulation_id|user|equation|theta|status|submit_time|complete_time)$",
    ),
    sort_order: Optional[str] = Query("asc", regex="^(asc|desc)$"),
) -> SortParams:
    return SortParams(sort_order=sort_order, sort_by=sort_by)


def get_simulation_filter_params(
    theta: Optional[float] = Query(None, ge=0, le=1),
    status: Optional[str] = Query(None, pattern="^(queued|running|finished|failed)$"),
    equation: Optional[str] = Query(None, pattern="^(heat|diffusionadvection|wave)$"),
    user: Optional[str] = Query(None),
) -> SimulationFilterParams:
    return SimulationFilterParams(
        theta=theta, status=status, equation=equation, user=user
    )


def apply_query_features(
    result: Sequence[T],
    filters: Optional[BaseModel] = None,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = "asc",
    page: Optional[int] = 1,
    per_page: Optional[int] = 10,
) -> Dict[str, Any]:
    if not result:
        return {
            "page": page or 1,
            "per_page": per_page or 0,
            "total_items": 0,
            "total_pages": 0,
            "items": [],
        }

    if filters:
        for k, v in filters.model_dump(exclude_none=True).items():
            result = [r for r in result if getattr(r, k, None) == v]

    columns = list(result[0].model_dump().keys())

    if sort_by and sort_by in columns:
        result = sorted(
            result,
            key=lambda r: getattr(r, sort_by),
            reverse=bool(sort_order and sort_order.lower() == "desc"),
        )

    if per_page is None:
        per_page = len(result)
    if page is None:
        page = 1

    total_items = len(result)
    start = (page - 1) * per_page
    end = start + per_page

    return {
        "page": page,
        "per_page": per_page,
        "total_items": total_items,
        "total_pages": (total_items + per_page - 1) // per_page,
        "items": result[start:end],
    }
