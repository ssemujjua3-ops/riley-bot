import asyncio
import time
from typing import List, Dict, Optional
from loguru import logger

class TournamentManager:
    """Manages tournament finding and automated joining."""
    def __init__(self, client, agent, db=None):
        self.client = client
        self.agent = agent
        self.db = db
        self.last_join_attempt = 0
        # Check interval set to 4 hours (14400 seconds) to catch daily/new free tournaments
        self.check_interval = 4 * 60 * 60 
        self.is_joined = False # State of joining the primary free tournament

    async def get_all_active_free_tournaments(self) -> List[Dict]:
        """Fetches all currently active tournaments with a zero entry fee."""
        try:
            tournaments = await self.client.get_tournaments()
            
            # Filter for active tournaments with no entry fee. 
            free_tournaments = [
                t for t in tournaments 
                if t.get("entry_fee", 1) == 0 and t.get("status") in ["active", "invitation_open"]
            ]
            
            logger.info(f"Found {len(free_tournaments)} active free tournaments.")
            return free_tournaments
            
        except Exception as e:
            logger.error(f"Error fetching tournaments: {e}")
            return []

    async def join_tournament_by_id(self, tournament_id: str) -> bool:
        """Joins a specific tournament by ID."""
        if not self.client.is_connected():
            logger.warning("Client not connected. Cannot join tournament.")
            return False
            
        try:
            success = await self.client.join_tournament(tournament_id)
            if success:
                self.is_joined = True
                logger.success(f"SUCCESS: Joined tournament ID: {tournament_id}")
            else:
                logger.warning(f"Failed to join tournament ID: {tournament_id} (may be already joined or invalid).")
            return success
        except Exception as e:
            logger.error(f"Error joining tournament ID {tournament_id}: {e}")
            return False

    async def join_daily_free_tournament(self) -> Optional[str]:
        """
        Attempts to find and join the specific 'Daily Free Tournament'
        automatically, adhering to the check interval.
        """
        if (time.time() - self.last_join_attempt) < self.check_interval:
            return None 

        self.last_join_attempt = time.time()
        logger.info("Attempting automated join for Daily Free Tournament...")
        
        try:
            free_tournaments = await self.get_all_active_free_tournaments()
            
            # Case-insensitive search for the common name
            daily_free_tour = next((
                t for t in free_tournaments 
                if "daily free tournament" in t.get("name", "").lower()
            ), None)
            
            if daily_free_tour:
                tournament_id = daily_free_tour["id"]
                success = await self.join_tournament_by_id(tournament_id)
                if success:
                    return tournament_id
                
            logger.info("Specific Daily Free Tournament not found or already joined/failed.")
            return None
            
        except Exception as e:
            logger.error(f"Error during automated tournament join: {e}")
            return None
