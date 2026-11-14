"""M3 local API adapter. Reuses the M2 engine without changing its model."""
import json
import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .routing import DEFAULT_REGION, ROOT, RoutingError, TerrainGrid
from .environment import load_environment

Number = Annotated[float, Field(strict=True, allow_inf_nan=False)]


class RouteRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    start_lonlat: tuple[Number, Number]
    end_lonlat: tuple[Number, Number]
    terrain_weight: Annotated[Number, Field(ge=0, le=1_000_000)] = 100.0
    max_cell_slope_deg: Annotated[Number, Field(ge=0, le=90)] | None = None
    primary_objective: Literal['distance', 'terrain'] = 'distance'
    region_manifest_sha256: Annotated[str, Field(pattern=r'^[a-f0-9]{64}$')]
    region_id: Annotated[str, Field(pattern=r'^[a-z0-9-]{1,40}$')] = 'jezero-m1'


class BodyLimit:
    """Bound actual streamed JSON before FastAPI parsing, not just Content-Length."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['method'] != 'POST':
            return await self.app(scope, receive, send)
        chunks = []
        size = 0
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            size += len(message.get('body', b''))
            if size > 4096:
                return await JSONResponse({'code': 'body_too_large', 'message': 'Route request exceeds 4096 bytes'}, status_code=413)(scope, receive, send)
            chunks.append(message)
            if not message.get('more_body', False):
                break
        async def replay():
            return chunks.pop(0) if chunks else await receive()
        await self.app(scope, replay, send)


def create_app(region_dir=DEFAULT_REGION, grid_factory=None, environment_dir=ROOT/'data/processed/environment', additional_region_dirs=None):
    region_dir = Path(region_dir)
    region_dirs = {'jezero-m1': region_dir, **(additional_region_dirs or {})}
    @asynccontextmanager
    async def lifespan(app):
        app.state.grid = None
        app.state.region = None
        app.state.regions = {}
        try:
            for region_id, directory in region_dirs.items():
                grid = grid_factory() if grid_factory and region_id == 'jezero-m1' else TerrainGrid.load(directory)
                manifest = json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
                app.state.regions[region_id] = {'grid': grid, 'manifest': manifest}
            default = app.state.regions.get('jezero-m1')
            if default:
                app.state.grid, app.state.region = default['grid'], default['manifest']
        except (OSError, ValueError, KeyError, RuntimeError):
            logging.exception('Routing dataset could not be loaded; terrain frontend remains available')
        app.state.environment = None
        try:
            app.state.environment = load_environment(environment_dir)
        except (OSError, ValueError, KeyError, TypeError):
            logging.warning('M4 environmental data unavailable; routing remains independent')
        app.state.route_lock = threading.BoundedSemaphore(1)
        yield

    app = FastAPI(title='MARSWALK local mission API', version='0.3.0', lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', 'testserver'])
    app.add_middleware(BodyLimit)

    @app.middleware('http')
    async def local_guards(request, call_next):
        origins = {f'http://{host}:{port}' for host in ['localhost', '127.0.0.1'] for port in [5173, 4173, 8000]}
        if request.method == 'POST':
            if request.headers.get('origin') and request.headers['origin'] not in origins:
                return JSONResponse({'code': 'origin_rejected', 'message': 'Use the local mission interface'}, status_code=403)
            if request.headers.get('content-type', '').split(';')[0].strip() != 'application/json':
                return JSONResponse({'code': 'json_required', 'message': 'Use application/json'}, status_code=415)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        return JSONResponse({'code': 'invalid_request', 'message': 'Check finite numeric coordinates and mission parameters',
                             'fields': ['.'.join(map(str, item['loc'])) for item in error.errors()]}, status_code=422)

    @app.get('/api/health')
    def health():
        ready = app.state.grid is not None and app.state.region is not None
        return JSONResponse({'status': 'ready' if ready else 'data_unavailable'}, status_code=200 if ready else 503)

    @app.get('/api/region')
    def region(request: Request):
        region_id = request.query_params.get('region_id', 'jezero-m1')
        selected = ({'grid': app.state.grid, 'manifest': app.state.region} if app.state.grid is not None and app.state.region is not None else None) if region_id == 'jezero-m1' else app.state.regions.get(region_id)
        if selected is None:
            return JSONResponse({'code': 'data_unavailable', 'message': 'Run and verify the M1 preprocessing pipeline'}, status_code=503)
        grid, manifest = selected['grid'], selected['manifest']
        return {'region_id': region_id, 'region': manifest, 'region_manifest_sha256': grid.provenance['region_manifest_sha256'],
                'routing_available': True, 'model': 'marswalk-grid-astar-v1',
                'availability': {'terrain': 'validated', 'imagery': 'validated', 'temperature_weather': 'historical_MEDA_local' if app.state.environment else 'unavailable_M4_data',
                                 'dust_storms': 'historical_MARCI_report_only' if app.state.environment else 'unavailable_M4_data', 'radiation': 'Gale_reference_only_metadata' if app.state.environment else 'Gale_reference_only_unavailable',
                                 'minerals': 'planned_M5', 'geology': 'planned_M5', 'ancient_water': 'context_pending_M5',
                                 'budgets_recommendations': 'planned_M6'}}

    @app.get('/api/environment')
    def environment():
        if app.state.environment is None:
            return JSONResponse({'code':'environment_unavailable','message':'Verified environmental archive unavailable. Run M4 fetch/preprocessing and restart the backend.'},status_code=503)
        return app.state.environment

    @app.post('/api/routes')
    def routes(body: RouteRequest):
        selected = ({'grid': app.state.grid, 'manifest': app.state.region} if app.state.grid is not None and app.state.region is not None else None) if body.region_id == 'jezero-m1' else app.state.regions.get(body.region_id)
        if selected is None:
            return JSONResponse({'code': 'data_unavailable', 'message': 'Verified terrain is unavailable'}, status_code=503)
        grid = selected['grid']
        if body.region_manifest_sha256 != grid.provenance['region_manifest_sha256']:
            return JSONResponse({'code': 'dataset_mismatch', 'message': 'Map and routing datasets differ. Regenerate data and reload.'}, status_code=409)
        if not app.state.route_lock.acquire(blocking=False):
            return JSONResponse({'code': 'busy', 'message': 'A route calculation is already running. Retry shortly.'}, status_code=429, headers={'Retry-After': '1'})
        try:
            result = grid.compare(body.start_lonlat, body.end_lonlat, body.terrain_weight, body.max_cell_slope_deg)
            result['primary_objective'] = body.primary_objective
            result['region_manifest_sha256'] = grid.provenance['region_manifest_sha256']
            return result
        except RoutingError as error:
            return JSONResponse({'code': error.code, 'message': str(error)}, status_code=422)
        finally:
            app.state.route_lock.release()

    # Optional built frontend, same origin. Development uses the Vite /api proxy.
    dist = ROOT/'frontend/dist'
    if dist.is_dir():
        app.mount('/', StaticFiles(directory=dist, html=True), name='mission-control')
    return app


_expanded_region = ROOT/'data/processed/jezero-expanded-7p5km'
app = create_app(additional_region_dirs={'expanded-7p5km': _expanded_region} if _expanded_region.is_dir() else None)
