#!/usr/bin/env python3
import asyncio
import json
import websockets

from aiortc import (
    RTCPeerConnection,
    RTCSessionDescription,
    RTCConfiguration,
    RTCIceServer,
    RTCIceCandidate
)
from aiortc.contrib.media import MediaRecorder
from aiortc.contrib.media import MediaPlayer
SIGNALING_URL = "wss://shmeg1repo.onrender.com"

config = RTCConfiguration(
    iceServers=[
        RTCIceServer(urls="stun:stun.l.google.com:19302"),
        RTCIceServer(
            urls="turn:openrelay.metered.ca:443?transport=tcp",
            username="openrelayproject",
            credential="openrelayproject"
        )
    ]
)

pc = RTCPeerConnection(configuration=config)

player = MediaPlayer('default', format='alsa')
pc.addTrack(player.audio)

channel = pc.createDataChannel("test")

@channel.on("open")
def on_open():
    print("✅ DataChannel open")
    channel.send("Hello from Raspberry Pi")

@channel.on("message")
def on_message(message):
    print("📩 From browser:", message)

@pc.on("connectionstatechange")
async def on_connectionstatechange():
    print("Connection state:", pc.connectionState)

async def run():
    async with websockets.connect(SIGNALING_URL) as ws:
        print("✅ Connected to signaling server")

        # ICE handler MUST be inside run (so ws exists)
        @pc.on("icecandidate")
        async def on_icecandidate(candidate):
            if candidate:
                await ws.send(json.dumps({
                    "type": "ice",
                    "candidate": {
                        "candidate": candidate.to_sdp(),
                        "sdpMid": candidate.sdpMid,
                        "sdpMLineIndex": candidate.sdpMLineIndex
                    }
                }))

        # 1️⃣ Create offer
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)

        await ws.send(json.dumps({
            "type": pc.localDescription.type,
            "sdp": pc.localDescription.sdp
        }))

        print("📤 Sent WebRTC offer")

        # 2️⃣ Listen for messages
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

            elif data["type"] == "ice":
                from aiortc.sdp import candidate_from_sdp

                candidate = candidate_from_sdp(
                    data["candidate"]["candidate"]
                )

                candidate.sdpMid = data["candidate"]["sdpMid"]
                candidate.sdpMLineIndex = data["candidate"]["sdpMLineIndex"]

                await pc.addIceCandidate(candidate)
            

        recorder = MediaRecorder('default', format='alsa')

        @pc.on("track")
        async def on_track(track):
            print("🎵 Audio received from browser")
            await recorder.addTrack(track)
            await recorder.start()

asyncio.run(run())
