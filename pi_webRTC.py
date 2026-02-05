#!/usr/bin/env python3
async with websockets.connect("wss://YOUR_RENDER_URL") as ws:
    await ws.send("hello")
    message = await ws.recv()
