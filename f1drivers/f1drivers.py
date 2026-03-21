import asyncio
import os
import random
import unicodedata
import re
import urllib.parse
from pathlib import Path
from typing import Optional, Dict, List

import aiohttp
import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.data_manager import cog_data_path

# ---------------------------------------------------------------------------
# Answer matching
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^a-z0-9 ]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _answers_match(user_input: str, accepted: List[str]) -> bool:
    norm_input = _normalize(user_input)
    if not norm_input:
        return False
    for ans in accepted:
        norm_ans = _normalize(ans)
        if norm_input == norm_ans:
            return True
        words_ans = norm_ans.split()
        if len(words_ans) > 1 and norm_input in words_ans:
            return True
        words_input = norm_input.split()
        if len(words_input) > 1 and norm_ans in words_input:
            return True
    return False


# ---------------------------------------------------------------------------
# Driver database
# Each entry: slug (filesystem-safe), wiki (Wikipedia page title),
#             name (display), answers (accepted strings)
# ---------------------------------------------------------------------------

DRIVERS: List[Dict] = [
    # ===== 2025-2026 CURRENT GRID =====
    {
        "slug": "max_verstappen",
        "wiki": "Max Verstappen",
        "name": "Max Verstappen",
        "answers": ["Max Verstappen", "Verstappen", "Max", "Super Max"],
    },
    {
        "slug": "liam_lawson",
        "wiki": "Liam Lawson (racing driver)",
        "name": "Liam Lawson",
        "answers": ["Liam Lawson", "Lawson", "Liam"],
    },
    {
        "slug": "lewis_hamilton",
        "wiki": "Lewis Hamilton",
        "name": "Lewis Hamilton",
        "answers": ["Lewis Hamilton", "Hamilton", "Lewis", "Sir Lewis"],
    },
    {
        "slug": "charles_leclerc",
        "wiki": "Charles Leclerc",
        "name": "Charles Leclerc",
        "answers": ["Charles Leclerc", "Leclerc", "Charles"],
    },
    {
        "slug": "lando_norris",
        "wiki": "Lando Norris",
        "name": "Lando Norris",
        "answers": ["Lando Norris", "Norris", "Lando"],
    },
    {
        "slug": "oscar_piastri",
        "wiki": "Oscar Piastri",
        "name": "Oscar Piastri",
        "answers": ["Oscar Piastri", "Piastri", "Oscar"],
    },
    {
        "slug": "george_russell",
        "wiki": "George Russell (racing driver)",
        "name": "George Russell",
        "answers": ["George Russell", "Russell", "George", "Mr Saturday"],
    },
    {
        "slug": "kimi_antonelli",
        "wiki": "Andrea Kimi Antonelli",
        "name": "Kimi Antonelli",
        "answers": ["Kimi Antonelli", "Antonelli", "Kimi", "Andrea Antonelli", "Andrea Kimi Antonelli"],
    },
    {
        "slug": "fernando_alonso",
        "wiki": "Fernando Alonso",
        "name": "Fernando Alonso",
        "answers": ["Fernando Alonso", "Alonso", "Fernando", "El Plan"],
    },
    {
        "slug": "lance_stroll",
        "wiki": "Lance Stroll",
        "name": "Lance Stroll",
        "answers": ["Lance Stroll", "Stroll", "Lance"],
    },
    {
        "slug": "pierre_gasly",
        "wiki": "Pierre Gasly",
        "name": "Pierre Gasly",
        "answers": ["Pierre Gasly", "Gasly", "Pierre"],
    },
    {
        "slug": "jack_doohan",
        "wiki": "Jack Doohan",
        "name": "Jack Doohan",
        "answers": ["Jack Doohan", "Doohan", "Jack"],
    },
    {
        "slug": "alex_albon",
        "wiki": "Alexander Albon",
        "name": "Alex Albon",
        "answers": ["Alex Albon", "Albon", "Alex", "Alexander Albon"],
    },
    {
        "slug": "carlos_sainz",
        "wiki": "Carlos Sainz Jr.",
        "name": "Carlos Sainz",
        "answers": ["Carlos Sainz", "Sainz", "Carlos", "Carlando"],
    },
    {
        "slug": "esteban_ocon",
        "wiki": "Esteban Ocon",
        "name": "Esteban Ocon",
        "answers": ["Esteban Ocon", "Ocon", "Esteban"],
    },
    {
        "slug": "oliver_bearman",
        "wiki": "Oliver Bearman",
        "name": "Oliver Bearman",
        "answers": ["Oliver Bearman", "Bearman", "Oliver", "Ollie Bearman", "Ollie"],
    },
    {
        "slug": "yuki_tsunoda",
        "wiki": "Yuki Tsunoda",
        "name": "Yuki Tsunoda",
        "answers": ["Yuki Tsunoda", "Tsunoda", "Yuki"],
    },
    {
        "slug": "isack_hadjar",
        "wiki": "Isack Hadjar",
        "name": "Isack Hadjar",
        "answers": ["Isack Hadjar", "Hadjar", "Isack"],
    },
    {
        "slug": "nico_hulkenberg",
        "wiki": "Nico Hülkenberg",
        "name": "Nico Hulkenberg",
        "answers": ["Nico Hulkenberg", "Hulkenberg", "Nico", "Hulk", "Hülkenberg"],
    },
    {
        "slug": "gabriel_bortoleto",
        "wiki": "Gabriel Bortoleto",
        "name": "Gabriel Bortoleto",
        "answers": ["Gabriel Bortoleto", "Bortoleto", "Gabriel"],
    },

    # ===== RECENTLY RETIRED (2020s) =====
    {
        "slug": "sebastian_vettel",
        "wiki": "Sebastian Vettel",
        "name": "Sebastian Vettel",
        "answers": ["Sebastian Vettel", "Vettel", "Seb", "Seb Vettel"],
    },
    {
        "slug": "kimi_raikkonen",
        "wiki": "Kimi Räikkönen",
        "name": "Kimi Raikkonen",
        "answers": ["Kimi Raikkonen", "Raikkonen", "Kimi", "The Iceman", "Räikkönen"],
    },
    {
        "slug": "valtteri_bottas",
        "wiki": "Valtteri Bottas",
        "name": "Valtteri Bottas",
        "answers": ["Valtteri Bottas", "Bottas", "Valtteri"],
    },
    {
        "slug": "daniel_ricciardo",
        "wiki": "Daniel Ricciardo",
        "name": "Daniel Ricciardo",
        "answers": ["Daniel Ricciardo", "Ricciardo", "Daniel", "Danny Ric", "Honey Badger"],
    },
    {
        "slug": "sergio_perez",
        "wiki": "Sergio Pérez",
        "name": "Sergio Perez",
        "answers": ["Sergio Perez", "Perez", "Sergio", "Checo", "Pérez"],
    },
    {
        "slug": "nico_rosberg",
        "wiki": "Nico Rosberg",
        "name": "Nico Rosberg",
        "answers": ["Nico Rosberg", "Rosberg", "Nico"],
    },
    {
        "slug": "jenson_button",
        "wiki": "Jenson Button",
        "name": "Jenson Button",
        "answers": ["Jenson Button", "Button", "Jenson", "JB"],
    },
    {
        "slug": "mark_webber",
        "wiki": "Mark Webber (racing driver)",
        "name": "Mark Webber",
        "answers": ["Mark Webber", "Webber", "Mark"],
    },
    {
        "slug": "felipe_massa",
        "wiki": "Felipe Massa",
        "name": "Felipe Massa",
        "answers": ["Felipe Massa", "Massa", "Felipe"],
    },
    {
        "slug": "mick_schumacher",
        "wiki": "Mick Schumacher",
        "name": "Mick Schumacher",
        "answers": ["Mick Schumacher", "Mick", "Schumacher"],
    },
    {
        "slug": "romain_grosjean",
        "wiki": "Romain Grosjean",
        "name": "Romain Grosjean",
        "answers": ["Romain Grosjean", "Grosjean", "Romain"],
    },
    {
        "slug": "daniil_kvyat",
        "wiki": "Daniil Kvyat",
        "name": "Daniil Kvyat",
        "answers": ["Daniil Kvyat", "Kvyat", "Daniil", "The Torpedo"],
    },
    {
        "slug": "nyck_de_vries",
        "wiki": "Nyck de Vries",
        "name": "Nyck de Vries",
        "answers": ["Nyck de Vries", "de Vries", "Nyck"],
    },
    {
        "slug": "robert_kubica",
        "wiki": "Robert Kubica",
        "name": "Robert Kubica",
        "answers": ["Robert Kubica", "Kubica", "Robert"],
    },
    {
        "slug": "nikita_mazepin",
        "wiki": "Nikita Mazepin",
        "name": "Nikita Mazepin",
        "answers": ["Nikita Mazepin", "Mazepin", "Nikita"],
    },
    {
        "slug": "antonio_giovinazzi",
        "wiki": "Antonio Giovinazzi",
        "name": "Antonio Giovinazzi",
        "answers": ["Antonio Giovinazzi", "Giovinazzi", "Antonio"],
    },
    {
        "slug": "nicholas_latifi",
        "wiki": "Nicholas Latifi",
        "name": "Nicholas Latifi",
        "answers": ["Nicholas Latifi", "Latifi", "Nicholas"],
    },
    {
        "slug": "brendon_hartley",
        "wiki": "Brendon Hartley",
        "name": "Brendon Hartley",
        "answers": ["Brendon Hartley", "Hartley", "Brendon"],
    },
    {
        "slug": "stoffel_vandoorne",
        "wiki": "Stoffel Vandoorne",
        "name": "Stoffel Vandoorne",
        "answers": ["Stoffel Vandoorne", "Vandoorne", "Stoffel"],
    },
    {
        "slug": "marcus_ericsson",
        "wiki": "Marcus Ericsson",
        "name": "Marcus Ericsson",
        "answers": ["Marcus Ericsson", "Ericsson", "Marcus"],
    },
    {
        "slug": "pascal_wehrlein",
        "wiki": "Pascal Wehrlein",
        "name": "Pascal Wehrlein",
        "answers": ["Pascal Wehrlein", "Wehrlein", "Pascal"],
    },
    {
        "slug": "zhou_guanyu",
        "wiki": "Zhou Guanyu",
        "name": "Zhou Guanyu",
        "answers": ["Zhou Guanyu", "Zhou", "Guanyu", "Guanyu Zhou"],
    },
    {
        "slug": "logan_sargeant",
        "wiki": "Logan Sargeant",
        "name": "Logan Sargeant",
        "answers": ["Logan Sargeant", "Sargeant", "Logan"],
    },
    {
        "slug": "kevin_magnussen",
        "wiki": "Kevin Magnussen",
        "name": "Kevin Magnussen",
        "answers": ["Kevin Magnussen", "Magnussen", "Kevin", "KMag"],
    },

    # ===== 2010s ERA =====
    {
        "slug": "paul_di_resta",
        "wiki": "Paul di Resta",
        "name": "Paul di Resta",
        "answers": ["Paul di Resta", "di Resta", "Paul"],
    },
    {
        "slug": "kamui_kobayashi",
        "wiki": "Kamui Kobayashi",
        "name": "Kamui Kobayashi",
        "answers": ["Kamui Kobayashi", "Kobayashi", "Kamui"],
    },
    {
        "slug": "jean_eric_vergne",
        "wiki": "Jean-Éric Vergne",
        "name": "Jean-Eric Vergne",
        "answers": ["Jean-Eric Vergne", "Vergne", "JEV", "Jean Eric Vergne"],
    },
    {
        "slug": "jules_bianchi",
        "wiki": "Jules Bianchi",
        "name": "Jules Bianchi",
        "answers": ["Jules Bianchi", "Bianchi", "Jules"],
    },
    {
        "slug": "esteban_gutierrez",
        "wiki": "Esteban Gutiérrez",
        "name": "Esteban Gutierrez",
        "answers": ["Esteban Gutierrez", "Gutierrez", "Gutiérrez"],
    },
    {
        "slug": "pastor_maldonado",
        "wiki": "Pastor Maldonado",
        "name": "Pastor Maldonado",
        "answers": ["Pastor Maldonado", "Maldonado", "Pastor"],
    },
    {
        "slug": "heikki_kovalainen",
        "wiki": "Heikki Kovalainen",
        "name": "Heikki Kovalainen",
        "answers": ["Heikki Kovalainen", "Kovalainen", "Heikki"],
    },
    {
        "slug": "adrian_sutil",
        "wiki": "Adrian Sutil",
        "name": "Adrian Sutil",
        "answers": ["Adrian Sutil", "Sutil", "Adrian"],
    },
    {
        "slug": "vitaly_petrov",
        "wiki": "Vitaly Petrov",
        "name": "Vitaly Petrov",
        "answers": ["Vitaly Petrov", "Petrov", "Vitaly"],
    },
    {
        "slug": "bruno_senna",
        "wiki": "Bruno Senna",
        "name": "Bruno Senna",
        "answers": ["Bruno Senna", "Senna", "Bruno"],
    },
    {
        "slug": "timo_glock",
        "wiki": "Timo Glock",
        "name": "Timo Glock",
        "answers": ["Timo Glock", "Glock", "Timo"],
    },
    {
        "slug": "karun_chandhok",
        "wiki": "Karun Chandhok",
        "name": "Karun Chandhok",
        "answers": ["Karun Chandhok", "Chandhok", "Karun"],
    },
    {
        "slug": "jarno_trulli",
        "wiki": "Jarno Trulli",
        "name": "Jarno Trulli",
        "answers": ["Jarno Trulli", "Trulli", "Jarno"],
    },
    {
        "slug": "giancarlo_fisichella",
        "wiki": "Giancarlo Fisichella",
        "name": "Giancarlo Fisichella",
        "answers": ["Giancarlo Fisichella", "Fisichella", "Giancarlo", "Fisi"],
    },
    {
        "slug": "nick_heidfeld",
        "wiki": "Nick Heidfeld",
        "name": "Nick Heidfeld",
        "answers": ["Nick Heidfeld", "Heidfeld", "Nick", "Quick Nick"],
    },
    {
        "slug": "sebastien_buemi",
        "wiki": "Sébastien Buemi",
        "name": "Sebastien Buemi",
        "answers": ["Sebastien Buemi", "Buemi", "Sebastien"],
    },
    {
        "slug": "pedro_de_la_rosa",
        "wiki": "Pedro de la Rosa",
        "name": "Pedro de la Rosa",
        "answers": ["Pedro de la Rosa", "de la Rosa", "Pedro"],
    },
    {
        "slug": "narain_karthikeyan",
        "wiki": "Narain Karthikeyan",
        "name": "Narain Karthikeyan",
        "answers": ["Narain Karthikeyan", "Karthikeyan", "Narain"],
    },
    {
        "slug": "vitantonio_liuzzi",
        "wiki": "Vitantonio Liuzzi",
        "name": "Tonio Liuzzi",
        "answers": ["Tonio Liuzzi", "Vitantonio Liuzzi", "Liuzzi", "Tonio"],
    },
    {
        "slug": "scott_speed",
        "wiki": "Scott Speed",
        "name": "Scott Speed",
        "answers": ["Scott Speed", "Speed", "Scott"],
    },
    {
        "slug": "takuma_sato",
        "wiki": "Takuma Sato",
        "name": "Takuma Sato",
        "answers": ["Takuma Sato", "Sato", "Takuma"],
    },
    {
        "slug": "olivier_panis",
        "wiki": "Olivier Panis",
        "name": "Olivier Panis",
        "answers": ["Olivier Panis", "Panis", "Olivier"],
    },
    {
        "slug": "ralf_schumacher",
        "wiki": "Ralf Schumacher",
        "name": "Ralf Schumacher",
        "answers": ["Ralf Schumacher", "Ralf"],
    },
    {
        "slug": "nelson_piquet_jr",
        "wiki": "Nelson Piquet Jr.",
        "name": "Nelson Piquet Jr",
        "answers": ["Nelson Piquet Jr", "Piquet Jr", "Nelson Jr"],
    },
    {
        "slug": "alexander_wurz",
        "wiki": "Alexander Wurz",
        "name": "Alexander Wurz",
        "answers": ["Alexander Wurz", "Wurz", "Alex Wurz"],
    },
    {
        "slug": "sebastien_bourdais",
        "wiki": "Sébastien Bourdais",
        "name": "Sebastien Bourdais",
        "answers": ["Sebastien Bourdais", "Bourdais", "Sebastien"],
    },
    {
        "slug": "anthony_davidson",
        "wiki": "Anthony Davidson",
        "name": "Anthony Davidson",
        "answers": ["Anthony Davidson", "Davidson", "Anthony"],
    },
    {
        "slug": "christian_klien",
        "wiki": "Christian Klien",
        "name": "Christian Klien",
        "answers": ["Christian Klien", "Klien", "Christian"],
    },
    {
        "slug": "tiago_monteiro",
        "wiki": "Tiago Monteiro",
        "name": "Tiago Monteiro",
        "answers": ["Tiago Monteiro", "Monteiro", "Tiago"],
    },
    {
        "slug": "christijan_albers",
        "wiki": "Christijan Albers",
        "name": "Christijan Albers",
        "answers": ["Christijan Albers", "Albers", "Christijan"],
    },
    {
        "slug": "giedo_van_der_garde",
        "wiki": "Giedo van der Garde",
        "name": "Giedo van der Garde",
        "answers": ["Giedo van der Garde", "van der Garde", "Giedo"],
    },
    {
        "slug": "max_chilton",
        "wiki": "Max Chilton",
        "name": "Max Chilton",
        "answers": ["Max Chilton", "Chilton"],
    },
    {
        "slug": "charles_pic",
        "wiki": "Charles Pic",
        "name": "Charles Pic",
        "answers": ["Charles Pic", "Pic", "Charles"],
    },
    {
        "slug": "zsolt_baumgartner",
        "wiki": "Zsolt Baumgartner",
        "name": "Zsolt Baumgartner",
        "answers": ["Zsolt Baumgartner", "Baumgartner", "Zsolt"],
    },
    {
        "slug": "enrique_bernoldi",
        "wiki": "Enrique Bernoldi",
        "name": "Enrique Bernoldi",
        "answers": ["Enrique Bernoldi", "Bernoldi", "Enrique"],
    },
    {
        "slug": "marc_gene",
        "wiki": "Marc Gené",
        "name": "Marc Gene",
        "answers": ["Marc Gene", "Gene", "Marc", "Marc Gené"],
    },
    {
        "slug": "luca_badoer",
        "wiki": "Luca Badoer",
        "name": "Luca Badoer",
        "answers": ["Luca Badoer", "Badoer", "Luca"],
    },

    # ===== 2000s ERA =====
    {
        "slug": "michael_schumacher",
        "wiki": "Michael Schumacher",
        "name": "Michael Schumacher",
        "answers": ["Michael Schumacher", "Schumacher", "Michael", "Schumi"],
    },
    {
        "slug": "rubens_barrichello",
        "wiki": "Rubens Barrichello",
        "name": "Rubens Barrichello",
        "answers": ["Rubens Barrichello", "Barrichello", "Rubens", "Rubinho"],
    },
    {
        "slug": "david_coulthard",
        "wiki": "David Coulthard",
        "name": "David Coulthard",
        "answers": ["David Coulthard", "Coulthard", "David", "DC"],
    },
    {
        "slug": "mika_hakkinen",
        "wiki": "Mika Häkkinen",
        "name": "Mika Hakkinen",
        "answers": ["Mika Hakkinen", "Hakkinen", "Mika", "Häkkinen", "The Flying Finn"],
    },
    {
        "slug": "jacques_villeneuve",
        "wiki": "Jacques Villeneuve",
        "name": "Jacques Villeneuve",
        "answers": ["Jacques Villeneuve", "Villeneuve", "Jacques"],
    },
    {
        "slug": "damon_hill",
        "wiki": "Damon Hill",
        "name": "Damon Hill",
        "answers": ["Damon Hill", "Hill", "Damon"],
    },
    {
        "slug": "eddie_irvine",
        "wiki": "Eddie Irvine",
        "name": "Eddie Irvine",
        "answers": ["Eddie Irvine", "Irvine", "Eddie"],
    },
    {
        "slug": "heinz_frentzen",
        "wiki": "Heinz-Harald Frentzen",
        "name": "Heinz-Harald Frentzen",
        "answers": ["Heinz-Harald Frentzen", "Frentzen", "HHF", "Heinz"],
    },
    {
        "slug": "juan_pablo_montoya",
        "wiki": "Juan Pablo Montoya",
        "name": "Juan Pablo Montoya",
        "answers": ["Juan Pablo Montoya", "Montoya", "JPM", "Juan Pablo"],
    },
    {
        "slug": "martin_brundle",
        "wiki": "Martin Brundle",
        "name": "Martin Brundle",
        "answers": ["Martin Brundle", "Brundle", "Martin"],
    },
    {
        "slug": "johnny_herbert",
        "wiki": "Johnny Herbert",
        "name": "Johnny Herbert",
        "answers": ["Johnny Herbert", "Herbert", "Johnny"],
    },
    {
        "slug": "mika_salo",
        "wiki": "Mika Salo",
        "name": "Mika Salo",
        "answers": ["Mika Salo", "Salo"],
    },
    {
        "slug": "jos_verstappen",
        "wiki": "Jos Verstappen",
        "name": "Jos Verstappen",
        "answers": ["Jos Verstappen", "Jos"],
    },
    {
        "slug": "jan_magnussen",
        "wiki": "Jan Magnussen",
        "name": "Jan Magnussen",
        "answers": ["Jan Magnussen", "Jan"],
    },
    {
        "slug": "gianni_morbidelli",
        "wiki": "Gianni Morbidelli",
        "name": "Gianni Morbidelli",
        "answers": ["Gianni Morbidelli", "Morbidelli", "Gianni"],
    },
    {
        "slug": "cristiano_da_matta",
        "wiki": "Cristiano da Matta",
        "name": "Cristiano da Matta",
        "answers": ["Cristiano da Matta", "da Matta", "Cristiano"],
    },
    {
        "slug": "ralph_firman",
        "wiki": "Ralph Firman Jr.",
        "name": "Ralph Firman Jr",
        "answers": ["Ralph Firman", "Firman", "Ralph"],
    },
    {
        "slug": "justin_wilson",
        "wiki": "Justin Wilson (racing driver)",
        "name": "Justin Wilson",
        "answers": ["Justin Wilson", "Wilson", "Justin"],
    },
    {
        "slug": "riccardo_zonta",
        "wiki": "Ricardo Zonta",
        "name": "Ricardo Zonta",
        "answers": ["Ricardo Zonta", "Zonta", "Riccardo Zonta"],
    },
    {
        "slug": "michael_andretti",
        "wiki": "Michael Andretti",
        "name": "Michael Andretti",
        "answers": ["Michael Andretti", "Andretti", "Michael"],
    },

    # ===== 1990s ERA =====
    {
        "slug": "ayrton_senna",
        "wiki": "Ayrton Senna",
        "name": "Ayrton Senna",
        "answers": ["Ayrton Senna", "Senna", "Ayrton", "Magic"],
    },
    {
        "slug": "alain_prost",
        "wiki": "Alain Prost",
        "name": "Alain Prost",
        "answers": ["Alain Prost", "Prost", "Alain", "The Professor"],
    },
    {
        "slug": "nigel_mansell",
        "wiki": "Nigel Mansell",
        "name": "Nigel Mansell",
        "answers": ["Nigel Mansell", "Mansell", "Nigel", "Red Five"],
    },
    {
        "slug": "nelson_piquet",
        "wiki": "Nelson Piquet",
        "name": "Nelson Piquet",
        "answers": ["Nelson Piquet", "Piquet", "Nelson"],
    },
    {
        "slug": "gerhard_berger",
        "wiki": "Gerhard Berger",
        "name": "Gerhard Berger",
        "answers": ["Gerhard Berger", "Berger", "Gerhard"],
    },
    {
        "slug": "jean_alesi",
        "wiki": "Jean Alesi",
        "name": "Jean Alesi",
        "answers": ["Jean Alesi", "Alesi", "Jean"],
    },
    {
        "slug": "riccardo_patrese",
        "wiki": "Riccardo Patrese",
        "name": "Riccardo Patrese",
        "answers": ["Riccardo Patrese", "Patrese", "Riccardo"],
    },
    {
        "slug": "michele_alboreto",
        "wiki": "Michele Alboreto",
        "name": "Michele Alboreto",
        "answers": ["Michele Alboreto", "Alboreto", "Michele"],
    },
    {
        "slug": "thierry_boutsen",
        "wiki": "Thierry Boutsen",
        "name": "Thierry Boutsen",
        "answers": ["Thierry Boutsen", "Boutsen", "Thierry"],
    },
    {
        "slug": "martin_donnelly",
        "wiki": "Martin Donnelly (racing driver)",
        "name": "Martin Donnelly",
        "answers": ["Martin Donnelly", "Donnelly", "Martin"],
    },
    {
        "slug": "derek_warwick",
        "wiki": "Derek Warwick",
        "name": "Derek Warwick",
        "answers": ["Derek Warwick", "Warwick", "Derek"],
    },
    {
        "slug": "stefan_johansson",
        "wiki": "Stefan Johansson",
        "name": "Stefan Johansson",
        "answers": ["Stefan Johansson", "Johansson", "Stefan"],
    },
    {
        "slug": "pierluigi_martini",
        "wiki": "Pierluigi Martini",
        "name": "Pierluigi Martini",
        "answers": ["Pierluigi Martini", "Martini", "Pierluigi"],
    },
    {
        "slug": "andrea_de_cesaris",
        "wiki": "Andrea de Cesaris",
        "name": "Andrea de Cesaris",
        "answers": ["Andrea de Cesaris", "de Cesaris", "Andrea"],
    },
    {
        "slug": "eddie_cheever",
        "wiki": "Eddie Cheever",
        "name": "Eddie Cheever",
        "answers": ["Eddie Cheever", "Cheever", "Eddie"],
    },
    {
        "slug": "bertrand_gachot",
        "wiki": "Bertrand Gachot",
        "name": "Bertrand Gachot",
        "answers": ["Bertrand Gachot", "Gachot", "Bertrand"],
    },
    {
        "slug": "eric_comas",
        "wiki": "Éric Comas",
        "name": "Eric Comas",
        "answers": ["Eric Comas", "Comas", "Eric", "Éric Comas"],
    },
    {
        "slug": "aguri_suzuki",
        "wiki": "Aguri Suzuki",
        "name": "Aguri Suzuki",
        "answers": ["Aguri Suzuki", "Suzuki", "Aguri"],
    },
    {
        "slug": "ukyo_katayama",
        "wiki": "Ukyo Katayama",
        "name": "Ukyo Katayama",
        "answers": ["Ukyo Katayama", "Katayama", "Ukyo"],
    },
    {
        "slug": "mark_blundell",
        "wiki": "Mark Blundell",
        "name": "Mark Blundell",
        "answers": ["Mark Blundell", "Blundell", "Mark"],
    },
    {
        "slug": "christian_fittipaldi",
        "wiki": "Christian Fittipaldi",
        "name": "Christian Fittipaldi",
        "answers": ["Christian Fittipaldi", "Christian"],
    },
    {
        "slug": "karl_wendlinger",
        "wiki": "Karl Wendlinger",
        "name": "Karl Wendlinger",
        "answers": ["Karl Wendlinger", "Wendlinger", "Karl"],
    },
    {
        "slug": "jj_lehto",
        "wiki": "JJ Lehto",
        "name": "JJ Lehto",
        "answers": ["JJ Lehto", "Lehto", "JJ"],
    },
    {
        "slug": "mika_salo2",
        "wiki": "Mika Salo",
        "name": "Mika Salo",
        "answers": ["Mika Salo", "Salo"],
    },
    {
        "slug": "pedro_lamy",
        "wiki": "Pedro Lamy",
        "name": "Pedro Lamy",
        "answers": ["Pedro Lamy", "Lamy", "Pedro"],
    },
    {
        "slug": "olivier_grouillard",
        "wiki": "Olivier Grouillard",
        "name": "Olivier Grouillard",
        "answers": ["Olivier Grouillard", "Grouillard", "Olivier"],
    },
    {
        "slug": "emanuele_pirro",
        "wiki": "Emanuele Pirro",
        "name": "Emanuele Pirro",
        "answers": ["Emanuele Pirro", "Pirro", "Emanuele"],
    },
    {
        "slug": "ivan_capelli",
        "wiki": "Ivan Capelli",
        "name": "Ivan Capelli",
        "answers": ["Ivan Capelli", "Capelli", "Ivan"],
    },
    {
        "slug": "mauricio_gugelmin",
        "wiki": "Maurício Gugelmin",
        "name": "Mauricio Gugelmin",
        "answers": ["Mauricio Gugelmin", "Gugelmin", "Mauricio"],
    },
    {
        "slug": "roberto_moreno",
        "wiki": "Roberto Moreno",
        "name": "Roberto Moreno",
        "answers": ["Roberto Moreno", "Moreno", "Roberto"],
    },
    {
        "slug": "Alessandro_zanardi",
        "wiki": "Alessandro Zanardi",
        "name": "Alessandro Zanardi",
        "answers": ["Alessandro Zanardi", "Zanardi", "Alessandro", "Alex Zanardi"],
    },

    # ===== 1980s ERA =====
    {
        "slug": "niki_lauda",
        "wiki": "Niki Lauda",
        "name": "Niki Lauda",
        "answers": ["Niki Lauda", "Lauda", "Niki"],
    },
    {
        "slug": "james_hunt",
        "wiki": "James Hunt",
        "name": "James Hunt",
        "answers": ["James Hunt", "Hunt", "James"],
    },
    {
        "slug": "gilles_villeneuve",
        "wiki": "Gilles Villeneuve",
        "name": "Gilles Villeneuve",
        "answers": ["Gilles Villeneuve", "Gilles"],
    },
    {
        "slug": "keke_rosberg",
        "wiki": "Keke Rosberg",
        "name": "Keke Rosberg",
        "answers": ["Keke Rosberg", "Keke"],
    },
    {
        "slug": "carlos_reutemann",
        "wiki": "Carlos Reutemann",
        "name": "Carlos Reutemann",
        "answers": ["Carlos Reutemann", "Reutemann", "Lole"],
    },
    {
        "slug": "alan_jones",
        "wiki": "Alan Jones (racing driver)",
        "name": "Alan Jones",
        "answers": ["Alan Jones", "Jones", "Alan"],
    },
    {
        "slug": "john_watson",
        "wiki": "John Watson (racing driver)",
        "name": "John Watson",
        "answers": ["John Watson", "Watson", "John", "Wattie"],
    },
    {
        "slug": "patrick_tambay",
        "wiki": "Patrick Tambay",
        "name": "Patrick Tambay",
        "answers": ["Patrick Tambay", "Tambay", "Patrick"],
    },
    {
        "slug": "elio_de_angelis",
        "wiki": "Elio de Angelis",
        "name": "Elio de Angelis",
        "answers": ["Elio de Angelis", "de Angelis", "Elio"],
    },
    {
        "slug": "rene_arnoux",
        "wiki": "René Arnoux",
        "name": "Rene Arnoux",
        "answers": ["Rene Arnoux", "Arnoux", "Rene", "René Arnoux"],
    },
    {
        "slug": "patrick_depailler",
        "wiki": "Patrick Depailler",
        "name": "Patrick Depailler",
        "answers": ["Patrick Depailler", "Depailler", "Patrick"],
    },
    {
        "slug": "jacques_laffite",
        "wiki": "Jacques Laffite",
        "name": "Jacques Laffite",
        "answers": ["Jacques Laffite", "Laffite", "Jacques"],
    },
    {
        "slug": "didier_pironi",
        "wiki": "Didier Pironi",
        "name": "Didier Pironi",
        "answers": ["Didier Pironi", "Pironi", "Didier"],
    },
    {
        "slug": "stefan_bellof",
        "wiki": "Stefan Bellof",
        "name": "Stefan Bellof",
        "answers": ["Stefan Bellof", "Bellof", "Stefan"],
    },
    {
        "slug": "marc_surer",
        "wiki": "Marc Surer",
        "name": "Marc Surer",
        "answers": ["Marc Surer", "Surer", "Marc"],
    },
    {
        "slug": "manfred_winkelhock",
        "wiki": "Manfred Winkelhock",
        "name": "Manfred Winkelhock",
        "answers": ["Manfred Winkelhock", "Winkelhock", "Manfred"],
    },
    {
        "slug": "teo_fabi",
        "wiki": "Teo Fabi",
        "name": "Teo Fabi",
        "answers": ["Teo Fabi", "Fabi", "Teo"],
    },
    {
        "slug": "emerson_fittipaldi",
        "wiki": "Emerson Fittipaldi",
        "name": "Emerson Fittipaldi",
        "answers": ["Emerson Fittipaldi", "Emerson"],
    },
    {
        "slug": "wilson_fittipaldi",
        "wiki": "Wilson Fittipaldi",
        "name": "Wilson Fittipaldi",
        "answers": ["Wilson Fittipaldi", "Wilson"],
    },
    {
        "slug": "philippe_streiff",
        "wiki": "Philippe Streiff",
        "name": "Philippe Streiff",
        "answers": ["Philippe Streiff", "Streiff", "Philippe"],
    },
    {
        "slug": "jonathan_palmer",
        "wiki": "Jonathan Palmer",
        "name": "Jonathan Palmer",
        "answers": ["Jonathan Palmer", "Palmer", "Jonathan"],
    },

    # ===== 1970s ERA =====
    {
        "slug": "jackie_stewart",
        "wiki": "Jackie Stewart",
        "name": "Jackie Stewart",
        "answers": ["Jackie Stewart", "Stewart", "Jackie", "The Flying Scotsman"],
    },
    {
        "slug": "jochen_rindt",
        "wiki": "Jochen Rindt",
        "name": "Jochen Rindt",
        "answers": ["Jochen Rindt", "Rindt", "Jochen"],
    },
    {
        "slug": "denny_hulme",
        "wiki": "Denny Hulme",
        "name": "Denny Hulme",
        "answers": ["Denny Hulme", "Hulme", "Denny", "The Bear"],
    },
    {
        "slug": "clay_regazzoni",
        "wiki": "Clay Regazzoni",
        "name": "Clay Regazzoni",
        "answers": ["Clay Regazzoni", "Regazzoni", "Clay"],
    },
    {
        "slug": "chris_amon",
        "wiki": "Chris Amon",
        "name": "Chris Amon",
        "answers": ["Chris Amon", "Amon", "Chris"],
    },
    {
        "slug": "jacky_ickx",
        "wiki": "Jacky Ickx",
        "name": "Jacky Ickx",
        "answers": ["Jacky Ickx", "Ickx", "Jacky"],
    },
    {
        "slug": "francois_cevert",
        "wiki": "François Cevert",
        "name": "Francois Cevert",
        "answers": ["Francois Cevert", "Cevert", "François Cevert"],
    },
    {
        "slug": "ronnie_peterson",
        "wiki": "Ronnie Peterson",
        "name": "Ronnie Peterson",
        "answers": ["Ronnie Peterson", "Peterson", "Ronnie", "Super Swede"],
    },
    {
        "slug": "jody_scheckter",
        "wiki": "Jody Scheckter",
        "name": "Jody Scheckter",
        "answers": ["Jody Scheckter", "Scheckter", "Jody"],
    },
    {
        "slug": "mario_andretti",
        "wiki": "Mario Andretti",
        "name": "Mario Andretti",
        "answers": ["Mario Andretti", "Andretti", "Mario"],
    },
    {
        "slug": "carlos_pace",
        "wiki": "Carlos Pace",
        "name": "Carlos Pace",
        "answers": ["Carlos Pace", "Pace", "Carlos"],
    },
    {
        "slug": "tom_pryce",
        "wiki": "Tom Pryce",
        "name": "Tom Pryce",
        "answers": ["Tom Pryce", "Pryce", "Tom"],
    },
    {
        "slug": "gunnar_nilsson",
        "wiki": "Gunnar Nilsson",
        "name": "Gunnar Nilsson",
        "answers": ["Gunnar Nilsson", "Nilsson", "Gunnar"],
    },
    {
        "slug": "vittorio_brambilla",
        "wiki": "Vittorio Brambilla",
        "name": "Vittorio Brambilla",
        "answers": ["Vittorio Brambilla", "Brambilla", "Vittorio", "The Monza Gorilla"],
    },
    {
        "slug": "jo_siffert",
        "wiki": "Jo Siffert",
        "name": "Jo Siffert",
        "answers": ["Jo Siffert", "Siffert", "Jo", "Seppi"],
    },
    {
        "slug": "peter_revson",
        "wiki": "Peter Revson",
        "name": "Peter Revson",
        "answers": ["Peter Revson", "Revson", "Peter"],
    },
    {
        "slug": "henri_pescarolo",
        "wiki": "Henri Pescarolo",
        "name": "Henri Pescarolo",
        "answers": ["Henri Pescarolo", "Pescarolo", "Henri"],
    },
    {
        "slug": "rolf_stommelen",
        "wiki": "Rolf Stommelen",
        "name": "Rolf Stommelen",
        "answers": ["Rolf Stommelen", "Stommelen", "Rolf"],
    },
    {
        "slug": "jean_pierre_beltoise",
        "wiki": "Jean-Pierre Beltoise",
        "name": "Jean-Pierre Beltoise",
        "answers": ["Jean-Pierre Beltoise", "Beltoise", "Jean-Pierre"],
    },
    {
        "slug": "jo_bonnier",
        "wiki": "Jo Bonnier",
        "name": "Jo Bonnier",
        "answers": ["Jo Bonnier", "Bonnier", "Jo"],
    },
    {
        "slug": "jochen_mass",
        "wiki": "Jochen Mass",
        "name": "Jochen Mass",
        "answers": ["Jochen Mass", "Mass", "Jochen"],
    },
    {
        "slug": "jean_pierre_jabouille",
        "wiki": "Jean-Pierre Jabouille",
        "name": "Jean-Pierre Jabouille",
        "answers": ["Jean-Pierre Jabouille", "Jabouille", "Jean-Pierre"],
    },
    {
        "slug": "jean_pierre_jarier",
        "wiki": "Jean-Pierre Jarier",
        "name": "Jean-Pierre Jarier",
        "answers": ["Jean-Pierre Jarier", "Jarier"],
    },
    {
        "slug": "pedro_rodriguez",
        "wiki": "Pedro Rodríguez (racing driver)",
        "name": "Pedro Rodriguez",
        "answers": ["Pedro Rodriguez", "Rodriguez", "Pedro", "Pedro Rodríguez"],
    },
    {
        "slug": "hans_stuck",
        "wiki": "Hans-Joachim Stuck",
        "name": "Hans-Joachim Stuck",
        "answers": ["Hans-Joachim Stuck", "Stuck", "Hans Stuck"],
    },
    {
        "slug": "peter_gethin",
        "wiki": "Peter Gethin",
        "name": "Peter Gethin",
        "answers": ["Peter Gethin", "Gethin", "Peter"],
    },

    # ===== 1960s ERA =====
    {
        "slug": "jim_clark",
        "wiki": "Jim Clark (racing driver)",
        "name": "Jim Clark",
        "answers": ["Jim Clark", "Clark", "Jim"],
    },
    {
        "slug": "graham_hill",
        "wiki": "Graham Hill",
        "name": "Graham Hill",
        "answers": ["Graham Hill", "Graham", "Mr Monaco"],
    },
    {
        "slug": "jack_brabham",
        "wiki": "Jack Brabham",
        "name": "Jack Brabham",
        "answers": ["Jack Brabham", "Brabham", "Jack", "Black Jack"],
    },
    {
        "slug": "john_surtees",
        "wiki": "John Surtees",
        "name": "John Surtees",
        "answers": ["John Surtees", "Surtees", "John"],
    },
    {
        "slug": "dan_gurney",
        "wiki": "Dan Gurney",
        "name": "Dan Gurney",
        "answers": ["Dan Gurney", "Gurney", "Dan"],
    },
    {
        "slug": "bruce_mclaren",
        "wiki": "Bruce McLaren",
        "name": "Bruce McLaren",
        "answers": ["Bruce McLaren", "McLaren", "Bruce"],
    },
    {
        "slug": "lorenzo_bandini",
        "wiki": "Lorenzo Bandini",
        "name": "Lorenzo Bandini",
        "answers": ["Lorenzo Bandini", "Bandini", "Lorenzo"],
    },
    {
        "slug": "richie_ginther",
        "wiki": "Richie Ginther",
        "name": "Richie Ginther",
        "answers": ["Richie Ginther", "Ginther", "Richie"],
    },
    {
        "slug": "innes_ireland",
        "wiki": "Innes Ireland",
        "name": "Innes Ireland",
        "answers": ["Innes Ireland", "Ireland", "Innes"],
    },
    {
        "slug": "mike_spence",
        "wiki": "Mike Spence",
        "name": "Mike Spence",
        "answers": ["Mike Spence", "Spence", "Mike"],
    },
    {
        "slug": "piers_courage",
        "wiki": "Piers Courage",
        "name": "Piers Courage",
        "answers": ["Piers Courage", "Courage", "Piers"],
    },
    {
        "slug": "tony_brooks",
        "wiki": "Tony Brooks",
        "name": "Tony Brooks",
        "answers": ["Tony Brooks", "Brooks", "Tony"],
    },
    {
        "slug": "ludovico_scarfiotti",
        "wiki": "Ludovico Scarfiotti",
        "name": "Ludovico Scarfiotti",
        "answers": ["Ludovico Scarfiotti", "Scarfiotti", "Ludovico"],
    },
    {
        "slug": "mike_hailwood",
        "wiki": "Mike Hailwood",
        "name": "Mike Hailwood",
        "answers": ["Mike Hailwood", "Hailwood", "Mike", "Mike the Bike"],
    },

    # ===== 1950s ERA =====
    {
        "slug": "juan_manuel_fangio",
        "wiki": "Juan Manuel Fangio",
        "name": "Juan Manuel Fangio",
        "answers": ["Juan Manuel Fangio", "Fangio", "Juan Manuel", "El Maestro"],
    },
    {
        "slug": "alberto_ascari",
        "wiki": "Alberto Ascari",
        "name": "Alberto Ascari",
        "answers": ["Alberto Ascari", "Ascari", "Alberto"],
    },
    {
        "slug": "nino_farina",
        "wiki": "Giuseppe Farina",
        "name": "Nino Farina",
        "answers": ["Nino Farina", "Farina", "Giuseppe Farina", "Nino"],
    },
    {
        "slug": "stirling_moss",
        "wiki": "Stirling Moss",
        "name": "Stirling Moss",
        "answers": ["Stirling Moss", "Moss", "Stirling"],
    },
    {
        "slug": "mike_hawthorn",
        "wiki": "Mike Hawthorn",
        "name": "Mike Hawthorn",
        "answers": ["Mike Hawthorn", "Hawthorn", "Mike"],
    },
    {
        "slug": "phil_hill",
        "wiki": "Phil Hill (racing driver)",
        "name": "Phil Hill",
        "answers": ["Phil Hill", "Phil"],
    },
    {
        "slug": "peter_collins",
        "wiki": "Peter Collins (racing driver)",
        "name": "Peter Collins",
        "answers": ["Peter Collins", "Collins", "Peter"],
    },
    {
        "slug": "wolfgang_von_trips",
        "wiki": "Wolfgang von Trips",
        "name": "Wolfgang von Trips",
        "answers": ["Wolfgang von Trips", "von Trips", "Wolfgang", "Taffy"],
    },
    {
        "slug": "luigi_musso",
        "wiki": "Luigi Musso",
        "name": "Luigi Musso",
        "answers": ["Luigi Musso", "Musso", "Luigi"],
    },
    {
        "slug": "piero_taruffi",
        "wiki": "Piero Taruffi",
        "name": "Piero Taruffi",
        "answers": ["Piero Taruffi", "Taruffi", "Piero"],
    },
    {
        "slug": "jose_froilan_gonzalez",
        "wiki": "José Froilán González",
        "name": "Jose Froilan Gonzalez",
        "answers": ["Jose Froilan Gonzalez", "Gonzalez", "Jose", "The Pampas Bull"],
    },
    {
        "slug": "maurice_trintignant",
        "wiki": "Maurice Trintignant",
        "name": "Maurice Trintignant",
        "answers": ["Maurice Trintignant", "Trintignant", "Maurice", "Pétoulet"],
    },
    {
        "slug": "harry_schell",
        "wiki": "Harry Schell",
        "name": "Harry Schell",
        "answers": ["Harry Schell", "Schell", "Harry"],
    },
    {
        "slug": "eugenio_castellotti",
        "wiki": "Eugenio Castellotti",
        "name": "Eugenio Castellotti",
        "answers": ["Eugenio Castellotti", "Castellotti", "Eugenio"],
    },

    # ===== OTHER NOTABLE =====
    {
        "slug": "david_purley",
        "wiki": "David Purley",
        "name": "David Purley",
        "answers": ["David Purley", "Purley", "David"],
    },
    {
        "slug": "david_brabham",
        "wiki": "David Brabham",
        "name": "David Brabham",
        "answers": ["David Brabham", "David"],
    },
]

# Deduplicate by slug (mika_salo2 is same person — remove duplicate)
seen_slugs = set()
_UNIQUE_DRIVERS = []
for d in DRIVERS:
    if d["slug"] not in seen_slugs:
        seen_slugs.add(d["slug"])
        _UNIQUE_DRIVERS.append(d)
DRIVERS = _UNIQUE_DRIVERS


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------

WIKI_REST = "https://en.wikipedia.org/api/rest_v1/page/summary/{}"
WIKI_API  = "https://en.wikipedia.org/w/api.php"   # fallback
ROUND_TIME = 20  # seconds per question


class F1Drivers(commands.Cog):
    """Guess the F1 driver from their photo — first to the target wins!"""

    __version__ = "1.0.0"
    __author__ = "jaffar21"

    def __init__(self, bot: Red):
        self.bot = bot
        self._games: Dict[int, dict] = {}

    # ------------------------------------------------------------------
    # Image helpers
    # ------------------------------------------------------------------

    def _image_dir(self) -> Path:
        return cog_data_path(self) / "images"

    def _image_path(self, slug: str) -> Optional[Path]:
        """Return path if any image file exists for this slug."""
        d = self._image_dir()
        for ext in ("jpg", "jpeg", "png", "webp"):
            p = d / f"{slug}.{ext}"
            if p.exists():
                return p
        return None

    async def _fetch_wiki_image_url(self, session: aiohttp.ClientSession, wiki_title: str) -> Optional[str]:
        """Fetch driver portrait URL using Wikipedia REST summary API (most reliable).
        Falls back to the pageimages API if the REST call fails."""

        # --- Primary: REST summary endpoint (returns infobox image for virtually every person article) ---
        encoded = urllib.parse.quote(wiki_title.replace(" ", "_"), safe="():")
        rest_url = WIKI_REST.format(encoded)
        try:
            async with session.get(
                rest_url,
                timeout=aiohttp.ClientTimeout(total=20),
                headers={"User-Agent": "F1DriversTriviaBot/1.0 (Red-DiscordBot cog by jaffar21)"},
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # thumbnail.source is already a sized Wikimedia URL — resize to 500px portrait quality
                    thumb = data.get("thumbnail", {}).get("source")
                    if thumb:
                        return self._resize_wikimedia_url(thumb, 500)
        except Exception:
            pass

        # --- Fallback: old pageimages API ---
        params = {
            "action": "query",
            "titles": wiki_title,
            "prop": "pageimages",
            "format": "json",
            "pithumbsize": 500,
            "redirects": 1,
        }
        try:
            async with session.get(
                WIKI_API,
                params=params,
                timeout=aiohttp.ClientTimeout(total=20),
                headers={"User-Agent": "F1DriversTriviaBot/1.0 (Red-DiscordBot cog by jaffar21)"},
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    pages = data.get("query", {}).get("pages", {})
                    for page in pages.values():
                        src = page.get("thumbnail", {}).get("source")
                        if src:
                            return src
        except Exception:
            pass

        return None

    @staticmethod
    def _resize_wikimedia_url(url: str, size: int) -> str:
        """Rewrite a Wikimedia thumbnail URL to request a specific pixel width."""
        # Wikimedia thumbnail URLs look like:
        # https://upload.wikimedia.org/wikipedia/commons/thumb/a/bc/File.jpg/320px-File.jpg
        # We swap the size segment to get the quality we want.
        import re as _re
        new_url = _re.sub(r"/\d+px-", f"/{size}px-", url)
        return new_url

    async def _download_image(self, session: aiohttp.ClientSession, url: str, slug: str) -> bool:
        """Download an image from url and save it locally. Returns True on success."""
        # Detect extension from URL
        url_path = url.split("?")[0]
        ext = url_path.rsplit(".", 1)[-1].lower()
        if ext not in ("jpg", "jpeg", "png", "webp"):
            ext = "jpg"

        dest = self._image_dir() / f"{slug}.{ext}"
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    return False
                data = await resp.read()
                if len(data) < 1000:
                    return False
                dest.write_bytes(data)
                return True
        except Exception:
            return False

    def _available_drivers(self) -> List[Dict]:
        """Return only drivers who have a locally cached image."""
        return [d for d in DRIVERS if self._image_path(d["slug"]) is not None]

    # ------------------------------------------------------------------
    # Commands — main group
    # ------------------------------------------------------------------

    @commands.group(name="f1drivers", aliases=["f1d", "f1guess", "f1pic"])
    @commands.guild_only()
    async def f1drivers(self, ctx: commands.Context):
        """F1 Driver Picture Quiz commands.
        Run `[p]f1drivers setup` once (admin) to download images, then `[p]f1drivers start` to play."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    # ------------------------------------------------------------------
    # Setup — download all images
    # ------------------------------------------------------------------

    @f1drivers.command(name="setup")
    @commands.admin_or_permissions(administrator=True)
    async def f1drivers_setup(self, ctx: commands.Context):
        """Download all driver portraits locally (run this once before playing)."""
        img_dir = self._image_dir()
        img_dir.mkdir(parents=True, exist_ok=True)

        total = len(DRIVERS)
        embed = discord.Embed(
            title="📥  Downloading Driver Portraits",
            description=f"Fetching images for **{total}** drivers from Wikipedia. This might take a minute...",
            colour=0xE8002D,
        )
        embed.set_footer(text="jaffar21")
        status_msg = await ctx.send(embed=embed)

        ok = 0
        failed = []
        skipped = 0

        connector = aiohttp.TCPConnector(limit=15)
        async with aiohttp.ClientSession(
            connector=connector,
            headers={"User-Agent": "F1DriversTriviaBot/1.0 (Red-DiscordBot cog by jaffar21)"},
        ) as session:
            for i, driver in enumerate(DRIVERS, 1):
                slug = driver["slug"]
                # Skip if already downloaded
                if self._image_path(slug) is not None:
                    skipped += 1
                    ok += 1
                    continue

                url = await self._fetch_wiki_image_url(session, driver["wiki"])
                if not url:
                    failed.append(driver["name"])
                    continue

                success = await self._download_image(session, url, slug)
                if success:
                    ok += 1
                else:
                    failed.append(driver["name"])

                # Update status every 10 drivers
                if i % 10 == 0:
                    new_embed = discord.Embed(
                        title="📥  Downloading Driver Portraits",
                        description=(
                            f"Progress: **{i}/{total}**\n"
                            f"✅ Downloaded: {ok}  |  ❌ Failed: {len(failed)}"
                        ),
                        colour=0xE8002D,
                    )
                    new_embed.set_footer(text="jaffar21")
                    try:
                        await status_msg.edit(embed=new_embed)
                    except discord.HTTPException:
                        pass

                await asyncio.sleep(0.1)

        # Final report
        available = len(self._available_drivers())
        result_embed = discord.Embed(
            title="✅  Setup Complete!",
            colour=0x00CC44,
        )
        result_embed.add_field(
            name="Results",
            value=(
                f"**{available}** driver images ready to play\n"
                f"✅ Downloaded: {ok}\n"
                f"⏩ Already cached: {skipped}\n"
                f"❌ Failed: {len(failed)}"
            ),
            inline=False,
        )
        if failed:
            fail_str = ", ".join(failed[:20])
            if len(failed) > 20:
                fail_str += f" (+{len(failed)-20} more)"
            result_embed.add_field(name="Could Not Fetch", value=fail_str, inline=False)
            result_embed.add_field(
                name="Tip",
                value=(
                    "For any driver that failed, try `[p]f1drivers refresh <name>` individually.\n"
                    "To wipe everything and retry from scratch: "
                    "`[p]f1drivers clearimages` then `[p]f1drivers setup`."
                ),
                inline=False,
            )
        result_embed.add_field(
            name="Next Step",
            value="Use `[p]f1drivers start` to start a game!",
            inline=False,
        )
        result_embed.set_footer(text="jaffar21")
        await status_msg.edit(embed=result_embed)

    # ------------------------------------------------------------------
    # Game commands
    # ------------------------------------------------------------------

    @f1drivers.command(name="start")
    @commands.guild_only()
    async def f1drivers_start(self, ctx: commands.Context, target: int = 10):
        """Start an F1 driver photo quiz. First to the target score wins!

        Optional: set a custom target (default 10).
        Example: `[p]f1drivers start 15`
        """
        if self._games.get(ctx.guild.id):
            await ctx.send("A game is already running! Use `[p]f1drivers stop` to end it first.")
            return

        available = self._available_drivers()
        if len(available) < 5:
            await ctx.send(
                "Not enough driver images downloaded. Run `[p]f1drivers setup` first!"
            )
            return

        if target < 1 or target > 50:
            await ctx.send("Point target must be between 1 and 50.")
            return

        pool = list(available)
        random.shuffle(pool)

        game = {
            "channel_id": ctx.channel.id,
            "target": target,
            "scores": {},
            "pool": pool,
            "used_indices": [],
            "current_driver": None,
            "round_task": None,
            "round_number": 0,
            "active": True,
        }
        self._games[ctx.guild.id] = game

        embed = discord.Embed(
            title="🏎️  F1 Driver Quiz — Game On!",
            description=(
                f"**First to {target} points wins!**\n\n"
                f"• I'll post a photo of an F1 driver\n"
                f"• {ROUND_TIME} seconds to guess — just type the name in chat\n"
                f"• First name, last name, full name, nickname — all accepted\n\n"
                "First photo coming up!"
            ),
            colour=0xE8002D,
        )
        embed.set_footer(text="[p]f1drivers stop to end | jaffar21")
        await ctx.send(embed=embed)

        await asyncio.sleep(2)
        await self._next_round(ctx.guild.id, ctx.channel)

    @f1drivers.command(name="stop", aliases=["end", "quit"])
    @commands.guild_only()
    async def f1drivers_stop(self, ctx: commands.Context):
        """Stop the current driver quiz game."""
        if not self._games.get(ctx.guild.id):
            await ctx.send("No game is running right now.")
            return
        await self._end_game(ctx.guild.id, ctx.channel, reason="stopped")

    @f1drivers.command(name="scores", aliases=["score", "leaderboard"])
    @commands.guild_only()
    async def f1drivers_scores(self, ctx: commands.Context):
        """Show the current scores."""
        game = self._games.get(ctx.guild.id)
        if not game:
            await ctx.send("No game is running right now.")
            return
        await ctx.send(embed=self._build_scoreboard(game, ctx.guild))

    @f1drivers.command(name="skip")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def f1drivers_skip(self, ctx: commands.Context):
        """Skip the current driver (moderators only)."""
        game = self._games.get(ctx.guild.id)
        if not game:
            await ctx.send("No game is running right now.")
            return
        if not game.get("current_driver"):
            await ctx.send("No question is active right now.")
            return

        driver_name = game["current_driver"]["name"]
        if game.get("round_task") and not game["round_task"].done():
            game["round_task"].cancel()

        channel = self.bot.get_channel(game["channel_id"])
        await channel.send(f"⏩ Skipped! That was **{driver_name}**.")
        await asyncio.sleep(1)
        await self._next_round(ctx.guild.id, channel)

    @f1drivers.command(name="refresh")
    @commands.admin_or_permissions(administrator=True)
    async def f1drivers_refresh(self, ctx: commands.Context, *, driver_name: str):
        """Re-download the image for a specific driver by name."""
        target = None
        norm_input = _normalize(driver_name)
        for d in DRIVERS:
            if _normalize(d["name"]) == norm_input or norm_input in [_normalize(a) for a in d["answers"]]:
                target = d
                break

        if not target:
            await ctx.send(f"Couldn't find a driver matching `{driver_name}`.")
            return

        # Remove old images
        for ext in ("jpg", "jpeg", "png", "webp"):
            old = self._image_dir() / f"{target['slug']}.{ext}"
            if old.exists():
                old.unlink()

        msg = await ctx.send(f"Re-downloading image for **{target['name']}**...")
        async with aiohttp.ClientSession(
            headers={"User-Agent": "F1DriversTriviaBot/1.0 (Red-DiscordBot cog by jaffar21)"}
        ) as session:
            url = await self._fetch_wiki_image_url(session, target["wiki"])
            if not url:
                await msg.edit(content=f"❌ Couldn't find a Wikipedia image for **{target['name']}**.")
                return
            success = await self._download_image(session, url, target["slug"])
            if success:
                await msg.edit(content=f"✅ Image refreshed for **{target['name']}**!")
            else:
                await msg.edit(content=f"❌ Failed to download image for **{target['name']}**.")

    @f1drivers.command(name="clearimages")
    @commands.admin_or_permissions(administrator=True)
    async def f1drivers_clearimages(self, ctx: commands.Context):
        """Delete all locally cached driver images so setup downloads them fresh.

        Run this if the old setup downloaded wrong or corrupted images,
        then run `[p]f1drivers setup` again.
        """
        img_dir = self._image_dir()
        if not img_dir.exists():
            await ctx.send("No cached images found — nothing to clear.")
            return

        deleted = 0
        for f in img_dir.iterdir():
            if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                f.unlink()
                deleted += 1

        await ctx.send(
            f"🗑️ Cleared **{deleted}** cached driver images.\n"
            f"Run `[p]f1drivers setup` to re-download everything fresh."
        )

    # ------------------------------------------------------------------
    # Game logic
    # ------------------------------------------------------------------

    def _pick_driver(self, game: dict) -> Optional[Dict]:
        pool = game["pool"]
        available = [i for i in range(len(pool)) if i not in game["used_indices"]]
        if not available:
            game["used_indices"] = []
            available = list(range(len(pool)))
        idx = random.choice(available)
        game["used_indices"].append(idx)
        return pool[idx]

    async def _next_round(self, guild_id: int, channel: discord.TextChannel):
        game = self._games.get(guild_id)
        if not game or not game["active"]:
            return

        driver = self._pick_driver(game)
        img_path = self._image_path(driver["slug"])

        # Safety: if somehow no image, pick another
        attempts = 0
        while img_path is None and attempts < 20:
            driver = self._pick_driver(game)
            img_path = self._image_path(driver["slug"])
            attempts += 1

        if img_path is None:
            await channel.send("⚠️ Ran out of driver images! Use `[p]f1drivers setup` to refresh.")
            await self._end_game(guild_id, channel, reason="no_images")
            return

        game["current_driver"] = driver
        game["round_number"] += 1

        file = discord.File(str(img_path), filename=f"driver_{game['round_number']}.{img_path.suffix.lstrip('.')}")
        embed = discord.Embed(
            title=f"❓  Who is this F1 driver? (Round {game['round_number']})",
            description=f"⏱ **{ROUND_TIME} seconds** — type the name in chat!",
            colour=0xFFCC00,
        )
        embed.set_image(url=f"attachment://driver_{game['round_number']}.{img_path.suffix.lstrip('.')}")
        embed.set_footer(text="jaffar21")

        await channel.send(file=file, embed=embed)

        task = asyncio.ensure_future(self._run_round(guild_id, channel))
        game["round_task"] = task

    async def _run_round(self, guild_id: int, channel: discord.TextChannel):
        game = self._games.get(guild_id)
        if not game:
            return

        import time
        end_time = time.monotonic() + ROUND_TIME

        def check(msg: discord.Message) -> bool:
            if msg.channel.id != game["channel_id"]:
                return False
            if msg.author.bot:
                return False
            driver = game.get("current_driver")
            if not driver:
                return False
            return _answers_match(msg.content, driver["answers"])

        try:
            remaining = end_time - __import__("time").monotonic()
            msg = await self.bot.wait_for("message", check=check, timeout=max(0.5, remaining))
        except asyncio.TimeoutError:
            driver = game.get("current_driver")
            name = driver["name"] if driver else "Unknown"
            game["current_driver"] = None
            await channel.send(f"⏰ Time's up! Nobody got it — that was **{name}**.")
            await asyncio.sleep(1.5)
            await self._next_round(guild_id, channel)
            return
        except asyncio.CancelledError:
            return

        driver = game["current_driver"]
        game["current_driver"] = None
        driver_name = driver["name"]

        user_id = msg.author.id
        game["scores"][user_id] = game["scores"].get(user_id, 0) + 1
        score = game["scores"][user_id]

        if score >= game["target"]:
            await channel.send(
                f"✅ **{msg.author.display_name}** got it! That was **{driver_name}**.\n"
                f"They now have **{score} point{'s' if score != 1 else ''}** — "
                f"**{msg.author.display_name} WINS THE GAME! 🏆**"
            )
            await self._end_game(guild_id, channel, winner=msg.author, reason="won")
        else:
            remaining_pts = game["target"] - score
            await channel.send(
                f"✅ **{msg.author.display_name}** got it! That was **{driver_name}**. "
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
        game = self._games.get(guild_id)
        if not game:
            return

        game["active"] = False
        if game.get("round_task") and not game["round_task"].done():
            game["round_task"].cancel()
        del self._games[guild_id]

        if reason == "stopped":
            embed = discord.Embed(title="Game Stopped", description="The driver quiz was stopped.", colour=0x888888)
        elif winner:
            embed = discord.Embed(
                title="🏆 We Have a Winner!",
                description=f"**{winner.display_name}** wins with {game['scores'].get(winner.id, 0)} points!",
                colour=0xFFD700,
            )
        else:
            embed = discord.Embed(title="Game Over", colour=0x888888)

        scores = game["scores"]
        if scores:
            guild = channel.guild
            sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            medals = ["🥇", "🥈", "🥉"]
            lines = []
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

    def cog_unload(self):
        for game in self._games.values():
            task = game.get("round_task")
            if task and not task.done():
                task.cancel()
        self._games.clear()
