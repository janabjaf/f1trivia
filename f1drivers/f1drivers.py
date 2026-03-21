import asyncio
import os
import random
import unicodedata
import re
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

DRIVER_IMAGE_URLS = {
    "max_verstappen": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/52/2024-08-25_Motorsport%2C_Formel_1%2C_Gro%C3%9Fer_Preis_der_Niederlande_2024_STP_3973_by_Stepro_%28medium_crop%29.jpg/500px-2024-08-25_Motorsport%2C_Formel_1%2C_Gro%C3%9Fer_Preis_der_Niederlande_2024_STP_3973_by_Stepro_%28medium_crop%29.jpg",
    "liam_lawson": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/53/Liam_Lawson_at_the_Red_Bull_Fan_Zone_%E2%80%93_Crown_Riverwalk%2C_Melbourne_%28028A7793%29.jpg/500px-Liam_Lawson_at_the_Red_Bull_Fan_Zone_%E2%80%93_Crown_Riverwalk%2C_Melbourne_%28028A7793%29.jpg",
    "lewis_hamilton": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Prime_Minister_Keir_Starmer_meets_Sir_Lewis_Hamilton_%2854566928382%29_%28cropped%29.jpg/500px-Prime_Minister_Keir_Starmer_meets_Sir_Lewis_Hamilton_%2854566928382%29_%28cropped%29.jpg",
    "charles_leclerc": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7b/2024-08-25_Motorsport%2C_Formel_1%2C_Gro%C3%9Fer_Preis_der_Niederlande_2024_STP_3978_by_Stepro_%28cropped2%29.jpg/500px-2024-08-25_Motorsport%2C_Formel_1%2C_Gro%C3%9Fer_Preis_der_Niederlande_2024_STP_3978_by_Stepro_%28cropped2%29.jpg",
    "lando_norris": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/90/2024-08-25_Motorsport%2C_Formel_1%2C_Gro%C3%9Fer_Preis_der_Niederlande_2024_STP_3968_by_Stepro_%28cropped2%29.jpg/500px-2024-08-25_Motorsport%2C_Formel_1%2C_Gro%C3%9Fer_Preis_der_Niederlande_2024_STP_3968_by_Stepro_%28cropped2%29.jpg",
    "oscar_piastri": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e5/2026_Chinese_GP_-_Oscar_Piastri_%28cropped%29_%28cropped%29.jpg/500px-2026_Chinese_GP_-_Oscar_Piastri_%28cropped%29_%28cropped%29.jpg",
    "george_russell": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7f/KingsLeonSilverstne040724_%2828_of_112%29_%2853838006028%29_%28cropped%29.jpg/500px-KingsLeonSilverstne040724_%2828_of_112%29_%2853838006028%29_%28cropped%29.jpg",
    "kimi_antonelli": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f3/Kimi_Antonelli_at_the_2025_US_Grand_Prix_in_Austin%2C_TX_%28cropped%29.jpg/500px-Kimi_Antonelli_at_the_2025_US_Grand_Prix_in_Austin%2C_TX_%28cropped%29.jpg",
    "fernando_alonso": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/33/Fernando_Alonso_racing_at_the_2024_F1_in_Schools_World_Finals_%28cropped%29.jpg/500px-Fernando_Alonso_racing_at_the_2024_F1_in_Schools_World_Finals_%28cropped%29.jpg",
    "lance_stroll": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4e/2025_Japan_GP_-_Aston_Martin_-_Lance_Stroll_-_Fanzone_Stage_%28cropped%29.jpg/500px-2025_Japan_GP_-_Aston_Martin_-_Lance_Stroll_-_Fanzone_Stage_%28cropped%29.jpg",
    "pierre_gasly": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/fd/2022_French_Grand_Prix_%2852279065728%29_%28midcrop%29.png/500px-2022_French_Grand_Prix_%2852279065728%29_%28midcrop%29.png",
    "jack_doohan": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/42/Jack_Doohan_2023.jpg/500px-Jack_Doohan_2023.jpg",
    "alex_albon": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c1/Alex_Albon_%28cropped%29.jpg/500px-Alex_Albon_%28cropped%29.jpg",
    "carlos_sainz": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/ce/Formula1Gabelhofen2022_%2804%29_%28cropped2%29.jpg/500px-Formula1Gabelhofen2022_%2804%29_%28cropped2%29.jpg",
    "esteban_ocon": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2e/Esteban_Ocon_2024_Suzuka_%28cropped%29.jpg/500px-Esteban_Ocon_2024_Suzuka_%28cropped%29.jpg",
    "yuki_tsunoda": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a0/Yuki_Tsunoda_at_the_Melbourne_Walk_during_the_2026_Australian_Grand_Prix_%28028A8096%29.jpg/500px-Yuki_Tsunoda_at_the_Melbourne_Walk_during_the_2026_Australian_Grand_Prix_%28028A8096%29.jpg",
    "isack_hadjar": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/75/Isack_Hadjar_at_the_Melbourne_Walk_during_the_2026_Australian_Grand_Prix_%28028A8753%29_%28cropped%29.jpg/500px-Isack_Hadjar_at_the_Melbourne_Walk_during_the_2026_Australian_Grand_Prix_%28028A8753%29_%28cropped%29.jpg",
    "nico_hulkenberg": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cd/Nico_Hulkenberg_2016_Malaysia.jpg/500px-Nico_Hulkenberg_2016_Malaysia.jpg",
    "gabriel_bortoleto": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/fe/Gabriel_Bortoleto_%28cropped%29.jpg/500px-Gabriel_Bortoleto_%28cropped%29.jpg",
    "oliver_bearman": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9a/2025_Japan_GP_-_Haas_-_Oliver_Bearman_-_Thursday_%28cropped%29.jpg/500px-2025_Japan_GP_-_Haas_-_Oliver_Bearman_-_Thursday_%28cropped%29.jpg",
    "sebastian_vettel": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4c/Sebastian_Vettel_-_2022236172324_2022-08-24_Champions_for_Charity_-_Sven_-_1D_X_MK_II_-_0418_-_B70I2428_%28cropped%29.jpg/500px-Sebastian_Vettel_-_2022236172324_2022-08-24_Champions_for_Charity_-_Sven_-_1D_X_MK_II_-_0418_-_B70I2428_%28cropped%29.jpg",
    "kimi_raikkonen": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/ff/F12019_Schloss_Gabelhofen_%2822%29_%28cropped%29.jpg/500px-F12019_Schloss_Gabelhofen_%2822%29_%28cropped%29.jpg",
    "jenson_button": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0c/Jenson_Button_2024_WEC_Fuji.jpg/500px-Jenson_Button_2024_WEC_Fuji.jpg",
    "nico_rosberg": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/31/Nico_Rosberg_2016.jpg/500px-Nico_Rosberg_2016.jpg",
    "mark_webber": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/16/Mark_Webber_at_the_Melbourne_Walk_during_the_2026_Australian_Grand_Prix_%28028A8720%29.jpg/500px-Mark_Webber_at_the_Melbourne_Walk_during_the_2026_Australian_Grand_Prix_%28028A8720%29.jpg",
    "felipe_massa": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e7/Felipe_Massa.jpg/500px-Felipe_Massa.jpg",
    "rubens_barrichello": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ae/Rubinho.jpg/500px-Rubinho.jpg",
    "michael_schumacher": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8e/Michael_Schumacher_china_2012_rotated.png/500px-Michael_Schumacher_china_2012_rotated.png",
    "mika_hakkinen": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a6/Mika_H%C3%A4kkinen_Champions_for_Charity_2016-07-27.jpg/500px-Mika_H%C3%A4kkinen_Champions_for_Charity_2016-07-27.jpg",
    "david_coulthard": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a4/David_Coulthard_at_the_2025_Adelaide_Grand_Final_Parade_-_12.jpg/500px-David_Coulthard_at_the_2025_Adelaide_Grand_Final_Parade_-_12.jpg",
    "ralf_schumacher": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d1/Ralf_Schumacher%2C_2016.png/500px-Ralf_Schumacher%2C_2016.png",
    "giancarlo_fisichella": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e2/Giancarlo_Fisichella_2012_WEC_Fuji.jpg/500px-Giancarlo_Fisichella_2012_WEC_Fuji.jpg",
    "heinz_harold_frentzen": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8a/Heinz-Harald_Frentzen_a_%28cropped%29.jpg/500px-Heinz-Harald_Frentzen_a_%28cropped%29.jpg",
    "eddie_irvine": "https://upload.wikimedia.org/wikipedia/commons/e/eb/Eddie_Irvine_after_the_1999_Australian_Grand_Prix.jpg",
    "damon_hill": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/31/Damon_Hill_at_the_Atlassian_Williams_Racing_Fan_Zone_of_2026_%28028A8247%29.jpg/500px-Damon_Hill_at_the_Atlassian_Williams_Racing_Fan_Zone_of_2026_%28028A8247%29.jpg",
    "nigel_mansell": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e4/Nigel_Mansell_-_Mexican_Grand_Prix_01_%28cropped%29.jpeg/500px-Nigel_Mansell_-_Mexican_Grand_Prix_01_%28cropped%29.jpeg",
    "alain_prost": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/74/Festival_automobile_international_2015_-_Photocall_-_065_%28cropped3%29.jpg/500px-Festival_automobile_international_2015_-_Photocall_-_065_%28cropped3%29.jpg",
    "ayrton_senna": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/65/Ayrton_Senna_9_%28cropped%29.jpg/500px-Ayrton_Senna_9_%28cropped%29.jpg",
    "nelson_piquet": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5b/Cerimonia_de_entrega_da_medalha_Bras%C3%ADlia_60_anos_-_16.jpg/500px-Cerimonia_de_entrega_da_medalha_Bras%C3%ADlia_60_anos_-_16.jpg",
    "jackie_stewart": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4b/Jackie_Stewart_at_the_2014_WEC_Silverstone_round.jpg/500px-Jackie_Stewart_at_the_2014_WEC_Silverstone_round.jpg",
    "jim_clark": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4f/Jim_Clark_in_1963_%28cropped%29.JPG/500px-Jim_Clark_in_1963_%28cropped%29.JPG",
    "juan_manuel_fangio": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/20/Fangio_in_1955_%28cropped%29.jpg/500px-Fangio_in_1955_%28cropped%29.jpg",
    "jack_brabham": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e7/BrabhamJack1966B.jpg/500px-BrabhamJack1966B.jpg",
    "stirling_moss": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b4/Stirling_Moss.jpg/500px-Stirling_Moss.jpg",
    "graham_hill": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/fc/Graham_Hill_Bestanddeelnr_924-6564.jpg/500px-Graham_Hill_Bestanddeelnr_924-6564.jpg",
    "emerson_fittipaldi": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Emerson_Fittipaldi_in_2020_%28cropped%29.JPG/500px-Emerson_Fittipaldi_in_2020_%28cropped%29.JPG",
    "mario_andretti": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c3/Mario_Andretti_Goodwood_Festival_of_Speed_2021_%28cropped%29.jpg/500px-Mario_Andretti_Goodwood_Festival_of_Speed_2021_%28cropped%29.jpg",
    "gilles_villeneuve": "https://upload.wikimedia.org/wikipedia/en/3/3f/Gilles_Villeneuve_1979_Portrait.jpg",
    "james_hunt": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/12/J._Hunt_in_1977_%28cropped%29.jpg/500px-J._Hunt_in_1977_%28cropped%29.jpg",
    "niki_lauda": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2d/Lauda_at_1982_Dutch_Grand_Prix.jpg/500px-Lauda_at_1982_Dutch_Grand_Prix.jpg",
    "jochen_rindt": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cb/Rindt_at_1970_Dutch_Grand_Prix_%282C%29.jpg/500px-Rindt_at_1970_Dutch_Grand_Prix_%282C%29.jpg",
    "ronnie_peterson": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e2/Peterson_at_1978_Dutch_Grand_Prix.jpg/500px-Peterson_at_1978_Dutch_Grand_Prix.jpg",
    "carlos_reutemann": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/Reutemann_1981.jpg/500px-Reutemann_1981.jpg",
    "alan_jones": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/ce/Jones_alan.JPG/500px-Jones_alan.JPG",
    "keke_rosberg": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3c/Anefo_932-2378_Keke_Rosberg%2C_Zandvoort%2C_03-07-1982_-_Restoration.jpg/500px-Anefo_932-2378_Keke_Rosberg%2C_Zandvoort%2C_03-07-1982_-_Restoration.jpg",
    "rene_arnoux": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6f/Rene_Arnoux_WSR2008_HU.png/500px-Rene_Arnoux_WSR2008_HU.png",
    "didier_pironi": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/86/Pironi_celebrating_at_1982_Dutch_Grand_Prix_%28cropped%29.jpg/500px-Pironi_celebrating_at_1982_Dutch_Grand_Prix_%28cropped%29.jpg",
    "elio_de_angelis": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4e/Anefo_932-2371_Elio_de_Angelis_03.07.1982.jpg/500px-Anefo_932-2371_Elio_de_Angelis_03.07.1982.jpg",
    "riccardo_patrese": "https://upload.wikimedia.org/wikipedia/commons/3/3e/Riccardo_Patrese_in_the_paddock_before_the_1993_British_Grand_Prix_%2833686653515%29_%28Cropped%29.jpg",
    "gerhard_berger": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c9/Gerhard_Berger_1991USA_%28cropped%29.jpg/500px-Gerhard_Berger_1991USA_%28cropped%29.jpg",
    "michele_alboreto": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/76/SCA_0029_MICHELE_ALBORETO_-_Ferrari_F_1-87_-_1987_neg._125_10x15_R_%28cropped%29.JPG/500px-SCA_0029_MICHELE_ALBORETO_-_Ferrari_F_1-87_-_1987_neg._125_10x15_R_%28cropped%29.JPG",
    "derek_warwick": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/Derek_Warwick_Silverstone_2014.JPG/500px-Derek_Warwick_Silverstone_2014.JPG",
    "thierry_boutsen": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6b/Thierry_Boutsen_at_the_2026_Adelaide_Motorsport_Festival_%28028A6537%29.jpg/500px-Thierry_Boutsen_at_the_2026_Adelaide_Motorsport_Festival_%28028A6537%29.jpg",
    "ivan_capelli": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1c/Capelli_1991_%28cropped%29.jpg/500px-Capelli_1991_%28cropped%29.jpg",
    "jean_alesi": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c7/Jean_Alesi%2C_GIMS_2019%2C_Le_Grand-Saconnex_%28GIMS0047%29.jpg/500px-Jean_Alesi%2C_GIMS_2019%2C_Le_Grand-Saconnex_%28GIMS0047%29.jpg",
    "martin_brundle": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/36/Martin_Brundle_2021_%2851591210921%29_%28cropped%29.jpg/500px-Martin_Brundle_2021_%2851591210921%29_%28cropped%29.jpg",
    "johnny_herbert": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/bf/Johnny_Herbert_%2831729263593%29.jpg/500px-Johnny_Herbert_%2831729263593%29.jpg",
    "mika_salo": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c7/Mika_Salo_Le_Mans_2009_cropped.jpg/500px-Mika_Salo_Le_Mans_2009_cropped.jpg",
    "jarno_trulli": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/30/12._Internationale_Sportnacht_Davos_2014_%2815246044859%29_%28cropped%29.jpg/500px-12._Internationale_Sportnacht_Davos_2014_%2815246044859%29_%28cropped%29.jpg",
    "olivier_panis": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e1/Olivier_Panis_%28cropped%29.jpg/500px-Olivier_Panis_%28cropped%29.jpg",
    "alex_wurz": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/ef/Alexander_Wurz_-_2016_24_Hours_of_Le_Mans_-_Pit_Walk_%28cropped%29.jpg/500px-Alexander_Wurz_-_2016_24_Hours_of_Le_Mans_-_Pit_Walk_%28cropped%29.jpg",
    "nick_heidfeld": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2c/Nick_Heidfeld_Goodwood_Festival_of_Speed_2019_%2848242681251%29.jpg/500px-Nick_Heidfeld_Goodwood_Festival_of_Speed_2019_%2848242681251%29.jpg",
    "robert_kubica": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7b/Robert_Kubica_at_Monza_2023.jpg/500px-Robert_Kubica_at_Monza_2023.jpg",
    "heikki_kovalainen": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/29/Effect_20190609_091716.jpg/500px-Effect_20190609_091716.jpg",
    "timo_glock": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/75/2025-04-26_Motorsport%2C_DTM%2C_Oschersleben_STP_2988_%28cropped%29.jpg/500px-2025-04-26_Motorsport%2C_DTM%2C_Oschersleben_STP_2988_%28cropped%29.jpg",
    "vitantonio_liuzzi": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/01/Vitantonio_Liuzzi_2011_Malaysia.jpg/500px-Vitantonio_Liuzzi_2011_Malaysia.jpg",
    "sebastien_buemi": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/05/Ryo_Hirakawa%2C_Brendon_Hartley_%26_Sebastien_Buemi_take_the_podium_for_2nd_in_Hypercar_at_the_2023_Le_Mans_%2853468554280%29_%28cropped%29.jpg/500px-Ryo_Hirakawa%2C_Brendon_Hartley_%26_Sebastien_Buemi_take_the_podium_for_2nd_in_Hypercar_at_the_2023_Le_Mans_%2853468554280%29_%28cropped%29.jpg",
    "jaime_alguersuari": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/84/Jaime_Alguersuari_Canada_2010_cropped.jpg/500px-Jaime_Alguersuari_Canada_2010_cropped.jpg",
    "paul_di_resta": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e8/Paul_di_Resta_2022_%28cropped%29.jpg/500px-Paul_di_Resta_2022_%28cropped%29.jpg",
    "daniel_ricciardo": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c0/Daniel_Ricciardo_January_2024.jpg/500px-Daniel_Ricciardo_January_2024.jpg",
    "pastor_maldonado": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/00/Pastor_Maldonado_2015_Malaysia.jpg/500px-Pastor_Maldonado_2015_Malaysia.jpg",
    "romain_grosjean": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/58/Grosjean_at_2024_Chevrolet_Detroit_Grand_Prix.jpg/500px-Grosjean_at_2024_Chevrolet_Detroit_Grand_Prix.jpg",
    "kamui_kobayashi": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4f/Kamui_Kobayashi_2024_WEC_Fuji_2.jpg/500px-Kamui_Kobayashi_2024_WEC_Fuji_2.jpg",
    "sergio_perez": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/55/2021_US_GP_driver_parade_%28cropped2%29.jpg/500px-2021_US_GP_driver_parade_%28cropped2%29.jpg",
    "valtteri_bottas": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/93/Valtteri_Bottas_at_the_2026_Adelaide_Motorsport_Festival_%28028A7567%29.jpg/500px-Valtteri_Bottas_at_the_2026_Adelaide_Motorsport_Festival_%28028A7567%29.jpg",
    "daniil_kvyat": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/09/Daniil_Kvyat_2024_Suzuka_A2RL_%28cropped%29.jpg/500px-Daniil_Kvyat_2024_Suzuka_A2RL_%28cropped%29.jpg",
    "felipe_nasr": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c8/Piloto_Felipe_Nasr_fala_%C3%A0_imprensa_ap%C3%B3s_encontro_com_Temer_%2828412246304%29_%28cropped%29.jpg/500px-Piloto_Felipe_Nasr_fala_%C3%A0_imprensa_ap%C3%B3s_encontro_com_Temer_%2828412246304%29_%28cropped%29.jpg",
    "will_stevens": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c5/Will_Stevens_2017.jpg/500px-Will_Stevens_2017.jpg",
    "alexander_rossi": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/45/Andretti_Autosport_Visit_180405-F-KS667-0012_%28cropped%29.jpg/500px-Andretti_Autosport_Visit_180405-F-KS667-0012_%28cropped%29.jpg",
    "stoffel_vandoorne": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c6/2023-04-23_Motorsport%2C_ABB_FIA_Formula_E_World_Championship%2C_Berlin_E-Prix_2023_1DX_1774_by_Stepro_%28cropped%29.jpg/500px-2023-04-23_Motorsport%2C_ABB_FIA_Formula_E_World_Championship%2C_Berlin_E-Prix_2023_1DX_1774_by_Stepro_%28cropped%29.jpg",
    "antonio_giovinazzi": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/91/Antonio_Giovinazzi_-_Ferrari_499P_-_Hybrid_during_the_pitwalk_at_the_2023_Le_Mans_%2853468237574%29.jpg/500px-Antonio_Giovinazzi_-_Ferrari_499P_-_Hybrid_during_the_pitwalk_at_the_2023_Le_Mans_%2853468237574%29.jpg",
    "brendon_hartley": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/ca/Brendon_Hartley_2024_WEC_Fuji.jpg/500px-Brendon_Hartley_2024_WEC_Fuji.jpg",
    "sergey_sirotkin": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/fa/Sergey_Sirotkin_Moscow.jpg/500px-Sergey_Sirotkin_Moscow.jpg",
    "vitaly_petrov": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/00/Vitaly_Petrov_2010_Malaysia_%28cropped%29.jpg/500px-Vitaly_Petrov_2010_Malaysia_%28cropped%29.jpg",
    "esteban_gutierrez": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/df/Esteban_Guti%C3%A9rrez_en_el_Gran_Premio_de_Italia_2019_%28cropped%29.jpg/500px-Esteban_Guti%C3%A9rrez_en_el_Gran_Premio_de_Italia_2019_%28cropped%29.jpg",
    "marcus_ericsson": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/87/Marcus_Ericsson_in_2023.jpg/500px-Marcus_Ericsson_in_2023.jpg",
    "kevin_magnussen": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/63/Kevin_Magnussen%2C_2019_Formula_One_Tests_Barcelona_%28cropped%29.jpg/500px-Kevin_Magnussen%2C_2019_Formula_One_Tests_Barcelona_%28cropped%29.jpg",
    "jolyon_palmer": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6c/Jolyon_Palmer_2016_Malaysia.jpg/500px-Jolyon_Palmer_2016_Malaysia.jpg",
    "rio_haryanto": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6a/Rio_Haryanto_2016_paddock.jpg/500px-Rio_Haryanto_2016_paddock.jpg",
    "mick_schumacher": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9e/Mick_Schumacher_2024_WEC_Fuji.jpg/500px-Mick_Schumacher_2024_WEC_Fuji.jpg",
    "nikita_mazepin": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e8/%D0%9D%D0%B8%D0%BA%D0%B8%D1%82%D0%B0_%D0%9C%D0%B0%D0%B7%D0%B5%D0%BF%D0%B8%D0%BD_-_%D0%B8%D0%BD%D1%82%D0%B5%D1%80%D0%B2%D1%8C%D1%8E_-_2019%2C_02.jpg/500px-%D0%9D%D0%B8%D0%BA%D0%B8%D1%82%D0%B0_%D0%9C%D0%B0%D0%B7%D0%B5%D0%BF%D0%B8%D0%BD_-_%D0%B8%D0%BD%D1%82%D0%B5%D1%80%D0%B2%D1%8C%D1%8E_-_2019%2C_02.jpg",
    "nicholas_latifi": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/58/Nicholas_Latifi_at_Singapore_in_2022_%28cropped%29.jpg/500px-Nicholas_Latifi_at_Singapore_in_2022_%28cropped%29.jpg",
    "guanyu_zhou": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8b/Zhou_Guanyu_at_the_Melbourne_Walk_during_the_2026_Australian_Grand_Prix_%28028A7999%29.jpg/500px-Zhou_Guanyu_at_the_Melbourne_Walk_during_the_2026_Australian_Grand_Prix_%28028A7999%29.jpg",
    "nyck_de_vries": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/56/TGR_Nyck_de_Vries_240908.jpg/500px-TGR_Nyck_de_Vries_240908.jpg",
    "logan_sargeant": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/02/Logan_Sargeant_NYC_%28cropped%29.jpg/500px-Logan_Sargeant_NYC_%28cropped%29.jpg",
    "zhou_guanyu": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8b/Zhou_Guanyu_at_the_Melbourne_Walk_during_the_2026_Australian_Grand_Prix_%28028A7999%29.jpg/500px-Zhou_Guanyu_at_the_Melbourne_Walk_during_the_2026_Australian_Grand_Prix_%28028A7999%29.jpg",
    "heinz_frentzen": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8a/Heinz-Harald_Frentzen_a_%28cropped%29.jpg/500px-Heinz-Harald_Frentzen_a_%28cropped%29.jpg",
    "pascal_wehrlein": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0b/2024-05-10_Motorsport%2C_ABB_FIA_Formula_E_World_Championship%2C_Berlin_E-Prix_2024_STP_2554_by_Stepro.jpg/500px-2024-05-10_Motorsport%2C_ABB_FIA_Formula_E_World_Championship%2C_Berlin_E-Prix_2024_STP_2554_by_Stepro.jpg",
    "jean_eric_vergne": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/70/Jean-Eric_Vergne_2024_WEC_Fuji.jpg/500px-Jean-Eric_Vergne_2024_WEC_Fuji.jpg",
    "jules_bianchi": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/03/Jules_Bianchi_2012-1.JPG/500px-Jules_Bianchi_2012-1.JPG",
    "adrian_sutil": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e4/Adrian_Sutil.jpg/500px-Adrian_Sutil.jpg",
    "bruno_senna": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9c/Senna_by_United_Autosports_team_04.jpg/500px-Senna_by_United_Autosports_team_04.jpg",
    "karun_chandhok": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/32/Karun_Chandhok_Goodwood_Festival_of_Speed_2019_%2848242680701%29.jpg/500px-Karun_Chandhok_Goodwood_Festival_of_Speed_2019_%2848242680701%29.jpg",
    "pedro_de_la_rosa": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/fe/Pedro_de_la_Rosa_2010_Malaysia.jpg/500px-Pedro_de_la_Rosa_2010_Malaysia.jpg",
    "narain_karthikeyan": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a6/Narain_Karthikeyan_2011_Malaysia2.jpg/500px-Narain_Karthikeyan_2011_Malaysia2.jpg",
    "scott_speed": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c7/Scott_Speed_Sonoma_2024.jpg/500px-Scott_Speed_Sonoma_2024.jpg",
    "takuma_sato": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d1/Takuma_Sato_%282021%29.jpg/500px-Takuma_Sato_%282021%29.jpg",
    "nelson_piquet_jr": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a5/Nelson_Piquet_Jr._2021.jpg/500px-Nelson_Piquet_Jr._2021.jpg",
    "sebastien_bourdais": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/40/Sebastien_Bourdais_in_2021_%2851221641988%29_%28cropped%29.jpg/500px-Sebastien_Bourdais_in_2021_%2851221641988%29_%28cropped%29.jpg",
    "anthony_davidson": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7f/Anthony_Davidson_Goodwood_Festival_of_Speed_2019_%2848242774922%29.jpg/500px-Anthony_Davidson_Goodwood_Festival_of_Speed_2019_%2848242774922%29.jpg",
    "christian_klien": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/97/Christian_Klien_%2813994163352%29_%28cropped%29.jpg/500px-Christian_Klien_%2813994163352%29_%28cropped%29.jpg",
    "tiago_monteiro": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/ec/Tiago_monteiro_spafrancorchamps2014_%28cropped%29.JPG/500px-Tiago_monteiro_spafrancorchamps2014_%28cropped%29.JPG",
    "christijan_albers": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/04/Christijan_Albers_2006_%28cropped%29.JPG/500px-Christijan_Albers_2006_%28cropped%29.JPG",
    "giedo_van_der_garde": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b7/Giedo_van_der_Garde.jpg/500px-Giedo_van_der_Garde.jpg",
    "max_chilton": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f8/Max_Chilton_2.jpg/500px-Max_Chilton_2.jpg",
    "charles_pic": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/ef/Charles_Pic_Moscow_2013.jpg/500px-Charles_Pic_Moscow_2013.jpg",
    "zsolt_baumgartner": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e3/ChampCar_2007_Baumgartner.jpg/500px-ChampCar_2007_Baumgartner.jpg",
    "enrique_bernoldi": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f7/Enrique_Bernoldi_2007_Curitiba.jpg/500px-Enrique_Bernoldi_2007_Curitiba.jpg",
    "marc_gene": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/61/Marc_Gene_2007_Montjuic.jpg/500px-Marc_Gene_2007_Montjuic.jpg",
    "luca_badoer": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/98/Luca_Badoer_2021_%28cropped%29.jpg/500px-Luca_Badoer_2021_%28cropped%29.jpg",
    "jacques_villeneuve": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9c/Jacques_Villeneuve_August_2011.jpg/500px-Jacques_Villeneuve_August_2011.jpg",
    "juan_pablo_montoya": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2b/DSC1509_%2851683678455%29%28cropped%29.jpg/500px-DSC1509_%2851683678455%29%28cropped%29.jpg",
    "jos_verstappen": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b9/Jos_Verstappen%2C_2006.jpg/500px-Jos_Verstappen%2C_2006.jpg",
    "jan_magnussen": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/03/Jan_Magnussen_%2837535519996%29_%28cropped%29.jpg/500px-Jan_Magnussen_%2837535519996%29_%28cropped%29.jpg",
    "gianni_morbidelli": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/16/Gianni_morbidelli_spafrancorchamps2014.JPG/500px-Gianni_morbidelli_spafrancorchamps2014.JPG",
    "cristiano_da_matta": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a7/Cdmlb06.jpg/500px-Cdmlb06.jpg",
    "ralph_firman": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/82/Ralph_Firman_2008_Super_GT.jpg/500px-Ralph_Firman_2008_Super_GT.jpg",
    "justin_wilson": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2b/Justin_Wilson_2013.jpg/500px-Justin_Wilson_2013.jpg",
    "riccardo_zonta": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/97/Ricardo_Zonta_2007_Curitiba.jpg/500px-Ricardo_Zonta_2007_Curitiba.jpg",
    "michael_andretti": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/07/Michael_Andretti_%2853785910028%29_%28cropped%29.jpg/500px-Michael_Andretti_%2853785910028%29_%28cropped%29.jpg",
    "jody_scheckter": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dc/Jody_Scheckter_during_the_1979_Monaco_Grand_Prix.jpg/500px-Jody_Scheckter_during_the_1979_Monaco_Grand_Prix.jpg",
    "carlos_pace": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a6/Jos%C3%A9_Carlos_Pace%2C_sem_data.tif/lossy-page1-330px-Jos%C3%A9_Carlos_Pace%2C_sem_data.tif.jpg",
    "tom_pryce": "https://upload.wikimedia.org/wikipedia/en/0/04/Tom_Pryce_1974_British_Grand_Prix.jpg",
    "gunnar_nilsson": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/16/1976-07-10_Gunnar_Nilsson_im_BMW_CSL_%28cropped%29.jpg/500px-1976-07-10_Gunnar_Nilsson_im_BMW_CSL_%28cropped%29.jpg",
    "vittorio_brambilla": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/75/Vittorio_Brambilla.jpg/500px-Vittorio_Brambilla.jpg",
    "jo_siffert": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7e/Siffert%2C_Joseph_1968.jpg/500px-Siffert%2C_Joseph_1968.jpg",
    "peter_revson": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7a/Peter_Revson_1973_N%C3%BCrburgring_a_%28cropped%29.jpg/500px-Peter_Revson_1973_N%C3%BCrburgring_a_%28cropped%29.jpg",
    "henri_pescarolo": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/30/PescaroloHenry1973N%C3%BCrb.jpg/500px-PescaroloHenry1973N%C3%BCrb.jpg",
    "rolf_stommelen": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c4/Stommelen%2C_Rolf_am_1972-07-07.jpg/500px-Stommelen%2C_Rolf_am_1972-07-07.jpg",
    "jean_pierre_beltoise": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f1/Jean_Pierre_Beltoise_te_Zandvoort_1968.jpg/500px-Jean_Pierre_Beltoise_te_Zandvoort_1968.jpg",
    "jo_bonnier": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f9/BonnierJo196608.jpg/500px-BonnierJo196608.jpg",
    "jochen_mass": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/34/Mass_at_1982_Dutch_Grand_Prix.jpg/500px-Mass_at_1982_Dutch_Grand_Prix.jpg",
    "jean_pierre_jabouille": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/55/JeanPierreJabouille1975.jpg/500px-JeanPierreJabouille1975.jpg",
    "jean_pierre_jarier": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7e/Jean-Pierre_Jarier_en_1976.jpg/500px-Jean-Pierre_Jarier_en_1976.jpg",
    "pedro_rodriguez": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/68/Pedro_Rodr%C3%ADguez_1968_N%C3%BCrburgring-1_%28cropped%29.jpg/500px-Pedro_Rodr%C3%ADguez_1968_N%C3%BCrburgring-1_%28cropped%29.jpg",
    "hans_stuck": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cf/HansJoachimStuck2008.jpg/500px-HansJoachimStuck2008.jpg",
    "peter_gethin": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3f/Peter_Gethin%2C_Bestanddeelnr_924-6614_%28cropped2%29.jpg/500px-Peter_Gethin%2C_Bestanddeelnr_924-6614_%28cropped2%29.jpg",
    "john_surtees": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c3/John_Surtees.JPG/500px-John_Surtees.JPG",
    "dan_gurney": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b8/Dan_Gurney_%281970%29.jpg/500px-Dan_Gurney_%281970%29.jpg",
    "bruce_mclaren": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a0/McLarenBruce.jpg/500px-McLarenBruce.jpg",
    "lorenzo_bandini": "https://upload.wikimedia.org/wikipedia/commons/d/d8/Bandini1966cropped.jpg",
    "richie_ginther": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5c/Richie_Ginther_and_Roger_Penske%2C_1964_%28cropped%29.jpg/500px-Richie_Ginther_and_Roger_Penske%2C_1964_%28cropped%29.jpg",
    "innes_ireland": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8c/Innes_Ireland.jpg/500px-Innes_Ireland.jpg",
    "mike_spence": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/50/Mike_Spence_%28cropped%29.jpg/500px-Mike_Spence_%28cropped%29.jpg",
    "piers_courage": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/32/Piers_Courage_1968_N%C3%BCrburgring.JPG/500px-Piers_Courage_1968_N%C3%BCrburgring.JPG",
    "tony_brooks": "https://upload.wikimedia.org/wikipedia/en/8/8e/Tony_Brooks_1958_German_Grand_Prix.jpg",
    "ludovico_scarfiotti": "https://upload.wikimedia.org/wikipedia/commons/b/b7/Ludivico_Scarfiotti_1966_N%C3%BCrburgring.jpg",
    "mike_hailwood": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f0/Mike_Hailwood.jpg/500px-Mike_Hailwood.jpg",
    "alberto_ascari": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/69/Ascari_last_photo_in_car.jpg/500px-Ascari_last_photo_in_car.jpg",
    "nino_farina": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d0/Giuseppe_Farina_-_El_Gr%C3%A1fico_1750.jpg/500px-Giuseppe_Farina_-_El_Gr%C3%A1fico_1750.jpg",
    "mike_hawthorn": "https://upload.wikimedia.org/wikipedia/en/9/99/Mike_Hawthorn.jpg",
    "phil_hill": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/84/Phil_Hill_1991_USA_%28cropped%29.jpg/500px-Phil_Hill_1991_USA_%28cropped%29.jpg",
    "peter_collins": "https://upload.wikimedia.org/wikipedia/en/5/5e/Peter_Collins_car_racer.jpg",
    "wolfgang_von_trips": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f1/Wolfgang_von_Trips_in_1957.JPG/500px-Wolfgang_von_Trips_in_1957.JPG",
    "luigi_musso": "https://upload.wikimedia.org/wikipedia/commons/8/8b/Luigi_Musso.jpg",
    "piero_taruffi": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8e/Piero_Taruffi.jpg/500px-Piero_Taruffi.jpg",
    "jose_froilan_gonzalez": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/51/Jos%C3%A9_Froil%C3%A1n_Gonz%C3%A1lez_1950.jpg/500px-Jos%C3%A9_Froil%C3%A1n_Gonz%C3%A1lez_1950.jpg",
    "maurice_trintignant": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/35/Maurice_Trintignant_-_El_Gr%C3%A1fico_1801.jpg/500px-Maurice_Trintignant_-_El_Gr%C3%A1fico_1801.jpg",
    "harry_schell": "https://upload.wikimedia.org/wikipedia/en/3/32/Harry_Schell_Sebring_1959.jpg",
    "eugenio_castellotti": "https://upload.wikimedia.org/wikipedia/commons/7/75/Eugenio_Castellotti.jpg",
    "david_purley": "https://upload.wikimedia.org/wikipedia/en/thumb/e/e9/Davidpurley.jpg/500px-Davidpurley.jpg",
    "david_brabham": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/08/David_Brabham_at_the_2026_Adelaide_Motorsport_Festival_%28028A6665%29.jpg/500px-David_Brabham_at_the_2026_Adelaide_Motorsport_Festival_%28028A6665%29.jpg",
    "martin_donnelly": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/97/Martin_Donnelly_at_the_2026_Adelaide_Motorsport_Festival_%28028A6545%29.jpg/500px-Martin_Donnelly_at_the_2026_Adelaide_Motorsport_Festival_%28028A6545%29.jpg",
    "stefan_johansson": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/67/Stefan_Johansson_at_the_2026_Adelaide_Motorsport_Festival_%28028A6525%29.jpg/500px-Stefan_Johansson_at_the_2026_Adelaide_Motorsport_Festival_%28028A6525%29.jpg",
    "pierluigi_martini": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/58/Pierluigi_Martini_in_2016.jpg/500px-Pierluigi_Martini_in_2016.jpg",
    "andrea_de_cesaris": "https://upload.wikimedia.org/wikipedia/commons/2/22/Andrea_De_Cesaris_1982.jpg",
    "eddie_cheever": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/87/Eddie_Cheever_Jr_2009_Indy_500_Second_Qual_Day.JPG/500px-Eddie_Cheever_Jr_2009_Indy_500_Second_Qual_Day.JPG",
    "bertrand_gachot": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/08/Bertrand_Gachot_-_1991_US_GP.jpg/500px-Bertrand_Gachot_-_1991_US_GP.jpg",
    "eric_comas": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d2/Comas_lm2005.jpg/500px-Comas_lm2005.jpg",
    "aguri_suzuki": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ac/Suzuki_Sepang_25.png/500px-Suzuki_Sepang_25.png",
    "ukyo_katayama": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6e/Ukyo_Katayama_2008.jpg/500px-Ukyo_Katayama_2008.jpg",
    "mark_blundell": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/99/Mark_Blundell_portrait_2011_%28cropped%29.jpg/500px-Mark_Blundell_portrait_2011_%28cropped%29.jpg",
    "christian_fittipaldi": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f9/Christian_Fittipaldi_2006_Curitiba.jpg/500px-Christian_Fittipaldi_2006_Curitiba.jpg",
    "karl_wendlinger": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/ef/GTS_class_winners_%2810th_overall%29_-_Karl_Wendlinger_-_Chrysler_Viper_GTS-R_-_on_the_podium_at_the_1999_Le_Mans_%2851897678180%29_%28cropped%29.jpg/500px-GTS_class_winners_%2810th_overall%29_-_Karl_Wendlinger_-_Chrysler_Viper_GTS-R_-_on_the_podium_at_the_1999_Le_Mans_%2851897678180%29_%28cropped%29.jpg",
    "jj_lehto": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3f/JJ_Lehto_%28Petit_Le_Mans%2C_2004%29.jpg/500px-JJ_Lehto_%28Petit_Le_Mans%2C_2004%29.jpg",
    "mika_salo2": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c7/Mika_Salo_Le_Mans_2009_cropped.jpg/500px-Mika_Salo_Le_Mans_2009_cropped.jpg",
    "pedro_lamy": "https://upload.wikimedia.org/wikipedia/commons/7/7f/Pedro_Lamy_Le_Mans_drivers_parade_2011_crop.jpg",
    "olivier_grouillard": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/af/Andy_Wallace_%26_Olivier_Grouillard_on_the_podium_at_the_Norwich_Union_Empire_Trophy%2C_Silverstone_4_Hrs_1995_%2849890621322%29_%28cropped%29.jpg/500px-Andy_Wallace_%26_Olivier_Grouillard_on_the_podium_at_the_Norwich_Union_Empire_Trophy%2C_Silverstone_4_Hrs_1995_%2849890621322%29_%28cropped%29.jpg",
    "emanuele_pirro": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b3/Emanuele_Pirro_2012_WEC_Fuji_2_%28cropped%29.jpg/500px-Emanuele_Pirro_2012_WEC_Fuji_2_%28cropped%29.jpg",
    "mauricio_gugelmin": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/ea/Gugelmin_%28cropped%29.jpg/500px-Gugelmin_%28cropped%29.jpg",
    "roberto_moreno": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f4/Roberto_Bud_suite_97.tif/lossy-page1-330px-Roberto_Bud_suite_97.tif.jpg",
    "Alessandro_zanardi": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/52/Alex_Zanardi_2019.jpg/500px-Alex_Zanardi_2019.jpg",
    "john_watson": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3d/Watson_at_1982_Dutch_Grand_Prix_%28cropped%29.jpg/500px-Watson_at_1982_Dutch_Grand_Prix_%28cropped%29.jpg",
    "patrick_tambay": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d1/Zandvoort_circuit_De_striptekenaar_Graton_in_de_pits%2C_NL-HlmNHA_54005237_-_Patrick_Tambay_%28cropped%29.JPG/500px-Zandvoort_circuit_De_striptekenaar_Graton_in_de_pits%2C_NL-HlmNHA_54005237_-_Patrick_Tambay_%28cropped%29.JPG",
    "patrick_depailler": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4e/PatrickDepailler-ar.jpg/500px-PatrickDepailler-ar.jpg",
    "jacques_laffite": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Jacques_Laffite_2015.jpg/500px-Jacques_Laffite_2015.jpg",
    "stefan_bellof": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e1/Stefan_Bellof_7508-cropped.jpg/500px-Stefan_Bellof_7508-cropped.jpg",
    "marc_surer": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3e/Marc_Surer_1982.jpg/500px-Marc_Surer_1982.jpg",
    "manfred_winkelhock": "https://upload.wikimedia.org/wikipedia/en/9/98/Manfred_Winkelhock_1984.png",
    "wilson_fittipaldi": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a9/Wilson_Fittipaldi_J%C3%BAnior_2017.jpg/500px-Wilson_Fittipaldi_J%C3%BAnior_2017.jpg",
    "philippe_streiff": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c7/Festival_automobile_international_2014_-_Photocall_-_019.jpg/500px-Festival_automobile_international_2014_-_Photocall_-_019.jpg",
    "jonathan_palmer": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2b/Jonathan_Palmer_Profile.jpg/500px-Jonathan_Palmer_Profile.jpg",
    "denny_hulme": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/92/HulmeDenis196508_%28cropped%29.jpg/500px-HulmeDenis196508_%28cropped%29.jpg",
    "clay_regazzoni": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e7/Anefo_924-6609_Clay_Reggazoni%2C_Catherine_Blaton%2C_Jacky_Ickx_Zandvoort_18_06_1971_-_Cropped.jpg/500px-Anefo_924-6609_Clay_Reggazoni%2C_Catherine_Blaton%2C_Jacky_Ickx_Zandvoort_18_06_1971_-_Cropped.jpg",
    "chris_amon": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7b/AmonChris19730706.jpg/500px-AmonChris19730706.jpg",
    "jacky_ickx": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/19/Jacky_Ickx_Portr%C3%A4t_Mille_Miglia_2018.jpg/500px-Jacky_Ickx_Portr%C3%A4t_Mille_Miglia_2018.jpg",
    "francois_cevert": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d4/Francois_Cevert_1973.jpg/500px-Francois_Cevert_1973.jpg",
}
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

    async def _download_image(self, session: aiohttp.ClientSession, url: str, slug: str) -> bool:
        """Download an image from url and save it locally.
        Automatically retries on HTTP 429 (rate limit), respecting Retry-After header.
        Returns True on success."""
        url_path = url.split("?")[0]
        ext = url_path.rsplit(".", 1)[-1].lower()
        if ext not in ("jpg", "jpeg", "png", "webp"):
            ext = "jpg"

        dest = self._image_dir() / f"{slug}.{ext}"
        backoff = 5.0
        for attempt in range(4):
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 429:
                        retry_after = float(resp.headers.get("Retry-After", backoff))
                        await asyncio.sleep(retry_after)
                        backoff = min(backoff * 2, 60.0)
                        continue
                    if resp.status != 200:
                        return False
                    data = await resp.read()
                    if len(data) < 1000:
                        return False
                    dest.write_bytes(data)
                    return True
            except Exception:
                if attempt < 3:
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 60.0)
        return False

    def _available_drivers(self) -> List[Dict]:
        """Return only drivers who have a locally cached image."""
        return [d for d in DRIVERS if self._image_path(d["slug"]) is not None]

    # ------------------------------------------------------------------
    # Commands — main group
    # ------------------------------------------------------------------

    @commands.group(name="f1drivers", aliases=["f1d", "f1guess", "f1pic"], invoke_without_command=True)
    @commands.guild_only()
    async def f1drivers(self, ctx: commands.Context):
        """F1 Driver Picture Quiz commands.
        Run `[p]f1drivers setup` once (admin) to download images, then `[p]f1drivers start` to play."""
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
            description=(
                f"Downloading portraits for **{total}** drivers.\n"
                "This takes **2–4 minutes** — please be patient and don't run it again!"
            ),
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

                # Use the pre-resolved direct image URL — no API lookup needed
                url = DRIVER_IMAGE_URLS.get(slug)
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

                await asyncio.sleep(0.5)

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

    @f1drivers.command(name="clearimages")
    @commands.admin_or_permissions(administrator=True)
    async def f1drivers_clearimages(self, ctx: commands.Context):
        """Delete all locally cached driver images so setup re-downloads them fresh.

        Use this followed by `[p]f1drivers setup` to get a clean install.
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
