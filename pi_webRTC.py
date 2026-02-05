#!/usr/bin/env python3
import asyncio
import websockets

# This is an ASYNCHRONOUS function
async def signaling_test():
    # Connect to your signaling server
    async with websockets.connect("wss://YOUR_RENDER_URL") as ws:
        print("Connected to signaling server")

        # Send a test message
        await ws.send("hello from raspberry pi")

        # Wait for a message back
        message = await ws.recv()
        print("Received:", message)

# This starts the async function properly
asyncio.run(signaling_test())
