"""Team colors for leagues whose score feeds do not carry them (MLB statsapi, NHL api-web).

Taken from ESPN's team listings, keyed by the abbreviation each league's own feed uses.
(primary, alternate) as hex; ``team_color`` decides which one reads on an LED panel.
"""

from __future__ import annotations

MLB: dict[str, tuple[str, str]] = {
    "ATH": ("003831", "efb21e"),  # Athletics
    "ATL": ("0c2340", "ba0c2f"),  # Atlanta Braves
    "AZ": ("aa182c", "000000"),  # Arizona Diamondbacks
    "BAL": ("df4601", "000000"),  # Baltimore Orioles
    "BOS": ("0d2b56", "bd3039"),  # Boston Red Sox
    "CHC": ("0e3386", "cc3433"),  # Chicago Cubs
    "CIN": ("c6011f", "ffffff"),  # Cincinnati Reds
    "CLE": ("002b5c", "e31937"),  # Cleveland Guardians
    "COL": ("33006f", "000000"),  # Colorado Rockies
    "CWS": ("000000", "c4ced4"),  # Chicago White Sox
    "DET": ("0a2240", "ff4713"),  # Detroit Tigers
    "HOU": ("002d62", "eb6e1f"),  # Houston Astros
    "KC": ("004687", "7ab2dd"),  # Kansas City Royals
    "LAA": ("ba0021", "c4ced4"),  # Los Angeles Angels
    "LAD": ("005a9c", "ffffff"),  # Los Angeles Dodgers
    "MIA": ("00a3e0", "000000"),  # Miami Marlins
    "MIL": ("13294b", "ffc72c"),  # Milwaukee Brewers
    "MIN": ("031f40", "e20e32"),  # Minnesota Twins
    "NYM": ("002d72", "ff5910"),  # New York Mets
    "NYY": ("132448", "c4ced4"),  # New York Yankees
    "PHI": ("e81828", "003278"),  # Philadelphia Phillies
    "PIT": ("000000", "fdb827"),  # Pittsburgh Pirates
    "SD": ("2f241d", "ffc425"),  # San Diego Padres
    "SEA": ("005c5c", "0c2c56"),  # Seattle Mariners
    "SF": ("000000", "fd5a1e"),  # San Francisco Giants
    "STL": ("be0a14", "001541"),  # St. Louis Cardinals
    "TB": ("092c5c", "8fbce6"),  # Tampa Bay Rays
    "TEX": ("003278", "c0111f"),  # Texas Rangers
    "TOR": ("134a8e", "6cace5"),  # Toronto Blue Jays
    "WSH": ("ab0003", "11225b"),  # Washington Nationals
}

NHL: dict[str, tuple[str, str]] = {
    "ANA": ("fc4c02", "000000"),  # Anaheim Ducks
    "BOS": ("231f20", "fdb71a"),  # Boston Bruins
    "BUF": ("00468b", "fdb71a"),  # Buffalo Sabres
    "CAR": ("e30426", "000000"),  # Carolina Hurricanes
    "CBJ": ("002d62", "e31937"),  # Columbus Blue Jackets
    "CGY": ("dd1a32", "000000"),  # Calgary Flames
    "CHI": ("e31937", "000000"),  # Chicago Blackhawks
    "COL": ("860038", "005ea3"),  # Colorado Avalanche
    "DAL": ("20864c", "000000"),  # Dallas Stars
    "DET": ("e30526", "ffffff"),  # Detroit Red Wings
    "EDM": ("00205b", "ff4c00"),  # Edmonton Oilers
    "FLA": ("e51937", "002d62"),  # Florida Panthers
    "LAK": ("121212", "a2aaad"),  # Los Angeles Kings
    "MIN": ("124734", "ae122a"),  # Minnesota Wild
    "MTL": ("c41230", "013a81"),  # Montreal Canadiens
    "NJD": ("e30b2b", "000000"),  # New Jersey Devils
    "NSH": ("fdba31", "002d62"),  # Nashville Predators
    "NYI": ("00529b", "f47d31"),  # New York Islanders
    "NYR": ("0056ae", "e51937"),  # New York Rangers
    "OTT": ("dd1a32", "b79257"),  # Ottawa Senators
    "PHI": ("fe5823", "000000"),  # Philadelphia Flyers
    "PIT": ("000000", "fdb71a"),  # Pittsburgh Penguins
    "SEA": ("000d33", "a3dce4"),  # Seattle Kraken
    "SJS": ("00788a", "070707"),  # San Jose Sharks
    "STL": ("0070b9", "fdb71a"),  # St. Louis Blues
    "TBL": ("003e7e", "ffffff"),  # Tampa Bay Lightning
    "TOR": ("003e7e", "ffffff"),  # Toronto Maple Leafs
    "UTA": ("000000", "7ab2e1"),  # Utah Mammoth
    "VAN": ("003e7e", "008752"),  # Vancouver Canucks
    "VGK": ("344043", "b4975a"),  # Vegas Golden Knights
    "WPG": ("002d62", "c41230"),  # Winnipeg Jets
    "WSH": ("d71830", "0b1f41"),  # Washington Capitals
}
