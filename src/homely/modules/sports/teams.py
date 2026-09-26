"""Team palettes for the sports cards, as in the MLB LED scoreboard.

Each palette is three colors: ``home``, the band drawn behind the team's row; ``text``, the name and
score on it; and ``accent``, the bar at the row's left edge. They are drawn exactly as written, with
no lifting or swapping, so if a team looks wrong this table is what to change.

MLB comes from new-mlb-scoreboard's team-colors.txt (everyday uniforms); NFL, NBA and NHL from Leah's
"other team colors" list. Keys are the abbreviations each league's feed uses: statsapi for MLB, the
NHL web API for hockey, ESPN for football and basketball. Leagues not listed here fall back to the
colors ESPN sends (see ``palette_for``).
"""

from __future__ import annotations

from dataclasses import dataclass

Color = tuple[int, int, int]


@dataclass(frozen=True)
class Palette:
    home: Color  # the band behind the row
    text: Color  # name and score
    accent: Color  # the bar at the left edge


P = Palette

MLB: dict[str, Palette] = {
    "ATH": P((2, 70, 56), (255, 184, 28), (255, 184, 28)),  # Athletics
    "ATL": P((12, 35, 64), (255, 255, 255), (186, 12, 47)),  # Atlanta Braves
    "AZ": P((166, 25, 46), (217, 200, 157), (0, 0, 0)),  # Arizona Diamondbacks
    "BAL": P((252, 76, 2), (0, 0, 0), (255, 255, 255)),  # Baltimore Orioles
    "BOS": P((200, 16, 46), (255, 255, 255), (12, 35, 64)),  # Boston Red Sox
    "CHC": P((0, 47, 108), (255, 255, 255), (200, 16, 46)),  # Chicago Cubs
    "CIN": P((186, 12, 47), (255, 255, 255), (0, 0, 0)),  # Cincinnati Reds
    "CLE": P((227, 227, 239), (204, 0, 46), (11, 34, 63)),  # Cleveland Guardians
    "COL": P((51, 0, 114), (141, 144, 147), (0, 0, 0)),  # Colorado Rockies
    "CWS": P((0, 0, 0), (141, 144, 147), (255, 255, 255)),  # Chicago White Sox
    "DET": P((12, 35, 64), (250, 70, 22), (250, 70, 22)),  # Detroit Tigers
    "HOU": P((4, 30, 66), (207, 69, 32), (229, 114, 0)),  # Houston Astros
    "KC": P((0, 45, 114), (255, 255, 255), (137, 115, 76)),  # Kansas City Royals
    "LAA": P((186, 12, 47), (255, 255, 255), (12, 35, 64)),  # Los Angeles Angels
    "LAD": P((0, 47, 108), (255, 255, 255), (145, 157, 157)),  # Los Angeles Dodgers
    "MIA": P((0, 0, 0), (0, 163, 224), (239, 51, 64)),  # Miami Marlins
    "MIL": P((19, 41, 75), (255, 199, 44), (0, 61, 165)),  # Milwaukee Brewers
    "MIN": P((12, 35, 64), (255, 255, 255), (186, 12, 47)),  # Minnesota Twins
    "NYM": P((0, 45, 114), (252, 76, 2), (255, 255, 255)),  # New York Mets
    "NYY": P((12, 35, 64), (255, 255, 255), (255, 255, 255)),  # New York Yankees
    "PHI": P((186, 12, 47), (255, 255, 255), (0, 45, 114)),  # Philadelphia Phillies
    "PIT": P((0, 0, 0), (255, 199, 44), (255, 199, 44)),  # Pittsburgh Pirates
    "SD": P((62, 52, 47), (255, 199, 44), (183, 169, 154)),  # San Diego Padres
    "SEA": P((12, 44, 86), (141, 144, 147), (0, 104, 94)),  # Seattle Mariners
    "SF": P((250, 70, 22), (0, 0, 0), (239, 209, 159)),  # San Francisco Giants
    "STL": P((186, 12, 47), (255, 255, 255), (12, 35, 64)),  # St. Louis Cardinals
    "TB": P((4, 30, 66), (255, 255, 255), (105, 179, 231)),  # Tampa Bay Rays
    "TEX": P((0, 45, 114), (255, 255, 255), (186, 12, 47)),  # Texas Rangers
    "TOR": P((0, 61, 165), (255, 255, 255), (108, 172, 228)),  # Toronto Blue Jays
    "WSH": P((186, 12, 47), (255, 255, 255), (4, 30, 66)),  # Washington Nationals
}

NFL: dict[str, Palette] = {
    "ARI": P((151, 35, 63), (255, 255, 255), (255, 255, 255)),  # Arizona Cardinals
    "ATL": P((167, 25, 48), (255, 255, 255), (0, 0, 0)),  # Atlanta Falcons
    "BAL": P((36, 19, 95), (255, 255, 255), (154, 118, 17)),  # Baltimore Ravens
    "BUF": P((0, 51, 141), (255, 255, 255), (198, 12, 48)),  # Buffalo Bills
    "CAR": P((0, 133, 202), (255, 255, 255), (0, 0, 0)),  # Carolina Panthers
    "CHI": P((230, 65, 0), (255, 255, 255), (11, 22, 42)),  # Chicago Bears
    "CIN": P((251, 79, 20), (255, 255, 255), (0, 0, 0)),  # Cincinnati Bengals
    "CLE": P((49, 29, 0), (255, 255, 255), (255, 60, 0)),  # Cleveland Browns
    "DAL": P((0, 34, 68), (176, 183, 188), (0, 51, 141)),  # Dallas Cowboys
    "DEN": P((252, 76, 2), (255, 255, 255), (10, 35, 67)),  # Denver Broncos
    "DET": P((0, 118, 182), (255, 255, 255), (176, 183, 188)),  # Detroit Lions
    "GB": P((32, 55, 49), (255, 255, 255), (255, 182, 18)),  # Green Bay Packers
    "HOU": P((2, 16, 24), (255, 255, 255), (235, 0, 40)),  # Houston Texans
    "IND": P((1, 51, 105), (165, 172, 175), (165, 172, 175)),  # Indianapolis Colts
    "JAX": P((0, 103, 120), (0, 0, 0), (215, 162, 42)),  # Jacksonville Jaguars
    "KC": P((227, 24, 55), (255, 255, 255), (255, 182, 18)),  # Kansas City Chiefs
    "LAC": P((0, 128, 198), (255, 255, 255), (255, 194, 14)),  # Los Angeles Chargers
    "LAR": P((0, 53, 148), (255, 255, 255), (255, 209, 0)),  # Los Angeles Rams
    "LV": P((0, 0, 0), (255, 255, 255), (200, 199, 199)),  # Las Vegas Raiders
    "MIA": P((0, 142, 151), (255, 255, 255), (252, 76, 2)),  # Miami Dolphins
    "MIN": P((79, 38, 131), (255, 255, 255), (255, 198, 47)),  # Minnesota Vikings
    "NE": P((0, 34, 68), (176, 183, 188), (198, 12, 48)),  # New England Patriots
    "NO": P((211, 188, 141), (0, 0, 0), (255, 255, 255)),  # New Orleans Saints
    "NYG": P((11, 34, 101), (255, 255, 255), (167, 25, 48)),  # New York Giants
    "NYJ": P((17, 87, 64), (255, 255, 255), (0, 0, 0)),  # New York Jets
    "PHI": P((0, 72, 81), (255, 255, 255), (162, 170, 173)),  # Philadelphia Eagles
    "PIT": P((255, 182, 18), (0, 0, 0), (0, 0, 0)),  # Pittsburgh Steelers
    "SEA": P((0, 34, 68), (165, 172, 175), (105, 190, 40)),  # Seattle Seahawks
    "SF": P((170, 0, 0), (255, 255, 255), (179, 153, 93)),  # San Francisco 49ers
    "TB": P((167, 25, 48), (255, 255, 255), (50, 47, 43)),  # Tampa Bay Buccaneers
    "TEN": P((68, 149, 210), (255, 255, 255), (213, 10, 10)),  # Tennessee Titans
    "WSH": P((90, 20, 20), (255, 255, 255), (255, 182, 18)),  # Washington Commanders
}

NBA: dict[str, Palette] = {
    "ATL": P((200, 16, 46), (255, 255, 255), (253, 185, 39)),  # Atlanta Hawks
    "BKN": P((0, 0, 0), (255, 255, 255), (255, 255, 255)),  # Brooklyn Nets
    "BOS": P((0, 131, 72), (255, 255, 255), (255, 255, 255)),  # Boston Celtics
    "CHA": P((0, 120, 140), (255, 255, 255), (29, 17, 96)),  # Charlotte Hornets
    "CHI": P((206, 17, 65), (255, 255, 255), (0, 0, 0)),  # Chicago Bulls
    "CLE": P((134, 0, 56), (255, 255, 255), (188, 148, 92)),  # Cleveland Cavaliers
    "DAL": P((0, 100, 177), (184, 196, 202), (184, 196, 202)),  # Dallas Mavericks
    "DEN": P((14, 34, 64), (255, 255, 255), (254, 197, 36)),  # Denver Nuggets
    "DET": P((29, 66, 138), (190, 192, 194), (200, 16, 46)),  # Detroit Pistons
    "GS": P((29, 66, 138), (255, 255, 255), (253, 185, 39)),  # Golden State Warriors
    "HOU": P((206, 14, 45), (255, 255, 255), (255, 213, 32)),  # Houston Rockets
    "IND": P((12, 35, 64), (158, 162, 162), (255, 213, 32)),  # Indiana Pacers
    "LAC": P((18, 23, 63), (160, 162, 163), (200, 16, 46)),  # Los Angeles Clippers
    "LAL": P((49, 0, 111), (255, 255, 255), (253, 185, 39)),  # Los Angeles Lakers
    "MEM": P((93, 118, 169), (255, 255, 255), (18, 23, 63)),  # Memphis Grizzlies
    "MIA": P((152, 0, 46), (255, 255, 255), (249, 160, 27)),  # Miami Heat
    "MIL": P((0, 71, 27), (238, 225, 198), (238, 225, 198)),  # Milwaukee Bucks
    "MIN": P((29, 66, 138), (193, 198, 200), (0, 154, 68)),  # Minnesota Timberwolves
    "NO": P((12, 35, 64), (255, 255, 255), (185, 151, 91)),  # New Orleans Pelicans
    "NY": P((29, 66, 138), (158, 162, 162), (245, 132, 38)),  # New York Knicks
    "OKC": P((0, 122, 193), (255, 255, 255), (253, 187, 48)),  # Oklahoma City Thunder
    "ORL": P((0, 80, 181), (196, 206, 212), (0, 0, 0)),  # Orlando Magic
    "PHI": P((29, 66, 138), (196, 206, 212), (200, 16, 46)),  # Philadelphia 76ers
    "PHX": P((29, 17, 96), (249, 160, 27), (249, 160, 27)),  # Phoenix Suns
    "POR": P((0, 0, 0), (255, 255, 255), (224, 58, 62)),  # Portland Trail Blazers
    "SA": P((0, 0, 0), (255, 255, 255), (196, 206, 212)),  # San Antonio Spurs
    "SAC": P((90, 45, 129), (255, 255, 255), (112, 114, 113)),  # Sacramento Kings
    "TOR": P((206, 17, 65), (255, 255, 255), (0, 0, 0)),  # Toronto Raptors
    "UTAH": P((78, 0, 142), (255, 255, 255), (121, 163, 220)),  # Utah Jazz
    "WSH": P((0, 43, 92), (196, 206, 212), (227, 24, 55)),  # Washington Wizards
}

NHL: dict[str, Palette] = {
    "ANA": P((207, 69, 32), (255, 255, 255), (137, 115, 76)),  # Anaheim Ducks
    "BOS": P((255, 184, 28), (0, 0, 0), (1, 1, 1)),  # Boston Bruins
    "BUF": P((0, 48, 135), (255, 255, 255), (255, 184, 28)),  # Buffalo Sabres
    "CAR": P((204, 0, 0), (255, 255, 255), (0, 0, 0)),  # Carolina Hurricanes
    "CBJ": P((4, 30, 66), (162, 170, 173), (200, 16, 46)),  # Columbus Blue Jackets
    "CGY": P((200, 16, 46), (255, 255, 255), (241, 190, 72)),  # Calgary Flames
    "CHI": P((206, 17, 38), (255, 255, 255), (255, 255, 255)),  # Chicago Blackhawks
    "COL": P((138, 36, 50), (255, 255, 255), (35, 96, 147)),  # Colorado Avalanche
    "DAL": P((0, 130, 62), (0, 0, 0), (162, 170, 173)),  # Dallas Stars
    "DET": P((200, 16, 46), (255, 255, 255), (255, 255, 255)),  # Detroit Red Wings
    "EDM": P((0, 32, 91), (255, 255, 255), (209, 69, 32)),  # Edmonton Oilers
    "FLA": P((200, 16, 46), (255, 255, 255), (185, 151, 91)),  # Florida Panthers
    "LAK": P((162, 170, 173), (0, 0, 0), (0, 0, 0)),  # Los Angeles Kings
    "MIN": P((14, 68, 49), (221, 201, 163), (172, 26, 46)),  # Minnesota Wild
    "MTL": P((166, 25, 46), (255, 255, 255), (0, 30, 98)),  # Montreal Canadiens
    "NJD": P((255, 255, 255), (204, 0, 0), (0, 0, 0)),  # New Jersey Devils
    "NSH": P((4, 30, 66), (255, 255, 255), (255, 184, 28)),  # Nashville Predators
    "NYI": P((0, 48, 135), (252, 76, 2), (255, 255, 255)),  # New York Islanders
    "NYR": P((21, 75, 148), (255, 255, 255), (195, 32, 50)),  # New York Rangers
    "OTT": P((200, 16, 46), (255, 255, 255), (185, 151, 91)),  # Ottawa Senators
    "PHI": P((210, 67, 3), (255, 255, 255), (0, 0, 0)),  # Philadelphia Flyers
    "PIT": P((0, 0, 0), (255, 255, 255), (255, 184, 28)),  # Pittsburgh Penguins
    "SEA": P((0, 20, 37), (255, 255, 255), (150, 216, 216)),  # Seattle Kraken
    "SJS": P((0, 119, 139), (255, 255, 255), (0, 0, 0)),  # San Jose Sharks
    "STL": P((0, 106, 198), (255, 255, 255), (255, 184, 28)),  # St. Louis Blues
    "TBL": P((0, 32, 91), (255, 255, 255), (0, 0, 0)),  # Tampa Bay Lightning
    "TOR": P((0, 32, 91), (255, 255, 255), (255, 255, 255)),  # Toronto Maple Leafs
    "UTA": P((122, 178, 224), (1, 1, 1), (255, 255, 255)),  # Utah Mammoth
    "VAN": P((0, 32, 91), (255, 255, 255), (4, 106, 56)),  # Vancouver Canucks
    "VGK": P((51, 63, 72), (255, 255, 255), (185, 151, 91)),  # Vegas Golden Knights
    "WPG": P((162, 170, 173), (0, 0, 0), (4, 30, 66)),  # Winnipeg Jets
    "WSH": P((200, 16, 46), (255, 255, 255), (4, 30, 66)),  # Washington Capitals
}

PALETTES: dict[str, dict[str, Palette]] = {"mlb": MLB, "nfl": NFL, "nba": NBA, "nhl": NHL}
