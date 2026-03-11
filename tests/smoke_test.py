import unittest
from unittest.mock import MagicMock
from app.db.models import Team, GameStatus

class SmokeTest(unittest.TestCase):
    def test_team_enum(self):
        self.assertEqual(Team.A.value, "A")
        self.assertEqual(Team.B.value, "B")
        
    def test_game_status_enum(self):
        self.assertEqual(GameStatus.FINISHED.value, "finished")

if __name__ == '__main__':
    unittest.main()
