"""
TODO: add expiration to url
TODO: invalidate urls when plugin is removed
"""
import random
import re
import string
import json

import nio

from collections import defaultdict

from aiohttp import web


HELP_DESC = ("!invite\t\t\t-\tGenerate invitation link for current room. Will direct to a website where people can enter their user_id and be invited by the bot.\n")

OUTER_URL = "https://cyberbot.in.tum.de/invite-test"



def gen_site_content(room_name, inviter_display_name):
    return f"""
<!DOCTYPE html>
<html>
    <head>
        <title>Matrix Invitation</title>
        <meta charset="utf-8">
    </head>

    <body>
        <p>You have been invited to join the Matrix room {room_name} by {inviter_display_name}.
        Please enter your Matrix UserID (Not your display name!) in the box below.
        You will get an invitation to the room the next time your open your
        Matrix Client.</p>
        <form method=post>
            <input type=text placeholder="e.g. @max.karl:matrix.org" name=userid />
            <input type=submit /> (This can take some time (~10s))
        </form>
        <br />
        Where you can find your UserID:
        <br />
        <img src={get_picture_data()} \>
    </body>
</html>
    """


class InviteListener:

    def __init__(self,
            host="*",
            port="8084"):
        self.invitations = defaultdict(list) # maps a random url part to a room + invite creator
        self.is_running = False

        self.host = host
        self.port = port


    async def start(self, plugin):
        """
        start servers
        """
        if self.is_running:
            return
        self.nio_client = plugin.client
        self.plugin = plugin

        invitations_json = await plugin.kvstore_get_plugin_value('invitations')
        if invitations_json is None:
            self.invitations = {}
        else:
            self.invitations = json.loads(invitations_json)


        async def handle_request(request):
            def gen_html(msg):
                return f"""
<!DOCTYPE html>
<html>
<head>
    <title>Success</title>
    <meta charset="utf-8">
</head>

<body>
    <p>{msg}</p>
</body>
</html>
            """

            if not request.path.endswith("/"):
                path = request.path + "/"
            else:
                path = request.path

            random_part = path.split("/")[-2]

            if random_part not in self.invitations.keys():
                return web.Response(text=gen_html("Invalid Link"), content_type='text/html')

            room_id,inviter = self.invitations[random_part]
            room = self.nio_client.rooms.get(room_id)

            if request.method == "GET":
                if room is None:
                    room_name = "Unknown Room (Probably will fail to join)"
                else:
                    room_name = room.display_name
                content = gen_site_content(room_name,inviter)
                return web.Response(text=content, content_type='text/html')

            elif request.method == "POST":
                params = await request.post()
                if "userid" not in params:
                    return web.Response(status=400)
                user_id = params["userid"].strip()
                if not user_id.startswith("@"):
                    user_id = "@" + user_id
                room = self.nio_client.rooms.get(room_id)
                if room is None:
                    return web.Response(text=gen_html("Failed to send invitation (Bot is not member of the room)."), content_type='text/html')

                res = (await self.nio_client.room_invite(room_id, user_id))
                if type(res) == nio.responses.RoomInviteError:
                    return web.Response(text=gen_html(f"Failed to send invitation: {res.message}."), content_type='text/html')
                return web.Response(text=gen_html("Check your matrix client for a new invitation."), content_type='text/html')



        self.server = web.Server(handle_request)
        self.runner = web.ServerRunner(self.server)
        await self.runner.setup()

        self.site = web.TCPSite(self.runner, self.host, self.port)
        await self.site.start()

        self.is_running = True


    async def register_invite(self, room, random_part, inviter):
        self.invitations[random_part] = (room.room_id, inviter)
        await self.plugin.kvstore_set_plugin_value('invitations', json.dumps(self.invitations))


if "il" not in globals():
    il = InviteListener()




async def register_to(plugin):

    if not il.is_running:
        await il.start(plugin)

    async def invite_callback(room, event):

        def gen_random_part():
            #TODO: check for collisions
            chars = string.ascii_letters + string.digits
            n = 32
            return "".join(random.choice(chars) for i in range(n))
        def gen_url(random_part):
            return f"{OUTER_URL}/{random_part}/"

        random_part = gen_random_part()
        try:
            inviter = (await room.client.get_displayname(event.sender)).displayname
        except:
            inviter = "Unknown Inviter"

        await il.register_invite(room, random_part, inviter)

        await plugin.send_html("Send this link to the people you want to invite to this room: <br/><pre><code>" + gen_url(random_part) + "</pre></code>")

    # Add a command handler waiting for the corona command
    invite_handler = plugin.CommandHandler("invite", invite_callback)
    plugin.add_handler(invite_handler)









def get_picture_data():
    return """data:image/png;base64,
iVBORw0KGgoAAAANSUhEUgAAAj4AAAGICAYAAABBSepZAAAABHNCSVQICAgIfAhkiAAAIABJREFU
eJzs3Xd8U2Xfx/FPVmfSSSll7yFlFChTlKmiooiAiKgIigoKDlSU4R4oiCgOVEQcj7egoiBDZciQ
VcremzLaUgqd6Upznj/SpE1n2iYd9Pd+vbxtknOu6zq9TfrNtY6qRYu2CtVYlqqyWyBENVKt3+3V
R2pKcmU3QQhRBHVlN0AIIYQQoqJoK7sBQgghXMfNzY2OHdrTsmVz2oW2ZdjQewD45bdlHDh4iOPH
T7J3334yMzMruaVCVAyVDHUJUYNU63d79VEVhrq6hnfhi88+xsdgQKUq/oNSURSSkpN5YsIkdkbs
qqAWClE5JPgIUZNU63d79VFU8ImLjpJPLCEqWTmGulRo3bS46dxRazSo1Go0Gg0A2dnZKGYz5uxs
MrMyMGWaqG6fuCqdN7q6N+DeqCsaQxBqQ220hiAATMlxmJMvk50cR8a5nWRdOoySlVrJLRZCCCFE
SUoffFQqvLy8cfPwKPIQjUYDGg3odLbjMtPTMRpTQanaAUijr41Xp+F4tupT5DFaQxDkhCDrcWnH
/sW4eynZKZcroJVCCCGEKItSDHWp8PDywsPTs1wVpqcZSTem4aweIGcNdal03nh3GY5X6B3lKic1
cgnGA6ukB0hUTVX7e8d1Q4a6hKi6HFzOrkLv61vu0APg4emF3tcXqDrvf5XOG//Br5U79AB4dx6B
/+DXUOm8ndAyIYQQQjhTicFHrdHgG+CPVuu8le9arRbfAH/UOXOCKpM2sDGB93+KNrBxlS5TCCGE
EOVXQvBRYfD1RaVy/j6HKpUaQyX3/Kh03vjd8Rpqd+f3zqjdLWVLz48QQghRdRSTaCzDW64IPbYa
VOpKG/ayDm+5IvRYqd29ZdhLCCGEqEKKTDUeXl5OHd4qilarxcOr/HOHSsu7y4gyD0WF+OjYMaUN
Hw5tUOKx2sDGeLUr/9whIYQQQpRf4cFHpSrTROZOYR3pFNax1Od5eHpBCTuLOpNGXxuv0NsrrD7v
zsPR6GtXWH1CCCGEKFyhwcfLq2xDM507hdG5U1iZzi1rnWWqq/OICqurLHXedecd9Otzc6nruLFn
DyaMf5QR995T6nOFEEKImqCQ4KMqdnNCV7HU6fpeH5XOG8+WpQ8V5eXZ8maH5vrUCQ5m3pxZLPh0
nm0nbEc89cR4vl/0FS88/wyPjHmoPE0Vwika6fV80bsHjQ36ym6KEELYFJjEo3WrvBu2a920mDKz
XFqHrl5bl5ZfUt2ZZ3cWe0xMbCzPv/gKySkpZGdnO1z2mIdGA3DPiFGcOXOuXO0Uwhle6dSeW+rX
pVed2ty1Zh1nklMqu0lCCFGwx8dN514Z7aiwut0bdXV5HeWt+7c/lvPPuvWlKjswMIDk5BT27ttP
YlJiWZonhFO9s3sfKVkm9Dody2/rT2O99PwIISpfgeCjUlfepoIVUbfGUMvldZSnbo1Gw5ljB9m9
fYvtOV8fX95983W2b17P0f2RrF6xjJHD7wWgXWhbzhw7CIDBoOfMsYPM/eA9AFQqFY+NHcP6v/7k
6IHdbFy7hslPT8DNTeeCqxPC3rmUVAavWUtqTvh5o2vZ5v8JIYQzFQg+ao3r9u0piUrt+jk+6kpc
XaV2K9sE7m+//pyRI+5l0+YtfDhvPhqNhnffep0hg+/k0qVo3nzHEnQyMjJ48533+O2PFQC8Nv0V
XnlpCmfOnuPjTz7j2LHjPPPUBN5+/VWnXZMQxTmbnMLu+HgAOgUG0kTm+wghKlmBCT0lTagtbsl6
p7D2ADw6dkyhr+/es5fde/YW3ZiK2Dco567qlaEs+wap1WremTUbDw8PNv+3FYCoqAt8Pn8ufW6+
kd9X/Mk3i39gxitTycjM5JvFPwAQXLs2o0fdx7btO5nw9LO28hYvXMDQIXfx3gcfEn/1qlOuS4ji
zNi5mz8HDUSv07Litv7si79Gpjmb1yP3cdZF837atGnFqj9+5Z+16xk/YRIA+yK3oSgKHbv0BODL
zz5m4IB+9O57CxcuXnJJO4QQVU+ZkoaqiD13rM8X9booPbPZzKnTZ7j9tlsYfMebNG7UkJYtWwDg
5uZW5HntQtuiVqvp0b0rRw/sLvB6w4YNJPiICmEd8lpx2wD0Oh0961h6XcODahERd8WlASg/+WwS
QhQIPtnZ2cX2+hTfa/MIAF8tXFSmxphMpjKdV6o6UuLQ6iun18cUf7bU5wQF1mL1it8wGAys27CB
dRs2sv7fjbw05bliz7N+vP+zbgOfLfiqwOsnT54qdVvE9amRXs9rXTqgQsW++KsoQKi/H4euJZCW
nY2HRlPkYwUICwxAo84dIjeZzRxLSKS1n6/d84evJVDXyxODTofeTYe3TkefuiH0DqnD7stX2BN/
lWY+BvZdvcb3x0+RkJlZ5ms6cuQYTVqG2j3XoXMPu8fWniAhRM1SIPiYs82l2j/GmRSz4vI6zMmX
oZzBx01riRWm7NK115yZWuq6unfvSmBgAAu+/ob3PvgQgGH3DCnxvENHjqIoCi2aNeXQ4SNkZVm2
CXjogfsxm80cOXK01G0R16dXOrWnT90QAG6uW8f2fP/6de2OK+lxXnnLKYlGpSI8OIjw4CBbuU+0
aUVsWhqTt+7kwNVrDpclhBAlKRB8FHM2UDmrfix1u1Z28hUIcezYr0Y1pq6vjru+OEHejNM4wLLs
Pi61dD1U2clXSnU8wNlzlj15br/tVq5cicfDw4PR999X4nmXoqP5eelvjBxxL7/+7wfWbfiXli2a
c/ttt7IzYhc//PRzqdsirk/v7N6Pl0aDTq3mcIJlK4QWPgZOJCWTkZ2Nu0ZT5GOANn6+6PL1+JxK
TqGpQV/k8yrgVHIKN/j50i7QH02+ISgvnZYmOgMf9AjntpV/u/6XIISoMQoEn8ysjErZudlat6tl
nNvp8M7NUVczaV/Xk3E9g/jyvzgA9O5qHuluWZa+7Uzp5iVknCt+88LCHDh4iOmvvsH4R8cy5bnJ
HD58hPc++JC5s98r8dxpr77OhQsXGDZ0CE8+/hjXrl7jux9+YvbceaVuh7h+nUtJ4cENmyu0ThVw
Y0gw9bw8OZ2YRHM/X9vwrAKkmUzEp2fwwraICm2XEOL6p2rRom2+8RoVfoGBZSrssXHlm+OTEB+P
5WPPcVmlnKuo0nkTNOZbh46t66vj29FN8PXUcCkxi+ikLFoEuePjoWH72VQm/xJVqrrjvh2DklX8
cJevwYe9u7YSG3uZ7jf1K1X5QpTI9aPJxWps0PNO1040MRio45V7I2QzcOxaAvHpGczad4CDVxMq
r5FOkJqSXOjzcdFRMrtaiEpWyKouhcz09Arv9clMT6ciPpWVrFTSjm90qNfnUmIWD31/hsd7BdGt
sTcd6nlxOTmLX/Zc45vtpRu2Sju+scTQA9h6cg4ePlyq8oWoqhob9LzauQNuag0dAv3x1lmG0mOM
acQY00jJyrouwo4QonoodDm70ZhapuATuXtPmRtiNJZ+4m+Z64pc4vBwV0xSFq+vLv8eH8bIJQ4d
F96lM/9u3Myrr79T7jqFqGyBHu78PKAPtT1zP09SskxM3LKNzdGxld0BJYSogQrfx0dRSE8z4uHp
VarCitucsDjpaUZQKu4jMDvlMqmRS/HuPLxC6kuNXEp2ymWHjm3XuZuLWyOEa1nn74xr1YK2AX7U
8vDganoGZ5KSScvOZsauPRW2b0+uwj9fKvBjRwhRRRS5gWG6MQ2tzs3luymbTCbSjWkuraMwxgMr
cW8cXqbdlEvDFH8W44GVLq1DiMpmHc4yuLlRz8vLbv5OXFo6g1b/Q3y66xcv5LIkmsoKNookKiGq
rEImN9u9jG9AgMt2O1UUhcSrVynP3J7STm7OS6XzJvD+T1G7l+0eWiUxZ6QS/9NEh+b2CFEhnPz3
2Bp4woNq2ebugP38nYrr4Skp7Kiw+wXk/+xw4u8mNbWie7RyqdUqavkZMJuzURQFs9mM2WwuEMby
PzZmZJNtVlCr1XTt2p2uPXvi4+PP2jUr2bFjm4Q54XwF/pOyPKGy/Y/dD05TQvABtUaDwdfP6eFH
URSSExMwZ5dv757yBB+w3D/L747XnB5+zBmpJKx8rUy7NQvhMk7422Xd6Tn/ZGWjycSeuCssOHqS
LdExFTh/p6jAkxN08uWd/Oe5gjGl8oKPlVarweDlDii24GMNLyqVqsBjs1nBmG6SeVfCtYr8m63K
/W8vzw+5Ich5GaTE4GNtkN7X12nDXiaTiZTERJzxwVPe4AOWnh//wa85bdjLFH+Waytek54eUfWU
8y3XSK/n11v6EJhn8YPRZGJ33BVm7NpbKXN37ANPYSkn57GiyvMv1/55N1Zij09htGo1apUl4Ljp
LJtKZmTm9AgB2RWwa74Q9vL88VasjxS7nh4l5ynbIycFIAeDj6UyDy/PUk94zi89zZgzp8c5bzRn
BB+whB+vdneUe8JzauRSjAdWSugRVVM53naN9Hp+GdiHWjkrtNJM2UTGXanUycpFj74ogAoUUFQ5
vRpK7haJttPy7proREZj1Qo+QlQVtj/ZiqrAC0qe960l4+S8z3Oec1YPUCmCj/UMFV5e3qVe7p6Z
nm5Zsu7kcWJnBR8rjb42Xp1HOLzc3Srt+EaMkUscXr0lRKUo49vPz82NpQP70NzXB4BUk4n7126s
tPto2c83UVk+IK1fDxWVXdjJjTk5H6rWH+2+XYIzvklapVXg9hxCVB9Kvh8L9sKqbD2zlver5V/2
Aai8vT+lDz65p6J10+Kmc0el1qBSq2xDYSaTCcWsoJizyczKwJRpwulfqXI4O/hYqXTe6Oq1xb1R
VzSGWqjdvG1DYab4s5gzU8lOvkLGuZ1kXTwkPTyieijj23Bs6xbM6NQBgPj0DO79ewPnKm0eS/7h
rbyv5HwoKnkuNeeD0/KhqdjNmXTVfN20NKNrChaiGiryz7SSJ9CorO9dlS0IqRSV7b2rsnsfly/8
lCP4VA2uCj5CXJfK0ePzaOsW3ODvx+uR+6pY6Mnt5ckNNTkfji5akSqEKB+zWUFRsjGbzZiyssg2
my3vX0VBUamw9NVa5uyprO/vPEGoPOFHgo8QNUm1frfnDT3WScx5Qo+iApUKyTpCVC+KopCVlUVm
Roblna0ClTUAKUrO4+LCT+ne9GrXXIYQQriQKnellqWnR4VKLaFHiOpIpVLh5uaGl5cXKo3aMgSm
Utm+3uSGoZz5e4rK1ttjHSwrDQk+QohqIN8Qly33KGBWyZCWENcBtUaDTqMld08f6xu9mPCTm34c
r8eZjRZCCNfKtyRdUaGSTzEhrhtaNzfUGjW2VV62leyKZd6PyjrnJ+cEFba5QI6SjwwhRJWX29uT
O8Rl6epWpLdHiOuISqVCp7P0+qCocjceJWcELGdvLusKMFWeXiFHufYOpEIIUW4Fd2LOmd8oc3qE
uA6p0aCyfduxDmXbNquwUHKGviyHWEJR3r26ii1fCCGqBZXdv3O2N6u01gghXEOlUZN3c0PFtrTd
strLOuSFrdcHHAk8VtLjI4So0goOc1kCj1KGZaxCiKpPrVbn3r4CsN1+Jt973rphu90kZwc+EiT4
CCGqBxU5m5th28JHCHF9s25qmLO1c+7tZqwJJ282yn8XmiJI8BFCVGGF3dvHertmST5CXK/ybshs
fetbNy+0fg7Y35am0AeFkjk+QohqIPcTUKVYP/RkmEuI65mSs3+XyraDs4KiqHI6fK0ze1S2/3V0
nk+N7/HRaXV4eHqi1WhRa7Wo1ZIFhXA2s9lMtslEtimL9PR0srKySllC/t4dF95hVAhR6XI7dyxh
xxJ+cla324a+rHN/HF/RBTU5+KhU6L30eHh5yT4gQriYWq1G7eaGzs0Nd08v0oyppJbhRqfWDz21
So2nlwdp6enOb6wQotJZNym0blth7eO1DIHlfPFR8s3zAYcmONfI7g2tRkeAfwCe3t4SeoSoYCqV
Ci9vPX6BgWi1OgdPsv6g4OWlxy8gADd3D1c1UQhRybQ6jW14C6xByLKhYdu2N/Dh7Fms/2cVf61e
zlMTHrecpIJWrVoSff60XVnD7r2HDWvX2B7XyODj7uGBxtEPXCGES+i0Otw93Is9xn40S8HX1w9P
b0/LI/nSIsR1q1mzZjk3KlXZRrYA/P39mDltKjsjIhlx/4O89Mp0Hrj/Pm4ZOMB2rlLCMHiNG+rS
aXV4enlVdjOEEICnlzcZ6RmYTCXP+fH09ELr5pZn33qZ4yPE9crHx8cyapXnfa5S4GrCNR57YiJJ
ScmAwpX4K2zfsZNOYWH89c86h8quccHHw8NThreEqCJUKhWenh4kJxcffDRqLd56A2brPZsl8whx
XbMMR1m3rrCfuqPT6bj3niG0adOSpk2b0imsI7//viLvGQ6UXYNodDUu6wlRpWm0Jb8n3T0Kmc8j
4UeI61aeXXrs5io3atiQDz+YRaNGDYjYtZs5cz9m1eq/ih3eyt/ZUeNSgMOTKYUQFcKR+Xa6PF9Y
lPwbGQohrjuK9VZcWHdvtjzfsUN7Tpw8xYcffYI1HgUHBxN1LgqA5KQkAAICArh69SoAjRs1tCu7
xvX4yDCXEFWLI3tnyWIEIQRAbOxlGjVsQLvQttSpU4dHx46hY4d2ttejY2K5cOEir05/mfr16nLP
3Xcx+oH77cqoccFHCFH9yMaiQtQsiqJY9mNWWXfvsfy8c+cu1vz9DzOmTWXhl58TGBDImr/+sTtv
wtPP0KF9O/7btJ5h997D/E+/sCtb1aJF22rdX5xVyg6coNp1XNMQIUSZxcXGFPq8ddy+Vu1gUBTM
KChmBUVRUMxmkhITKrKZQpRaI72e17p0QKfWFHjNZDaz8NhJtkTHyMBtPqkpSWDdxJCcxZzWO9fY
3bPUus9PzhYXilLiyE6Nm+NTHqGh7Qnr3IXg4GAAYmNjOXjwAIcPHiAjQ3aQFeJ6cNutA/Fwd+f3
5X+W6rymTRrT56beoFKxdt0Gos6fd00DRbXR2KBn6YA+1PIserPNm+vWIcaYxkWjkeTMTF6P3MfZ
5NLvai4cJ8HHAe7uHowYOcoWeKyCg4MJDg4mNLQdf61eyeXLsZXUQiGEM9SrG8Lnn8wF4OSp0xw8
dNih83p078rihV/aJmEfPXZMgk8N18SgZ/lt/dHrLPPTEjIyOZWUbHeMRg11PL2o4+VJHS/Lxpzh
tYOIuBwnAciFJPg4wBp6MtLT2bB+HVFRUWRkpNOwYUP69BtAcHAwdw0ZyveLF5W658fX15+wLuHU
CqqNgsLlmGgid+3EWIb7GJXVsJGjOXX8GHt2R1RYnUJURZeiY/jy60V4eHhw7Phxh897bOwYdDot
O3ZGsODrRUTu3uvCVoqqLm/oMZpM7I67wvSIvZwr5HNdBdwYEsz41i3pVCsQb52WPnVDJAC5kASf
EoSGtreFni8XfG4XbE6cOE5UVJQtGHXuHM7WrZsdLlut0dB3wEAUVBw+sB+1RkPL1q256eZ+rFm5
3BWXI4QohqIovPv+nFKfV79+PQDWrv+XDf9ucnazRDUS6u/HTwNuRq/TkZJlYvCatcUGFwXYHB3L
5uhYGhv0vNklzC4AdQkKKrGM0jDo9XToGEbvm24ipE4d6tQJISQkBIDo6GhiYqKJjolh86ZN7Nu7
h+QK/BJeUWRycwkefHgswcHBrFm1koMH9xd6TIMGDbnv/gdISEjg6y8/d7hsP19/Bt01hD2RERw9
fBCAOnVCqFuvAfv27SbbZKJR46aEtu+Il96b+Lg4IrZtJTnFsk9Bw0aNCe0QhrdeT2JiIvsidhJ7
OYZWN4TSqXM4eyIjCG3fkf82biA+/gqdu3ajbv0GmLPNnD55nH17IgFLj8/Z0yfx8tYTXCeEa1fj
2bp5I0Zjaql+V0KUVVWZ3BxUK5CdWzcCcOsdQzh+4iQB/v688Pxk+t58E/4B/kRHx/D78j/55NMv
yM7O5szxgwXK6dC5B0nJyQy6dSCPPzaOVi2bk5aWzn9btzFrzkdcuHDRqe0Wla+RXs/cnl3pUCsA
NTgUeoqSNwB56bTlKssqpE4dxowdx+2Dbi/VeatWr+LbbxYSHVP4e9RVXDm5WdaIlsA6rycqKqrI
Y86ft7zm5+dXqrJTUpIxGo20aNWGps2a4+HlRUxMNLsjd5JtMlGrVm163HgTV65cZvvmTejcdPTu
1x8ADy8vuvXqzbWr8Wxev5bsrCx63tzXrvz6DRuze9dOkpIS6Nn7ZurWb8CBvXs4efw4N4S2p2Wr
NrZjGzVpxrX4qxw7cphaQbVp1yGsVNcixPXq24VfMHLEMFJTU1m1+i8C/P2Y/NSTvPD8ZAD+XLma
lFTLl4RDh4/w58rVZGZlMWzoED77ZC6tWjZn46YtnDp9hjvvGMQvP32Pv3/pPitE1fdm1zDCagUA
sPdKfLmCytnkFB7csJk716wlJSsLvU7Ln4MGsKhPLxob9KUqy6DX8/TTk1iy9NdShx6A2wfdzpKl
v/LII2Mx6EtXd1UlQ10OcsWqLVO2ifV/raZdWCc6hXenq1ZL3OVYdu3YTmLiNZo0a056eho7t21F
Ucykp6UzYNDt1AoM4kp8HL/89CNqlQovb2+Sk5KoHVwHLy9vW/k7t24mKSkRT08vQurW4+C+vRw/
apmsaTQmk5aWZjs25tIFDuzfDUDtOiH4Bfg7/XqFqG48PDxYtPgHfH19+Hnpb6SlpTH5qSd5ZtJE
evfqyXt8yNPPvsC6NSvQN23Cb8uW883i71GpVLzwnCUYPfvCy+zYaZk/N+vtNxg4oB/Dhg7hq4Xf
lro9of5+PN+hbaFLox2RbTZzNCGRVn6+aPPtjZRlzpb5JGVgXa7eJTAQgB2xcYxat9EpZZ9JTuGu
Nets84VKO/Rl0OuZ9/F8WrRoUe62jB07jt69b2LypKeq/fCXBJ8SxMbGEhwcTMOGDTlxovDJjrVr
W3qFMtJLH46SU5LYuvlfVGo1wbWDad85nAG33c7yZUvx8vbG3d2De+8bBeR283l6e6FN0tK5S3ca
Nm5CVlYmmRlZOcfkfphlZGQA4OVpCUPJSYm2107lu5b0nGMBTFmZ6LRyB3sh0tPT2bEzgjvvGMT7
77xBo0YNadWqJQAe7u5FnhdSJ5jatYMAbKvE8mrWtEmB5xob9LzSsT1nkpMLDSa+bjpuCPAvdzf9
TXWLHu4Prx3Evrh4y5BBPnlDk4IiIQlL6PllYO5y9ZQsEy/v2OXUOs4kpzB4zTrb0Jdep2XFbQO4
c/U/nEspejpCixbNmTdvPgaDwWltadGiBT8v+YXJk5/ixImTTiu3oknwKcGhQwcIDg7m5r79bau5
8uvbfwAAkbtK9x98nbr1aBvanojt20hKSiAmJhr9yROEd+2OXu9DWpqR9PQ01v29Bsi9X0laehpN
m7ekSbPmrF2ziitXLtOyTVs6d+laaD3GNMubw+Dra3uueas2pKWmcPGCLLkVoihNGjdi+bIl6L29
2RGxi42btnD02HGG33tPseflnWMw6bkXbfcMsrp8Oc72c2ODnlc7dyA8qBbeuuJvzWEGjlxLwGjK
Lv3FAFlmM6eTU2hm0BcIVm38fPHWaekZElzE2fahyRqSTIpiC0RAjdqQb2aXDrbQE5+ewbB/NhQb
RsrKOvTVxKBnxW0D0Ou0vNm1Ew+tL3wxjUGvd3rosZVtMDBv3nzuGzGs2vb8SPApwaEDB2jbth3B
wcGMGDmKf9evtc3pqV07mD79BtCggeUGaAcPHihV2cmJSfgHBHJT336cPnUKjUZLi1YtMRpTSUy8
xtlTp2jWvCWtW99AbGw0TZo2JzgkhBXLfsNsNqNSqfD198PNzY0WLVoVWU9ampHoSxdp1botmZmZ
uLt70LZdeyJ2bCv7L0aIGqBvn5ttoWfkA2MAePnF50s8Lzomlri4KwQF1cJHr2fFn6sAePGBkQz2
cCOxThAJDeuhAjoE+tsCT6rJxB9nomjmYygQTNJMJmbtO8DBq67Zrdo6odZTW/ifhbyhqV2Av11I
yhuI8m7Il5qZVWBorbjhtsLo1GqCPNy5nJ6ByWwu9Py8z6mAPfFXc363ASgozNl/yCW/t4NXE+hX
N4TTScmM/fe/QperO9OZ5BR2x8fTu04wnWsFsqhPrwI9b9bhLVeEHlsdBgPzPp5fbYe9JPiUICMj
nb9Wr+Tue+4lODiY++5/oMhj775nKEv+938OzwdKTU1m0/q1tO8YRpu2oSiKwtUrceyJ3IU5O5vL
l2PY/t8mbgjtQNPmLUlKTmTrpn9JTzdy9tRJQkLq0alLN1JTkjkfdY627doXWde2zRvp0q077dqH
kW3O5sihA5w8frTUvw8hahLrooawjh2Y9c4buLu7079fn2LPsfbgJM2fT1DTJrzZrBHPTxyPh2LG
MykJ0ozU93CHOrVt51j3epmxa2+lDR9ZexUckTck5Q1E7lp1gQ35ChtaK264rShNfHL/kJdUZv7X
b6obwuGr17iSnu7UIbpFR0+QkJHBsjNRJGRmOqXMkszcuYcVg+zn/OQd9npk7FinzOkpSYsWLRg+
fATfLPrG5XU5myxnd5C7uwedO4fTtl07fHOGjDLS04nctYuDBw9w9z1DCQ4OJjY2tlThRwhRtZez
P/P0BEaOGIafny8Ru3bzz7r1vD5zGqdPn6H/bYMB2LTkRxocPMCZU6epnZlR5JCVolJx1pjG1TzD
IWkmEzN27blu5svk3ZBPq1YXGForbritMFo1BLh7cDUjA5NZKfT8vM8pwJEEy3zGG/x8MbjpaO3v
Z5sblWoyEXk5jqMJSTTzMXAqKbnQnqK8batq85uswbNzUCCeWi2bYmJ5eP1mQurUYcnSXyu0LSOG
3+uSpe6uXM4uwcdJ8t7WIjY2lu8XV78ULERlqSrBp2mTxqz7y3KPrpv7DyrxthPWVVb55+cYTSaO
XE3I/aTG9UNVomih/n681LGdbV+c8sobnqyh6WhCYpFBqktQLUK8PLm5FPexAAAgAElEQVRkNDJt
5x6nDYktGdiX8KBAdsbFc98/G3jl5WkMut2xJevnz0fx0ez3+GvNShITLUHR19eXW2+7g2emTLVN
4SjJ6lWreOfdt8t8DUWR4FOMqhJ8IDf8ABJ8hCiFqhJ8NvyzisaNGhJ/9Spde/bBbDYXOMY6lFXL
w8NulZU17KRlZ19XPTjXE2tPibUnqqG3F1GpxkJ7ivL2+OSf31Se8PT3hUs8vmlreS8FgO/69aZ3
nWBSs0zct2krX/yyzKHzvv7yc16f+bLdc9173siF81FcyJnD+tqb7zLusScdKu/2Qbc6fa6PBJ9i
VKXgI4Qom5KCT0CtINQqlcuDz8E9Ozl85CjvzprNnn25O7Vbw46bWmM3GdkMHLuWQHx6hoSdGiJ/
eLKGpuKCVPsAP2p7enIx1cjUHZFO6/FprNfb5vukKQqJox7B5Ff8HmyFhR6A8zGW99Jfq1fy3OQJ
JCUl8uob7/Lo+JLDzyuvTGXzZsdv1+QICT7FKG3wCaxVG7UD48pCiIphNpuJj7tc6GvW4OPr54dO
5+by4JNXUWEHcicjz9p3UIauRKXKe0NUs5sbl4c9gMm38J3Bz5+Pome4/SKY+g0aMjxnr7jh942i
QYOGJCYm0jO8PUlJiWyN2F/isJcrhrvklhVOlJ2VVdlNEELkYXLgPZmVZaqAlljmgizq04sf+93E
n7f1p0/dEHrWqY13zl22Iy9fYUt0LHesXsuDG7ZI6BGVzrq7s0mjQZ2Zid/mDUUeO3f2e3aPh983
im0R+3luylTmzn6PnuHtWfLz/+Hr68uH8z4r9JzChIRUr5GUGrecPctkQlfMjqtCiIplMpUcfNLT
0/Hw8AB1Kbt4HZT/BpNWMm9HVAdnklNI9wtEH38ZVXbRXxL+Wr3S9nP9Bg1t4Sav5ydPoEfPG7l1
0B3Ub9CQv9esLHBMft561+0Z5Ao1Lvikpxnx9PKmhJ4wIUQFUBSF9Dz3jCuKOduE0ZiKl5Nvkmgd
zmoXEECgh7vdzsjX2zJzcX3TubuVeExSntsWWYe3CvPX6pU8Ov5J6jdoyPatW0ostyL2DXKmGhd8
ss3ZGFOTq11CFeJ6ZExJITvbsdsvpKcZcdO5oSnhtg6OKGoZujNvMClEhbKuQCxkJaKwV+Pm+AAY
jakOda8LIVwny5SF0Vi6+xolJiWQnmYsc52NDXp+u6UffwwaQJ+6IQXm7ry8I7LMZQtRqZKTANAU
8/7w8cm9X+MvP/9fkcfdOugOAC6cj7I7pygnT5xwtJVVQo0MPgDXrl3FmJpqWzUihKgYiqKQlppC
Qr4bdzrKmJpKwrWrDg2R5WW5wWN/wmoFAJYhLetE5WFr/+XBDZtdfq8lIVwlRWMZwMn2Lno42Bpo
wLLC6/nJEwocM2feZzRo0JC/Vq/kwvkou3OKrDsluQwtrjw1bjl7fjqtDg8PT7RaLWqtVpa6C+EC
ZrOZbJOJ7Ows0tPSyXJwdaX9F5OchatK7msajcahcvIu+U3JMnH/2n85eE1WZInrx4onHiM06Rop
7cNI6NWn0GMKW87eIGc5u4L9cvZeXduTmHh9LmevcXN88ssyZZGVIsNeooao1l9zSs86edk6lycl
y8TgNWudPmHZy8uTVct/46f/LWXB167dtX3CE4/x8OhReHi407vvrSQll//b9ttvzMTHYODpZ19w
QguvP0t/+p6Nm7cw/7MFld2UIqnjYsHdDd3V+CKPadCgIa++8a7dBobnz0fx4ez37DYwfP6ZCSQm
WjYwdOTWFZu3bCr/BVSgGh98hBDXp7y9PECpQ09gQADDhg5h4IC+hISE4O3lxbWEBHZG7GLx9z9y
+Mgx27Hp6RmsXLWGffsPuORarNq3C+WF5yYzcdJzHD5y1Cmhx1H9+t7M55/MpVVop3KVs/y3n1m9
5m8+/3Khk1rm2nKri7SUVHB3K3Fys3Un5vy7N48YeicXzkdxPueWFY7u2gw4fddmV5NxHSHEdSdv
6DGaTGyJjilV6LmxVw/WrFxGkyaNeOvd9xk4aDAdw3sy6sGxHDl6jG+/XsDjj461HW82m/ngw3ls
3xnhqksCoFatQDKzsli15m/OnotyaV2ieskuxWquR8c/ydaI/Qy/b5Rt8vK2rVtITExk+H2j2Bqx
3+HQs3rVqjK1tzJJ8BFCXFfyz+ex7rLsaOhp1rQJn8//iJmvvcXUaa+yd98BjEbLROromBi+/e5H
hgwbycMPjeLO22+znbduzQoeGDnC9viWgf1ZtvQnDu+LIGLbRt56fQaenp52x499+EG+/PwTDu+L
YNvmdUx44rEi2/Xe26+zcMGnuOl0nDl+kOW//Wx77aHR97P+75Uc2b+Lv1b+zrChQ+zO9fT0ZOb0
qURs3cjRA5H8/ONiwjp2KFDH5KeeZNf2TezfvZ1PP/6QAH/LfZ9emvKspW43N84cP8jCBZ8CENah
Pfsjt3HHoFttZdx/3zDW/72SY4f2sHHdakaNHA6Ae8657ULb8uKUZ20/F/a7A/jys4+ZOe2lcpUb
4O/Pm69NZ8eWDRw9EMmypT9x8003Fvk7BrihTSt++v4bDu+LYMeWDdxz9+ACx+T9fR7Ys4P//bCI
Lp3Dii23qmmQs4HhoePnOB+TwPmYBA4dP8eHOZObHbVoUfXrYZPgI4S4buQPPWWZz/PCc5P5Y/mf
rP7rH3Q6LS9NeZYN/6xi/d8rmTb1BT79+EMuRccw49W3eGnKs4WW0S28C5/Om8MfK/6kz8DbGTPu
CXp078YzT9uvonns0TF8+90PdOzSk5env8YzT0+kf98+hZY5beYbPD5xMpmZmbQO7cS99z0AwMQn
xzP+0bHMeO1N+t1yJ/M++YxpU1+wBQOABZ/No3t4OBMmPcuA2wYTuXsPPy7+mrp5bjVwY6+eeHh6
MHT4Azzy6JO0vaENM3KCx+y5H9vV/fjEyQCkpKZyLuo8CYmWjfF69ujGq9Nf5t1Zs+l+Y19ef+s9
Zk6bSliH9mTknHvw0GHmfPQJrUM7ceDgIYf+PylrufPnzeGGNq159ImnuKn/bazb8C9fzP/IFujy
q107iJ++X8Sp02e47c6hjB0/gXuGDKZF82Z2xy34bB4tmzfn4XHjGTR4KBs3beHHxQtp3aqlQ9fj
bI303rT1s/TcXIwp/Ia/rrDom4VEV2B9ziJzfIQQ1wVnhB5vby/69r2Ze4aNBOCNV6fTpHEjHnvi
Kby8vHjj1ekEBwcBsP7fjXz4wTu0atmCY8ft9zHZEbGLHr37cyXeMtH08uU4Vq3+ixt79bA7btnv
K9i6bQcA/27czOYt/9G9WzjrNvxboG3Z2dmYTJbbEWRkZgKW3o4nxo/jkUefYFfkHgCi18QQElKH
0aNG8n//W0rnTmH06NaVfrfeyfnzFwB4f85HnL9wAS8vL1v5Fy9dYtYHcwGIOn+ezxd8zbOTJhZZ
N8CJk6cYfE9uT03DBg1ISEhk05atZGRksH7DRsK63khaztYDGZmZKIpCtslkV05JylruI489iVar
ITXVsrfNl199w7OTJtIu9AY2bv6vQD2jRo4gJvYy01990/bcM8+9xNZNa22PO3cKI6xjB8J73Ex6
ejoAn3+5kE6dwhgxfChvvFXyva2c7Y2unfDWaUnNMjFp4yam9LuN5i7eTfnkiRMsXbrEpXW4igQf
IUS154zQA9Cgfn3UKhVHjh5H7+3NsKFD6HvLHVy4cBGAjz75lHffeg2wLKe/eCmakJA6BYIPgMGg
Z+g9d9GyeXPq169Lu9BQzuWbl3Px4iW7x9euJeDvV/idtQvTtGkT9N7efPnZJ3bP69x0qLAs6W0f
2paoqPO20GP108+/2D0+c/ac3eO4K1fw93e8LQCr1vzNmIceYMuGv9mwcRPbd0Twz9r1pSrDmeUq
ZjO9b7yJTh070LhRQ5o1a4parca9iPs13tC6FXv27rN77uq1a5w6fcb2uH1oWzzc3dm6ca3dcV5e
nmzZuq0MV1c+jfR62ub0YB1OSOTQ5ctMmvQUS5b+gt5FdyhISUlm0qSnSK6m+15J8BFCVGvOCj0A
/v5+JCQmoigKQUG1MCuKLfQAXLliv1RYp9MVuifRoFsHMuf9d1j2xwr+27adc1Hn6dWjO4NuHVim
dpXk4XGPExd3xe452/4mKhUqR/Ync8JmrklJSdxx9zDCu3SmR/euPDR6FK9MncL9ox/hxMlTpSss
z14sZSlXp9Oy5KfvcXPTseyPFWzfGcHxEyf568/fi602I6NgT1T+/d1iYmIZfv9DBc/NzHDkypym
sUHPkoF9CMy5T1d6zg1Kk1NSmDTpKT7+eL7Tw091Dz0gc3yEENVYuwB/Vt8+0CmhByA11Yje2xuw
hBytRmM3DybvzwBBtWoRExNboJx7h97Nn6vWMG3mGyz7YwW79+zFz8+nzO0qypmz5zAa02jZojkx
sbG2f/z9/fDOGcbaf/AgDRvUp2GDBnbn3n/fMJo1a+pwXYqioFIV/ycjwN+fBvXrsX3HTubOm8+Q
YSO5dCmae4febVeOOt/GkwmJiQQGBtg916Rxo3KV26plSzq0D+XRxyfy1cJvWb9hI0lJyXh4FN7b
A3D4yFF69ehmtwFe7dpBNG3axPb40JEjhITUQeems/udN27UEHUJvx9naqT3ZsVtAwjy8AAgPj2d
GTv32F4/ceIkI4YPc+rtJE6eOMGI4cM4ceKk08qsDNdNj8/Z44fkfutCXMcaNW9ToEvio55dcddo
yDSbnbIx4anTp9HpdDRv1pSTp06zcdMWXn7xeaZMnY6fny8PP/gAQbVqUb9+PVq2aE5WVpbdMIjV
yVOnuXXgADqFdSQ2NpbeN/Zi6JC7iY52fCKom07HV1/MZ/N/W/n6m8WFHpOens6XX3/D9JdfxGw2
s2v3Hpo2acysty2Ba9bsueyK3MP2HRF8Mf8jXn/rXaJjYhl+7xDGPfIQ/W8tuGKpKJcvx6HTaRkx
bChbt+/gwoWLNGvWlNnvvcWs2R+xfcdORt0/glEjh/PM8y9xLuo8YR070LRJE7797sfccuKu0Pfm
3vy3dRuHDx8lMyuLnbsiefCB+9m1ew8xMbE8Nm4MtQIDbeeUpdwLFy+Snp7OyPuGseSXZfj7+TH5
afsl2nfefhsPjR7FxEnPEnclnh//t4SHH3yAWe+8wYKvvsFg0DP1hedITMi9q/nOiEh2RkSy4NN5
vPXu+0Sdv0Cfm3ozc9pUHnvyKTZuKvlu5s7wRtdO6HVa0kwmIuPimR6xp8AtV6w9P8OHj+CRsePK
Vd+ibxaydOmSat3TY3XdBB8hRM1zJSODphjYF3/VKbsxp6Ya+W/rdu6/bxhvvvM+L70yg9nvv8Oe
nVuIvRzHKzNeIzo6htUrfiM5OZkXX5lRaDkfzv0ED3cPFn31GWazwoaNm/jux58Y2K+vw23Ruelo
1qxpifv1zJv/OdcSEnjqyfHUr1+PuLgr/PTzUj7Js8vw+AlPM/WF55j/8Rx8DAYOHT7Cg4+ML9WK
nEOHj/D+7Lm88Pxkjhw9xkOPjMfHYKBZs6bUyumt+XzB13h7ezHvw/cJDAjkUnQ0H86bz2+/L7eV
88bb7/Hh++/y84+LGT3mUSJ27Wb+ZwsIqVOHLz6dR5oxjQVffUNgQG4PUFnLHT3mMd56fQaPPzqW
s+ei+GDOR/To1s12Tu3atWnRvBmenl5APHFxVxg5egyvTn+ZP39fSmJiEm/Pms2we3J7lgDGPT6R
F56bxNwP3sPX14fTp8/y7JSXKiz0NDbkzus5eC2RBzcUvYFgckoK3yz6htWrV/HII+MYdPvtpapr
9apVLFpUPVdvFeW6uVeX9PgIcX1r1LyNkv9eXW907cyYVs359thJXo/c65R62oW2Zcn/LebpZ6aw
dv2/Dp+3/u+VLPjqG35e+qtT2iFEYUL9/fhpQB/0Oku/xeaYWB5a7/jOyQa9no5hYfS+8SZCQuqg
1xtsK8BOnjhBSkoy0dExbN6yib179lRaD4/cq0sIIQrRMmfvEuu/neHAwUM8+8LLzJ0zi5Wr1vDr
sj84cuQYKamp1AoMpEP7dpy/cIHjOfMcdDotPbp1o369epw8ddpp7RAir8YGPXN7hNO+ViBqwJhl
YveVeGZE7Cnx3LySU1LYvHlztbvNhDNJ8BFCVFvanNU2WkdWLZXCmr/+Ye/e/Tw0+n5mvPISjRs1
xNPTk8SkJI4dO8GnX3xpCz4tmjfj47kfsGjx90TuLt0fISEc0digZ8VtA9DrtJiBPVeu8ty2nU6/
2W5NIcFHCCEKERMby/tzPuL9OR8Ve9zhI8foGN6zglolahrr6i29TktKVhb3r93IwWsJld2sak2C
jxBCCFFFfdSrmy303LVmHWekl6fcZB8fIYQQooppbNDzfb/etA8MQAFGr98socdJpMdHCFHtyZJO
cT3JO6cHYG/8VfbFX63kVl0/JPgIIaolQz1v2xb9HQL8aBfgz4Gr1yq5VUKUXWODnlc7dyC8dhDe
Wq1t5db0Uq7cEsWToS4hRLWj0qrQADN37ibTbMZNo+Gjnl0ru1lClJm1l6dP3RC8tZY5PXeuWcuD
GzYX2JFZlI8EHyFEtZOREsvVM+c5l5LKoWuWXp6EQm4WKkR1kHdoy5hlYkt0LINlIrPLyFCXEKJa
MSkZqNVatDrLzRmTsyzDXa18fGjp68PxxKTKbJ4QDgsN8OP59m1tQ1uycqtiSPARQlQr5qw0MKvw
MASSYcxg5s7d/DloIHqdlj9u68+0nbv57cy5ym6mEAVY5/Do1Bp83XTcEOBvG3aR0FNx5F5dQohq
oVHzNoqiKKiVTNKMqfgH1yPdmAFY/qAsuKknLX19ADiTlExUSioLj51gS3Qs1fpDTlR7+SctW5mB
o9cSuJqewYxde2Qn5jxcea8uCT5CiGqhUfM2is5bTUaSEa06G7W7N9lZ9tMUhzZpxNtdO+Gh0die
izGmcdFoJDkzkzn7Dsmut6LCFBZ4jFkmjiQkkmYyMWvvAfnvsQhyk1IhhAC8vLVkJYGXlwGf2plE
R7nZvf7bmXMcuHqNmZ06oNfpqOPlafsH4Ka6IRy+eo3EzCyyzNm8HrlPvmULp7KGHTeVmg5BgXaB
Z/eVeOnZqQIk+Aghqg8vheAmgVw5n8iomzL46ge3AoecSEziwQ2WO0+rgBtD6vB4mxYEuLvTyt+P
0AB/27HhQbWIiLsiAUiUW1HDWRJ4qh4JPkKIaqNReG2UdA/i4q6xdb+uxOMVYHN0DJujYwDLKpqX
OrTDU6OhTYAf3jodfeqGEB5Ui33x10qcC2QymzmWkEgzHwOnkpJp7eeLAuyLv4oChOXcXuBYQqLt
NevPGgfuIG8ym+3Ksp5jrTd/mYWVn/fYwurMX5bMgyo7a7Ae16oZXYoYzpLAU/XIHB8hRLXQqHkb
pefo5sRcSsFgjuPObgrvvF/28hob9LzZpSOdgmrhpa3Z3wGt86BSMrNKDFiOBLuSwpdVVR9uzA02
zQH7gOvtpqOel5dtGBWkd8eZZHJzMST4CFEzNGreRvEJzCbT20TTxj4002fy5+ryv+0tASgMTwfC
j8ls5lRyCg29vYhKNdLUoEcFHE5IBKCNny8q4FRyiu016886B3t88paly9OLU1iZhZWf99jC6sz7
uodGYzcHqjKkZmXZ9bYVFpoc6fHKH8JK00tmraOkYFOYGGMaMWlGUjKld8eZJPgUQ4KPEDVDo+Zt
FJWSSlAbL9QaD9IupZGUULN7apwh7zworUpdYsByJNiVFL4AUBTaBPhV+d42a7DJMNmHUpPZzJdH
j8swoYvIqi4hhADQumNONqGrpUHfwpekiNTKblG1l38eVEUqrLetsNDkSI9X/hBWml4yax0SbKqH
l1+cwuUrl/lm0XdlOl+CjxCi2jCb1MSdjyPER41O71PZzRHldDY5xbYCTwhHRURGkpiYWObzJfgI
IaoPlZrA1rVx83UjPTG9slsjhKgEa9dtsA11lYXcnV0IUa0kRCnERSWTdK3s3/iEEFWbn6+v7We9
t54Z06bi6WG5MfGUZyczetTIMpctwUcIUa1kG9WkJRpxV8t6BiFE6UnwEUJUP2k+uKfLx5cQovTk
k0MIUe0o2VouXzJXdjOEENWQTG4WQlRLZo0XIUFBld0MIYQLXLt6JfeBk0e1JfgIIaqty3Fxld0E
IYQLeHnk3oDY18e5W1fIUJcQQgghqpSGDRtgMOgJqlWLXr16OHxep04dWfH7LzRoUB+AMQ8/yPeL
F6LO2axy3twPpMdHCCGEEFVLVlYWN/W+EZVaTUREJC1btHDovAA/P5o3b4be2xuA+vXq0qpFCzQa
NWazmRbNm8u9uoQQ1UOj5m0UBbDeP0BRFDQaTWU2SQjhIq68V5cMdQkhhBCixpDgI4QQQogaQ4KP
EEIIIWoMCT5CCCGEqDEk+AghhBCixpDgI4QQQogaQ4KPEEIIIWoMCT5CCCGEqDEk+AghhBCixpDg
I4QQQogaQ4KPEEIIIWoMCT5CCCGEqDEk+AghhANuGdCPWwb0q+xmCCHKSYKPEEIUw8dg4JGHRvPW
6zN56/WZPPLQaHwMBqfX89knc9ny7z/ovb0LvDbo1oEcO7i73HV0aB/Kji0b6N2rp+25Pjf3Zt2a
FRzZv4ubbuxV6DGu8NDo+9ny7z8EBgS4tJ6KdD1e0/VIgo8QQhTBx2Bg5R+/MHP6VIKCahEUVIuZ
06ey8o9fXBJ+6tUN4bUZrzilLC8vT84cP0hYh/a25y5Fx7By9RrORZ0HQKVSMf+jOfyzfgN3DhnO
9h07CxzjDP363lwguB04eJiVq9aQnJzstHpcZflvP/Pk+HF2z1X3a6rJtJXdACGEqKpmTptK/fr1
Cjxfv349Zk6bypSp05xa35Ejxxg8+Hb+XruOv9eud2rZAHFxV3jj7Vm2x56eHnh7e/HX3+s4dfpM
oce4yp69+9izd5/L66lI1+M1XY+kx0cIIYpw79C7y/RaWR07cYKP5s3nnbdeK3G4pHevnixb+n8c
2b+L7ZvXM/XF53DT6QC4uXcvDu2NAOC3pf9n+zmoViBnjh+kWdMmDLnrztxjlvzImeMH8fLytDvG
6sZePezqeumFZ9Hpcr833zKwP8uW/sThfRFEbNvIW6/PwNPTE4CXpjzLwgWf4ubmxpnjB1m44FMA
Bt8xiIitG+2uacxDD7D+75UcPRDJP6uXc9/we+1eX7dmBWMffpAvP/+Ew/si2LZ5HROeeKzY31NI
nTp8Mf8jDuzZwYE9O1i44FOCg2vbXvf09GTm9KlEbN3IgT07+N8Pi+jSOQwA95w2twtty4tTnrX9
7Og1OdJeH4OB2bPeZm/EVg7s2cG0qS8w4YnH+OHbrx2+BlE6EnyEEKIQN7Rp5ZRjSuuLr77hzJlz
vPv260UeE96lE19/+SnLV6yi/613MmHSc9zYswcfz/0AgE1bthLWtRcA9z3wMGHhBefr/LFipd0x
rUM7YTSmFTiua3hnvvnyc/5eu55b77iHSc+9wKBbb2H6yy8B0C28C5/Om8MfK/6kz8DbGTPuCXp0
78YzT08AYPbcj3l84mQyMzNpHdqJxydOLvSaJjzxGBOfHM/b735AnwG3M3vux7z84vOMeegBu+Me
e3QM3373Ax279OTl6a/xzNMT6d+3T5G/q3kfvo9KpeL2u+7llkF3k202895bub/bBZ/No2Xz5jw8
bjyDBg9l46Yt/Lh4Ia1btSQjp80HDx1mzkef0Dq0EwcOHnL4mhxp71dfzKdxo4Y8+Mhj3D30PnQ6
HQ+PHlWqaxClI0NdQghRCB+Dj1OOKS1FUXj+xVdYveI3ht97D0t/XVbgmKcnPsEvv/7Oou9+ACxz
dyY9+wLr/vqT1q1acvTYcTIzMwHIyswiMyur0HryHpOR83OBuiY8wbI/lvP5AksPRNT58zwxcTLt
QtsCsCNiFz169+dKfDwAly/HsWr1X9zYqwcA2dnZmEwmgCLrcHdz44nx45g28w3WbfgXgJi/Ywnw
9+P5Zyfx/Y//Izs7G4Blv69g67YdAPy7cTObt/xH927htvPya9igPqvX/M358xcAeGrSc5hyyurc
KYywjh0I73Ez6enpAHz+5UI6dQpjxPChvPHWe2RkZqIoCtkmk639jlyTVXHt7dI5jPAunejeux+X
L8cB8Nqb79A1vLPD1yBKT4KPEEJUMVHnz/POex8wc/pUtm3fUeD1Du1C+f2PP+2eO33mLBcvRdMu
tC1Hjx13Wlvat2vLkl9+s3vu6LHjdnUYDHqG3nMXLZs3p379urQLDeXcuSiH62jatAkGvZ7ISPvJ
wpv/28Y7b75G3bohtj/6Fy9esjvm2rUE/P38iiz7k88W8Or0l7n1lv5s3xHB+n83sf/AQcu1hbbF
w92drRvX2p3j5eXJlq3bHG5/cYprb7u2bbl48ZIt9Fjt2LmLFs2bOXQNovQk+AghRCF8fJy/aqs0
fvzfEgYO6Mfs99/h+x9+KvC6oigV0g6VSoVKpSry9UG3DmTO+++w7I8V/LdtO+eiztOrR3cG3Tqw
1HW54pJ+/Oln1q7fQJ+behPepRM/LP6aP5b/yYzX3gIgJiaW4fc/VOC8jMwM5zcmH5VaTXpGwXqy
8/XmlHQNonRkjo8QQuTjYzAwOWeOSnFmTHvJJcvarV58ZQatWrRg3CP2f5j3HThIeBf74ZCmTRpT
r24IBw4eAnJDhFqjKVcb9h84RO8b7ecItW7VkmFDhwCWSd5/rlrDtJlvsOyPFezesxc/P/shQEVR
UKmK/nNz+vQZklNSCO/Sye75m27sSfzVq1y6FF2mtqvVatre0IYrV+L5eemvTHlpGs88/xKjR43E
09OTQ0eOEBJSB52bjpjYWNs/jRs1RJ2nvYqiFPg9lnRNjjh+4gSNGjYsMFG5S+fc30NJ1yBKT4KP
EELkM3vW29zQpnWJx93QpjWzZ73tsnZcvhzHzNffIqxjB7vnP3RkVuAAACAASURBVPn0C+4dejeP
jn2Y+vXr0TW8M/PnzWHNX//YhqDS0tJITk7m7sG307pVyzK3Yf7nX3L34DuZ+OR4mjRuZJnM/PGH
tL2hDQAnT50mvEtnOoV1pF7dEEaOGMbQIfYr3i5fjkOn0zJi2NBCtwfIyMzkiy8XMnP6VG4Z2J/6
9epyx6BbeWnKs3zy6RcFekAc5eHhzv99t5CXX3yeenVDaN6sKcOGDiHq/HnS0tLYGRHJzohIFnw6
j549ulG/fj1GjxrJd4u+IjT0htz2x12h78296dihnW3lXEnX5Iit23Zw/MQJPp03h7COHWjWrCnT
X36RBg1yyyvpGkTpyVCXEELkM+WlaQ4FH4DDR466tC0rVq623C5jYH/bcxG7djNu/ASef2YSzz/z
NElJyfy+/E/mzP3Y7tynJk/htZmvcM+Qu+jc9cYy1b99x04ee2Iiz05+mqcnPE5ycgp/rFjJrNkf
AvDh3E/wcPdg0VefYTYrbNi4ie9+/ImB/frayjh0+Ajvz57LC89P5sjRYzz0yPgC9Xz2xVcYjUZe
fvF56obU4fz5C7wzaw4/L/21TO0GMBrTGDPuCaa++Dx/r1qOWTGzY2cED4993HbMuMcn8sJzk5j7
wXv4+vpw+vRZnp3yEhs3bbEd88bb7/Hh++/y84+LGT3mUSJ27XbomkpiNpt5eOzjvDbjZRYv/AK1
WsOSX37l5yW/0r5dqMPXIEpH1aJF24oZKHaRrJyh57PHDxU9CC2EqPYaNW9jGb3J+cRSFAVNOYdx
HNW9azg//bAIgPtHP8L2nREVUq+4/mm1WtsKMau3Xp9BrcBAnnjqmUpqVeVLTUkCRYWiAhWWoVvr
VDNFAazP53wgqBRQVCpQlGLnpIH0+AghRIm274xg3ief2X4Wwhk0Gg3Lf/uZ7Tsj+Hbxj6Slp9Gr
R3eGDrmL6a++WdnNu25Jj48QolqozB4fIVzlhjatePH5Z+kU1gF3Dw/Onj3H4u9/5P/+t7Sym1ap
pMdHCCGEuA4dPnKMMY8+UdnNqFFkVZcQQgghagwJPkIIIYSoMST4CCGEEKLGkOAjhBBCiBpDgo8Q
QgghagwJPkIIIYSoMST4CCGEEKLGkOAjhBBCiBpDgo8QQgghagwJPkIIIYSoMST4CCGEEKLGkOAj
hBBCiBpDgo8QQgghagwJPkIIIYSoMST4CCGEEKLGkOAjhBBCiBpDgo8QQgghagwJPkIIIYSoMST4
CCGEEKLGkOAjhBBCiBpDgo8QQgghagwJPkIIIYSoMST4CCGEEKLGkOAjhBBCiBpDgo8QQgghagwJ
PkIIIYSoMST4CCGEEKLGkOAjhBBCiBpDgo8QQgghagwJPkIIIYSoMST4CCGEEKLGkOAjhBBCiBpD
W9kNEEKIqszHYODee+6me7dwALbviODXZX+QlJxcyS0TQpSF9PgIIUQR6tery8o/fmHm9KncMrA/
twzsz8zpU1n5xy/Ur1fX6fUNunUgy5b+H0f272J/5Da++mI+rVu1dHo9ZeHh4cGGf1YxaeITTi87
wN+fBZ/O48CeHezYsoGxYx5yeh1WrrwOUT1I8BFCiCLMnDaV+vXrsWjx9/Tuewu9+97CosXfU79+
PWZOm+rUuu4efAdzZ7/HipVruPe+B3jksQmkpKSw9H/f07BBA6fWVRYZGRmsXLWG3Xv32Z5b/tvP
PDl+XLnLfuWlKdSvX4/BQ4bz4svTefnF5+jSOazc5RamsOsQNYsMdQkhRBG6dwvn4sVLvPH2LNtz
b7w9i1sG9Kdb1y5OrevBB0ayaPEPfPPtd7bnInfvYcGn8+jeLZyo8+edWl9pKYrC7Lkfu6Tstm3b
sPzPVZw9F8W5qPMkJSfTuFEjdkXucXpdrrwOUT1Ij48QQhTBYDBw4eLFAs9fuHgRHx8fp9aVlZVF
YGBAgecfnziZJb/8ZnvcoEF9vvz8E/bv3k7kjs38f3v3HR9Fnbhx/DOzm2TTE3oJHaSLSlMBEQSk
g4i9/dQ7VDzr2QtWLCgiRRSVA8V6CIqIYKiCR5UiHURACC1AgPSyu/P7YwtZEoRgSAj7vF+v5Xb6
d9abybPfMjvynWFUq1olYJv27S7zN5ktXTSPJx9/hJAQz/fcihXKs2PreurVrROwzdqVS+jWpTMA
fXr1YMGcmdz1f7ezYsnPTJrwEQBzZ03nlhuvJyw0lB1b19O8WVOeeOwR//urOl3J1g1riI0N/Gw+
+mAMY0YOP+m5r9+wkWv69SEmJoY3X3uZsNAwfvnfkr/8vIa+PIQ3hr7EA4PvZfXy/7Fu9TI+Hjcm
oAnyVOcBntqm76d+HbBvu93OqmW/cNMNAwFo3KghH30whjUrFrN+9XI+HjeG2rVqnvZnPv3b//LM
k48FrN+0SWN2bF1Pg/r1/vI8pfgp+IiIFCImOhrwhJ+2rVsFvKK9y3zrFIexH3xMvz69mDThI3p2
71YgPADEx8cx5avPSEpKole/gdx4y/9hGgZffTaRsNBQANq0bsl/PnyfxDnzuLrXNTz46OP0uLob
zz39ZJHKU7VqFS5s3pRrrruZ+/71cMCynNxcGjW7hPUbNjL83dE0anYJ69ZvYMHCRRw7doxePa72
rxsbG0PHDu2ZPOXbkx7rzbdGEB8fx/9+nk23Llfxz/v+xf4DB05Zxu7dulK5ckWuuro37Tp2Zf/+
A3w5aQLh4eGndR4Ak6d8S/NmTQOC4BUd2hEe7uCHGbOIiY7my0kTOHToEP2uvYHufa7B7XIz8p1h
/vVP9Zl/M/U7+vbuiWEY/m369enFmt/W8fu2P055nlK8FHxERE4QEx3Novk/AdCkcSO++nxiwKtJ
40YALJr/U7GFn0X/W0zPfgPZnbSHV156npVLFzFpwkcBfV1uvvF6tv6+jZeHvsnu3Un8vu0PHnn8
aaKjo+nYsQMADwy+l2+nfc/74z5m1+7dLF+xknvvf4j1GzYWrUCWxRNPPUdS0h7SMzIKLM7JzcWy
LFxOJzm5uQC4XC6++/4H+vXp7V+vV4+rSUlJYdEvi096qBo1EnA5XURFRjJy9FiWLF1+WkXMys7i
xVdeJ+XIEVJTU3nh5dewh9jp06vHaZ/H79v+YO269fTt08s/r3+fXsxKnENaejqpaWl07taLp597
kT937SYpaQ+ffPYFFzZv5g+bp/rMp02fQXy5eP/IQMMw6NO7B9/8RRiUs0fBR0TkBE0aNzqtpqyY
mBh/CCoOf/yxnWeef5FWl17BdTfdzsFDh/ji0wlcdmkbAC5s1pSWl1zEqmW/+F/L/7eA6OgoatZI
8KzTvGmBZqLNW7b+ZY1LYVJT08jNyyvyOUye8i2tW11C9WpVAejXpzdTvp2G2+0udP1mTZvwxafj
mfnTbJ5/8VWeeOxhWlzoCRVffTaBWjVP3rF73fqNOJ1O/7TL5WLNmrUB/01O5zy+mTqN/n09wSci
IpwuV3UK+Lzclpsbrx/Iqy89zyfjx/Hu254+X2FhYcCpP/OjR48xb94C+vf1BMJL27YmPi6O73/4
8S/LJWeHOjeLiJxjLMti9ZrfWL3mNxwOB7fcdIO/FiRxzjxef7Ngf5m0dM9zhQzDCGhSOW1nsk0h
tv6+jQ0bN9G3d0+mTZ9Bq5YX89SzQ066/t133s669Rt56dXXAUhIqMaHY0fz4iuv0aZ1q798XlKI
veCfMHtICJZlFanM06bP4LmnH+fiFhdSu3YtUo4cZfGSZQDUqV2LyV9NYs1va5k/fyE/zkokxG5n
4vhx/u1P5zP/Zuo0Rrz9OkNefJX+fXv7a5Sk5KnGR0SklIWFhbFiyc/0uLprgWWRkRFkZWUBsGHj
Jpo3a8qhw4fZf+AA+w8c4EByMo0aXYDT6QJg7boNdGh/ecA+GjW8gIED+gOeGhDLsgI6UlcoX57o
qKgil9uyLEybrcD8b6Z+R7++venXpxcrV61hx84/T7qP0NBQ9uzd659+Y9g7rFq9htHvvs28BT9z
5MjRk257UYsLcTgc/mmHw0HLiy9iw8ZNRTqP1NRUZs+dT7++venftzffTP3Ov+yqzleSlZnFP+75
F59/9V8WL1lGqLeJy+dUnznAgoWLyMnJpfvVXelxddeADutSshR8RERKWU5ODjNnJTL05Re4/dab
aN6sKR07tOOtN17l0rZtmPT5VwB8/uV/iY6KYuQ7w2japDF1atfilRefY9SIt/zBZcz7H9KvT2/u
v28QdWrXom3rVrw36h2aNmnsOVZuLr+tXc/jjz7MBQ3q07xZU0a8/QZ5ec6Tlu9kkg8eolPHDlzU
ojmhISH++dOmz6BOndr84+7/O2UT23fTptOnVw/uvP1WKlaswMUtLiQiMgKbzUZOTu5fbut0Ohk1
4i2aNG5EwwsaMGrEW6SlpzFj5k9FPpfJU77lmn69ufyytkz5dpp//rY/tlOpUkV6du9GtapV6Nih
HY89+lDAtqf6zOF4/6chzz1Famqav0ZJSp6Cj4jIOeClV99g7LiPuOWmG/j684mMGvEWlSpW5MZb
/o+169YDcDglhWtvuBWbafLFp+OZ/u1katWsyY23/B+HDh8GYOmy5fzz3vvpelVnZk6fypiRw5m/
YCGvvfmW/1iPPfkMbrebaVO+Yviw1/jgo/FkZ2cVucwvD30Dy4KvP/+EFi2a++f7+rQ4whzMmDnr
L/cxe+58/v3EM1w38Bp+mZ/I6HffZteu3fTqdy2XtW3DPf+466TbLl22nMVLljJp4kdM+fpzTNPg
5tvu8teQFcWiXxaTlZXNylWr2b07yT9/wc+LeOnV13numSeYPXM69w66mw8+HF+gHKf6zMETrsrF
x/NNvmAlJc9o0KBp0RpDzzF53mbVnVs3FE8DtYick2rVb+zpueG9Y1mWha2QZpbi0KRxQ2ZMm3Ja
6/bqdy0bN205K+Uoy94d/iZ5eXk8/tRzZ2X/Q18eQkx0NA888vhZ2f/ZUKd2LebMmk7HLj1ISir4
fCg5LiM9FSwDywADsKzj3dAsC/DN994QDAsswwDLOmV/K3VuFhE5wcZNW7hn8IMMHNCfmJjCh6un
pqbxzdTvFHpOULNGDZo3a0KP7t249vpbSrs45wSHw0H9enV59KF/MXf+zwo9pUzBR0SkEIlz5pE4
Z15pF6PMeW/UcKpUqczLr7xe9GcHnac6tLuMMSOHs3LVGh56tOzUUJ2v1NQlImVCSTZ1iUjpOptN
XercLCIiIkFDwUdERESChoKPiIiIBA0FHxERESkzvvxsIhfUr39G2152aVsFHxEREQkOf/65S8FH
REREgsPeffv0HB8RERE5N0VFRnJV5ytp3KgRdrudb6YE/rjrDdddS8crrmBPUhI333wjmZmZvPDi
K0RERPDMU08QHx/PDzN+5NHHn8LpdNKoUUPV+IiIiMi5xzRNunTpTHZWNh+Nn8AXX33NgGv6F3h+
V5vWLdm3/wCXtr+SCRMnMXrkO/Tu1ZMu3XvTo09/Ol3ZkWsH9D++35I+EREREZFTqVy5EiH2EObM
m8/hwyns2LGTb6Z8W+ABhYcOHWbCxE9JS0vnPxM/JSIigvfHfcSRI0fYsmUrc+bNp1nTJv71FXxE
RETknBMdHU3KkRTcbrd/3vYdO7CswB+c2H/ggP+90+kEICMjwz8vJzsHh8Phn1bwERERkXOSaQTG
lOL4bSoFHxERETnnpKamUa5cPCEhIf559evXO+VvcZ2Kgo+IiIicc5KTk8nJyaHrVZ0pX74cdevW
4Zr+/fzNWWdKwUdERETOKVGRkbjdbubMm09IaAiD/nEXN1w3kG+mfEt2dvbf2rfRoEFT69Srnbvy
vDVeO7duKI6mPxE5R9Wq39jTpdF7x7Isq8CwVhE5P2Skp4JlYBmefj2WBb4WLssCfPO9NwTDAssw
wLJO2RSmGh8REREJGgo+IiIiEjQUfERERCRoKPiIiIhI0FDwERERkaCh4CMiIiJBQ8FHREREgoaC
j4iIiAQNBR8REREJGgo+IiIiEjQUfERERCRoKPiIiIhI0FDwERERkaCh4CMiIiJBQ8FHREREgoaC
j4iIiAQNBR8REREJGgo+IiKn4e03hvLWG6+WdjFE5G9S8BERKURMdDQJ1asB0K1LZ64d0I+BA/rT
rUtnABKqVyMmOvqsHHvalK9YseRnbDZbgWVDXx7C6BFvAVCxQnl2bF1Pvbp1zko5isLhcDB/9o88
eP+9pV0Ukb+k4CMiUoivPpvIovmJfDnpP4wbO8o/f9zYUXw56T+eZZ9NKPbj1qtbhwubNyM2JpYr
OrQr9v0XVedOHdmyflWB+d9P/Zr7Bt3tn87JyWHGj7NYtea3kiyeSJHZS7sAIiLnmpjoaBo3bgjA
pW3bALBs+QoA2rZp7Z/XpHEjYqKjSU1LK7ZjX9OvDxs2buLPXbsZ0L8v8xcsLLZ9n02WZfH2iFGn
XlGklKnGR0TkBKlpaf6gs2nTFjp06saNt97JjbfeSYdO3di0aQvgCUPFGXoA+vftzQ8zZvHDjJl0
vaoT0VFRf2t/N90wkHmJM9iyYTU/z53JzTdeF7C8fbvL+HbyF2xa+yu/LJjNY488iMPhAODJxx5h
/Lj3CA0NZcfW9Ywf9x5h3vfNmzXlicce8b8HmDtrOrfceD0AfXr1YMGcmVzTrw+L5v3Ext9W8OWk
/xRolru6WxdmTp/KlvWrmPXDtzRt0pgt61fRquXFp30OIkWh4CMicoJuXTrTtk1rAAYNfoCkPXv9
y5L27GXQ4AcAT+1P16s6Fdtx27ZuRfXq1fhh5izmLViIy+WmZ4+rz3h/l1/Wlheee5rX33ybS9t3
4qVX32DIs09xcYsLAWjTuiXj3hvF15On0qlrLx557Ek6XXkFw157GYC3R4zinvsfIjc3l0bNLuGe
+x8ix/t+/YaNDH93NI2aXcK69RsKPX6VypVod9ml9L32Btpf2Y2MzEzeHf6mf3n7dpcxesTbfPn1
ZDp17cnrw4bzxtCXsNuPN0ac6hxEikrBR0Qkn7ffGOrv07Ns+YqA0OOTtGevv0bow/dH8/YbQ4vl
2Nf078PadetJStpDTk4O8+Yv4Jr+fc54fzVr1ODo0WMs/GUxR44cZd78n7m4TXtW/7YWgAcG38v7
H37MV//9hv0HDrDi11U88fTz9OrZnbi4WFwuF06nE4Cc3NyA95Zl4XI6ycnNPenx7XY7z7/0KkeO
HCXlyBFGjn6fZk2bEBUZCcC9/7ybyVO+5dPPvmTvvv38vPAXRo8dh2ke/9N0qnMQKSoFHxGRc0BY
aCg9u3djxsyf/PN+mPkTbVq19I8uK6ofZyVy9NgxfpmfyLDXX2FA/77Y840Uu7B5Uwb9405WLfvF
//ps4seYpklC9ep/+5yOHDlKVlZWvukjAMTFxQLQvFkTVq1eE7CNL1Ce7jmIFJU6N4uI5PPYU8+S
OGcu48aOom2b1iRUr1ag1iehejV/U9g9gx9k6bIVhe2qSLpc1Yno6Ggee+Qh/v2wpykNw8AwDPr3
68OYseOKvM/U1FR69RtI61YtuezSNtx+680889Rj3HTrnfy+7Q8Aho8YxU+Jcwtsezjl8N86n9Nh
mCbZ2dkB81xOV8D06ZyDSFGoxkdE5ASJc+b5ax7GjR0VUOOSUL1aQFNY4px5xdLB+Zr+fViydDk9
+lxDz77Xel59BjBl6jSu6XdmzV3l4uOpkVCdpcuWM2LkGPoPvJG9e/dx7YB+AGzYuJlmTZuw/8AB
/8vldpGQUI28PE+zlmVZGEbBPxWWZWH+zZqXrVt/p22bVgHzWrW6pEjnIFJUCj4iIieIiY721+g0
adzI/zwf3/N7mjRuBHg6NxfHQwzLxcfTsUN7vvjqv/yxfUfA65PPvqBundpc1KJ5kfd7803X88Wk
/9CmdUsqV65E96u7UrdOHbZu3QbA6LEf0L9vbx68/17q1qlN82ZNGfPucJ596nH/PpKTDxISYuf6
gQNISDje/JV88BCdOnbgohbNCQ0JOaPz/nD8RG68/jruvP1WateqSccO7XjkwfuLdA4iRaXgIyJy
gtS0tIAh6+B5ns+Jz/TZtGlLsdT29Ondg/T0DBJnF2xyWrd+A5s2b2FA/75F3u/74z5m2vQZjHxn
GIvmJfLU44/yzsgxTP3uewCWLF3Onf+8jys6tOOH7yYzcfwH7E5K4q5Bg/372LBxE8PeHsHj/36I
1155wT//5aFvYFnw9eef0OIMQhlA4uy5PPnM89xy0/Uk/vg9zz79BC++/FqRzkGkqIwGDZpapV2I
vyPP8Pzvzq0bjNItiYicTbXqN7YsAO8dy7KsQn/SobjEREcTExNN0p69dOvS2d+8dc/gB0mcM4+E
6tVITU0r9uf4BBu73e4fLQZQoXx5Viz5mR59BrB5y9ZSLJmUpgubNSYtLYPNW7fgzHNiWfDKS88z
c1Yi/fr0pnHjhuw/kMxbw0fw+7ZtGBZYhgGWhWEY3HD9QP41+F46XNkFgLjYWDZvWMMrr72hGh8R
kcKkpqX5OzUnzpnHlKnTmDJ1mr8jc9KevQo9f1Pvnt2ZM2s6V3bsQLn4eBo3asgbr73E9h071XE5
yK1fv5HY2Bguv+zSgPldOnfivQ8+5Obb7uTPP3fx6ktDCt1+3vwFNKhfj6pVqgDQvv3luFxurmjf
TqO6REROx2NPPVvaRTjvzPxpNrVr1+LF55+hatUqZKRn8L8lS7njrkG4XK5T70DOW2npaaxevYYB
A/oTFhpGdk4OAHPmzWfXrt1gwPgJnzDj+ylER0WRnpYesP3Bg4dYu249HTt24KuvJ9Pxig588OFH
3PV/tyv4iIhI6XC5XIwZO+6MhurL+a3d5ZcREx2LYRhERkX6g09KSop/ndTUVACiY2IKBB+AOXPn
0/EKb/Dp0J477h7ElR2vUPARERGRc8vKVasxDRPDZpKdmXXqDQoxd/58Jt0+nlq1ahIREcGmTZtZ
8PNC9fERERGRc0t2djZ5eU4iwiNwud1ntI/Vq3/DNA3uv3cQPy9cBMCCnxcp+IiIiMi5JTIykksu
voiWLS8+43243W7mLVjIbbfezPyfFwKeR1Eo+IiIiMg55aIWF+JyuViwYOHf2s+cOfMwTdNf45Ob
m6vn+IhI2VDSz/ERkdKTkZ4KloFlgAFYFhjev/KWBfjme28IJz7H56+oxkdERESChoKPiIiIBA0F
HxEREQkaCj4iIiISNBR8REREJGgo+IiIiEjQUPARERGRoKHgIyIiIkFDwUdERESChoKPiIiIBA0F
HxEREQkaCj4iIiISNBR8REREJGgo+IiIiEjQUPARERGRoKHgIyIiIkFDwUdERESChoKPiIiIBA0F
HxEREQkaCj4iIiISNBR8REREJGgo+IiIiEjQUPARERGRoKHgIyIiIkFDwUdERESChoKPiIiIBA0F
HxEREQkaCj4iIifRquXFzJ/9I9u3rGPH1vXs2Lqe7VvWMX/2j7RqeXFpF09EzoCCj4hIIca9N5LJ
X06idq2aGIbhn28YBrVr1WTyl5N4f/SIYjve2NEj/OEq/2vBnJnFdoyT+ffDD/DZxI8DyvLSkGfP
+nGHvjyE0SPeOuvHEcnPXtoFEBE514x7byTdul51yvW6X92Vce+N5J77HyqW4ybOnssrr70ZMC/P
6SyWfYuIh2p8RETyadXy4oDQY1kW74/7GJfLVej63bpeVWzNXplZWSTt2RvwOnAguVj2LSIeCj4i
Ivm8/eZr/veWZfHgI4+zcdNmTPPkt8v825xN7dtdxreTv2DT2l/5ZcFsHnvkQRwOR8A6t996E/MS
Z7Bp7a/8NOM7Bg7oH7A8Li6Wd956nd9+Xcy61ct47uknTnpu/374AX77dTFrVy1lzMjhVKxQ3r/M
NE3u/efdzEucwZb1q5g/+0f+cdcdAduHh4cz5LmnWLH4ZzavW8nXn3/CxRe1OOn5NWnckJXLFnHn
7bcW9aMROW0KPiIi+dSqWQM4Hnp++HEWAK++NoxXhr5J4uy5pKWlBWxTs0bCWS9Xm9YtGffeKL6e
PJVOXXvxyGNP0unKKxj22sv+de6/bxCD/nEXz7/4Cp279Wbk6LE8+9Tj3HzjdYCnf9KEj96nerVq
3HLHP+h7zfUA3HjDwALH692rO+XLl2fADbdy/U23Ex0VxacTPsJu9/SQ+Nd9g7jr/27jldfepP2V
XXn1tWE8/uhDdLryCv8+xo0dyaWtWzP4wUfo0r0PK1et5vNPPqZa1SoFjtekcUM+mzieUWPeZ8Kn
nxXrZyeSn/r4iIgUwrIsVq/5zT/tttwATJ8xk3vuf4i1K5cQHR0NEND5+e/o27snPbt3C5j31LMv
8O206Tww+F7e//BjvvrvNwDsP3CAJ55+nu+nfs2Ql4eSlZnFvYPu5s5/3MuvK1cDsG/WfqpWrcKt
N9/IF19Npm2b1lzYvBlt23Xi0OHDALz6+jDatG5ZoCzHjqXy7JCXsCwLgAcefoylv8yjU8cOzJ47
n9Fjx/HZF1+TcuQIAHPnL2Dtug20adWS+QsW0vKSi7msbRs6X92b3buTABg2/F12JyURERERcKwm
jRvx2cSPGTHqPSZ9/mWxfJYiJ6PgIyJSCNM0mTNrOl269wHgheee9i+rVLEiP85K5Ibrri3WY85b
sJA3hg0PmJecfBCAC5s3pUWL5tx1x23+ZYZhYJomCdWr43K5iIqM5MOxowO2DwkNwcATzJo0asju
pD3+0OOz4teVNLzggoB5K1et9ocegNS0NNZv2ESTxo2YPXc+lmVRr14d7mh3C3Xr1KZGQgLNmzVh
3fr1nvI2a8quXbv9ocfny6+/CZiuX78en38yntVrflPokRKh4CMichIOh4M5s6bz+FPPkZ2d7e9P
U6FCeVJSjhT78dLT0/lj+46TLh8+YhQ/Jc4tMP9wymHq16sHwB1338PBg4cCllscDzA5OTkFtjdN
W4F5hdVimabhD0NDnn2Svn168cVX/+XHmT+x889dPP7oN/7T/gAAGmxJREFUQwHbG3/RL8onIaE6
7439kEcffoD+fXvz3fc/nHIbkb9DfXxERPL5c9fugGmHw8Hod9/G4XCwbPkKEmfPZdjwdwM6DZ+4
zdmwYeNmmjVtwv4DB/wvl9tFQkI18vKc7Nj5J5mZWVzQoH7AOvHxcUR6m5Y2btpMvbp1qFK5csC+
L23busDxWre6JKDTc1xcLE2bNGbDxs0AXD/wWl57423eeXcMM3+azabNW6hcuZJ//bXr11OzRgI1
a9QI2O9NNwykXr26/ukFCxbywUfjefX1N3lj6Es0b9b0739YIn9BwUdEJJ/Hnnym0PnZ2dnMSpzD
kmXLWfbLfCpWrHDKbYrT6LEf0L9vbx68/17q1qlN82ZNGfPucJ596nF/+T78+D889/QTXNOvDzVq
JNDxivZM+Oh9rrv2GgCWrfiVNb+t5f0xI7ioRXPq16vLqy89T1xcbIHjhYaGMuz1V7igQX2aNmnM
2FEj2LHjTxYsXATAtj+206N7N+rXq0vdOrV57uknqFO7ln/7X1euZumyFXww5l3atm5FzRo1+PfD
D/D8M0+SmZFZ4HiffvYl3//wI+PGjgwYPSZS3BR8RETy+XXlahJnF2xOcjgcvPDc07zw3NNUqlTR
Pz9x9lx/Z+KzacnS5dz5z/u4okM7fvhuMhPHf8DupCTuGjTYv87IMe8zYtQY/nXfIObM/J6hLw3h
y68n89Y7IwFPh+27Bt3PH9t38Mn4cUyd/AXpGRlM+vyrAsf7btoPJCXtYfKXn/LV5xNJOXKE2+78
p/95RoMGP0CI3c4P301m0sSPOXYslSVLlwfsY9DgB/h11SrGjBrO7JnTaHf5pdx25yD27d9f6Dk+
N+RlDhxI5v0x7xISop4YcnYYDRo0tU692rkrz9sMvXPrhuIZViEi56Ra9Rt7epd471iWZWGzFeyb
UlxO5+nNibPnFttTm0XkuIz0VLAMLAMMwLLA1+3MsgDffO8NwbDAMgywrFOOslSNj4hIIe65/yGu
u+m2Qvvv/LlrN9fddJtCj0gZpLpEEZGT+HXlaq7s0qO0iyEixUg1PiIiIhI0FHxEREQkaCj4iIiI
SNBQ8BEREZGgoeAjIiIiQUPBR0RERIKGgo+IiIgEDQUfERERCRoKPiIiIhI0FHxEREQkaCj4iIiI
SNBQ8BEREZGgoeAjIiIiQUPBR0RERIKGgo+IiIgEDQUfERERCRr20i6AiMiZqlSxYmkXQUTOgh3p
qWdt3wo+IlJmJR88WNpFEJEyRk1dIiIiEjQUfERERCRoKPiIiIhI0FDwERERkaCh4CMiIiJBQ8FH
REREgoaCj4iIiAQNBR8REREJGgo+IiIiEjQUfERERCRoKPiIiIhI0FDwERERkaCh4CMiIiJBQ8FH
REREgoaCj4iIiAQNBR8REREJGgo+IiIiEjQUfERERCRoKPiIiIhI0FDwERE5A03CwugaGVXaxRCR
IrKXdgFERM5FMYaJdcK8W+PiucgRzqUREcTYPLfPm3bvZGlWZrEcs0dkNIPKladRmIM8y2JZVibD
DyWzOTcHgNtj4xlUrgL9/tzOYberWI4pEiyi7l1E1o9PKviIiJyonGljZf2GJXrMflExvFmlGsMO
JfNs8j7CDZNb4+KZXLM2vXZuZ5czj3XZ2cxIO0ZaGQk9nSOjeL9qAg23bS7tooj4KfiIiJxEna0b
A6Z3XNDkrB3rtvh4JhxN4T9HU/zzVu7PYlzVBC6NiGRX6lFW52SxOifrrJVB5FxhRFfFjK6OhQt7
1RZgC8O5cxFGSAQhF96AGVkJ57415CwZDW4nALaEloRdOhhb5WaQl0He+m/IWTwWIyyG6H8tAyDy
uvHq4yMici7IsyzK22wF5t+zL4n/ph4FoE90DCvqXhCw/OqoaGbWrMuW+o2YVasuTUPD2FK/Ea0c
4QAMrVSFYZWr8kyFSqyqewFr6jVkeOVqRJrGX5anQ3gk39aozab6jVhapwFPVahEaL7lQytVYXSV
6gHb3BVXjh9r1gXgyQqVGF+9JqGmyY4LmjC+Wo2ifiQS5IyIeMjNJHfNlzj3riak6QBsVVuQNedl
smY/j736JYTU6+xZN6oSEX3H4Nz5CxkTepM14zFCW9yCvUFXrJxUUt+9CHfGITKnDlLwERE5F4w9
fJh+0bFMql6TnlHRxJqnvj23j4hkdJUEvjx2hE47t/H6wQO8UaUadiMw1PSKimWvM4/Ld/zOwF07
aBURzsPlKp10v63Dw/k4oSbfp6Zy1c5tDN6XRPuISEZVTTjt83n7UDL37N1NrttNo60buWfv7tPe
VgQAZy6uQ1vBlYtrz2oMeyjO7QsgNx33sd04k37FKF8PACs9mfQJvchd8R+szIO49qzCuXsZtmoX
e/bl8vSTs1wuNXWJiJwLFmVl0HPXdu6OK88rlasSa9pYkpnByMMH+TW78Oate+PLMzn1KJ8eOwLA
XqeTsJRDjDuhdmVLbjYTj3rW2ZaXy2dHj9A3OvakZXmgXEW+OXaUCcdS/Pt9cN8e5tapT6PDYf7O
1n/FBTgtT/fwU68tUpDlzM434fbOy/f/Jlcu2MP8k4YtlJBL7sBesSFmuVqYlZuTt+6bAvtVjY+I
yDnij9xcnkneR6ttW7hu104Oupx8kVCby8IjCl2/ucPBquzAEWXLMjMKrLcnLy9g+ojLRbxZsFnN
p4XDwcoTRqptz8tlT14ezR2O0z0dkRJjVmxIxM1fY5avR97uJWT//CbOLT8Wuq5qfEREzjGWYXg6
Mu/PwlHV5Ja4eJYUMmTewCDb7Q6Y57JOHIR/hmUolr2IlAxbnStwH1hP9uwhGN6mXqN9FazD24+v
ZAGmqRofEZHSFobBiroN6BEZXWBZpGmQ5S48hmzNzabtCbVBrU5SO1QUv2Vn0/qE/dQNCaV6SAjr
sj3ND0ddLsrbAr871wkNDZi28IQziimMiZyMdXQXZoUG2Gq0xoipRljbe7BVbRG4TuYhQhp0VY2P
iEhpy8FiZloqQytXpeJhO6uzsyhns9E7OpZLI6K4bteOQrf78EgKY6oksCM3j/mZadQKCeWR8hX/
dnlGpxzks4TabM/NYVZ6GtVC7LxYsQqzUo/5+/csz8rkvnIVuCEmjv9lZtAlKoruUTEcdDr9+0nO
yyPENLg+Np7FmRkkOfNOdkiRv8X5eyJmfE0ier4NpolzSyLOrbMC1sme8wKO7q9jNGjQtExH8Tzv
4IWdWzf89dhMESnTatVv7Kk38N6xLMvCVsjw7+JQlAcYFteTm23AnXHluC42jhohIeRZFmuys3n3
0EH/s3v6RMcwpGIVWm/f6t/umuhY7i9XnpohYezMy+XJ/XuYWqsu1+3awa/ZWQytVIUY08YD+/f4
txkYE8vD5SrSfue2k5anfUQk/y5fiUZhYaS6XHyXdozhh5LJzbfOv8pV4I64cjhMgx9Sj7ErL48+
0bH03HW8eeG++PLcFV+OTTk53L5n19/+nCQ4ZKSngmVgGWDgqTT0DVa0PFWJnvneG4JheZqIsSx/
U9fJKPiISJlQksEHPD9ZcaJb4uK52BHOpRGRRHuPXZw/WXEm7IAz33QFm40V9RrSY+cfpzX6SuRc
dDaDj5q6REQKkWq5C8x7/8hh//smYWEk2ENKNfT0jorhsQqVeDF5H2uzs6kcYuff5SuyPSeH3xV6
RAql4CMicgY25uSwMad0w8XM9FRqh4byYqWqVA0JIcPl4n+ZGdyx50/Kxq95iZQ8BR8RkTLKBYxJ
OcSYlEOlXRSRMkPD2UVERCRoKPiIiIhI0FDwERERkaCh4CMiIiJBQ8FHREREgoaCj4iIiAQNDWcX
ERGRc46F5fulW98MLIN8M86ManxEpAwq07+0IyJ/kyf6nNl9QMFHREREzj1GvrqdYvw1TgUfERER
ObdYhb496ZyiBCMFHxEpW4rxm5+InJssDPC9rMDLPv+Pr594Ozid24OCj4iULZbnZRhgudXXR+R8
43Z5rmsj4B8DyzB8vZs9LLzTRfs2pOAjImVE/huc4a3tVvAROd+4LReGYYFlYWF5ani8l7rh+9fK
P9yraBR8RKRMyT+a1VLuETnvWC4XWJ4aHsNbw2MZFoZlgfEXF/1p3g/0HB8RKTM89zzP1z/PPc6N
vr+JnD8syyI3z4ll4A06ni84hpFvALuvtsfw3hPyV/6cRiWQ7hgiUnb4b2qW90Zo4HK5S7FAIlKc
cnOzwXJjWBaWAZZleK51y8IyfA809I1zt/INeT/9Zi8FHxEpQ7w3P/I1+ltuLLV5iZR5LpcLZ16e
v/+ygeEZxIDlrQEyMAzfeC/PNW95Rzv4pk6HmrpEpGzIl3V8MwxP10fcbhcGJoZp+KvERaRssCwL
Z24eubnZ/tDjG7tg+JqzfG8s343A8NwSDE7o93Pq61/BR0TKBm//Ht89zvMt0HsTtMCNG1wWpmmC
YXi/LSoEiZyL3G4Ly3Lhdrtw5jlxu9ze6xnyd9rJ163PI9/ohoD+PdbpN3Yp+IhIGXH87ub78ULD
8lVwe74NWha4XPmaviwrXzOYpzrc86XR883RwsI4fo8tNi6Xs3h3WER2u53q1apRPaE6NrvN+3lZ
mN5vyU7AMExs4Okoalk4XU6S9u5jz569OJ2lW345j1m+hxPiHbJueEZs4b02PUuOr4y/3cszwst3
PXsf6WPkf47PaV7HCj4iUkZ4v9JZvmpuT41Pvujjr/o2MHB7hoIE3kIt33KOP/7Vv09f5XlxFLX0
appq1EigWdMm2O123G7v52Kanj4Rlif+Ob0fhN0yPcHP2z+8fJOKNG7YmDW/rWX//v2ldg5y/vH1
wvF1Sja8z+KyjPzXpe/5XPnWybcHDON4aPJlIsPyzjv9fn4KPiJSduRr7vJ3gHSf+C0RMHw3zXz1
4L47rHddz/03X/gpxmax0so9rVpdRKNGDT0FsMA0THB7argsE1y4ybZyOJC2H4fDQYXQeBxuO6bT
xDBNz3YmdOnamY2bN7Py11WlcyJyHvLU1uS7BPN31/F/IzGMQq5njg9jN3y1u77anoBmrtO78BR8
RKQM8d3lvLU+FliG2z+yNX+28YcPX1gyPN8hTW+HaLzPCCF/HiqmGp/SyD2dO3egUeP6gInlMjAt
E9NbkjybRZbh5Kg7jV1Z+9jGehyWjQaRDahur04csTjcDmwubwAy4bK2bYmLiWHevAWlcDZy/vE1
U5PvZ2cMbx46PnqrsKZn36WKfx3jhNqegtv8FQUfESlDAmtsrICqH88NMX8ljqcGwzp+Q/XeeQ0A
0xucfENH/P5+bCnp0fXdunamTauLvH0lPGnOcFtY7jzcNjfHzCyOug6xLWc3f7p24a6Rw7HcHLYZ
O8kNgzr2MKra44iwwrFbBiaez7Ft27YYNpM5ifNK9oTkPBPwexPk78NsGZb/OT3+mld/+LGOv/V+
cfH10fOEH9/1XLSOego+IlIm+O6Nngm8FT/G8Yea+apuAkZ/+TsCeIMR3n4Cvn16gsJJg8oZNn+V
5GCyVpe05OpOXbwH9nTYsQwnkI3TdHKENPY7d7E5dzu7wg/hrOgkwjRxGPE4s0z25xzBZezB5ggn
MjSKSCIIxebpJ2XAVV2vYu/efWzasKnkTsorLuYScnKTycpOwjQdxMdcwrH0dTidaSVeFimiwi6q
fLOs45elf9rIV2V7PNhYJwk9+fr2FPF6U/ARkbLHOn7DCww/3m7PBv5n/HgqdCwsb/8Vw/e4+/xf
EvN3DyqVhqozExEezi0330xUePjxPyCmmzwjiwwjj8NWBr/n/cnmrD84GpmB4YAQTMJyTWJDY3DG
OXC57SSnHiArI5UsI4VW5ZsTY5YjlFDAjhu4+x93MeSZIWRmZZXYuTlCq1Cr2m1kZSexdedw4mNa
kVDlWsJSKrI3eVqJlUPOUL70b1F4CDpek8OJvZw9IzI9D6Xw19gWCD1F7Nvjo+AjImWE4Q0wcOLD
O3zhx7BMLDN/B8rjDzk0fB2BDO8IJ1+HSu++PYqnjaqkmrq69ryactUqYwfs3s/FZeRxjEySsw+y
MWsTSbY9pEUdwwyziMBJqMtG5dAoHLYQckJdZJjZuO1ZZJPCluT9RJDNxZVaUjWyJuFmNG6XSXx0
LD179GDylKklc2JAVs4B9h6YTmb2biwLjqauJsQeS8rRJfpx2jIncHSW4e2f46+NtXzNzfl7O/s2
tfJd3yeGnhObqU+Pgo+IlCF/EX78NT0eln8ou2cbvE1a/m+IxvGYY+TbfzEVs0Rcd31/IiKjsFlg
w8IkD8vIIicvmVDrT6qEHSYu1IXTFo5FHtHuGGKsSCJdEeTmOUkPySQNFwfT0sjFjWXa2L/5V3Yc
s5NwUXVioqKw8kwME24YcC2Tp5Zc8AGL5CPevkUGON0Z7Ds0wz8tZYdxsinrxCvweOjJXwHk+3JT
MPScWXkUfESkjCkk/Hibugx8D0TzLPM3g3kDkv9JzhaeobFG4H6Lr4RnX4d27ahRsRpO0/Qe042N
TAwgKy2LOtFQJ6o8mFG4ycWOjVhnJLYMGzZnBJnOTFLS3GS4nRw8ZudQcgbpRywOHEgjzXkI+4V2
oqOisVyes4mOiuCKyy9n0eLFJXB2YLfH0rbF5xxJXcXG34dQPr4djeo+zc6kiew58E2JlEGKm3XC
24CRCMd75HkDT0C/H98zfAJCz5ldaQo+IlIGnRB+8g9HN04Y5eEf9OX7TWbLG4zyVw8Vb+kK7dNQ
zNq0uoSIsAhcJjhNzzFt2AnBSRWrNhFHs9m6fAWHkpOIiytPgzoNiSAWl8tOhmHhzsnESHZycGsy
GakuqpevR3puGFHRkUSE18F0R2K5QwlzmNhsbjByaNOmGQsX/++sn5uPaYZhGiHez9PENMMwDHuJ
fL5ydhRWu3p80IF1vPueP/DgDzz4Bq//zdEDCj4iUkblDz/H53FC6DnxFun/fa8TNytjmjVphiPM
4Xkwoc3z8GXTCsVu2XDYQrAds0hZtZgFP22nafMQWt3TktiEehASituei+XOIyP5MDuXTsQ8FsXV
AwZjxVXFZY/EsDsIj47GHhqKzQTTyMPlzqFpk7oleIYGNtOBaYZ4pgwbNtOBYdhKsAxS3Ap9ZJbl
zzj53+QLPH+/lic/BR8RKcN8/XfI1/R1fBm+zo8FKoAKCT/FWaoSqJCoUbcqYRGG9+cmbN62ARPD
bQBubKHVqVHhQuyutcTG1CS6aj2iypcnCxdRIeUgJ5uQ+ChiHZWJjwijUt3mWBEOck0bzpBwct0W
bsOGzW1ht9kINUIoX6F6iZybj2mGYhh2799CE9MMxTRsJVoGKWb+3GKdMO/4z1EcX2TlyzrF9+1E
wUdEyjhvlAkIQOC/ewZ8xcx/sz3hRlqMf0ytEniQT0KdahiW5bmJuy1wm+AOAUIgJBRsWVSMr07l
ipVo2LgBkfGRHDh6ACvERnT5KhAWTmiIk+qVq2C47WTs2IVZpRqhNathmQYhgA07NkxMwAY0aXJR
iZwb4BmRZ9g9TVuG4RmNZ9jBMEuuDHJ2FbjmvM/w8f8T8KbYKPiIyHnCF4DAdwMNbAY74S57NmsN
SmC8dYTNgae6x+U9pg3DZQenAXlgt4cTHWEnPDQTu/sgxv6NLJiVSOduvbCXrwxkEZq7l5ioLMiN
YvtvG/g9cRk3PDCY8Phw8uxunHh+5MOOid0Cl9soubH6lqd5y8D0dETHN12CZZBiddIIcxZDTmEU
fETkPJQ/BPkU/GN5tv5+GiVQI7F/TzLVa1TFhYnbMDAIwWbaPH0hnLm4zFwOH0siLTOdsDAX3387
iaxsF1VrVcTM2o0rK50l33/Jnh37qV2tGYYZwu8b1rFi4UIu73s1hmnDMNwYWJ6h8pbJlq1/lMi5
gee/nWnYMAzTe0wD07ABZomVQc5PCj4iEiQK/rEsy38/k/bso0bNGmCYmIYdAwNPt18neaSyftMi
Nv++nAZN4oiv7MCKqUqfy68E90FcOfvJycjgt82rCCeODVtWkZ4JtrAwnM59uHKOYXPE4jZdgMv3
IF1SUw+X4BkagOl9+cKkQo/8feapVxERkXPNhk2bMDAwCcE0TEzDwjCyMczD7Nq6gA1rfyIlaxfH
cg6Qkp7MZb07E1O7HBs2LGPf0V1s3r6eI+nHyHFncTjtT45mbiKq/EEsYztZmduwWanYDBemYXiD
VRgbNm4rsfPzjOAycFu5nmlbhHfaWWJlkPOTanxERMqgxUuWM+juuzz1PIYbyAMjFWzJhEQdpWqD
KGIqX0BYiEGTixrhiAolOyOZJi3qsW/vH0SWr8iVvbpjpGfizErBFppNtjuDsIg/yMlZh2VFEWIk
4LaiMAjDwGTx4uUlcm6R4XVpVO8ZwCA9YysVy3WkdvW7vdObS6QMcv5S8BERKYNm/pRI2rFMYmKj
PX2VjBwsIxXDPEatBpWodUEPDHsI5LrB6QIMIuIqkJ62jwaNG+K23DS72IGVchhX5lHc7lSOHNlL
ep5JTsYfZKVXJiI2BtOIwrAM0o6lMSvxpxI5t4jwmsRGXci+gz+yM2k89WoOJtQexx+7xnD46NIS
KYOcvxR8RETKqHEfj+fxRx8Cy4llZGCRCmYamLmeUV7OUDDCwRECVhZudwaR0bG4ScVyHgP3foxo
F6aZTd6hNEzLTYjpIidjH0f2bSLEUY0wR3lwhTBu/Mcldl4HUxYwb2kb//SWHW+xZcdbJXZ8Ob8Z
DRo0LdPjAvPOYj83d3Q4uc2rk1e9HFZMOHmt6gAQ8usOjNQsQvakELpuD2Za1tkrhEhxKtNXe9mR
kZ5WIseJjYlh5dL5RMe5cLMLF0mYpGBiYLqjwB0HrkhPP2F7Hk4OYBipQDY2ssA6BK4c3KnZ5B1K
JTfbTUZOHmk5FnlWJSrUaEe5au3JTIukZfsuHEtNLZHzEjmbVOPzF8y0LByLt+HwzRj/c2kWR0Qk
wLHUVJ576UVGjvgnbvbg5gCQgYEDy4jAMO1ghHl/BiDH8xMfWJiEAjl4ftMjFzPMSUi0HbeVh5kL
NgPSs45ycM8GomJq8MDjExV65Lzx/ze1eTR4owP5AAAAAElFTkSuQmCC""".replace("\n","")
