from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# from jinja2 import Template

import duckdb, pathlib, datetime, os
from dotenv import load_dotenv

load_dotenv()

CLOUDFLARE_KEY_ID = os.environ.get("CLOUDFLARE_KEY_ID")
CLOUDFLARE_SECRET = os.environ.get("CLOUDFLARE_SECRET")
CLOUDFLARE_ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
CLOUDFLARE_BUCKET = os.environ.get("CLOUDFLARE_BUCKET")

app = FastAPI(
    title="availReporter",
    description="Broadband availability lookup by location ID",
    docs_url="/",
    redoc_url=None
)

app.mount("/static", StaticFiles(directory="src/static"), name="static")
templates = Jinja2Templates(directory="src/templates")

try:
    db = duckdb.connect(":memory:")
    db.execute(f"""
        INSTALL httpfs;
        LOAD httpfs;""")

    db.execute(f"""
        CREATE OR REPLACE SECRET r2_secret (
            TYPE r2,
            KEY_ID '{CLOUDFLARE_KEY_ID}',
            SECRET '{CLOUDFLARE_SECRET}',
            ACCOUNT_ID '{CLOUDFLARE_ACCOUNT_ID}'
            );""")

    db.execute(f"""
        CREATE OR REPLACE VIEW avail AS 
        SELECT * FROM read_parquet('r2://{CLOUDFLARE_BUCKET}/avail_*.parquet');
        """)

except:
    raise Exception("db issue")


techName = {
    10: "Copper",
    40: "Cable",
    50: "Fiber",
    60: "GSO",
    61: "NGSO",
    70: "UFW",
    71: "LFW",
    72: "LBRW",
}
versionMap = {
    "2022-06-30": "v1",
    "2022-12-31": "v2",
    "2023-06-30": "v3",
    "2023-12-31": "v4",
    "2024-06-30": "v5",
    "2024-12-31": "v6",
    "2025-06-30": "v7",
    "2025-12-31": "v8",
    "2026-06-30": "v9",
    "2026-12-31": "v10"
}


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("src/static/favicon.ico")


# @app.get("/")
# async def root():
#     return {"message": "Hello World"}


@app.get("/availability", response_class=JSONResponse)
async def get_availability(location_id: str):
    before = datetime.datetime.now()
    result = db.execute(
        f"SELECT * FROM avail WHERE location_id = '{location_id}'"
    ).fetchdf()
    after = datetime.datetime.now()
    print(f"Query time: {after - before}")
    return result.to_dict(orient="records")


@app.get("/pretty", response_class=HTMLResponse)
async def get_pretty_availability(request: Request, location_id: str):
    before = datetime.datetime.now()
    result = db.execute(
        f"SELECT * FROM avail WHERE location_id = '{location_id}'"
    ).fetchdf()
    after = datetime.datetime.now()
    print(f"Query time: {after - before}")
    data = {}
    result["tech_name"] = result["technology"].map(techName)
    result["version"] = result["release"].map(versionMap)
    result["verRel"] = result["version"] + " - (" + result["release"] + ")"
    for release in result.verRel.drop_duplicates().to_list():
        data[release] = result[result.verRel == release].to_dict(orient="records")
    # return result.to_html()
    # return result[['brand_name', 'max_down', 'max_up']].to_html()
    return templates.TemplateResponse(
        request=request, name="pretty.jinja2", context={"data": data}
    )
