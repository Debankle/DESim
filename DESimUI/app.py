# From week 3 tutorial https://canvas.qut.edu.au/courses/20367/pages/practical-rest-api-with-multi-container-service-architecture-python?module_item_id=2065855

from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title="Differential Equation Simulator UI",
    description="UI for modelling differential equations app",
    version="0.0.1",
)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", include_in_schema=False)
async def serve_index():
    return FileResponse(Path("static/index.html"))


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(Path("static/favicon.ico"))


@app.get("/{page_name}", include_in_schema=False)
async def serve_page(page_name: str):
    file_path = Path(f"static/{page_name}.html")
    if file_path.exists():
        return FileResponse(file_path)
    return FileResponse(Path("static/404.html"), status_code=404)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3001)
