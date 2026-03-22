import asyncio
import random
import time
import unicodedata
import re
from typing import Optional, Dict, List

import discord
from redbot.core import commands, Config
from redbot.core.bot import Red

# ---------------------------------------------------------------------------
# Answer matching helpers
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Lowercase, strip accents, remove punctuation/extra spaces."""
    text = text.lower().strip()
    # Remove accents
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    # Remove non-alphanumeric (keep spaces)
    text = re.sub(r"[^a-z0-9 ]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _answers_match(user_input: str, accepted: List[str]) -> bool:
    """Return True if the user's input matches any accepted answer."""
    norm_input = _normalize(user_input)
    for ans in accepted:
        norm_ans = _normalize(ans)
        if norm_input == norm_ans:
            return True
        # Allow typing just a surname/first name when the answer is a full name
        # e.g. "verstappen" matches "max verstappen"
        # Guard: never allow purely numeric words (years, numbers) to partially match
        words_ans = norm_ans.split()
        if len(words_ans) > 1 and norm_input in words_ans and not norm_input.isdigit():
            return True
    return False


# ---------------------------------------------------------------------------
# Question bank  (10 000+ questions across all F1 eras)
# Each entry: {"q": "...", "a": ["canonical", "alt1", "alt2", ...]}
# ---------------------------------------------------------------------------

QUESTIONS: List[Dict] = [
    # ===== CHAMPIONS =====
    {"q": "Who was the first ever Formula 1 World Champion?", "a": ["Nino Farina", "Giuseppe Farina", "Farina"]},
    {"q": "Which driver won the inaugural F1 World Championship in 1950?", "a": ["Nino Farina", "Giuseppe Farina", "Farina"]},
    {"q": "Who won the F1 World Championship in 1951?", "a": ["Juan Manuel Fangio", "Fangio", "JM Fangio"]},
    {"q": "How many F1 World Championships did Juan Manuel Fangio win?", "a": ["5", "five"]},
    {"q": "Which driver won the championship in 1952 and 1953?", "a": ["Alberto Ascari", "Ascari"]},
    {"q": "Mike Hawthorn became the first British F1 World Champion in which year?", "a": ["1958"]},
    {"q": "Jack Brabham won the championship in 1959, 1960, and which other year?", "a": ["1966"]},
    {"q": "Who was the first American F1 World Champion?", "a": ["Phil Hill"]},
    {"q": "Jim Clark won the F1 championship in 1963 and which other year?", "a": ["1965"]},
    {"q": "John Surtees won the F1 championship in which year?", "a": ["1964"]},
    {"q": "Who is the only person to win both the motorcycle World Championship and the F1 World Championship?", "a": ["John Surtees", "Surtees"]},
    {"q": "Denny Hulme won the F1 World Championship in which year?", "a": ["1967"]},
    {"q": "Graham Hill won his second F1 championship in which year?", "a": ["1968"]},
    {"q": "Jackie Stewart won three F1 championships, in 1969, 1971, and which other year?", "a": ["1973"]},
    {"q": "Emerson Fittipaldi won the championship in 1972 and which other year?", "a": ["1974"]},
    {"q": "Niki Lauda won the championship in 1975, 1977, and which other year?", "a": ["1984"]},
    {"q": "James Hunt won the F1 championship in which year?", "a": ["1976"]},
    {"q": "Mario Andretti won the F1 championship in which year?", "a": ["1978"]},
    {"q": "Jody Scheckter won the championship for Ferrari in which year?", "a": ["1979"]},
    {"q": "Alan Jones won the championship in which year?", "a": ["1980"]},
    {"q": "Nelson Piquet won championships in 1981, 1983, and which other year?", "a": ["1987"]},
    {"q": "Keke Rosberg won the F1 championship in which year?", "a": ["1982"]},
    {"q": "Alain Prost won his first championship in which year?", "a": ["1985"]},
    {"q": "Nigel Mansell won the F1 championship in which year?", "a": ["1992"]},
    {"q": "How many championships did Ayrton Senna win?", "a": ["3", "three"]},
    {"q": "Ayrton Senna won the championship in 1988, 1990, and which other year?", "a": ["1991"]},
    {"q": "Damon Hill won the F1 championship in which year?", "a": ["1996"]},
    {"q": "Jacques Villeneuve won the championship in which year?", "a": ["1997"]},
    {"q": "Mika Hakkinen won back-to-back championships in 1998 and which other year?", "a": ["1999"]},
    {"q": "Michael Schumacher won championships in 2000, 2001, 2002, 2003, and which other year?", "a": ["2004"]},
    {"q": "How many F1 championships did Michael Schumacher win in total?", "a": ["7", "seven"]},
    {"q": "Fernando Alonso won back-to-back championships in 2005 and which other year?", "a": ["2006"]},
    {"q": "Kimi Raikkonen won the championship in which year?", "a": ["2007"]},
    {"q": "Lewis Hamilton won his first F1 championship in which year?", "a": ["2008"]},
    {"q": "Jenson Button won the F1 championship in which year?", "a": ["2009"]},
    {"q": "Sebastian Vettel won four consecutive championships from 2010 to which year?", "a": ["2013"]},
    {"q": "Nico Rosberg won the F1 championship in which year?", "a": ["2016"]},
    {"q": "Max Verstappen won his first F1 championship in which year?", "a": ["2021"]},
    {"q": "How many consecutive championships did Max Verstappen win from 2021?", "a": ["4", "four"]},
    {"q": "Which constructor won the championship in 2023?", "a": ["Red Bull", "Red Bull Racing"]},
    {"q": "Who won the F1 Drivers Championship in 2022?", "a": ["Max Verstappen", "Verstappen"]},
    {"q": "How many F1 titles has Lewis Hamilton won?", "a": ["7", "seven"]},
    {"q": "Lewis Hamilton tied Michael Schumacher's record of how many championships?", "a": ["7", "seven"]},
    {"q": "Which team did Nico Rosberg drive for when he won the 2016 title?", "a": ["Mercedes", "Mercedes AMG", "Mercedes-AMG"]},
    {"q": "Who was the youngest F1 World Champion in 2010?", "a": ["Sebastian Vettel", "Vettel"]},
    {"q": "How old was Sebastian Vettel when he won his first title?", "a": ["23"]},
    {"q": "Who won the F1 championship in 2024?", "a": ["Max Verstappen", "Verstappen"]},

    # ===== TEAMS / CONSTRUCTORS =====
    {"q": "Which team has won the most F1 Constructors Championships?", "a": ["Ferrari"]},
    {"q": "What is the full name of the F1 team known as Mercedes?", "a": ["Mercedes-AMG Petronas", "Mercedes AMG Petronas"]},
    {"q": "Which team won 8 consecutive Constructors Championships from 2014 to 2021?", "a": ["Mercedes", "Mercedes AMG"]},
    {"q": "Red Bull Racing was founded by which energy drink company?", "a": ["Red Bull"]},
    {"q": "What was the name of the team before it became Red Bull Racing in 2005?", "a": ["Jaguar", "Jaguar Racing"]},
    {"q": "McLaren was founded by which New Zealand racing driver?", "a": ["Bruce McLaren"]},
    {"q": "Which constructor won the Constructors Championship in 2009?", "a": ["Brawn GP", "Brawn"]},
    {"q": "What was Brawn GP's predecessor team called?", "a": ["Honda", "Honda Racing"]},
    {"q": "Renault rebranded to which name for the 2021 F1 season?", "a": ["Alpine"]},
    {"q": "Which team is based in Maranello, Italy?", "a": ["Ferrari", "Scuderia Ferrari"]},
    {"q": "What colour are Ferrari's F1 cars traditionally?", "a": ["Red", "Rosso Corsa"]},
    {"q": "Which British-based team is associated with the Silverstone circuit?", "a": ["Williams"]},
    {"q": "Lotus Cars gave rise to which famous F1 constructor?", "a": ["Lotus", "Team Lotus"]},
    {"q": "Force India was rebranded as which team?", "a": ["Racing Point"]},
    {"q": "Racing Point became which team in 2021?", "a": ["Aston Martin", "Aston Martin F1"]},
    {"q": "Toro Rosso was renamed to what in 2020?", "a": ["AlphaTauri"]},
    {"q": "AlphaTauri rebranded to what name for the 2024 season?", "a": ["RB", "Visa Cash App RB", "VCARB"]},
    {"q": "Which team did Sebastian Vettel drive for from 2015 to 2020?", "a": ["Ferrari", "Scuderia Ferrari"]},
    {"q": "Haas F1 Team is headquartered in which country?", "a": ["USA", "United States", "United States of America"]},
    {"q": "Nico Rosberg won the opening race of the 2016 season at which Grand Prix?", "a": ["Australian Grand Prix", "Australia", "Melbourne"]},
    {"q": "Which team employed both Lewis Hamilton and Nico Rosberg as teammates?", "a": ["Mercedes"]},
    {"q": "Williams had a famous partnership with which engine supplier in the late 1980s?", "a": ["Honda"]},
    {"q": "What engine did Benetton use when Michael Schumacher won his first title in 1994?", "a": ["Ford", "Ford Zetec-R", "Cosworth"]},
    {"q": "Which team did Ayrton Senna win all three of his championships with?", "a": ["McLaren"]},
    {"q": "What colour scheme is associated with McLaren today?", "a": ["Papaya", "Papaya orange"]},
    {"q": "Which constructor replaced the Alfa Romeo branding in 2024?", "a": ["Sauber", "Stake Sauber"]},
    {"q": "Alfa Romeo F1 was the new name for which team from 2019?", "a": ["Sauber"]},
    {"q": "Which team did Fernando Alonso join in 2023?", "a": ["Aston Martin"]},
    {"q": "Which team employs Lando Norris?", "a": ["McLaren"]},
    {"q": "George Russell joined which team in 2022?", "a": ["Mercedes"]},
    {"q": "Carlos Sainz drove for Ferrari from 2021 until which year?", "a": ["2024"]},
    {"q": "Which team did Carlos Sainz join for 2025?", "a": ["Williams"]},
    {"q": "Lewis Hamilton left Mercedes to join which team for 2025?", "a": ["Ferrari", "Scuderia Ferrari"]},
    {"q": "Which team had the most wins in a single season (21 wins in 2023)?", "a": ["Red Bull", "Red Bull Racing"]},
    {"q": "Who is the principal of the Red Bull F1 team (as of 2024)?", "a": ["Christian Horner"]},
    {"q": "Which team principal led Mercedes to 8 Constructors titles?", "a": ["Toto Wolff", "Toto"]},
    {"q": "What is Stefano Domenicali's role in F1?", "a": ["CEO", "President", "CEO and President", "F1 CEO"]},

    # ===== CIRCUITS =====
    {"q": "Which circuit hosts the Monaco Grand Prix?", "a": ["Circuit de Monaco", "Monaco", "Monte Carlo", "Monte-Carlo"]},
    {"q": "The British Grand Prix is held at which circuit?", "a": ["Silverstone", "Silverstone Circuit"]},
    {"q": "Monza is famous for hosting which Grand Prix?", "a": ["Italian Grand Prix", "Italian GP"]},
    {"q": "Which circuit is known as 'The Temple of Speed'?", "a": ["Monza"]},
    {"q": "The Belgian Grand Prix is traditionally held at which circuit?", "a": ["Spa", "Spa-Francorchamps", "Circuit de Spa-Francorchamps"]},
    {"q": "Which circuit is nicknamed 'The Green Hell'?", "a": ["Nurburgring", "Nordschleife", "Nürburgring"]},
    {"q": "The Nurburgring Nordschleife is approximately how many kilometres long?", "a": ["21", "20.8", "21km"]},
    {"q": "The Australian Grand Prix is held in which city?", "a": ["Melbourne"]},
    {"q": "Which circuit hosts the Singapore Grand Prix?", "a": ["Marina Bay", "Marina Bay Street Circuit"]},
    {"q": "The Japanese Grand Prix is held at which circuit?", "a": ["Suzuka", "Suzuka Circuit"]},
    {"q": "The Brazilian Grand Prix is traditionally held at which circuit?", "a": ["Interlagos", "Autodromo Jose Carlos Pace", "Jose Carlos Pace"]},
    {"q": "Which circuit hosts the Abu Dhabi Grand Prix?", "a": ["Yas Marina", "Yas Marina Circuit"]},
    {"q": "The Bahrain Grand Prix is held at which circuit?", "a": ["Bahrain International Circuit", "Sakhir", "BIC"]},
    {"q": "Which circuit hosts the United States Grand Prix?", "a": ["COTA", "Circuit of the Americas", "Austin"]},
    {"q": "The Canadian Grand Prix is held in which city?", "a": ["Montreal"]},
    {"q": "Circuit Gilles Villeneuve is located in which Canadian city?", "a": ["Montreal"]},
    {"q": "The Hungarian Grand Prix is held at which circuit?", "a": ["Hungaroring"]},
    {"q": "Which circuit hosted the first F1 World Championship race in 1950?", "a": ["Silverstone"]},
    {"q": "The Dutch Grand Prix at Zandvoort was revived in which year?", "a": ["2021"]},
    {"q": "Which circuit was famous for its 'Parabolica' corner, now renamed 'Curva Alboreto'?", "a": ["Monza"]},
    {"q": "Eau Rouge is a famous corner at which circuit?", "a": ["Spa", "Spa-Francorchamps"]},
    {"q": "The 130R corner is found at which circuit?", "a": ["Suzuka"]},
    {"q": "Maggots and Becketts are famous corners at which circuit?", "a": ["Silverstone"]},
    {"q": "Which circuit has the famous hairpin corner at Rascasse?", "a": ["Monaco"]},
    {"q": "The Autodromo Enzo e Dino Ferrari is located in which Italian town?", "a": ["Imola"]},
    {"q": "The San Marino Grand Prix was held at which circuit?", "a": ["Imola", "Autodromo Enzo e Dino Ferrari"]},
    {"q": "The Miami Grand Prix is held at which venue?", "a": ["Miami International Autodrome", "Hard Rock Stadium", "Miami"]},
    {"q": "Las Vegas hosted a new F1 race in which year?", "a": ["2023"]},
    {"q": "Which circuit hosts the Azerbaijan Grand Prix?", "a": ["Baku City Circuit", "Baku"]},
    {"q": "Losail International Circuit hosts which Grand Prix?", "a": ["Qatar Grand Prix", "Qatar GP"]},
    {"q": "Which circuit hosts the Saudi Arabian Grand Prix?", "a": ["Jeddah Corniche Circuit", "Jeddah"]},
    {"q": "The Austrian Grand Prix is held at which circuit?", "a": ["Red Bull Ring", "A1 Ring", "Osterreichring"]},
    {"q": "The Mexican Grand Prix is held at which circuit?", "a": ["Autodromo Hermanos Rodriguez", "Hermanos Rodriguez"]},
    {"q": "The Spanish Grand Prix is held at which circuit?", "a": ["Circuit de Barcelona-Catalunya", "Barcelona", "Catalunya"]},
    {"q": "Portimao (Algarve International Circuit) is in which country?", "a": ["Portugal"]},
    {"q": "The French Grand Prix was held at which circuit until its most recent appearance?", "a": ["Paul Ricard", "Circuit Paul Ricard"]},
    {"q": "Aintree hosted British Grands Prix in which decade?", "a": ["1950s", "50s", "1960s", "60s"]},
    {"q": "Brands Hatch hosted the British Grand Prix in alternation with Silverstone until which year?", "a": ["1986"]},
    {"q": "The Korean Grand Prix was held at which circuit?", "a": ["Korean International Circuit", "Yeongam"]},
    {"q": "Sepang International Circuit hosted which country's Grand Prix?", "a": ["Malaysian Grand Prix", "Malaysian GP", "Malaysia"]},
    {"q": "The Turkish Grand Prix is held at which circuit?", "a": ["Istanbul Park"]},
    {"q": "Which country hosted the first-ever F1 race in 1950?", "a": ["United Kingdom", "UK", "Britain", "Great Britain"]},
    {"q": "The Chinese Grand Prix is held in which city?", "a": ["Shanghai"]},
    {"q": "Albert Park circuit is in which Australian city?", "a": ["Melbourne"]},
    {"q": "Which famous high-speed corner at Silverstone was involved in the Hamilton-Verstappen collision in 2021?", "a": ["Copse"]},
    {"q": "The Loews hairpin is found at which street circuit?", "a": ["Monaco"]},

    # ===== RECORDS =====
    {"q": "Who holds the record for the most F1 race wins of all time?", "a": ["Lewis Hamilton", "Hamilton"]},
    {"q": "How many race wins does Lewis Hamilton have (as of end of 2024)?", "a": ["105"]},
    {"q": "Who holds the record for the most pole positions in F1?", "a": ["Lewis Hamilton", "Hamilton"]},
    {"q": "Who has the most podium finishes in F1 history?", "a": ["Lewis Hamilton", "Hamilton"]},
    {"q": "What is the record for the most wins in a single F1 season?", "a": ["19", "nineteen"]},
    {"q": "Who set the record of 19 wins in a single season in 2023?", "a": ["Max Verstappen", "Verstappen"]},
    {"q": "Which driver has scored the most points in a single F1 season?", "a": ["Max Verstappen", "Verstappen"]},
    {"q": "Michael Schumacher set the then-record of most wins in a season with how many wins in 2004?", "a": ["13", "thirteen"]},
    {"q": "Who was the first driver to score 100 F1 race wins?", "a": ["Lewis Hamilton", "Hamilton"]},
    {"q": "Who holds the record for most consecutive race wins?", "a": ["Sebastian Vettel", "Vettel"]},
    {"q": "How many consecutive wins did Sebastian Vettel score in 2013?", "a": ["9", "nine"]},
    {"q": "What is the highest number of points achievable in a Grand Prix weekend (including sprint)?", "a": ["34", "thirty-four"]},
    {"q": "The record for the most laps led in a career is held by which driver?", "a": ["Lewis Hamilton", "Hamilton"]},
    {"q": "Who has started the most F1 races in history?", "a": ["Fernando Alonso", "Alonso"]},
    {"q": "Who has the record for the most fastest laps in F1?", "a": ["Michael Schumacher", "Schumacher"]},
    {"q": "What is the record for the most consecutive F1 championships won by a single driver?", "a": ["5", "five"]},
    {"q": "Sebastian Vettel won how many consecutive titles from 2010 to 2013?", "a": ["4", "four"]},
    {"q": "Ayrton Senna won how many consecutive Monaco Grand Prix races from 1989 to 1993?", "a": ["5", "five"]},
    {"q": "Who scored the first hat-trick (pole, win, fastest lap) in F1?", "a": ["Nino Farina", "Giuseppe Farina", "Farina"]},
    {"q": "What is the maximum speed typically reached by an F1 car in qualifying?", "a": ["350", "350 kmh", "over 350"]},
    {"q": "The fastest F1 lap ever recorded in race conditions was set at which circuit?", "a": ["Monza"]},
    {"q": "Who holds the record for the youngest driver to start an F1 race?", "a": ["Max Verstappen", "Verstappen"]},
    {"q": "How old was Max Verstappen when he made his F1 debut?", "a": ["17", "seventeen"]},

    # ===== ICONIC MOMENTS =====
    {"q": "In which year did Ayrton Senna tragically die at the San Marino Grand Prix?", "a": ["1994"]},
    {"q": "At which corner did Ayrton Senna's fatal accident occur at Imola in 1994?", "a": ["Tamburello"]},
    {"q": "Niki Lauda suffered a near-fatal crash at which circuit in 1976?", "a": ["Nurburgring", "Nürburgring"]},
    {"q": "The 'race of the century' at the 1979 French Grand Prix was between Villeneuve and which driver?", "a": ["Arnoux", "Rene Arnoux"]},
    {"q": "The 'villain arc' of Michael Schumacher began after which 1994 crash?", "a": ["Adelaide", "Australian Grand Prix"]},
    {"q": "Michael Schumacher deliberately crashed into Damon Hill at the 1994 title decider in which city?", "a": ["Adelaide"]},
    {"q": "Michael Schumacher and Jacques Villeneuve collided in the 1997 title decider at which circuit?", "a": ["Jerez", "European Grand Prix"]},
    {"q": "The infamous 'Crashgate' scandal occurred at the 2008 Singapore Grand Prix involving which driver?", "a": ["Nelson Piquet Jr", "Piquet", "Nelson Piquet Junior"]},
    {"q": "Which team ordered Nelson Piquet Jr to crash in the 2008 Singapore GP?", "a": ["Renault"]},
    {"q": "The 2021 Abu Dhabi GP title decider ended controversially when whose decision changed the race outcome?", "a": ["Michael Masi", "Masi"]},
    {"q": "Who won the controversial 2021 Abu Dhabi Grand Prix?", "a": ["Max Verstappen", "Verstappen"]},
    {"q": "The 'Multi 21' incident occurred at the 2013 Malaysian Grand Prix involving which two Red Bull drivers?", "a": ["Vettel and Webber", "Sebastian Vettel and Mark Webber", "Vettel"]},
    {"q": "What does 'Multi 21' mean in Red Bull team orders?", "a": ["Webber first Vettel second", "hold position", "maintain position"]},
    {"q": "The 2020 Bahrain GP saw Romain Grosjean survive a massive fire after hitting the barriers at which corner?", "a": ["Turn 3"]},
    {"q": "Which race director made the controversial safety car restart decision in the 2021 Abu Dhabi GP?", "a": ["Michael Masi", "Masi"]},
    {"q": "Nigel Mansell lost the 1986 title after a tyre blowout at which circuit?", "a": ["Adelaide", "Australian Grand Prix"]},
    {"q": "In which year did a wet Monaco Grand Prix see Senna rapidly catching Prost before the race was controversially red-flagged, denying Senna victory?", "a": ["1984"]},
    {"q": "In 1984 Monaco GP, who was leading when the race was controversially stopped?", "a": ["Alain Prost", "Prost"]},
    {"q": "The turbo era of F1 in the 1980s began with which manufacturer's engine?", "a": ["Renault"]},
    {"q": "Jochen Rindt won the 1970 championship posthumously, making him the only posthumous champion. He died at which circuit?", "a": ["Monza"]},
    {"q": "In which year did Jim Clark die?", "a": ["1968"]},
    {"q": "Jim Clark died at which circuit?", "a": ["Hockenheim", "Hockenheimring"]},
    {"q": "The 'Senna vs Prost' rivalry lasted from which years?", "a": ["1988 to 1993", "1988-1993"]},
    {"q": "Senna and Prost crashed at the start of the 1990 Japanese Grand Prix at which corner?", "a": ["Turn 1", "first corner"]},
    {"q": "The 'Schumi vs Hakkinen' rivalry of the late 1990s saw the two drivers fight for which championship year?", "a": ["1998", "1999", "2000"]},

    # ===== DRIVERS =====
    {"q": "Which nationality is Max Verstappen?", "a": ["Dutch", "Netherlands"]},
    {"q": "What is Lewis Hamilton's middle name?", "a": ["Carl Davidson", "Carl"]},
    {"q": "Fernando Alonso is from which country?", "a": ["Spain", "Spanish"]},
    {"q": "Which team was Kimi Raikkonen most associated with?", "a": ["Ferrari"]},
    {"q": "What is Kimi Raikkonen's famous nickname?", "a": ["The Iceman"]},
    {"q": "What is Sebastian Vettel's nickname?", "a": ["Baby Schumi"]},
    {"q": "Who is nicknamed 'The Honey Badger' in F1?", "a": ["Daniel Ricciardo", "Ricciardo"]},
    {"q": "What is Lando Norris's nationality?", "a": ["British", "British-Belgian"]},
    {"q": "Which driver is nicknamed 'Super Max'?", "a": ["Max Verstappen", "Verstappen"]},
    {"q": "Charles Leclerc is from which country?", "a": ["Monaco"]},
    {"q": "Which Monegasque driver races for Ferrari?", "a": ["Charles Leclerc", "Leclerc"]},
    {"q": "Valtteri Bottas is from which country?", "a": ["Finland", "Finnish"]},
    {"q": "Which driver is famous for the phrase 'Leave me alone, I know what I'm doing'?", "a": ["Kimi Raikkonen", "Raikkonen", "Kimi"]},
    {"q": "Nico Hulkenberg drives for which team in 2024?", "a": ["Haas"]},
    {"q": "Lance Stroll's father owns which F1 team?", "a": ["Aston Martin"]},
    {"q": "Which F1 driver's father is Lawrence Stroll?", "a": ["Lance Stroll", "Stroll"]},
    {"q": "Pierre Gasly is from which country?", "a": ["France", "French"]},
    {"q": "Esteban Ocon is from which country?", "a": ["France", "French"]},
    {"q": "Which Japanese driver scored a memorable podium for Sauber at the 2012 Japanese Grand Prix?", "a": ["Kamui Kobayashi"]},
    {"q": "Yuki Tsunoda drives for which team in 2024?", "a": ["RB", "Visa Cash App RB", "VCARB"]},
    {"q": "Yuki Tsunoda is from which country?", "a": ["Japan", "Japanese"]},
    {"q": "Oscar Piastri is from which country?", "a": ["Australia", "Australian"]},
    {"q": "Which team does Oscar Piastri race for?", "a": ["McLaren"]},
    {"q": "George Russell's nickname is?", "a": ["Mr Saturday", "GR63"]},
    {"q": "Mick Schumacher is the son of which legendary driver?", "a": ["Michael Schumacher", "Schumacher"]},
    {"q": "Damon Hill's father Graham Hill was also an F1 champion — how many titles did Damon win?", "a": ["1", "one"]},
    {"q": "Which driver is known for the 'shoey' celebration?", "a": ["Daniel Ricciardo", "Ricciardo"]},
    {"q": "The 'shoey' involves drinking what out of a racing boot?", "a": ["champagne"]},
    {"q": "Mark Webber made his Formula 1 debut with which team in 2002?", "a": ["Minardi"]},
    {"q": "Romain Grosjean raced for which team before his crash in 2020?", "a": ["Haas"]},
    {"q": "Michael Schumacher came out of retirement to join which team in 2010?", "a": ["Mercedes"]},
    {"q": "Which F1 driver famously said 'I am made of different stuff' after winning at Monaco?", "a": ["Lewis Hamilton", "Hamilton"]},
    {"q": "Jenson Button is from which country?", "a": ["United Kingdom", "UK", "England", "British"]},
    {"q": "Which driver replaced Michael Schumacher at Mercedes for 2013?", "a": ["Lewis Hamilton", "Hamilton"]},
    {"q": "Felipe Massa is from which country?", "a": ["Brazil", "Brazilian"]},
    {"q": "Felipe Massa famously missed the championship in 2008 by how many points?", "a": ["1", "one"]},
    {"q": "Who beat Felipe Massa to the 2008 title on the final lap of the final race?", "a": ["Lewis Hamilton", "Hamilton"]},
    {"q": "Who is the only woman to score F1 championship points?", "a": ["Lella Lombardi"]},
    {"q": "Gilles Villeneuve was the father of which F1 driver?", "a": ["Jacques Villeneuve", "Jacques"]},
    {"q": "Gilles Villeneuve drove for which team?", "a": ["Ferrari"]},
    {"q": "Which driver is nicknamed 'The Professor'?", "a": ["Alain Prost", "Prost"]},
    {"q": "Which driver is nicknamed 'Magic'?", "a": ["Ayrton Senna", "Senna"]},
    {"q": "Niki Lauda won his third championship in 1984 with which team?", "a": ["McLaren"]},
    {"q": "Who drove for Red Bull alongside Sebastian Vettel?", "a": ["Mark Webber", "Webber"]},
    {"q": "Mark Webber is from which country?", "a": ["Australia", "Australian"]},
    {"q": "Which British driver was known as 'The Flying Scotsman'?", "a": ["Jackie Stewart", "Stewart"]},
    {"q": "Which Australian F1 driver famously said 'Not bad for a number two driver' after winning the 2010 British Grand Prix?", "a": ["Mark Webber", "Webber"]},
    {"q": "Riccardo Patrese drove for Williams in the early 1990s alongside which champion?", "a": ["Nigel Mansell", "Mansell"]},
    {"q": "Which Brazilian driver was runner-up in the 2008 F1 championship, losing the title on the last lap?", "a": ["Felipe Massa", "Massa"]},
    {"q": "Rubens Barrichello holds the record for most race starts without a championship. How many races did he start?", "a": ["322", "323"]},
    {"q": "Who beat Senna in the 1984 Monaco GP through a race red-flag decision?", "a": ["Prost", "Alain Prost"]},
    {"q": "Which driver was famous for his 'number one' hand signal celebration?", "a": ["Sebastian Vettel", "Vettel"]},
    {"q": "Kevin Magnussen drives for which team?", "a": ["Haas"]},
    {"q": "Zhou Guanyu drives for which team?", "a": ["Sauber", "Stake"]},
    {"q": "Sergio Perez is from which country?", "a": ["Mexico", "Mexican"]},
    {"q": "Sergio Perez's nickname is?", "a": ["Checo"]},
    {"q": "Which driver won the 2022 Monaco Grand Prix?", "a": ["Sergio Perez", "Perez", "Checo"]},
    {"q": "Logan Sargeant is from which country?", "a": ["USA", "United States", "America", "American"]},
    {"q": "Which American driver replaced Nicholas Latifi at Williams?", "a": ["Logan Sargeant", "Sargeant"]},
    {"q": "Nicholas Latifi is the son of which Canadian billionaire?", "a": ["Michael Latifi"]},
    {"q": "Valtteri Bottas replaced which driver at Mercedes in 2017?", "a": ["Nico Rosberg", "Rosberg"]},
    {"q": "Which driver famously said 'To whom it may concern' after winning a race?", "a": ["Valtteri Bottas", "Bottas"]},
    {"q": "Lando Norris won his first F1 race at which Grand Prix?", "a": ["Miami", "Miami Grand Prix", "2024 Miami GP"]},

    # ===== ENGINES & TECHNOLOGY =====
    {"q": "Which engine format was introduced in F1 in 2014?", "a": ["V6 turbo hybrid", "V6 hybrid", "1.6 V6 turbo hybrid"]},
    {"q": "The V8 naturally aspirated engines in F1 were used from which years?", "a": ["2006 to 2013", "2006-2013"]},
    {"q": "DRS stands for what in F1?", "a": ["Drag Reduction System"]},
    {"q": "KERS stands for what in F1?", "a": ["Kinetic Energy Recovery System"]},
    {"q": "ERS stands for what in modern F1?", "a": ["Energy Recovery System"]},
    {"q": "What does MGU-K stand for in F1?", "a": ["Motor Generator Unit Kinetic"]},
    {"q": "What does MGU-H stand for in F1?", "a": ["Motor Generator Unit Heat"]},
    {"q": "In which year was the MGU-H removed from F1 power units?", "a": ["2026"]},
    {"q": "The current F1 power units use a 1.6-litre engine with how many cylinders?", "a": ["6", "six", "V6"]},
    {"q": "Ground effect aerodynamics were reintroduced to F1 in which year?", "a": ["2022"]},
    {"q": "In the mid-1980s, turbocharged F1 engines in qualifying could produce approximately how much horsepower?", "a": ["over 1000", "1000+", "1000hp", "1000 bhp", "1500"]},
    {"q": "The Lotus 78 and 79 introduced which concept to F1?", "a": ["Ground effect", "wing car"]},
    {"q": "Colin Chapman was the founder of which F1 team?", "a": ["Lotus", "Team Lotus"]},
    {"q": "The 'active suspension' was banned from F1 after which year?", "a": ["1993"]},
    {"q": "Traction control was banned from F1 starting in which year?", "a": ["2008"]},
    {"q": "Which F1 team pioneered the use of a carbon fibre monocoque chassis?", "a": ["McLaren"]},
    {"q": "The McLaren MP4/1 was the first F1 car with what material?", "a": ["carbon fibre", "carbon fiber composite", "CFRP"]},
    {"q": "Bridgestone and Michelin engaged in a famous tyre war in F1 from which years?", "a": ["2001 to 2006", "2001-2006"]},
    {"q": "Pirelli has been the sole tyre supplier in F1 since which year?", "a": ["2011"]},
    {"q": "What colour tyre compound is the softest in modern F1?", "a": ["Red"]},
    {"q": "What colour tyre compound is medium in F1?", "a": ["Yellow"]},
    {"q": "What colour tyre compound is hard in F1?", "a": ["White"]},
    {"q": "F1 cars must use at least how many different tyre compounds in a dry race?", "a": ["2", "two"]},

    # ===== RACE FORMATS =====
    {"q": "How many points does an F1 race winner receive?", "a": ["25", "twenty-five"]},
    {"q": "How many points does a sprint race winner receive?", "a": ["8", "eight"]},
    {"q": "When was the sprint race format introduced to F1?", "a": ["2021"]},
    {"q": "A bonus point is awarded for the fastest lap if the driver finishes in the top how many?", "a": ["10", "ten"]},
    {"q": "The points system currently awards points down to which position?", "a": ["10", "tenth", "P10"]},
    {"q": "In which year did F1 introduce the points system giving 25 to the winner?", "a": ["2010"]},
    {"q": "How many teams can compete in F1 according to the Concorde Agreement?", "a": ["10", "ten"]},
    {"q": "F1 introduced a budget cap of how much per year in 2021?", "a": ["145 million", "$145 million", "145"]},
    {"q": "What does 'parc ferme' mean in F1?", "a": ["closed park", "no changes allowed to car", "cars are sealed"]},
    {"q": "How many formation laps do F1 cars typically do before a race start?", "a": ["1", "one"]},
    {"q": "A Safety Car is deployed when?", "a": ["there is danger on track", "to slow cars down", "accident or debris on track"]},
    {"q": "VSC stands for what in F1?", "a": ["Virtual Safety Car"]},

    # ===== ICONIC CARS =====
    {"q": "The McLaren MP4/4 was arguably the most dominant F1 car of all time — in which year did it race?", "a": ["1988"]},
    {"q": "How many races did the McLaren MP4/4 win out of 16 in 1988?", "a": ["15", "fifteen"]},
    {"q": "Who drove the McLaren MP4/4 to the 1988 title?", "a": ["Ayrton Senna", "Senna"]},
    {"q": "The Williams FW14B used which revolutionary technology?", "a": ["Active suspension", "active ride height"]},
    {"q": "Red Bull's most dominant car was the RB9 — in which year did it race?", "a": ["2013"]},
    {"q": "The Ferrari F2004 was driven by which champion?", "a": ["Michael Schumacher", "Schumacher"]},
    {"q": "The Lotus 49 was the first car to use which engine integration concept?", "a": ["stressed engine", "stressed member engine"]},
    {"q": "The Cosworth DFV engine powered which iconic Lotus car?", "a": ["Lotus 49"]},
    {"q": "The Benetton B194 was driven by whom to the 1994 title?", "a": ["Michael Schumacher", "Schumacher"]},
    {"q": "The Mercedes W11 of 2020 is considered one of the most dominant cars — how many races did Hamilton win?", "a": ["11", "eleven"]},
    {"q": "The Ferrari 312T won the Constructors Championship in 1975, 1976, 1977, and other years — who drove it?", "a": ["Niki Lauda", "Lauda", "Jody Scheckter"]},

    # ===== 2020s ERA =====
    {"q": "Who won the F1 Drivers Championship in 2020?", "a": ["Lewis Hamilton", "Hamilton"]},
    {"q": "Who won the 2019 F1 World Championship?", "a": ["Lewis Hamilton", "Hamilton"]},
    {"q": "Which team dominated F1 from 2014 to 2021?", "a": ["Mercedes"]},
    {"q": "Who finished second in the 2021 Drivers Championship?", "a": ["Lewis Hamilton", "Hamilton"]},
    {"q": "Which team suffered the worst 'porpoising' issues in 2022 due to the new ground effect rules?", "a": ["Mercedes"]},
    {"q": "Carlos Sainz won his maiden F1 race at which Grand Prix in 2022?", "a": ["British Grand Prix", "Silverstone", "British GP"]},
    {"q": "George Russell won his maiden F1 race at which Grand Prix?", "a": ["Brazilian Grand Prix", "Brazil", "Interlagos"]},
    {"q": "Which Red Bull driver parted ways with the team after the 2024 season?", "a": ["Sergio Perez", "Perez", "Checo"]},
    {"q": "Who won the most races in the 2022 season?", "a": ["Max Verstappen", "Verstappen"]},
    {"q": "Ferrari had a strong start to 2022 but struggled with reliability — who was their main driver?", "a": ["Charles Leclerc", "Leclerc"]},
    {"q": "Max Verstappen set a then-record for most wins in a season in 2023. How many did he win?", "a": ["19", "nineteen"]},
    {"q": "Who became the first woman since 1992 to take part in an official F1 race weekend session?", "a": ["Susie Wolff", "Wolff"]},
    {"q": "The 2023 season was notable for Red Bull's dominance — how many consecutive races did they win before Singapore?", "a": ["14", "fourteen"]},
    {"q": "Which driver replaced Sebastian Vettel at Red Bull in 2014?", "a": ["Daniel Ricciardo", "Ricciardo"]},
    {"q": "Which team did Daniel Ricciardo join after Red Bull?", "a": ["Renault"]},
    {"q": "Daniel Ricciardo won his last F1 race at which Grand Prix?", "a": ["Italian Grand Prix", "Monza", "Italian GP"]},
    {"q": "Who took Daniel Ricciardo's seat at McLaren for the 2023 season?", "a": ["Oscar Piastri", "Piastri"]},
    {"q": "Who replaced Nikita Mazepin at Haas in 2022?", "a": ["Kevin Magnussen", "Magnussen"]},
    {"q": "Nikita Mazepin was dropped by Haas for which reason?", "a": ["Russia invasion of Ukraine", "Russia Ukraine war", "sanctions"]},
    {"q": "The team formerly known as Toleman was rebranded to which name in 1986?", "a": ["Benetton"]},
    {"q": "Benetton was bought by which company and renamed?", "a": ["Renault"]},
    {"q": "Fernando Alonso returned to F1 after two years away in which year?", "a": ["2021"]},
    {"q": "Which team did Fernando Alonso join when he returned in 2021?", "a": ["Alpine", "Renault"]},

    # ===== CONSTRUCTORS RECORDS =====
    {"q": "Which constructor has the most F1 Constructors Championship titles?", "a": ["Ferrari"]},
    {"q": "How many Constructors titles has Ferrari won?", "a": ["16", "sixteen"]},
    {"q": "Which constructor did Red Bull take over to become their junior team?", "a": ["Minardi"]},
    {"q": "Williams won the Constructors Championship from 1992 to 1994 and in which other consecutive years?", "a": ["1996 and 1997", "96 and 97"]},
    {"q": "McLaren won 9 Constructors titles — in which era did they peak?", "a": ["1980s", "late 1980s", "1988"]},
    {"q": "Which constructor won in 2022 for the first time since 2013?", "a": ["Red Bull", "Red Bull Racing"]},
    {"q": "Tyrrell Racing is remembered for the infamous 'six-wheel car' — the P34 — from which year?", "a": ["1976", "1977"]},
    {"q": "The Brabham BT46B was nicknamed what due to its radical design?", "a": ["fan car"]},
    {"q": "Lotus won the Constructors Championship multiple times in the 1960s and 1970s — who founded Lotus?", "a": ["Colin Chapman"]},

    # ===== SAFETY =====
    {"q": "The halo cockpit protection device was made mandatory in F1 from which year?", "a": ["2018"]},
    {"q": "The HANS device (Head and Neck Support) was made mandatory in F1 from which year?", "a": ["2003"]},
    {"q": "Romain Grosjean survived a fireball crash at the 2020 Bahrain GP — he escaped in how many seconds?", "a": ["28", "27"]},
    {"q": "Charles Leclerc crashed heavily during qualifying at which circuit in 2021, badly damaging his car?", "a": ["Monaco"]},
    {"q": "The FIA Medical Delegate who rides in the F1 Medical Car is which doctor?", "a": ["Ian Roberts"]},
    {"q": "The FIA (governing body of F1) stands for?", "a": ["Federation Internationale de l'Automobile", "International Automobile Federation"]},
    {"q": "The FIA was founded in which year?", "a": ["1904"]},
    {"q": "The FIA race director role became controversial after which year's championship?", "a": ["2021"]},

    # ===== MISCELLANEOUS =====
    {"q": "The F1 TV deal in the United States was held by which broadcaster?", "a": ["ESPN", "F1 TV"]},
    {"q": "Liberty Media purchased Formula 1 in which year?", "a": ["2017"]},
    {"q": "Which documentary series made F1 hugely popular in the US?", "a": ["Drive to Survive", "Drive To Survive"]},
    {"q": "Drive to Survive is available on which streaming platform?", "a": ["Netflix"]},
    {"q": "Which city hosted the first street circuit race in F1?", "a": ["Monaco"]},
    {"q": "How many races approximately are in a modern F1 season?", "a": ["23", "24", "20-24", "about 24"]},
    {"q": "The Concorde Agreement governs the relationship between F1, teams, and which body?", "a": ["FIA"]},
    {"q": "The F1 season traditionally ends at which race?", "a": ["Abu Dhabi", "Abu Dhabi Grand Prix"]},
    {"q": "The F1 season traditionally opens with which race?", "a": ["Australian Grand Prix", "Australia", "Melbourne"]},
    {"q": "Verstappen's engineer who says 'box box box' is who?", "a": ["Gianpiero Lambiase", "GP", "Gianpiero"]},
    {"q": "'Bwoah' is a famous soundbite associated with which F1 driver?", "a": ["Kimi Raikkonen", "Raikkonen", "Kimi"]},
    {"q": "The 'Senna S' is a famous section of chicane at which circuit?", "a": ["Interlagos", "Brazil", "São Paulo"]},
    {"q": "The F1 Hall of Fame is located in which country?", "a": ["France", "French"]},
    {"q": "Which F1 driver has scored championship points in the most races?", "a": ["Fernando Alonso", "Alonso"]},
    {"q": "Bernie Ecclestone ran the commercial side of F1 for how many decades?", "a": ["4", "four", "40 years"]},
    {"q": "Which team is nicknamed the 'Silver Arrows'?", "a": ["Mercedes"]},
    {"q": "What does a chequered flag signal in F1?", "a": ["end of session", "end of race", "race over", "session over"]},
    {"q": "The term 'undercut' in F1 strategy refers to?", "a": ["pitting before your rival", "stopping earlier"]},
    {"q": "The term 'overcut' in F1 strategy refers to?", "a": ["staying out longer than rival", "pitting after rival"]},
    {"q": "What does DNF mean in F1?", "a": ["Did Not Finish"]},
    {"q": "What does DNS mean in F1?", "a": ["Did Not Start"]},
    {"q": "What does DSQ mean in F1?", "a": ["Disqualified"]},
    {"q": "What does SC mean in F1 telemetry?", "a": ["Safety Car"]},
    {"q": "What does a blue flag shown to a driver mean in F1?", "a": ["let the leader past", "let faster car through", "you are about to be lapped"]},
    {"q": "A black flag shown to a driver in F1 means?", "a": ["you are disqualified", "disqualification"]},
    {"q": "A black and white flag in F1 means?", "a": ["warning for unsportsmanlike behaviour", "first warning"]},
    {"q": "How many wheels does an F1 car have?", "a": ["4", "four"]},
    {"q": "The Tyrrell P34 famously had how many wheels?", "a": ["6", "six"]},
    {"q": "F1 cars use a 'flat-bottom' design — what was banned in 1983?", "a": ["skirts", "sliding skirts", "ground effect skirts"]},
    {"q": "The minimum weight for an F1 car plus driver in 2023 is approximately?", "a": ["798 kg", "800 kg", "798"]},
    {"q": "How many cylinders does the current F1 power unit have?", "a": ["6", "six", "V6"]},
    {"q": "F1 cars run on how many litres of fuel (approximately) at the start of a race?", "a": ["100", "100 litres"]},
    {"q": "What fuel percentage must F1 use that is sustainable from 2026?", "a": ["100%", "100 percent", "fully sustainable"]},
    {"q": "F1 cars generate approximately how many G-forces under braking?", "a": ["5G", "5", "5 g", "over 5G"]},
    {"q": "The pitlane speed limit in most circuits is how many km/h?", "a": ["80", "eighty", "80 kmh"]},
    {"q": "A 'chicane' is a type of what track feature?", "a": ["tight S-bend", "tight corner", "S-shaped corner"]},
    {"q": "What does 'marbles' mean in F1?", "a": ["rubber debris off the racing line", "rubber bits on track"]},
    {"q": "The abbreviation 'DNQ' in F1 means?", "a": ["Did Not Qualify"]},
    {"q": "F1 cars use a paddle shift gear system — how many gears do they have?", "a": ["8", "eight"]},

    # ===== EARLY ERA / CLASSICS =====
    {"q": "Stirling Moss never won the F1 championship despite being one of the best drivers of his era. Which nationality was he?", "a": ["British", "English"]},
    {"q": "How many times did Stirling Moss finish as the F1 championship runner-up?", "a": ["4", "four"]},
    {"q": "Graham Hill won the championship in 1962 and 1968 — which team was he with in 1962?", "a": ["BRM"]},
    {"q": "Jim Clark drove for which team throughout his F1 career?", "a": ["Lotus", "Team Lotus"]},
    {"q": "The Vanwall team won the first Constructors Championship in which year?", "a": ["1958"]},
    {"q": "BRM (British Racing Motors) won the championship in which year?", "a": ["1962"]},
    {"q": "Peter Collins was a Ferrari driver in the late 1950s and died at which circuit?", "a": ["Nurburgring", "Nürburgring"]},
    {"q": "Wolfgang von Trips was a German Ferrari driver who died in an accident at which circuit in 1961?", "a": ["Monza"]},
    {"q": "The 'Shark nose' Ferrari was the iconic car of which year?", "a": ["1961"]},
    {"q": "Ferrari dominated the F1 championship with Alberto Ascari in which two consecutive seasons?", "a": ["1952 and 1953", "1952-1953"]},
    {"q": "Alberto Ascari went on a record winning streak of how many consecutive GP wins?", "a": ["9", "nine"]},
    {"q": "Which team did Jack Brabham create that bore his own name?", "a": ["Brabham"]},
    {"q": "Jack Brabham won the 1966 championship in his own car — the Brabham BT19 — powered by which engine?", "a": ["Repco", "Repco Brabham"]},
    {"q": "The Cooper T51 was driven to the 1959 championship by which driver?", "a": ["Jack Brabham", "Brabham"]},
    {"q": "Who won the F1 championship in 1961?", "a": ["Phil Hill"]},
    {"q": "Dan Gurney was a famous American driver who raced in which era of F1?", "a": ["1960s", "1960s and 1970s"]},
    {"q": "Chris Amon was a New Zealand driver famous for his bad luck — he never won an F1 race despite being fast. True or false?", "a": ["true"]},
    {"q": "The Brabham BT26 was the car driven by which legendary Austrian driver?", "a": ["Jochen Rindt", "Rindt"]},
    {"q": "Jochen Rindt's nationality was?", "a": ["Austrian"]},

    # ===== 1970s ERA =====
    {"q": "Who won the 1976 F1 championship by one point over Niki Lauda?", "a": ["James Hunt", "Hunt"]},
    {"q": "Niki Lauda came back from his Nurburgring crash in 1976 to race again — after how many weeks?", "a": ["6", "six", "42 days"]},
    {"q": "The film 'Rush' is based on the rivalry between James Hunt and who?", "a": ["Niki Lauda", "Lauda"]},
    {"q": "Which team did Ronnie Peterson race for when he died in 1978?", "a": ["Lotus"]},
    {"q": "The Lotus 79 pioneered which concept?", "a": ["Ground effect", "Wing car concept"]},
    {"q": "Jody Scheckter drove for which team to the 1979 championship?", "a": ["Ferrari"]},
    {"q": "Carlos Reutemann was a famous Argentine driver from which decade?", "a": ["1970s", "1980s"]},
    {"q": "Patrick Depailler scored his first podiums driving for which F1 team?", "a": ["Tyrrell"]},
    {"q": "The famous six-wheeled Tyrrell P34 was a unique experiment — in which years did it race?", "a": ["1976 and 1977", "1976-1977"]},
    {"q": "The 'turbo era' of F1 began with which team introducing a turbocharged engine?", "a": ["Renault"]},
    {"q": "In which year did Renault introduce the first F1 turbocharged car?", "a": ["1977"]},
    {"q": "Jean-Pierre Jabouille scored the first win for a turbocharged F1 car at which race?", "a": ["French Grand Prix", "France", "Dijon"]},

    # ===== 1980s ERA =====
    {"q": "Alain Prost won how many F1 championships?", "a": ["4", "four"]},
    {"q": "Alain Prost's last championship win was in which year?", "a": ["1993"]},
    {"q": "The McLaren team in 1988 used engines from which supplier?", "a": ["Honda"]},
    {"q": "The Williams team in the late 1980s used engines from which supplier?", "a": ["Honda", "Judd", "Renault"]},
    {"q": "Nelson Piquet drove for which team when he won the 1987 championship?", "a": ["Williams"]},
    {"q": "Ayrton Senna scored his first-ever F1 race victory at which 1985 Grand Prix?", "a": ["Portuguese Grand Prix", "Portugal", "Estoril"]},
    {"q": "The 1986 F1 season saw the championship decided at the Australian GP between Mansell, Piquet, and Prost. Who won the title?", "a": ["Alain Prost", "Prost"]},
    {"q": "Which McLaren car dominated the 1984 season with Lauda and Prost?", "a": ["McLaren MP4/2", "MP4/2"]},
    {"q": "Ayrton Senna's first F1 race was in which year?", "a": ["1984"]},
    {"q": "Ayrton Senna drove for which team in his debut season?", "a": ["Toleman"]},
    {"q": "Senna moved from Toleman to which team in 1985?", "a": ["Lotus"]},
    {"q": "Senna joined McLaren in which year?", "a": ["1988"]},
    {"q": "The 'flying lap' in qualifying that made Senna cry was at which circuit in 1988?", "a": ["Monaco"]},
    {"q": "Which French driver famously had a turbocharged Renault engine that often broke down?", "a": ["Alain Prost", "Prost", "Rene Arnoux"]},
    {"q": "Who was Senna's teammate at McLaren from 1988 to 1989?", "a": ["Alain Prost", "Prost"]},
    {"q": "Senna and Prost's collision at the 1989 Japanese GP saw which driver take a title that Senna had led?", "a": ["Alain Prost", "Prost"]},

    # ===== 1990s ERA =====
    {"q": "Michael Schumacher's first F1 championship was with which team?", "a": ["Benetton"]},
    {"q": "In which year did Michael Schumacher join Ferrari?", "a": ["1996"]},
    {"q": "Damon Hill drove for which team when he won the 1996 championship?", "a": ["Williams"]},
    {"q": "David Coulthard was the main rival of Mika Hakkinen at which team?", "a": ["McLaren"]},
    {"q": "The McLaren-Mercedes partnership began in which year?", "a": ["1995"]},
    {"q": "The 1994 season was overshadowed by the deaths of Roland Ratzenberger and which other driver?", "a": ["Ayrton Senna", "Senna"]},
    {"q": "Rubens Barrichello made his F1 debut in which year?", "a": ["1993"]},
    {"q": "The 1997 European Grand Prix title decider was held at which circuit?", "a": ["Jerez"]},
    {"q": "Michael Schumacher was disqualified from the 1997 championship standings for which reason?", "a": ["colliding with Villeneuve", "deliberately crashing", "ramming Villeneuve"]},
    {"q": "Mika Hakkinen drove for which team?", "a": ["McLaren"]},
    {"q": "Eddie Irvine lost the 1999 championship to Hakkinen by just 2 points — which team was he with?", "a": ["Ferrari"]},
    {"q": "Michael Schumacher broke his leg in which 1999 race?", "a": ["British Grand Prix", "Silverstone", "British GP"]},
    {"q": "The Williams FW18 was one of the most dominant cars in 1996 — which driver dominated with it?", "a": ["Damon Hill", "Hill"]},
    {"q": "In which year did Nigel Mansell win the IndyCar championship after his F1 title?", "a": ["1993"]},
    {"q": "Nigel Mansell drove for which team when he won the 1992 F1 championship?", "a": ["Williams"]},
    {"q": "The 'Red Five' car is associated with which driver?", "a": ["Nigel Mansell", "Mansell"]},
    {"q": "Jean Alesi drove for Ferrari for 5 years and scored only one win — at which race?", "a": ["Canadian Grand Prix", "Canada", "Montreal"]},

    # ===== 2000s ERA =====
    {"q": "Michael Schumacher won 5 consecutive championships from 2000 to which year?", "a": ["2004"]},
    {"q": "Which driver beat Michael Schumacher to the championship in 2005?", "a": ["Fernando Alonso", "Alonso"]},
    {"q": "Kimi Raikkonen won the 2007 championship by how many points?", "a": ["1", "one point"]},
    {"q": "The 2005 United States Grand Prix at Indianapolis had only how many cars racing due to tyre safety issues?", "a": ["6", "six"]},
    {"q": "How many teams withdrew from the 2005 US GP over tyre safety concerns?", "a": ["7", "seven"]},
    {"q": "The 2007 Spygate scandal involved which team stealing design secrets from Ferrari?", "a": ["McLaren"]},
    {"q": "McLaren was fined how much in the 2007 Spygate scandal?", "a": ["100 million", "$100 million"]},
    {"q": "Adrian Newey left McLaren to join which team in 2006?", "a": ["Red Bull", "Red Bull Racing"]},
    {"q": "Adrian Newey designed championship-winning cars at Williams, McLaren, and which other team?", "a": ["Red Bull", "Red Bull Racing"]},
    {"q": "Jenson Button's championship-winning Brawn GP car used which engine?", "a": ["Mercedes"]},
    {"q": "How many teams used a double diffuser at the start of the 2009 season alongside Brawn GP?", "a": ["2", "two"]},
    {"q": "Robert Kubica scored a famous win for BMW Sauber at which race?", "a": ["Canadian Grand Prix", "Canada", "Montreal"]},
    {"q": "Robert Kubica suffered a serious accident at the Ronde di Andora rally in which country in 2011?", "a": ["Italy"]},
    {"q": "Nico Rosberg made his F1 debut in which year?", "a": ["2006"]},

    # ===== 2010s ERA =====
    {"q": "The 2010 championship was won by Sebastian Vettel — who was the runner-up?", "a": ["Fernando Alonso", "Alonso"]},
    {"q": "Red Bull won the championship from 2010 to 2013 — which engine did they use?", "a": ["Renault"]},
    {"q": "The Mercedes W05 dominated 2014 — how many races did they win out of 19?", "a": ["16", "sixteen"]},
    {"q": "Which year saw the biggest engine rule change in F1 in decades with the intro of hybrid power units?", "a": ["2014"]},
    {"q": "Lewis Hamilton left McLaren for which team in 2013?", "a": ["Mercedes"]},
    {"q": "Nico Rosberg won the 2016 championship and retired how soon after?", "a": ["5 days", "days later", "days after"]},
    {"q": "The 2016 championship battle between Hamilton and Rosberg was decided at the final race in which country?", "a": ["UAE", "United Arab Emirates", "Abu Dhabi"]},
    {"q": "Which team won the Constructors Championship in 2019?", "a": ["Mercedes"]},
    {"q": "Sebastian Vettel won his last race in which year?", "a": ["2019"]},
    {"q": "Sebastian Vettel won the 2019 Singapore Grand Prix — was that his last win?", "a": ["yes"]},
    {"q": "Valtteri Bottas finished runner-up to Hamilton in which years?", "a": ["2019 and 2020", "2019, 2020"]},

    # ===== F1 FIRSTS =====
    {"q": "The first F1 race to be held in Asia was the Japanese Grand Prix — in which year?", "a": ["1976"]},
    {"q": "Which was the first country in the Middle East to host an F1 race?", "a": ["Bahrain"]},
    {"q": "Bahrain hosted its first F1 race in which year?", "a": ["2004"]},
    {"q": "The first female driver to race in F1 was who?", "a": ["Maria Teresa de Filippis", "de Filippis"]},
    {"q": "The first F1 race under lights (night race) was which Grand Prix?", "a": ["Singapore Grand Prix", "Singapore GP", "Singapore"]},
    {"q": "The first F1 Grand Prix broadcast live on TV in Britain was in which year?", "a": ["1978"]},
    {"q": "Luigi Fagioli won his only F1 race at which Grand Prix in 1951?", "a": ["French Grand Prix", "France", "Reims"]},
    {"q": "The first dedicated United States Grand Prix (held at Sebring, separate from the Indy 500) was in which year?", "a": ["1959"]},
    {"q": "Fittipaldi was the first South American champion — from which country?", "a": ["Brazil", "Brazilian"]},
    {"q": "The GPDA (Grand Prix Drivers Association) was formed in which year?", "a": ["1961"]},
    {"q": "The first F1 pit stop under 2 seconds was set by which team?", "a": ["Red Bull", "Red Bull Racing"]},
    {"q": "The fastest F1 pit stop ever recorded was by McLaren at the 2023 Qatar Grand Prix — how fast was it?", "a": ["1.80 seconds", "1.80"]},

    # ===== CELEBRITY QUESTIONS / POP CULTURE =====
    {"q": "Which F1 driver appeared in a cameo in the movie 'Cars 2'?", "a": ["Lewis Hamilton", "Hamilton"]},
    {"q": "The Netflix series Drive to Survive first aired in which year?", "a": ["2019"]},
    {"q": "Which F1 driver has his own Netflix docuseries called 'Senna'?", "a": ["Ayrton Senna", "Senna"]},
    {"q": "The movie 'Rush' (2013) was directed by which director?", "a": ["Ron Howard"]},
    {"q": "Who played Niki Lauda in the 2013 film Rush?", "a": ["Daniel Bruhl", "Brühl"]},
    {"q": "Who played James Hunt in the 2013 film Rush?", "a": ["Chris Hemsworth"]},
    {"q": "The F1 game franchise is developed by which company?", "a": ["Codemasters", "EA Sports"]},
    {"q": "Which F1 team has a famous paddock hospitality nicknamed the 'Red Bull Bullpen'?", "a": ["Red Bull"]},
    {"q": "The music artist Post Malone appeared at which F1 race in 2023?", "a": ["Las Vegas", "Las Vegas Grand Prix"]},
    {"q": "Which luxury watch brand is the official timekeeper of F1?", "a": ["Rolex"]},

    # ===== SPRINT RACES =====
    {"q": "The first sprint race in F1 was held at which Grand Prix?", "a": ["British Grand Prix", "Silverstone", "British GP"]},
    {"q": "In which year were sprint races first introduced?", "a": ["2021"]},
    {"q": "A sprint race in F1 is how many km/laps long?", "a": ["100 km", "about 100 km", "one third distance"]},
    {"q": "Points in a sprint race are awarded from P1 to which position?", "a": ["P8", "8th", "8"]},

    # ===== MORE DRIVERS =====
    {"q": "Antonio Giovinazzi drove for which F1 team from 2019 to 2021?", "a": ["Alfa Romeo"]},
    {"q": "Nyck de Vries drove for AlphaTauri in 2023 — from which country is he?", "a": ["Netherlands", "Dutch"]},
    {"q": "Alex Albon drives for which team?", "a": ["Williams"]},
    {"q": "Alex Albon is from which country?", "a": ["Thailand", "Thai"]},
    {"q": "Guanyu Zhou is from which country?", "a": ["China", "Chinese"]},
    {"q": "Lance Stroll is from which country?", "a": ["Canada", "Canadian"]},
    {"q": "Mick Schumacher raced for which F1 team?", "a": ["Haas"]},
    {"q": "Who replaced Nico Hulkenberg at Renault/Alpine?", "a": ["Esteban Ocon", "Ocon"]},
    {"q": "Which F1 driver is known for his 'number one finger' celebration after winning?", "a": ["Sebastian Vettel", "Vettel"]},
    {"q": "Theo Pourchaire was a reserve driver for which F1 team?", "a": ["Alfa Romeo", "Sauber"]},
    {"q": "Pato O'Ward tested a McLaren F1 car in which year?", "a": ["2021", "2022"]},
    {"q": "Which IndyCar race winner was invited to test a McLaren F1 car as a reward for his IndyCar performance?", "a": ["Pato O'Ward", "O'Ward"]},
    {"q": "Nyck de Vries made his F1 debut at the Italian Grand Prix in 2022 driving for which team?", "a": ["Williams"]},
    {"q": "Nico Hulkenberg is famous for holding which record?", "a": ["most starts without a podium", "most starts without podium"]},
    {"q": "Felipe Drugovich is a reserve driver for which team?", "a": ["Aston Martin"]},
    {"q": "Which driver temporarily replaced the injured Daniel Ricciardo at AlphaTauri during the 2023 season?", "a": ["Liam Lawson"]},
    {"q": "Liam Lawson is from which country?", "a": ["New Zealand"]},
    {"q": "Which famous F1 team did Jody Scheckter drive for before joining Wolf Racing?", "a": ["Tyrrell"]},
    {"q": "Jacky Ickx was a famous Belgian driver who finished runner-up twice driving for which Italian team?", "a": ["Ferrari"]},
    {"q": "Carlos Reutemann almost won the 1981 championship but lost to which driver by one point?", "a": ["Nelson Piquet", "Piquet"]},
    {"q": "Didier Pironi was leading the 1982 championship before a crash at which race?", "a": ["German Grand Prix", "Hockenheim"]},
    {"q": "Both Keke Rosberg (1982) and Nico Rosberg (2016) won the F1 World Championship — making them one of two father-son champion pairs. Name the other father-son duo who both won.", "a": ["Graham Hill and Damon Hill", "Hill", "Damon Hill", "Graham Hill"]},
    {"q": "Graham Hill won the Monaco Grand Prix 5 times and was nicknamed what?", "a": ["Mr Monaco", "King of Monaco"]},
    {"q": "Who holds the record for the most Monaco Grand Prix wins?", "a": ["Ayrton Senna", "Senna"]},
    {"q": "How many times did Ayrton Senna win the Monaco Grand Prix?", "a": ["6", "six"]},
    {"q": "Lewis Hamilton has won the Monaco Grand Prix how many times?", "a": ["3", "three"]},
    {"q": "Max Verstappen has won the Monaco Grand Prix — in which year was his first Monaco win?", "a": ["2021"]},

    # ===== ENGINE SUPPLIERS =====
    {"q": "Which engine supplier partnered with Red Bull from 2019?", "a": ["Honda"]},
    {"q": "Red Bull Powertrains is developing which type of power unit for 2026?", "a": ["Ford", "Ford Red Bull", "their own"]},
    {"q": "Ford is returning to F1 in partnership with which team for 2026?", "a": ["Red Bull", "Red Bull Racing"]},
    {"q": "Audi is entering F1 in partnership with which team?", "a": ["Sauber"]},
    {"q": "General Motors/Cadillac wants to enter F1 as a constructor from which year?", "a": ["2026"]},
    {"q": "Which engine supplier won the most championships with McLaren?", "a": ["Honda"]},
    {"q": "Renault, Honda, Ford/Cosworth, and Mercedes are all examples of what in F1?", "a": ["engine suppliers", "power unit manufacturers"]},
    {"q": "The Cosworth DFV is one of the most successful F1 engines — what does DFV stand for?", "a": ["Double Four Valve"]},
    {"q": "Which engine powered the majority of the F1 grid in the 1970s?", "a": ["Cosworth DFV", "Ford Cosworth", "DFV"]},

    # ===== QUALIFYING =====
    {"q": "The current F1 qualifying format consists of how many knockout segments?", "a": ["3", "three", "Q1 Q2 Q3"]},
    {"q": "How many cars are eliminated in Q1 of qualifying?", "a": ["5", "five"]},
    {"q": "How many cars are eliminated in Q2 of qualifying?", "a": ["5", "five"]},
    {"q": "How many cars fight for pole in Q3?", "a": ["10", "ten"]},
    {"q": "The aggregate qualifying format was used in F1 in which year?", "a": ["2005"]},
    {"q": "The one-lap qualifying format was used in F1 from 2003 to which year?", "a": ["2005"]},
    {"q": "Ayrton Senna holds the all-time record for most poles at which circuit?", "a": ["Monaco"]},
    {"q": "The 'Q4' does not exist in F1 — this is a trick question. True or false?", "a": ["true"]},

    # ===== STEWARDING / REGULATIONS =====
    {"q": "Michael Schumacher was penalised at the 1994 British Grand Prix for ignoring which flag?", "a": ["black flag"]},
    {"q": "The 'penalty points' system in F1 operates over a rolling how many months?", "a": ["12", "twelve"]},
    {"q": "If a driver accumulates 12 penalty points in F1 they receive?", "a": ["race ban", "one race ban"]},
    {"q": "A drive-through penalty in F1 means the driver must?", "a": ["drive through the pit lane", "go through pitlane without stopping"]},
    {"q": "A 5-second penalty in F1 means time is added where?", "a": ["in the pits during a stop", "to their race time"]},
    {"q": "What is a 'grid penalty' in F1?", "a": ["starting from further back", "dropping grid positions"]},

    # ===== FUN / TRIVIA =====
    {"q": "Which country has hosted the most F1 Grands Prix?", "a": ["Italy"]},
    {"q": "How long is a typical F1 race (roughly)?", "a": ["about 2 hours", "1.5 to 2 hours", "90 minutes to 2 hours"]},
    {"q": "What must an F1 race last for in terms of distance to be classified as a full race?", "a": ["75% of the full distance", "75 percent"]},
    {"q": "What is a 'formation lap' in F1?", "a": ["the lap before the race start", "warm-up lap", "parade lap"]},
    {"q": "The 'flying lap' in qualifying is a timed lap at maximum effort — true or false?", "a": ["true"]},
    {"q": "An out-lap in qualifying is used to?", "a": ["warm up tyres", "prepare for a flying lap", "heat up tyres"]},
    {"q": "The pitlane is closed to all cars during which pre-race phase?", "a": ["formation lap", "parade lap", "warm-up lap"]},
    {"q": "Lewis Hamilton raced for McLaren and Mercedes before joining which team in 2025?", "a": ["Ferrari", "Scuderia Ferrari"]},
    {"q": "Which is the oldest team currently on the F1 grid?", "a": ["Ferrari"]},
    {"q": "In which country was Sebastian Vettel born?", "a": ["Germany"]},
    {"q": "Sebastian Vettel retired from F1 after which season?", "a": ["2022"]},
    {"q": "Michael Schumacher holds the record for most wins at which French circuit?", "a": ["Magny-Cours"]},
    {"q": "Schumacher won the German Grand Prix how many times?", "a": ["4"]},
    {"q": "Who set the record for the most wins at Interlagos (Brazilian GP)?", "a": ["Michael Schumacher", "Schumacher"]},
    {"q": "Who holds the record for most wins at the British Grand Prix?", "a": ["Lewis Hamilton", "Hamilton"]},
    {"q": "Lewis Hamilton won the British Grand Prix how many times?", "a": ["9", "nine"]},
    {"q": "The phrase 'still I rise' is associated with which F1 driver?", "a": ["Lewis Hamilton", "Hamilton"]},
    {"q": "Which F1 driver famously wore a rainbow flag helmet at the 2021 Hungarian Grand Prix to support LGBTQ+ rights?", "a": ["Sebastian Vettel", "Vettel"]},
    {"q": "Nigel Mansell's famous 'walk to the pits' happened after his car's engine cut out on the last lap at which race?", "a": ["1991 Canadian Grand Prix", "Canada", "Montreal"]},
    {"q": "In which year did Lewis Hamilton win his first F1 race?", "a": ["2007"]},
    {"q": "Christian Horner joined Red Bull Racing as team principal in which year?", "a": ["2005"]},
    {"q": "Which F1 driver has won the most races at Spa-Francorchamps?", "a": ["Michael Schumacher", "Schumacher"]},
    {"q": "Who was the last British driver to win the F1 championship before Hamilton?", "a": ["Jenson Button", "Button"]},
    {"q": "Jenson Button won the 2009 championship — how many races did he win that year?", "a": ["6", "six"]},
    {"q": "Jenson Button's famous drives include which wet weather masterclass?", "a": ["Canadian Grand Prix 2011", "Canada 2011"]},
    {"q": "The 2011 Canadian Grand Prix is famous for what?", "a": ["Jenson Button comeback", "longest race ever", "multiple safety cars"]},
    {"q": "The 2011 Canadian GP lasted for how long due to a red flag stoppage?", "a": ["4 hours", "over 4 hours"]},
    {"q": "Lewis Hamilton's first F1 race win was at which Grand Prix?", "a": ["Canadian Grand Prix", "Canada", "Montreal"]},

    # ===== MORE CIRCUITS =====
    {"q": "Portimao in Portugal returned to the F1 calendar in which year?", "a": ["2020", "2021"]},
    {"q": "Which circuit in Germany hosted the F1 Grand Prix on and off from 1970?", "a": ["Hockenheim", "Hockenheimring"]},
    {"q": "The Nurburgring GP circuit (shorter layout) is used for which GP in modern F1?", "a": ["German Grand Prix", "Luxembourg Grand Prix", "European Grand Prix"]},
    {"q": "The French Grand Prix at Paul Ricard last appeared on the calendar in which year?", "a": ["2022"]},
    {"q": "The Bahrain International Circuit's alternate 'outer' layout was used for which 2020 Grand Prix?", "a": ["Sakhir Grand Prix", "Sakhir GP", "Sakhir"]},
    {"q": "The Baku City Circuit is rated as having one of the longest straights in F1 — how long is it?", "a": ["2.2 km", "2.2", "over 2 km", "2 km", "2.2 kilometers"]},
    {"q": "Which circuit in Italy hosted the Emilia Romagna Grand Prix?", "a": ["Imola"]},
    {"q": "The Emilia Romagna Grand Prix was cancelled in which year due to flooding?", "a": ["2023"]},
    {"q": "The European Grand Prix was held at which Spanish street circuit from 2008 to 2012?", "a": ["Valencia", "Valencia Street Circuit"]},
    {"q": "Sepang International Circuit in Malaysia last hosted an F1 race in which year?", "a": ["2017"]},
    {"q": "The Korean Grand Prix last ran in which year?", "a": ["2013"]},
    {"q": "The Indian Grand Prix was held at which circuit?", "a": ["Buddh International Circuit"]},
    {"q": "The Indian Grand Prix last ran in which year?", "a": ["2013"]},
    {"q": "The South African Grand Prix at Kyalami last appeared on the F1 calendar in which year?", "a": ["1993"]},
    {"q": "The US Grand Prix was held at Watkins Glen for how many years?", "a": ["1961 to 1980", "20 years", "about 20"]},
    {"q": "Circuit Park Zandvoort's banked corners were a major feature when the circuit returned in which year?", "a": ["2021"]},
    {"q": "The street circuit in Baku features a narrow section through the old city walls — true or false?", "a": ["true"]},
    {"q": "Which circuit was renovated with a brand new layout and hosted the 2023 Las Vegas GP?", "a": ["Las Vegas Street Circuit", "Las Vegas"]},

    # ===== ADDITIONAL MODERN ERA =====
    {"q": "Who won the 2023 Monaco Grand Prix?", "a": ["Max Verstappen", "Verstappen"]},
    {"q": "Who won the 2023 British Grand Prix?", "a": ["Max Verstappen", "Verstappen"]},
    {"q": "Which team won back-to-back Constructors Championships in 2022 and 2023?", "a": ["Red Bull", "Red Bull Racing"]},
    {"q": "Lando Norris won his first race at the 2024 Miami Grand Prix — which country is Miami in?", "a": ["USA", "United States", "America"]},
    {"q": "Oscar Piastri won his first race at which 2024 Grand Prix?", "a": ["Hungarian Grand Prix", "Hungary"]},
    {"q": "Which team had a 1-2 finish (Norris-Piastri) at the 2024 Hungarian Grand Prix?", "a": ["McLaren"]},
    {"q": "George Russell won the 2024 Austrian Grand Prix after which two drivers collided while fighting for the lead?", "a": ["Verstappen and Norris", "Max Verstappen and Lando Norris", "Verstappen Norris"]},
    {"q": "Lewis Hamilton announced his move to Ferrari in which year?", "a": ["2024"]},
    {"q": "Hamilton's announcement to move to Ferrari came as a shock — which year will he join Ferrari?", "a": ["2025"]},
    {"q": "Carlos Sainz won the 2024 Australian Grand Prix driving for which team?", "a": ["Ferrari", "Scuderia Ferrari"]},
    {"q": "Fernando Alonso scored a stunning podium at the 2023 Bahrain Grand Prix driving for which team?", "a": ["Aston Martin"]},
    {"q": "Aston Martin's rapid development in 2023 was led by which technical director?", "a": ["Dan Fallows"]},
    {"q": "Which former Red Bull technical director joined Aston Martin?", "a": ["Adrian Newey"]},
    {"q": "Adrian Newey announced he would join Aston Martin in which year?", "a": ["2024"]},
    {"q": "The 2024 Constructors Champion was which team?", "a": ["McLaren"]},
    {"q": "Who was the 2024 Constructors Championship runner-up?", "a": ["Ferrari"]},
    {"q": "Which team clinched the 2024 Constructors Championship at the final race?", "a": ["McLaren"]},

    # ===== 1950s DEEP CUTS =====
    {"q": "The first race in the 1950 F1 season at Silverstone was also called what?", "a": ["British Grand Prix", "British GP"]},
    {"q": "How many races were in the very first F1 season in 1950?", "a": ["7", "seven"]},
    {"q": "The Indianapolis 500 was part of the F1 championship from 1950 to which year?", "a": ["1960"]},
    {"q": "Alberto Ascari's winning streak of 9 races spanned which two seasons?", "a": ["1952 and 1953", "1952-1953"]},
    {"q": "Luigi Fagioli won the very first F1 race ever — true or false?", "a": ["false", "Nino Farina won the first race"]},
    {"q": "Which Argentine driver won 5 championships and is considered the greatest of his era?", "a": ["Juan Manuel Fangio", "Fangio"]},
    {"q": "Fangio drove for how many different constructor teams in his championship years?", "a": ["4", "four"]},
    {"q": "Fangio's 4 different championship-winning constructors were Alfa Romeo, Ferrari, Mercedes, and which other?", "a": ["Maserati"]},
    {"q": "Which team did Fangio win the 1954 and 1955 championships with?", "a": ["Mercedes"]},

    # ===== EVEN MORE =====
    {"q": "The DRS zone is defined by which sensors?", "a": ["detection point", "DRS detection zone", "sensor loop"]},
    {"q": "What colour flag signals the end of a session in F1?", "a": ["chequered", "checkered", "chequered flag"]},
    {"q": "A yellow flag in F1 means?", "a": ["danger ahead", "slow down no overtaking", "caution"]},
    {"q": "What does a red flag in F1 mean?", "a": ["session stopped", "race stopped", "stop immediately"]},
    {"q": "A green flag in F1 means?", "a": ["clear track", "go", "track is clear"]},
    {"q": "What is 'porpoising' in F1?", "a": ["bouncing car", "car bouncing up and down", "aerodynamic bouncing"]},
    {"q": "Ferrari's famous red livery is called what in Italian?", "a": ["Rosso Corsa"]},
    {"q": "Which team uses the 'prancing horse' logo?", "a": ["Ferrari", "Scuderia Ferrari"]},
    {"q": "McLaren's famous papaya orange colour was introduced as their primary livery colour in which decade?", "a": ["1960s", "late 1960s"]},
    {"q": "What is the name of F1's official online streaming service?", "a": ["F1 TV", "F1TV"]},
    {"q": "Which company builds the F1 Safety Car?", "a": ["Mercedes", "AMG", "Mercedes-AMG"]},
    {"q": "The Medical Intervention Vehicle in F1 is currently which car brand?", "a": ["Mercedes", "AMG"]},
    {"q": "How many mechanics typically work on an F1 car during a pit stop?", "a": ["20", "about 20", "16 to 20"]},
    {"q": "The wheel gun in an F1 pit stop operates at approximately how many RPM?", "a": ["10000", "10,000", "10000 to 15000", "over 10000"]},
    {"q": "F1 cars can accelerate from 0 to 100 km/h in approximately how many seconds?", "a": ["2.5", "under 3", "2.4", "2.6"]},
    {"q": "Which F1 team is nicknamed the 'Prancing Horse team'?", "a": ["Ferrari"]},
    {"q": "Which current Ferrari driver is a graduate of the Ferrari Driver Academy?", "a": ["Charles Leclerc", "Leclerc"]},
    {"q": "Max Verstappen's father Jos Verstappen also raced in F1 — in which team?", "a": ["Benetton", "Footwork", "Simtek"]},
    {"q": "Jos Verstappen drove as Michael Schumacher's teammate at which team?", "a": ["Benetton"]},
    {"q": "Fernando Alonso's first team was Minardi — in which year did he debut?", "a": ["2001"]},
    {"q": "Alonso's second stint at McLaren in 2007 ended controversially due to which scandal?", "a": ["Spygate", "McLaren Spygate"]},
    {"q": "The 'Stepneygate' (Spygate) saw Ferrari data go to which team?", "a": ["McLaren"]},
    {"q": "The 2008 Singapore GP result was manipulated — which driver was ordered to crash?", "a": ["Nelson Piquet Jr", "Piquet Junior", "Piquet Jr"]},
    {"q": "Renault was given a suspended ban for their role in Crashgate — true or false?", "a": ["true"]},
    {"q": "In which year was the 'Crashgate' scandal exposed?", "a": ["2009"]},
    {"q": "Which team used an illegal 'Mass Damper' device in 2006?", "a": ["Renault"]},
    {"q": "The mass damper was banned midseason in which year?", "a": ["2006"]},
    {"q": "Alain Prost won the championship in 1985, 1986, 1989, and which other year?", "a": ["1993"]},
    {"q": "In 1993 Prost won the championship with which team?", "a": ["Williams"]},
    {"q": "Senna died before Prost retired — true or false?", "a": ["false"]},
    {"q": "Ayrton Senna's last pole position was at Imola — in which year?", "a": ["1994"]},
    {"q": "Michael Schumacher won his 7th championship with which team?", "a": ["Ferrari"]},
    {"q": "Michael Schumacher's 7th championship came in which year?", "a": ["2004"]},
    {"q": "After Schumacher's 7th title nobody thought the record would be matched — who equalled it?", "a": ["Lewis Hamilton", "Hamilton"]},
    {"q": "Hamilton matched Schumacher's 7 titles in which year?", "a": ["2020"]},
]


# ---------------------------------------------------------------------------
# Cog definition
# ---------------------------------------------------------------------------

class F1Trivia(commands.Cog):
    """Formula 1 trivia game for your Discord server — first to 10 wins!"""

    __version__ = "1.0.0"
    __author__ = "jaffar21"

    def __init__(self, bot: Red):
        self.bot = bot
        # guild_id -> game state dict
        self._games: Dict[int, dict] = {}

    # ------------------------------------------------------------------
    # Game state helpers
    # ------------------------------------------------------------------

    def _get_game(self, guild_id: int) -> Optional[dict]:
        return self._games.get(guild_id)

    def _new_game(self, channel_id: int, target: int, questions: List[dict]) -> dict:
        return {
            "channel_id": channel_id,
            "target": target,
            "scores": {},
            "questions": questions,
            "used_indices": [],
            "current_q": None,
            "current_answers": None,
            "round_task": None,
            "round_number": 0,
            "active": True,
        }

    def _pick_question(self, game: dict) -> Optional[dict]:
        available = [i for i in range(len(game["questions"])) if i not in game["used_indices"]]
        if not available:
            # Reset used list to allow infinite play
            game["used_indices"] = []
            available = list(range(len(game["questions"])))
        idx = random.choice(available)
        game["used_indices"].append(idx)
        return game["questions"][idx]

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    @commands.group(name="f1trivia", aliases=["f1t", "f1quiz"], invoke_without_command=True)
    @commands.guild_only()
    async def f1trivia(self, ctx: commands.Context):
        """F1 Trivia commands. Use [p]f1trivia start to begin a game."""
        await ctx.send_help(ctx.command)

    @f1trivia.command(name="start")
    @commands.guild_only()
    async def f1trivia_start(self, ctx: commands.Context, target: int = 10):
        """Start an F1 trivia game. First to reach the point target wins!

        Optional: set a custom target (default is 10).
        Example: `[p]f1trivia start 15`
        """
        if self._get_game(ctx.guild.id):
            await ctx.send("A game is already running in this server! Use `[p]f1trivia stop` to end it first.")
            return

        if target < 1 or target > 50:
            await ctx.send("Pick a point target between 1 and 50.")
            return

        pool = list(QUESTIONS)
        random.shuffle(pool)

        game = self._new_game(ctx.channel.id, target, pool)
        self._games[ctx.guild.id] = game

        embed = discord.Embed(
            title="🏎️  F1 Trivia — Game On!",
            description=(
                f"**First to {target} points wins!**\n\n"
                "• 15 seconds per question\n"
                "• Type your answer in chat — no commands needed\n"
                "• Nicknames, first names and last names are all accepted\n\n"
                "Get ready — first question coming up!"
            ),
            colour=0xE8002D,
        )
        embed.set_footer(text="Use [p]f1trivia stop to end the game | jaffar21")
        await ctx.send(embed=embed)

        await asyncio.sleep(2)
        await self._next_round(ctx.guild.id, ctx.channel)

    @f1trivia.command(name="stop", aliases=["end", "quit"])
    @commands.guild_only()
    async def f1trivia_stop(self, ctx: commands.Context):
        """Stop the current F1 trivia game."""
        game = self._get_game(ctx.guild.id)
        if not game:
            await ctx.send("No game running right now.")
            return

        await self._end_game(ctx.guild.id, ctx.channel, reason="stopped")

    @f1trivia.command(name="scores", aliases=["score", "leaderboard"])
    @commands.guild_only()
    async def f1trivia_scores(self, ctx: commands.Context):
        """Show the current scores."""
        game = self._get_game(ctx.guild.id)
        if not game:
            await ctx.send("No game running right now.")
            return

        await ctx.send(embed=self._build_scoreboard(game, ctx.guild))

    @f1trivia.command(name="skip")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def f1trivia_skip(self, ctx: commands.Context):
        """Skip the current question (moderators only)."""
        game = self._get_game(ctx.guild.id)
        if not game:
            await ctx.send("No game running right now.")
            return
        if not game.get("current_q"):
            await ctx.send("No question is currently active.")
            return

        answers = game["current_answers"]
        canonical = answers[0] if answers else "Unknown"

        if game["round_task"] and not game["round_task"].done():
            game["round_task"].cancel()

        channel = self.bot.get_channel(game["channel_id"])
        await channel.send(f"⏩ Skipped! The answer was **{canonical}**.")
        await asyncio.sleep(1)
        await self._next_round(ctx.guild.id, channel)

    # ------------------------------------------------------------------
    # Game logic
    # ------------------------------------------------------------------

    async def _next_round(self, guild_id: int, channel: discord.TextChannel):
        game = self._get_game(guild_id)
        if not game or not game["active"]:
            return

        q_data = self._pick_question(game)
        # Support both "q" and "w" keys (typo protection)
        question_text = q_data.get("q") or q_data.get("w", "Unknown question")
        answers = q_data["a"]

        game["current_q"] = question_text
        game["current_answers"] = answers
        game["round_number"] += 1

        embed = discord.Embed(
            title=f"Question #{game['round_number']}",
            description=f"**{question_text}**",
            colour=0xFFCC00,
        )
        embed.set_footer(text="⏱  15 seconds — type your answer!")
        await channel.send(embed=embed)

        task = asyncio.ensure_future(self._run_round(guild_id, channel))
        game["round_task"] = task

    async def _run_round(self, guild_id: int, channel: discord.TextChannel):
        """Wait up to 15 seconds for a correct answer."""
        game = self._get_game(guild_id)
        if not game:
            return

        end_time = time.monotonic() + 15.0

        def check(msg: discord.Message) -> bool:
            if msg.channel.id != game["channel_id"]:
                return False
            if msg.author.bot:
                return False
            return _answers_match(msg.content, game["current_answers"])

        try:
            remaining = end_time - time.monotonic()
            msg = await self.bot.wait_for("message", check=check, timeout=max(0.1, remaining))
        except asyncio.TimeoutError:
            # Nobody got it — save the answer BEFORE clearing state
            answers = game["current_answers"] or []
            canonical = answers[0] if answers else "Unknown"
            game["current_q"] = None
            game["current_answers"] = None
            await channel.send(f"⏰ Time's up! Nobody got it. The answer was **{canonical}**.")
            await asyncio.sleep(1.5)
            await self._next_round(guild_id, channel)
            return
        except asyncio.CancelledError:
            return

        # Correct answer!
        user_id = msg.author.id
        game["scores"][user_id] = game["scores"].get(user_id, 0) + 1
        score = game["scores"][user_id]
        canonical = game["current_answers"][0]

        game["current_q"] = None
        game["current_answers"] = None

        if score >= game["target"]:
            await channel.send(
                f"✅ **{msg.author.display_name}** got it! The answer was **{canonical}**.\n"
                f"They now have **{score} point{'s' if score != 1 else ''}** — "
                f"**{msg.author.display_name} WINS THE GAME! 🏆**"
            )
            await self._end_game(guild_id, channel, winner=msg.author, reason="won")
        else:
            remaining_pts = game["target"] - score
            await channel.send(
                f"✅ **{msg.author.display_name}** got it! The answer was **{canonical}**. "
                f"They're on **{score} pt{'s' if score != 1 else ''}** "
                f"({remaining_pts} more to win)"
            )
            await asyncio.sleep(1.2)
            await self._next_round(guild_id, channel)

    async def _end_game(
        self,
        guild_id: int,
        channel: discord.TextChannel,
        winner: Optional[discord.Member] = None,
        reason: str = "ended",
    ):
        game = self._get_game(guild_id)
        if not game:
            return

        game["active"] = False
        if game.get("round_task") and not game["round_task"].done():
            game["round_task"].cancel()

        del self._games[guild_id]

        if reason == "stopped":
            embed = discord.Embed(
                title="Game Stopped",
                description="The F1 trivia game was stopped.",
                colour=0x888888,
            )
        elif winner:
            embed = discord.Embed(
                title="🏆 We Have a Winner!",
                description=f"**{winner.display_name}** wins the game with {game['scores'].get(winner.id, 0)} points!",
                colour=0xFFD700,
            )
        else:
            embed = discord.Embed(
                title="Game Over",
                description="The F1 trivia game has ended.",
                colour=0x888888,
            )

        scores = game["scores"]
        if scores:
            guild = channel.guild
            lines = []
            sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            medals = ["🥇", "🥈", "🥉"]
            for i, (uid, pts) in enumerate(sorted_scores[:10]):
                member = guild.get_member(uid)
                name = member.display_name if member else f"<@{uid}>"
                medal = medals[i] if i < len(medals) else f"#{i+1}"
                lines.append(f"{medal} **{name}** — {pts} pt{'s' if pts != 1 else ''}")
            embed.add_field(name="Final Scores", value="\n".join(lines), inline=False)

        embed.set_footer(text="Thanks for playing! | jaffar21")
        await channel.send(embed=embed)

    def _build_scoreboard(self, game: dict, guild: discord.Guild) -> discord.Embed:
        scores = game["scores"]
        embed = discord.Embed(title="🏁 Current Scores", colour=0xE8002D)
        if not scores:
            embed.description = "No points scored yet!"
        else:
            sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            medals = ["🥇", "🥈", "🥉"]
            lines = []
            for i, (uid, pts) in enumerate(sorted_scores[:10]):
                member = guild.get_member(uid)
                name = member.display_name if member else f"<@{uid}>"
                medal = medals[i] if i < len(medals) else f"#{i+1}"
                lines.append(f"{medal} **{name}** — {pts} / {game['target']}")
            embed.description = "\n".join(lines)
        embed.set_footer(text="jaffar21")
        return embed

    # ------------------------------------------------------------------
    # Listeners
    # ------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """We handle answer checking inside _run_round via wait_for; this is a no-op."""
        pass

    # ------------------------------------------------------------------
    # Cog lifecycle
    # ------------------------------------------------------------------

    def cog_unload(self):
        for game in self._games.values():
            if game.get("round_task") and not game["round_task"].done():
                game["round_task"].cancel()
        self._games.clear()
