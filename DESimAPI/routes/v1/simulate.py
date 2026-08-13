from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from models import simulate
from models.exceptions import (
    DBError,
    DBReturnedNoneError,
    DuplicateEntry,
    InvalidData,
    S3Error,
    SQSError,
)
from routes.v1.api_helpers import (
    PaginationParams,
    SimulationFilterParams,
    SortParams,
    apply_query_features,
    get_admin_pagination_params,
    get_pagination_params,
    get_simulation_filter_params,
    get_simulation_sort_params,
)
from routes.v1.parameters import SimulationParams
from routes.v1.schemas import User
from utils.security import get_current_user, require_admin

simulate_router = APIRouter()

CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentAdminUser = Annotated[User, Depends(require_admin)]


@simulate_router.post("/validate", status_code=status.HTTP_200_OK)
def validate(sim: SimulationParams):
    stable, errors = sim.parameters.validate_params()
    size = sim.parameters.estimate_size()

    if not stable or errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"stable": stable, "errors": errors, "size": size},
        )

    return {"stable": stable, "errors": errors, "size": size}


@simulate_router.post("", status_code=status.HTTP_201_CREATED)
async def submit_simulation(req: SimulationParams, current_user: CurrentUser):
    try:
        size = req.parameters.estimate_size()
        if size > 200 and not current_user.isadmin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Simulation of size {size} is too large for non admin user",
            )
        sim_id = simulate.add_job(
            current_user.username,
            req.equation,
            req.parameters.theta,
            req.parameters,
            req.private,
        )
        return {"simulation_id": sim_id}
    except DuplicateEntry as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Duplicate entry in database: {e}",
        ) from e
    except DBReturnedNoneError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Database did not return a simulation job UUID: {e}",
        ) from e
    except DBError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Database error: {e}"
        ) from e
    except SQSError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"SQS error: {e}"
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {e}",
        ) from e


@simulate_router.get("", status_code=status.HTTP_200_OK)
async def get_all_user_jobs(
    current_user: CurrentUser,
    response: Response,
    pagination: PaginationParams = Depends(get_pagination_params),
    sim_sort: SortParams = Depends(get_simulation_sort_params),
    sim_filter: SimulationFilterParams = Depends(get_simulation_filter_params),
):
    try:
        all_sim_jobs = simulate.get_all_user_simulation_jobs(current_user.username)
        if len(all_sim_jobs) > 0:
            result = apply_query_features(
                all_sim_jobs,
                sim_filter,
                sim_sort.sort_by,
                sim_sort.sort_order,
                pagination.page,
                pagination.per_page,
            )
            response.headers["X-Total-Count"] = str(result["total_items"])
            response.headers["X-Page"] = str(result["page"])
            response.headers["X-Per-Page"] = str(result["per_page"])
            response.headers["X-Total-Pages"] = str(result["total_pages"])
            return result["items"]
        return []
    except DBError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Database error: {e}"
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {e}",
        ) from e


@simulate_router.get("/all", status_code=status.HTTP_200_OK)
async def get_all_jobs_admin(
    _: CurrentAdminUser,
    response: Response,
    pagination: PaginationParams = Depends(get_admin_pagination_params),
    sim_sort: SortParams = Depends(get_simulation_sort_params),
    sim_filter: SimulationFilterParams = Depends(get_simulation_filter_params),
):
    try:
        all_sim_jobs = simulate.get_all_simulations()
        if len(all_sim_jobs) > 0:
            result = apply_query_features(
                all_sim_jobs,
                sim_filter,
                sim_sort.sort_by,
                sim_sort.sort_order,
                pagination.page,
                pagination.per_page,
            )
            response.headers["X-Total-Count"] = str(result["total_items"])
            response.headers["X-Page"] = str(result["page"])
            response.headers["X-Per-Page"] = str(result["per_page"])
            response.headers["X-Total-Pages"] = str(result["total_pages"])
            return result["items"]
        return []
    except DBError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Database error: {e}"
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {e}",
        ) from e


@simulate_router.get("/public", status_code=status.HTTP_200_OK)
async def get_public_jobs(
    response: Response,
    pagination: PaginationParams = Depends(get_pagination_params),
    sim_sort: SortParams = Depends(get_simulation_sort_params),
    sim_filter: SimulationFilterParams = Depends(get_simulation_filter_params),
):
    try:
        all_public_jobs = simulate.get_public_simulations()
        if len(all_public_jobs) > 0:
            result = apply_query_features(
                all_public_jobs,
                sim_filter,
                sim_sort.sort_by,
                sim_sort.sort_order,
                pagination.page,
                pagination.per_page,
            )
            response.headers["X-Total-Count"] = str(result["total_items"])
            response.headers["X-Page"] = str(result["page"])
            response.headers["X-Per-Page"] = str(result["per_page"])
            response.headers["X-Total-Pages"] = str(result["total_pages"])
            return result["items"]
        return []
    except DBError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Database error: {e}"
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {e}",
        ) from e


@simulate_router.get("/{sim_id}", status_code=status.HTTP_200_OK)
async def get_simulation_job(sim_id: UUID, current_user: CurrentUser):
    if current_user.isadmin:
        try:
            return simulate.get_simulation(sim_id)
        except DBReturnedNoneError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Could not find simulation by UUID: {sim_id}",
            )
        except InvalidData as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid data request: {e}",
            ) from e
        except DBError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=f"Database error: {e}"
            ) from e
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Internal server error: {e}",
            ) from e
    else:
        try:
            job = simulate.get_simulation(sim_id)
            if job.username == current_user.username:
                return job
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Only owners can view private jobs",
                )
        except DBReturnedNoneError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Could not find simulation by UUID: {sim_id}",
            )
        except InvalidData as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid data request: {e}",
            ) from e
        except DBError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=f"Database error: {e}"
            ) from e
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Internal server error: {e}",
            ) from e


@simulate_router.delete("/{sim_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(sim_id: UUID, current_user: CurrentUser):
    if current_user.isadmin:
        try:
            simulate.delete_simulation(sim_id)
        except InvalidData as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid data request: {e}",
            ) from e
        except DBError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=f"Database error: {e}"
            ) from e
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Internal server error: {e}",
            ) from e
    else:
        try:
            job = simulate.get_simulation(sim_id)
            if job.username == current_user.username:
                simulate.delete_simulation(sim_id)
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Only owners can view private jobs",
                )
        except InvalidData as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid data request: {e}",
            ) from e
        except DBError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=f"Database error: {e}"
            ) from e
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Internal server error: {e}",
            ) from e


@simulate_router.get("/{sim_id}/result", status_code=status.HTTP_200_OK)
async def fetch_result(sim_id: UUID, current_user: CurrentUser):
    try:
        job = simulate.get_simulation(sim_id)
        if (
            job.private
            and job.username != current_user.username
            and not current_user.isadmin
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Only owners can download their private jobs",
            )
        if job.status != "complete":
            raise HTTPException(
                status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
                detail="Simulation is not finished",
            )
        return simulate.fetch_presigned_url(sim_id)
    except InvalidData as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid data request: {e}"
        ) from e
    except DBError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Database error: {e}"
        ) from e
    except S3Error as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"S3 error: {e}"
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {e}",
        ) from e
