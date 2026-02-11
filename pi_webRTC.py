#!/usr/bin/env python3
import asyncio
import json
import websockets

from aiortc import RTCPeerConnection, RTCSessionDescription

SIGNALING_URL = "wss://shmeg1repo.onrender.com"

from aiortc import RTCConfiguration, RTCIceServer

config = RTCConfiguration(
    iceServers=[RTCIceServer(urls="stun:stun.l.google.com:19302")]
)

pc = RTCPeerConnection(configuration=config)

channel = pc.createDataChannel("test")

@channel.on("open")
def on_open():
    print("✅ DataChannel open")
    channel.send("Hello from Raspberry Pi")

@channel.on("message")
def on_message(message):
    print("📩 From browser:", message)


async def run():
    async with websockets.connect(SIGNALING_URL) as ws:
        print("✅ Connected to signaling server")

        # Raspberry Pi is the OFFERER
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)

        await ws.send(json.dumps({
            "type": pc.localDescription.type,
            "sdp": pc.localDescription.sdp
        }))

        print("📤 Sent WebRTC offer")

        async for message in ws:
            data = json.loads(message)

            if data["type"] == "answer":
                print("📥 Received WebRTC answer")

                await pc.setRemoteDescription(
                    RTCSessionDescription(
                        sdp=data["sdp"],
                        type=data["type"]
                    )
                )
            if data["type"] == "ice":
                from aiortc import RTCIceCandidate
                candidate = RTCIceCandidate(
                    sdpMid=data["candidate"]["sdpMid"],
                    sdpMLineIndex=data["candidate"]["sdpMLineIndex"],
                    candidate=data["candidate"]["candidate"]
                )
                await pc.addIceCandidate(candidate)

                print("🎉 WebRTC peer connection established (SDP complete)")

asyncio.run(run())

@pc.on("icecandidate")
async def on_icecandidate(candidate):
    if candidate:
        await ws.send(json.dumps({
            "type": "ice",
            "candidate": {
                "candidate": candidate.component,
                "sdpMid": candidate.sdpMid,
                "sdpMLineIndex": candidate.sdpMLineIndex
            }
        }))

