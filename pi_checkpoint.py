#!/usr/bin/env python3

import asyncio
import json
import websockets
from aiortc import (
    RTCConfiguration,
    RTCIceServer,
    RTCPeerConnection,
    RTCSessionDescription,
)
from aiortc.contrib.media import MediaPlayer, MediaRecorder
from aiortc.sdp import candidate_from_sdp
SIGNALING_URL = "wss://shmeg1repo.onrender.com"
MIC_DEVICE = "plughw:CARD=Device,DEV=0"
SPK_DEVICE = "default:CARD=UACDemoV10"

config = RTCConfiguration(
    iceServers=[
        RTCIceServer(urls="stun:stun.l.google.com:19302"),
        RTCIceServer(
            urls="turn:openrelay.metered.ca:443?transport=tcp",
            username="openrelayproject",
            credential="openrelayproject",
        ),
    ]
)
pc = RTCPeerConnection(configuration=config)

player = None
try:
    player = MediaPlayer(MIC_DEVICE, format="alsa", options={"channels": "1", "sample_rate": "48000"})
    if player.audio is not None:
        print("Audio source ready:", player.audio)
        pc.addTrack(player.audio)
    else:
        print("Audio source opened but no audio track was provided by ALSA")
except Exception as exc:
    print(f"Audio input unavailable on {MIC_DEVICE}: {exc}")

recorder = None
try:
    recorder = MediaRecorder(SPK_DEVICE, format="alsa")
    print(f"Audio output prepared on {SPK_DEVICE}")
except Exception as exc:
    print(f"Audio output unavailable on {SPK_DEVICE}: {exc}")
recording_started = False

@pc.on("track")
async def on_track(track):
    """Start playback once when the first remote audio track arrives."""
    global recording_started

    if track.kind != "audio":
        return
    print("Audio track received from browser")
    
    if recording_started:
        print("Recorder already started; ignoring duplicate audio track")
        return
        
    if recorder is None:
        print("Recorder not available; received audio will not be played")
        return
        
    recording_started = True
    recorder.addTrack(track)
    await recorder.start()
    print("Audio playback started")

channel = pc.createDataChannel("test")

@channel.on("open")
def on_open():
    print("DataChannel open!!!")
    channel.send("Hello from Raspberry Pi")

@channel.on("message")
def on_message(message):
    if message == "ping":
        channel.send("pong")
        return
    print("From browser:", message)

@pc.on("connectionstatechange")
async def on_connectionstatechange():
    print("Connection state:", pc.connectionState)

@pc.on("iceconnectionstatechange")
async def on_iceconnectionstatechange():
    print("ICE connection state:", pc.iceConnectionState)
    
async def run():
    async with websockets.connect(SIGNALING_URL) as ws:
        print("Connected to signaling server")
        
        @pc.on("icecandidate")
        async def on_icecandidate(candidate):
            if candidate is None:
                return

            sdp_text = candidate.to_sdp()
            print(f"Sending ICE candidate: {sdp_text[:60]}...")
            await ws.send(
                json.dumps(
                    {
                        "type": "ice",
                        "candidate": {
                            "candidate": sdp_text,
                            "sdpMid": candidate.sdpMid,
                            "sdpMLineIndex": candidate.sdpMLineIndex,
                        },
                    }
                )
            )
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)
        await ws.send(
            json.dumps(
                {
                    "type": pc.localDescription.type,
                    "sdp": pc.localDescription.sdp,
                }
            )
        )
        print("Sent WebRTC offer")
        
        async for message in ws:
            data = json.loads(message)
            msg_type = data.get("type")
            if msg_type == "ping":
                continue
            if msg_type == "answer":
                print("Received WebRTC answer")
                await pc.setRemoteDescription(
                    RTCSessionDescription(sdp=data["sdp"], type=data["type"])
                )
            elif msg_type == "ice":
                cand = data.get("candidate", {})
                cand_sdp = cand.get("candidate")
                if not cand_sdp:
                    print("Received malformed ICE payload (missing candidate string)")
                    continue
                print(f"Received ICE candidate: {cand_sdp[:60]}...")
                rtc_candidate = candidate_from_sdp(cand_sdp)
                rtc_candidate.sdpMid = cand.get("sdpMid")
                rtc_candidate.sdpMLineIndex = cand.get("sdpMLineIndex")
                await pc.addIceCandidate(rtc_candidate)
asyncio.run(run())
