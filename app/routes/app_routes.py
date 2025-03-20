from pathlib import Path

from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from starlette.responses import JSONResponse, RedirectResponse, HTMLResponse
from starlette.staticfiles import StaticFiles


def mount_routes(app: FastAPI, args):
    """
    mount global routes
    :param app:
    :param args:
    :return:
    """

    api_prefix = f'{args.servlet}'

    @app.exception_handler(Exception)
    async def handle_exception(request, exc):
        """
        global exception handler
        """
        return JSONResponse({'code': 500, 'message': str(exc)})

    # static files
    app.mount(f'{api_prefix}/static', StaticFiles(directory=Path('static').as_posix()))

    # redirect to swagger
    @app.get('/', include_in_schema=False)
    async def redirect_swagger_document():
        return RedirectResponse(url=f'{api_prefix}/docs')

    # swagger documentation
    @app.get(f'{api_prefix}/docs', include_in_schema=False)
    async def swagger_ui_html() -> HTMLResponse:
        return get_swagger_ui_html(
            openapi_url=f'{app.openapi_url}',
            title=app.title + ' - Swagger UI',
            oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
            swagger_js_url=f'{api_prefix}/static/swagger-ui-bundle.js',
            swagger_css_url=f'{api_prefix}/static/swagger-ui.css',
            swagger_favicon_url=f'{api_prefix}/static/favicon.png',
        )

    pass
