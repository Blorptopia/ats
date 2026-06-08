import typing
import asyncpg
from fastapi import Depends, FastAPI, Form, Header, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import tomllib
from urllib.parse import urlsplit
from jinja2.ext import DebugExtension
from pydantic import BaseModel
import re
from uuid import UUID
from .accept import get_preferred_mimetype

class ConfigSchema(BaseModel):
    database_url: str

@asynccontextmanager
async def lifespan(app: FastAPI) -> typing.AsyncGenerator[None]:
    with open("config.toml", "rb") as f:
        raw_config = tomllib.load(f)
    config = ConfigSchema.model_validate(raw_config)
    pool = await asyncpg.connect(config.database_url)
    app.state["postgres"] = pool
    yield

async def get_db_pool() -> typing.AsyncGenerator[asyncpg.Pool]:
    raw_pool = app.state["postgres"]
    pool = typing.cast(asyncpg.Pool, raw_pool)
    yield pool


app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates("templates")
templates.env.add_extension(DebugExtension)
app.mount("/static", StaticFiles(directory="static"))

FINN_URL_REGEX = re.compile("https://(?:www\\.)?finn.no/job/ad/(\\d+)")
ARBEIDSPLASSEN_URL_REGEX = re.compile("https://arbeidsplassen.nav.no/stillinger/stilling/([\\w\\d\\-_]+)")

@app.get("/")
async def render_index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.jinja",
        context={
            "active_href": "/"
        }
    )

@app.get("/applications")
async def render_applications(
    request: Request,
    pool: typing.Annotated[asyncpg.Pool, Depends(get_db_pool)],
    company_id: int | None = None,
) -> HTMLResponse:
    if company_id is None:
        applications = await pool.fetch(
            """
            select
                applications.id,
                applied_at,
                finn_ad_id,
                arbeidsplassen_post_id,
                application_platform_url,
                status,
                (
                    select count(*) from interviews 
                    where
                        application_id = applications.id
                ) as interview_count,
                company_id,
                companies.name as company_name
            from applications
            left join companies on companies.id = applications.company_id
            order by applications.id desc
            """
        )
    else:
        applications = await pool.fetch(
            """
            select
                applications.id,
                applied_at,
                finn_ad_id,
                arbeidsplassen_post_id,
                application_platform_url,
                status,
                (
                    select count(*) from interviews 
                    where
                        application_id = applications.id
                ) as interview_count,
                company_id,
                companies.name as company_name
            from applications
            left join companies on companies.id = applications.company_id
            where
                company_id = $1
            order by applications.id desc
            """,
            company_id
        )
    return templates.TemplateResponse(
        request,
        "applications/list.jinja",
        context={
            "active_href": "/applications",
            "applications": applications
        }
    )
@app.post("/applications/{application_id}")
async def update_application(
    application_id: int,
    status: typing.Annotated[typing.Literal["pending", "rejected", "offer"], Form()],
    pool: typing.Annotated[asyncpg.Pool, Depends(get_db_pool)],
) -> RedirectResponse:
    await pool.execute(
        """
        update applications
        set
            status = $1
        where
            id = $2
        """,
        status,
        application_id
    )
    return RedirectResponse(f"/applications/{application_id}", status_code=302)

async def render_create_application_page(
    request,
    finn_ad_id: int | None,
    arbeidsplassen_post_id: UUID | None,
    application_platform_url: str | None,
    pool: asyncpg.Pool
) -> HTMLResponse:
    applications = await pool.fetch(
        """
            select
                applications.id,
                applied_at,
                companies.name as company_name
            from applications
            left join companies on companies.id = applications.company_id
        """
    )
    companies = await pool.fetch(
        """
            select
                id,
                name
            from companies
        """
    )
    return templates.TemplateResponse(
        request,
        "applications/create.jinja",
        context={
            "finn_ad_id": finn_ad_id,
            "arbeidsplassen_post_id": arbeidsplassen_post_id,
            "application_platform_url": application_platform_url,
            "applications": applications,
            "companies": companies
        }
    )

@app.get("/applications/find", response_model=None)
async def find_application_by_id_or_url(
    id_or_url: str,
    request: Request,
    pool: typing.Annotated[asyncpg.Pool, Depends(get_db_pool)]
) -> HTMLResponse | RedirectResponse:
    if (parsed := FINN_URL_REGEX.search(id_or_url)) is not None:
        finn_ad_id = int(parsed.group(1))
        application = await pool.fetchrow(
            """
                select
                    id
                from applications
                where
                    finn_ad_id = $1
            """,
            finn_ad_id
        )
        if application is not None:
            return RedirectResponse(f"/applications/{application["id"]}")
        else:
            return await render_create_application_page(request, finn_ad_id, None, None, pool)
    if (parsed := ARBEIDSPLASSEN_URL_REGEX.search(id_or_url)) is not None:
        arbeidsplassen_post_id = UUID(parsed.group(1))
        application = await pool.fetchrow(
            """
                select
                    id
                from applications
                where
                    arbeidsplassen_post_id = $1
            """,
            arbeidsplassen_post_id
        )
        if application is not None:
            return RedirectResponse(f"/applications/{application["id"]}")
        else:
            return await render_create_application_page(request, None, arbeidsplassen_post_id, None, pool)
    try:
        finn_ad_id = int(id_or_url)
    except ValueError:
        finn_ad_id = None
    if finn_ad_id is not None:
        application = await pool.fetchrow(
            """
                select
                    id
                from applications
                where
                    finn_ad_id = $1
            """,
            finn_ad_id
        )
        if application is not None:
            return RedirectResponse(f"/applications/{application["id"]}")
        else:
            return await render_create_application_page(request, finn_ad_id, None, None, pool)
    try:
        arbeidsplassen_post_id = UUID(id_or_url)
    except ValueError:
        arbeidsplassen_post_id = None
    if arbeidsplassen_post_id is not None:
        application = await pool.fetchrow(
            """
                select
                    id
                from applications
                where
                    arbeidsplassen_post_id = $1
            """,
            arbeidsplassen_post_id
        )
        if application is not None:
            return RedirectResponse(f"/applications/{application["id"]}")
        else:
            return await render_create_application_page(request, None, arbeidsplassen_post_id, None, pool)
    application = await pool.fetchrow(
        """
            select
                id
            from applications
            where
                application_platform_url = $1
        """,
        id_or_url
    )
    if application is not None:
        return RedirectResponse(f"/applications/{application["id"]}")
    else:
        return await render_create_application_page(request, None, None, id_or_url, pool)
@app.get("/applications/{application_id}")
async def render_application(
    application_id: int,
    request: Request,
    pool: typing.Annotated[asyncpg.Pool, Depends(get_db_pool)]
) -> HTMLResponse:
    application = await pool.fetchrow(
        """
        select
            applications.id,
            finn_ad_id,
            arbeidsplassen_post_id,
            application_platform_url,
            status,
            companies.id as company_id,
            companies.name as company_name
        from applications
        left join companies on companies.id = applications.company_id
        where
            applications.id = $1
        """,
        application_id
    )
    if application is None:
        raise HTTPException(404, "application not found")
    interviews = await pool.fetch(
        """
        select
            id,
            date
        from interviews
        where
            application_id = $1
        """,
        application_id
    )
    return templates.TemplateResponse(
        request,
        "applications/view.jinja",
        context={
            "active_href": f"/applications/{application_id}",
            "application": application,
            "interviews": interviews,
            "get_hostname": get_hostname
        }
    )
@app.post("/applications", response_model=None)
async def create_application(
    pool: typing.Annotated[asyncpg.Pool, Depends(get_db_pool)],
    accept: typing.Annotated[str, Header()] = "text/html",
    company_id: typing.Annotated[int | None, Form()] = None,
    finn_ad_id: typing.Annotated[int | None, Form()] = None,
    application_platform_url: typing.Annotated[str | None, Form()] = None,
    arbeidsplassen_post_id: typing.Annotated[UUID | None, Form()] = None,
    recommended_after_application_id: typing.Annotated[UUID | None, Form()] = None,
) -> JSONResponse | RedirectResponse:
    application = await pool.fetchrow(
        """
        insert into applications (company_id, finn_ad_id, arbeidsplassen_post_id, application_platform_url, recommended_after_application_id)
        values ($1, $2, $3, $4, $5)
        returning id
        """,
        company_id,
        finn_ad_id,
        arbeidsplassen_post_id,
        application_platform_url,
        recommended_after_application_id
    )
    preferred_mimetype = get_preferred_mimetype(accept, ["text/html", "application/json"])
    if preferred_mimetype == "application/json":
        return JSONResponse({"id": application["id"]})
    return RedirectResponse(f"/applications/{application["id"]}", status_code=302)
    

def get_hostname(url: str) -> str:
    split = urlsplit(url)
    return split.hostname or "unknown"

@app.get("/companies")
async def render_companies(
    request: Request,
    pool: typing.Annotated[asyncpg.Pool, Depends(get_db_pool)]
) -> HTMLResponse:
    companies = await pool.fetch(
        """
        select
            id,
            name,
            (
                select count(*) from applications
                where
                    company_id = companies.id
            ) as application_count
        from companies
        order by id desc
        """
    )
    return templates.TemplateResponse(
        request,
        "companies/list.jinja",
        context={
            "companies": companies,
            "active_href": "/companies"
        }
    )
@app.post("/companies", response_model=None)
async def create_company(
    name: str,
    pool: typing.Annotated[asyncpg.Pool, Depends(get_db_pool)],
    accept: typing.Annotated[str, Header()] = "text/html"
) -> JSONResponse | RedirectResponse:
    result = await pool.fetchrow(
        """
        insert into companies
        (name)
        values ($1)
        returning id
        """,
        name
    )
    preferred_mimetype = get_preferred_mimetype(accept, ["text/html", "application/json"])
    if preferred_mimetype == "application/json":
        return JSONResponse({"id": result["id"]})
    return RedirectResponse(f"/applications?company_id={result["id"]}")
