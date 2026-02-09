#!/usr/bin/env python3
import asyncio
import json
import websockets

from aiortc import RTCPeerConnection, RTCSessionDescription

# Create a WebRTC peer connection
# This object represents the Raspberry Pi in the WebRTC system
pc = RTCPeerConnection()

channel = pc.createDataChannel("test")

@channel.on("open")
def on_open():
    print("DataChannel open!")
    channel.send("Hello from Raspberry Pi")

@channel.on("message")
def on_message(message):
    print("Received from browser:", message)

# URL of your signaling server (Render)
SIGNALING_URL = "wss://shmeg1repo.onrender.com"


async def run():
    # Connect to the signaling server
    async with websockets.connect(SIGNALING_URL) as ws:
        print("Connected to signaling server")

        # Listen for messages from the operator webpage
        async for message in ws:
            data = json.loads(message)

            # If we receive an SDP offer from the browser
            if data["type"] == "offer":
                print("Received WebRTC offer")

                # Set the remote description (browser's offer)
                await pc.setRemoteDescription(
                    RTCSessionDescription(
                        sdp=data["sdp"],
                        type=data["type"]
                    )
                )

                # Create an SDP answer
                answer = await pc.createAnswer()

                # Apply the answer locally
                await pc.setLocalDescription(answer)

                # Send the answer back to the browser via signaling server
                await ws.send(json.dumps({
                    "type": pc.localDescription.type,
                    "sdp": pc.localDescription.sdp
                }))

                print("Sent WebRTC answer")


# Start the async system
asyncio.run(run())

