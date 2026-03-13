"""Diagnose whether the bot can read live meeting transcripts.

Usage:
    python scripts/test_transcript_pipeline.py

Checks:
1. Graph API token works
2. Bot can list online meetings
3. Bot can access transcript resources
4. Webhook subscription can be created
"""

import asyncio
import sys
sys.path.insert(0, ".")

import httpx
from app.config import settings


async def main():
    print("=" * 60)
    print("TRANSCRIPT PIPELINE DIAGNOSTIC")
    print("=" * 60)

    client_id = settings.microsoft_app_id
    client_secret = settings.microsoft_app_password
    tenant_id = settings.microsoft_app_tenant_id
    callback_host = settings.callback_host

    # Step 1: Get Graph token
    print("\n[1] Getting Graph API token...")
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials",
            },
        )
        if resp.status_code != 200:
            print(f"  FAIL: {resp.status_code} {resp.text[:200]}")
            return
        token = resp.json()["access_token"]
        print(f"  OK: Got token")

    headers = {"Authorization": f"Bearer {token}"}

    # Step 2: Check Graph API permissions
    print("\n[2] Checking Graph API permissions...")
    async with httpx.AsyncClient() as client:
        # Try to list online meetings (needs OnlineMeetings.Read.All)
        resp = await client.get(
            "https://graph.microsoft.com/v1.0/communications/onlineMeetings",
            headers=headers,
        )
        if resp.status_code == 200:
            meetings = resp.json().get("value", [])
            print(f"  OK: Can list meetings ({len(meetings)} found)")
        elif resp.status_code == 403:
            print(f"  FAIL: 403 Forbidden — missing OnlineMeetings.Read.All permission")
            print(f"  Response: {resp.text[:300]}")
        else:
            print(f"  WARN: {resp.status_code} — {resp.text[:200]}")

    # Step 3: Check active sessions on the bot
    print("\n[3] Checking active bot sessions...")
    async with httpx.AsyncClient() as client:
        resp = await client.get("http://localhost:8000/api/debug/sessions")
        data = resp.json()
        sessions = data.get("active_sessions", [])
        if not sessions:
            print("  WARN: No active meeting sessions")
            print("  → Join a meeting first with /join in Teams")
        else:
            for s in sessions:
                print(f"  Session: call_id={s.get('call_id', '?')}")
                print(f"    user: {s.get('user_name')}")
                print(f"    meeting_id: {s.get('meeting_id') or 'NOT RESOLVED'}")
                print(f"    transcript_lines: {s.get('transcript_line_count', 0)}")
                print(f"    conversation_ref: {'OK' if s.get('conversation_reference', {}).get('service_url') else 'MISSING'}")

                meeting_id = s.get("meeting_id")
                if meeting_id:
                    # Step 4: Try to fetch transcripts for this meeting
                    print(f"\n[4] Fetching transcripts for meeting {meeting_id[:20]}...")
                    async with httpx.AsyncClient() as client2:
                        resp2 = await client2.get(
                            f"https://graph.microsoft.com/v1.0/communications/onlineMeetings/{meeting_id}/transcripts",
                            headers=headers,
                        )
                        if resp2.status_code == 200:
                            transcripts = resp2.json().get("value", [])
                            print(f"  OK: {len(transcripts)} transcript(s) available")
                            for t in transcripts:
                                print(f"    - id: {t.get('id')}, created: {t.get('createdDateTime')}")
                        elif resp2.status_code == 403:
                            print(f"  FAIL: 403 Forbidden — missing OnlineMeetings.Read.All or CallRecords permissions")
                            print(f"  → Go to Azure Portal > App Registration > API Permissions")
                            print(f"  → Add: OnlineMeetings.Read.All (Application)")
                            print(f"  → Add: OnlineMeetingTranscript.Read.All (Application)")
                            print(f"  → Click 'Grant admin consent'")
                        elif resp2.status_code == 404:
                            print(f"  WARN: Meeting not found — may have ended or ID is wrong")
                        else:
                            print(f"  WARN: {resp2.status_code} — {resp2.text[:200]}")
                else:
                    print(f"\n[4] Cannot check transcripts — meeting_id not resolved")
                    print(f"  This means the bot joined but couldn't map the call to an online meeting")
                    print(f"  Transcript polling will NOT work without a meeting_id")

    # Step 5: Check if callback host is reachable
    print(f"\n[5] Checking callback host...")
    if not callback_host:
        print(f"  WARN: CALLBACK_HOST not set in .env")
    else:
        print(f"  Configured: {callback_host}")
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(f"{callback_host.rstrip('/')}/health", timeout=10)
                print(f"  OK: Reachable ({resp.status_code})")
            except Exception as e:
                print(f"  WARN: Not reachable — {e}")
                print(f"  → Make sure ngrok is running: ngrok http 8000")

    # Step 6: Check required Azure permissions
    print(f"\n[6] Required Azure API Permissions (Application type):")
    print(f"  Go to: Azure Portal > App Registrations > {client_id} > API Permissions")
    print(f"  Required permissions:")
    print(f"    - Calls.JoinGroupCall.All        (to join meetings)")
    print(f"    - Calls.InitiateGroupCall.All    (to initiate calls)")
    print(f"    - OnlineMeetings.Read.All        (to list/read meetings)")
    print(f"    - OnlineMeetingTranscript.Read.All (to read transcripts)")
    print(f"  All must have 'Admin consent granted' status = Yes")

    # Step 7: Check Teams transcription policy
    print(f"\n[7] Teams Transcription Policy:")
    print(f"  Go to: Teams Admin Center > Meetings > Meeting policies")
    print(f"  Ensure 'Transcription' is set to ON for your policy")
    print(f"  Without this, no transcripts are generated in meetings")

    print(f"\n{'=' * 60}")
    print(f"SUMMARY")
    print(f"{'=' * 60}")
    print(f"For live transcripts to work, ALL of these must be true:")
    print(f"  1. Bot joins meeting (via /join) .................. check with /join")
    print(f"  2. Transcription enabled in Teams policy ......... check Teams Admin Center")
    print(f"  3. Someone starts transcription in the meeting ... click 'Start transcription' in meeting")
    print(f"  4. Graph API permissions granted ................. check Azure Portal")
    print(f"  5. meeting_id resolved ........................... check debug/sessions endpoint")
    print(f"  6. ngrok tunnel active ........................... check CALLBACK_HOST")


if __name__ == "__main__":
    asyncio.run(main())
