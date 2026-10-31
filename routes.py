"""Read-only catalogue and image routes for the character atlas."""
from __future__ import annotations

import asyncio

from aiohttp import web

from .catalog import KINDS, AtlasError, catalogue, public_item


def register_routes():
    from server import PromptServer

    routes = PromptServer.instance.routes

    @routes.get("/character_atlas/catalogue")
    async def get_catalogue(request):
        kind = request.query.get("kind", "")
        if kind not in KINDS:
            return web.json_response({"error": "未知图库类型。"}, status=400)
        try:
            cat = await asyncio.to_thread(catalogue, kind)
            return web.json_response({
                "kind": kind, "items": [public_item(item) for item in cat.items],
                "count": len(cat.items), "facets": cat.facets,
            }, headers={"Cache-Control": "no-cache"})
        except (AtlasError, OSError) as exc:
            return web.json_response({"error": str(exc)}, status=400)

    @routes.get("/character_atlas/image")
    async def get_image(request):
        kind = request.query.get("kind", "")
        if kind not in KINDS:
            return web.json_response({"error": "未知图库类型。"}, status=400)
        try:
            def resolve():
                cat = catalogue(kind)
                return cat.path(cat.item(request.query.get("id", "")), request.query.get("variant", "thumb"))
            path = await asyncio.to_thread(resolve)
            return web.FileResponse(path, headers={
                "Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff",
            })
        except (AtlasError, OSError) as exc:
            return web.json_response({"error": str(exc)}, status=404)
