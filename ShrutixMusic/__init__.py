from ShrutixMusic.core.bot import Shruti
from ShrutixMusic.core.dir import dirr
from ShrutixMusic.core.git import git
from ShrutixMusic.core.userbot import Userbot
from ShrutixMusic.misc import dbb, heroku

from .logging import LOGGER

dirr()
git()
dbb()
heroku()

nand = Shruti()   # <-- आपका main bot client
userbot = Userbot()

from .platforms import *

Apple = AppleAPI()
Carbon = CarbonAPI()
SoundCloud = SoundAPI()
Spotify = SpotifyAPI()
Resso = RessoAPI()
Telegram = TeleAPI()
YouTube = YouTubeAPI()

# ------------- FIX BELOW ---------------
# Export your bot instance as "app"
app = nand
# ---------------------------------------
