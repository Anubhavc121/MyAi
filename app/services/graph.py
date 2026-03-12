import logging
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

class GraphClient:
    """Handles authentication and calls to Microsoft Graph API."""
    def __init__(self):
        self.client_id = settings.microsoft_app_id
        self.client_secret = settings.microsoft_app_password
        self.tenant_id = settings.microsoft_app_tenant_id
        self.token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        
    async def get_access_token(self) -> str:
        """Fetch an OAuth2 access token for Microsoft Graph."""
        if not self.tenant_id:
            raise ValueError("microsoft_app_tenant_id is not set. Cannot authenticate with Microsoft Graph.")
            
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self.token_url,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "scope": "https://graph.microsoft.com/.default",
                    "grant_type": "client_credentials",
                }
            )
            resp.raise_for_status()
            return resp.json().get("access_token")

    async def answer_call(self, callback_uri: str, incoming_call_context: str):
        """Answer an incoming Teams P2P or Group call via Graph API."""
        token = await self.get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # The payload to answer an incoming notification call
        payload = {
            "@odata.type": "#microsoft.graph.call",
            "callbackUri": callback_uri,
            "acceptedModalities": ["audio"], # We only need audio/transcript
            "mediaConfig": {
                "@odata.type": "#microsoft.graph.serviceHostedMediaConfig"
            }
        }
        
        # Note: The Graph API requires passing the incoming context to correctly answer
        # https://graph.microsoft.com/v1.0/communications/calls/{id}/answer doesn't work directly 
        # for starting the signaling unless you have the call ID, or use answering endpoint.
        pass

    async def subscribe_to_transcript(self, meeting_id: str, notification_url: str):
        """Create a webhook subscription to a meeting's live transcript."""
        token = await self.get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # Subscriptions expire, so we set it for 1 hour from now
        from datetime import datetime, timedelta, timezone
        expiration = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        
        payload = {
            "changeType": "created",
            "notificationUrl": notification_url,
            "resource": f"communications/onlineMeetings/{meeting_id}/transcripts",
            "expirationDateTime": expiration,
            "clientState": "miai-transcript-secret"
        }
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://graph.microsoft.com/v1.0/subscriptions",
                headers=headers,
                json=payload
            )
            resp.raise_for_status()
            logger.info(f"Successfully subscribed to transcript for meeting {meeting_id}")
            return resp.json()
