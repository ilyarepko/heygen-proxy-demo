from __future__ import annotations
import asyncio
import logging

from aiohttp import web, WSCloseCode, WSMsgType
from pydantic import ValidationError

from api import HeyApi, HeyStream, HeyApiException
from peer import PeerWrapper
from wsschema import message_type_adapter, SDPMessage, TextMessage

API_KEY = "<YOUR API KEY>"

logger = logging.getLogger(__name__)
routes = web.RouteTableDef()

_api = web.AppKey("heyapi", HeyApi)
async def heyapi(app: web.Application):
    api = app[_api] = HeyApi(API_KEY)
    await api.stream_close_unmanaged()
    yield
    await api.close()

async def task_loop(stream: HeyStream, ws: web.WebSocketResponse):
    async for wsmsg in ws:
        if wsmsg.type != WSMsgType.TEXT:
            raise ValidationError()

        match message_type_adapter.validate_json(wsmsg.data):
            case TextMessage(text=text):
                await stream.task(text)
            case _:
                raise ValidationError()

@routes.get('/ws')
async def ws_handler(request: web.Request):
    ws = web.WebSocketResponse()
    if not ws.can_prepare(request):
        return web.HTTPBadRequest()

    await ws.prepare(request)

    api = request.app[_api]
    wscode = WSCloseCode.OK

    try:
        async with (
            await api.stream_new() as stream,
            await PeerWrapper.from_offer(stream.sdp, stream.ice_servers) as heypeer,
        ):
            await stream.start(heypeer.pc.localDescription)
            await asyncio.wait_for(heypeer.wait_tracks, timeout=3)

            tracks = heypeer.proxify()
            async with await PeerWrapper.offer(tracks) as peer:
                offer = SDPMessage(sdp=peer.pc.localDescription).model_dump()
                await ws.send_json(offer)

                incoming = await ws.receive_str(timeout=10)
                answer = SDPMessage.model_validate_json(incoming)
                await peer.pc.setRemoteDescription(answer.sdp)

                waiters = [
                    asyncio.create_task(heypeer.wait_connected),
                    asyncio.create_task(peer.wait_connected)
                ]
                await asyncio.wait(waiters, timeout=20)
                await task_loop(stream, ws)
    except asyncio.TimeoutError:
        logger.info(f"closing websocket connection with {request.remote} due to timeout")
        wscode = WSCloseCode.INTERNAL_ERROR
    except HeyApiException:
        logger.exception("HeyGen API error")
        wscode = WSCloseCode.INTERNAL_ERROR
    except ValidationError:
        logger.exception(f"schema error with {request.remote}")
        wscode = WSCloseCode.INVALID_TEXT
    finally:
        await ws.close(code=wscode)

    return ws

if __name__ == "__main__":
    logging.basicConfig(
        datefmt="%Y-%m-%d %H:%M:%S%z",
        format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
        level=logging.INFO,
    )

    loop = asyncio.get_event_loop()
    # loop.set_debug(True)

    app = web.Application()
    app.add_routes([*routes, web.static('/', './static', append_version=True)])
    app.cleanup_ctx.append(heyapi)

    web.run_app(app, loop=loop)
