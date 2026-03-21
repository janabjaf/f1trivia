import asyncio
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
        if norm_input == _normalize(ans):
            return True
    return False


# ---------------------------------------------------------------------------
# Player roster — well-known players only
# ---------------------------------------------------------------------------

PLAYERS: List[Dict] = [
    # ── Current Stars ─────────────────────────────────────────────────────
    {"slug": "lebron_james",            "name": "LeBron James",            "answers": ["lebron", "lebron james", "king james", "lbj", "the king"]},
    {"slug": "stephen_curry",           "name": "Stephen Curry",           "answers": ["steph", "curry", "stephen curry", "steph curry", "chef curry"]},
    {"slug": "kevin_durant",            "name": "Kevin Durant",            "answers": ["durant", "kd", "kevin durant", "slim reaper"]},
    {"slug": "giannis_antetokounmpo",   "name": "Giannis Antetokounmpo",   "answers": ["giannis", "greek freak", "giannis antetokounmpo", "antetokounmpo"]},
    {"slug": "kawhi_leonard",           "name": "Kawhi Leonard",           "answers": ["kawhi", "leonard", "the claw", "kawhi leonard"]},
    {"slug": "james_harden",            "name": "James Harden",            "answers": ["harden", "james harden", "the beard"]},
    {"slug": "russell_westbrook",       "name": "Russell Westbrook",       "answers": ["westbrook", "russ", "russell westbrook", "brodie"]},
    {"slug": "anthony_davis",           "name": "Anthony Davis",           "answers": ["anthony davis", "ad", "davis", "the brow", "unibrow"]},
    {"slug": "kyrie_irving",            "name": "Kyrie Irving",            "answers": ["kyrie", "irving", "kyrie irving", "uncle drew"]},
    {"slug": "damian_lillard",          "name": "Damian Lillard",          "answers": ["lillard", "dame", "damian lillard", "dame dolla"]},
    {"slug": "joel_embiid",             "name": "Joel Embiid",             "answers": ["embiid", "joel embiid", "the process", "jojo"]},
    {"slug": "nikola_jokic",            "name": "Nikola Jokić",            "answers": ["jokic", "nikola jokic", "the joker", "nikola"]},
    {"slug": "luka_doncic",             "name": "Luka Dončić",             "answers": ["luka", "doncic", "luka doncic", "luka magic"]},
    {"slug": "ja_morant",               "name": "Ja Morant",               "answers": ["ja", "morant", "ja morant"]},
    {"slug": "zion_williamson",         "name": "Zion Williamson",         "answers": ["zion", "williamson", "zion williamson"]},
    {"slug": "trae_young",              "name": "Trae Young",              "answers": ["trae", "trae young", "ice trae"]},
    {"slug": "devin_booker",            "name": "Devin Booker",            "answers": ["booker", "book", "devin booker"]},
    {"slug": "paul_george",             "name": "Paul George",             "answers": ["paul george", "pg", "pg13"]},
    {"slug": "jimmy_butler",            "name": "Jimmy Butler",            "answers": ["butler", "jimmy butler", "jimmy buckets"]},
    {"slug": "jayson_tatum",            "name": "Jayson Tatum",            "answers": ["tatum", "jayson tatum", "jt"]},
    {"slug": "jaylen_brown",            "name": "Jaylen Brown",            "answers": ["jaylen brown", "jaylen", "jb"]},
    {"slug": "bam_adebayo",             "name": "Bam Adebayo",             "answers": ["bam", "adebayo", "bam adebayo"]},
    {"slug": "donovan_mitchell",        "name": "Donovan Mitchell",        "answers": ["donovan mitchell", "mitchell", "spida"]},
    {"slug": "deaaron_fox",             "name": "De'Aaron Fox",            "answers": ["fox", "de'aaron fox", "deaaron fox", "swipa"]},
    {"slug": "shai_gilgeous_alexander", "name": "Shai Gilgeous-Alexander", "answers": ["sga", "shai", "shai gilgeous-alexander", "shai gilgeous alexander"]},
    {"slug": "karl_anthony_towns",      "name": "Karl-Anthony Towns",      "answers": ["kat", "towns", "karl-anthony towns", "karl anthony towns"]},
    {"slug": "draymond_green",          "name": "Draymond Green",          "answers": ["draymond", "green", "draymond green"]},
    {"slug": "klay_thompson",           "name": "Klay Thompson",           "answers": ["klay", "thompson", "klay thompson"]},
    {"slug": "chris_paul",              "name": "Chris Paul",              "answers": ["chris paul", "cp3", "point god"]},
    {"slug": "tyrese_haliburton",       "name": "Tyrese Haliburton",       "answers": ["haliburton", "tyrese haliburton", "tyrese", "hali"]},
    {"slug": "lamelo_ball",             "name": "LaMelo Ball",             "answers": ["lamelo", "lamelo ball", "melo ball"]},
    {"slug": "anthony_edwards",         "name": "Anthony Edwards",         "answers": ["ant", "anthony edwards", "edwards", "ant man"]},
    {"slug": "cade_cunningham",         "name": "Cade Cunningham",         "answers": ["cade", "cunningham", "cade cunningham"]},
    {"slug": "victor_wembanyama",       "name": "Victor Wembanyama",       "answers": ["wemby", "wembanyama", "victor wembanyama"]},
    {"slug": "paolo_banchero",          "name": "Paolo Banchero",          "answers": ["banchero", "paolo banchero", "paolo"]},
    {"slug": "jaren_jackson_jr",        "name": "Jaren Jackson Jr.",       "answers": ["jaren jackson", "jjj", "jaren jackson jr"]},
    {"slug": "brandon_ingram",          "name": "Brandon Ingram",          "answers": ["ingram", "brandon ingram", "bi"]},
    {"slug": "julius_randle",           "name": "Julius Randle",           "answers": ["randle", "julius randle"]},
    {"slug": "rudy_gobert",             "name": "Rudy Gobert",             "answers": ["gobert", "rudy gobert", "stifle tower"]},
    {"slug": "jamal_murray",            "name": "Jamal Murray",            "answers": ["murray", "jamal murray", "blue arrow"]},
    {"slug": "pascal_siakam",           "name": "Pascal Siakam",           "answers": ["siakam", "pascal siakam", "spicy p"]},
    {"slug": "bradley_beal",            "name": "Bradley Beal",            "answers": ["beal", "bradley beal", "bb3"]},
    {"slug": "jrue_holiday",            "name": "Jrue Holiday",            "answers": ["holiday", "jrue holiday", "jrue"]},
    {"slug": "zach_lavine",             "name": "Zach LaVine",             "answers": ["lavine", "zach lavine"]},
    {"slug": "kemba_walker",            "name": "Kemba Walker",            "answers": ["kemba", "walker", "kemba walker"]},
    {"slug": "john_wall",               "name": "John Wall",               "answers": ["wall", "john wall"]},
    {"slug": "kyle_lowry",              "name": "Kyle Lowry",              "answers": ["lowry", "kyle lowry"]},
    {"slug": "deron_williams",          "name": "Deron Williams",          "answers": ["deron williams", "deron", "d-will"]},
    {"slug": "rajon_rondo",             "name": "Rajon Rondo",             "answers": ["rondo", "rajon rondo"]},
    {"slug": "marc_gasol",              "name": "Marc Gasol",              "answers": ["marc gasol", "marc", "big spain"]},
    {"slug": "demarcus_cousins",        "name": "DeMarcus Cousins",        "answers": ["cousins", "demarcus cousins", "boogie"]},
    {"slug": "andre_iguodala",          "name": "Andre Iguodala",          "answers": ["iguodala", "andre iguodala", "iggy"]},
    {"slug": "kevin_love",              "name": "Kevin Love",              "answers": ["love", "kevin love"]},

    # ── 2000s–2010s Era ───────────────────────────────────────────────────
    {"slug": "dwyane_wade",             "name": "Dwyane Wade",             "answers": ["wade", "dwyane wade", "d wade", "flash"]},
    {"slug": "carmelo_anthony",         "name": "Carmelo Anthony",         "answers": ["carmelo", "melo", "carmelo anthony"]},
    {"slug": "chris_bosh",              "name": "Chris Bosh",              "answers": ["bosh", "chris bosh"]},
    {"slug": "dwight_howard",           "name": "Dwight Howard",           "answers": ["dwight", "howard", "dwight howard", "superman", "d12"]},
    {"slug": "pau_gasol",               "name": "Pau Gasol",               "answers": ["pau", "gasol", "pau gasol"]},
    {"slug": "tony_parker",             "name": "Tony Parker",             "answers": ["tony parker", "parker"]},
    {"slug": "manu_ginobili",           "name": "Manu Ginóbili",           "answers": ["manu", "ginobili", "manu ginobili"]},
    {"slug": "derrick_rose",            "name": "Derrick Rose",            "answers": ["rose", "derrick rose", "d rose"]},
    {"slug": "blake_griffin",           "name": "Blake Griffin",           "answers": ["blake", "griffin", "blake griffin"]},
    {"slug": "yao_ming",                "name": "Yao Ming",                "answers": ["yao", "yao ming"]},
    {"slug": "chauncey_billups",        "name": "Chauncey Billups",        "answers": ["billups", "chauncey", "mr big shot", "chauncey billups"]},
    {"slug": "vince_carter",            "name": "Vince Carter",            "answers": ["vince", "carter", "vince carter", "vinsanity"]},
    {"slug": "tracy_mcgrady",           "name": "Tracy McGrady",           "answers": ["tmac", "tracy mcgrady", "mcgrady"]},
    {"slug": "grant_hill",              "name": "Grant Hill",              "answers": ["grant hill", "hill", "grant"]},
    {"slug": "anfernee_hardaway",       "name": "Anfernee Hardaway",       "answers": ["penny", "hardaway", "penny hardaway", "anfernee"]},
    {"slug": "amare_stoudemire",        "name": "Amar'e Stoudemire",       "answers": ["amare", "stoudemire", "amar'e stoudemire", "stat"]},
    {"slug": "gilbert_arenas",          "name": "Gilbert Arenas",          "answers": ["arenas", "gilbert arenas", "agent zero", "hibachi"]},
    {"slug": "stephon_marbury",         "name": "Stephon Marbury",         "answers": ["marbury", "starbury", "stephon marbury"]},
    {"slug": "lamar_odom",              "name": "Lamar Odom",              "answers": ["lamar", "odom", "lamar odom"]},
    {"slug": "baron_davis",             "name": "Baron Davis",             "answers": ["baron davis", "boom dizzle", "baron"]},
    {"slug": "shawn_kemp",              "name": "Shawn Kemp",              "answers": ["kemp", "shawn kemp", "reign man"]},
    {"slug": "peja_stojakovic",         "name": "Peja Stojaković",         "answers": ["peja", "stojakovic", "peja stojakovic"]},
    {"slug": "antawn_jamison",          "name": "Antawn Jamison",          "answers": ["jamison", "antawn jamison"]},
    {"slug": "sam_cassell",             "name": "Sam Cassell",             "answers": ["cassell", "sam cassell"]},

    # ── 90s Legends ───────────────────────────────────────────────────────
    {"slug": "allen_iverson",           "name": "Allen Iverson",           "answers": ["iverson", "ai", "allen iverson", "the answer"]},
    {"slug": "ray_allen",               "name": "Ray Allen",               "answers": ["ray allen", "jesus shuttlesworth"]},
    {"slug": "paul_pierce",             "name": "Paul Pierce",             "answers": ["paul pierce", "pierce", "the truth"]},
    {"slug": "kevin_garnett",           "name": "Kevin Garnett",           "answers": ["garnett", "kg", "kevin garnett", "the big ticket"]},
    {"slug": "dirk_nowitzki",           "name": "Dirk Nowitzki",           "answers": ["dirk", "nowitzki", "dirk nowitzki"]},
    {"slug": "steve_nash",              "name": "Steve Nash",              "answers": ["nash", "steve nash"]},
    {"slug": "jason_kidd",              "name": "Jason Kidd",              "answers": ["kidd", "jason kidd"]},
    {"slug": "gary_payton",             "name": "Gary Payton",             "answers": ["gary payton", "payton", "the glove"]},
    {"slug": "reggie_miller",           "name": "Reggie Miller",           "answers": ["reggie miller", "miller", "reggie"]},
    {"slug": "alonzo_mourning",         "name": "Alonzo Mourning",         "answers": ["mourning", "alonzo mourning", "zo"]},
    {"slug": "scottie_pippen",          "name": "Scottie Pippen",          "answers": ["pippen", "scottie pippen", "scottie"]},
    {"slug": "dennis_rodman",           "name": "Dennis Rodman",           "answers": ["rodman", "dennis rodman", "the worm"]},
    {"slug": "dominique_wilkins",       "name": "Dominique Wilkins",       "answers": ["dominique", "wilkins", "dominique wilkins", "human highlight"]},
    {"slug": "isiah_thomas",            "name": "Isiah Thomas",            "answers": ["isiah", "isiah thomas", "zeke"]},
    {"slug": "clyde_drexler",           "name": "Clyde Drexler",           "answers": ["drexler", "clyde drexler", "clyde the glide"]},
    {"slug": "david_robinson",          "name": "David Robinson",          "answers": ["robinson", "david robinson", "the admiral"]},
    {"slug": "hakeem_olajuwon",         "name": "Hakeem Olajuwon",         "answers": ["hakeem", "olajuwon", "hakeem olajuwon", "the dream", "akeem"]},
    {"slug": "charles_barkley",         "name": "Charles Barkley",         "answers": ["barkley", "charles barkley", "sir charles"]},
    {"slug": "patrick_ewing",           "name": "Patrick Ewing",           "answers": ["ewing", "patrick ewing"]},
    {"slug": "john_stockton",           "name": "John Stockton",           "answers": ["stockton", "john stockton"]},
    {"slug": "karl_malone",             "name": "Karl Malone",             "answers": ["karl malone", "malone", "the mailman"]},
    {"slug": "joe_dumars",              "name": "Joe Dumars",              "answers": ["dumars", "joe dumars"]},
    {"slug": "mitch_richmond",          "name": "Mitch Richmond",          "answers": ["richmond", "mitch richmond", "the rock"]},
    {"slug": "latrell_sprewell",        "name": "Latrell Sprewell",        "answers": ["sprewell", "latrell sprewell", "spree"]},
    {"slug": "glen_rice",               "name": "Glen Rice",               "answers": ["glen rice", "rice"]},

    # ── All-Time Legends ──────────────────────────────────────────────────
    {"slug": "michael_jordan",          "name": "Michael Jordan",          "answers": ["jordan", "mj", "michael jordan", "air jordan", "his airness"]},
    {"slug": "kobe_bryant",             "name": "Kobe Bryant",             "answers": ["kobe", "bryant", "kobe bryant", "black mamba", "mamba"]},
    {"slug": "shaquille_oneal",         "name": "Shaquille O'Neal",        "answers": ["shaq", "shaquille oneal", "shaquille o'neal", "diesel", "shaquille"]},
    {"slug": "tim_duncan",              "name": "Tim Duncan",              "answers": ["tim duncan", "duncan", "big fundamental"]},
    {"slug": "magic_johnson",           "name": "Magic Johnson",           "answers": ["magic", "magic johnson", "earvin johnson"]},
    {"slug": "larry_bird",              "name": "Larry Bird",              "answers": ["bird", "larry bird", "larry legend"]},
    {"slug": "kareem_abdul_jabbar",     "name": "Kareem Abdul-Jabbar",     "answers": ["kareem", "jabbar", "kareem abdul jabbar", "kareem abdul-jabbar"]},
    {"slug": "julius_erving",           "name": "Julius Erving",           "answers": ["dr j", "julius erving", "erving", "the doctor", "doc"]},
    {"slug": "moses_malone",            "name": "Moses Malone",            "answers": ["moses", "malone", "moses malone"]},
    {"slug": "oscar_robertson",         "name": "Oscar Robertson",         "answers": ["oscar", "robertson", "oscar robertson", "the big o"]},
    {"slug": "jerry_west",              "name": "Jerry West",              "answers": ["jerry west", "west", "the logo"]},
    {"slug": "elgin_baylor",            "name": "Elgin Baylor",            "answers": ["baylor", "elgin baylor"]},
    {"slug": "bill_russell",            "name": "Bill Russell",            "answers": ["bill russell", "russell"]},
    {"slug": "wilt_chamberlain",        "name": "Wilt Chamberlain",        "answers": ["wilt", "chamberlain", "wilt chamberlain", "wilt the stilt"]},
    {"slug": "pete_maravich",           "name": "Pete Maravich",           "answers": ["maravich", "pistol pete", "pete maravich", "pistol"]},
    {"slug": "george_gervin",           "name": "George Gervin",           "answers": ["gervin", "george gervin", "the iceman", "iceman"]},
    {"slug": "nate_archibald",          "name": "Nate Archibald",          "answers": ["archibald", "nate archibald", "tiny", "tiny archibald"]},
    {"slug": "bob_mcadoo",              "name": "Bob McAdoo",              "answers": ["mcadoo", "bob mcadoo"]},
    {"slug": "elvin_hayes",             "name": "Elvin Hayes",             "answers": ["hayes", "elvin hayes", "the big e"]},
    {"slug": "bob_cousy",               "name": "Bob Cousy",               "answers": ["cousy", "bob cousy", "the cooz"]},
    {"slug": "rick_barry",              "name": "Rick Barry",              "answers": ["barry", "rick barry"]},
    {"slug": "dave_cowens",             "name": "Dave Cowens",             "answers": ["cowens", "dave cowens"]},
    {"slug": "bill_walton",             "name": "Bill Walton",             "answers": ["walton", "bill walton"]},
    {"slug": "walt_frazier",            "name": "Walt Frazier",            "answers": ["frazier", "walt frazier", "clyde frazier"]},
    {"slug": "george_mikan",            "name": "George Mikan",            "answers": ["mikan", "george mikan", "mr basketball"]},
    {"slug": "bob_pettit",              "name": "Bob Pettit",              "answers": ["pettit", "bob pettit"]},
    {"slug": "willis_reed",             "name": "Willis Reed",             "answers": ["reed", "willis reed"]},
    {"slug": "dan_issel",               "name": "Dan Issel",               "answers": ["issel", "dan issel", "the horse"]},
    {"slug": "artis_gilmore",           "name": "Artis Gilmore",           "answers": ["gilmore", "artis gilmore", "a-train"]},
    {"slug": "nate_archibald2",         "name": "Nate Archibald",          "answers": []},
]

# Strip duplicate slugs and entries with empty answers
_seen: set = set()
_deduped: List[Dict] = []
for _p in PLAYERS:
    if _p["slug"] not in _seen and _p["answers"]:
        _seen.add(_p["slug"])
        _deduped.append(_p)
PLAYERS = _deduped

# ---------------------------------------------------------------------------
# Image URLs — all Wikipedia (consistent with f1drivers approach)
# Uses Special:FilePath which redirects to the actual CDN file.
# If a filename is wrong Wikipedia returns 404 → skipped cleanly.
# ---------------------------------------------------------------------------

def _wiki(filename: str) -> str:
    return f"https://en.wikipedia.org/wiki/Special:FilePath/{filename}"

PLAYER_IMAGE_URLS: Dict[str, str] = {
    # ── Current Stars ─────────────────────────────────────────────────────
    "lebron_james":             _wiki("LeBron_James_cropped.jpg"),
    "stephen_curry":            _wiki("Stephen_Curry_Chef_Curry.jpg"),
    "kevin_durant":             _wiki("Kevin_Durant_%28gs%29.jpg"),
    "giannis_antetokounmpo":    _wiki("Giannis_Antetokounmpo_2019.jpg"),
    "kawhi_leonard":            _wiki("Kawhi_Leonard_2022.jpg"),
    "james_harden":             _wiki("James_Harden_2017.jpg"),
    "russell_westbrook":        _wiki("Russell_Westbrook_2016.jpg"),
    "anthony_davis":            _wiki("Anthony_Davis_%28basketball%29.jpg"),
    "kyrie_irving":             _wiki("Kyrie_Irving_2016.jpg"),
    "damian_lillard":           _wiki("Damian_Lillard_2019.jpg"),
    "joel_embiid":              _wiki("Joel_Embiid_2022.jpg"),
    "nikola_jokic":             _wiki("Nikola_Joki%C4%87_2022.jpg"),
    "luka_doncic":              _wiki("Luka_Don%C4%8Di%C4%87_2019-04-17.jpg"),
    "ja_morant":                _wiki("Ja_Morant_2022.jpg"),
    "zion_williamson":          _wiki("Zion_Williamson_2019.jpg"),
    "trae_young":               _wiki("Trae_Young_2020.jpg"),
    "devin_booker":             _wiki("Devin_Booker_2020.jpg"),
    "paul_george":              _wiki("Paul_George_2021.jpg"),
    "jimmy_butler":             _wiki("Jimmy_Butler_2022.jpg"),
    "jayson_tatum":             _wiki("Jayson_Tatum_2022.jpg"),
    "jaylen_brown":             _wiki("Jaylen_Brown_2022.jpg"),
    "bam_adebayo":              _wiki("Bam_Adebayo_2022.jpg"),
    "donovan_mitchell":         _wiki("Donovan_Mitchell_2022.jpg"),
    "deaaron_fox":              _wiki("De%27Aaron_Fox_2022.jpg"),
    "shai_gilgeous_alexander":  _wiki("Shai_Gilgeous-Alexander_2022.jpg"),
    "karl_anthony_towns":       _wiki("Karl-Anthony_Towns_2022.jpg"),
    "draymond_green":           _wiki("Draymond_Green_2016.jpg"),
    "klay_thompson":            _wiki("Klay_Thompson_2016.jpg"),
    "chris_paul":               _wiki("Chris_Paul_2022.jpg"),
    "tyrese_haliburton":        _wiki("Tyrese_Haliburton_2022.jpg"),
    "lamelo_ball":              _wiki("LaMelo_Ball_2022.jpg"),
    "anthony_edwards":          _wiki("Anthony_Edwards_2022.jpg"),
    "cade_cunningham":          _wiki("Cade_Cunningham_2022.jpg"),
    "victor_wembanyama":        _wiki("Victor_Wembanyama_2023.jpg"),
    "paolo_banchero":           _wiki("Paolo_Banchero_2022.jpg"),
    "jaren_jackson_jr":         _wiki("Jaren_Jackson_Jr._2022.jpg"),
    "brandon_ingram":           _wiki("Brandon_Ingram_2022.jpg"),
    "julius_randle":            _wiki("Julius_Randle_2022.jpg"),
    "rudy_gobert":              _wiki("Rudy_Gobert_2022.jpg"),
    "jamal_murray":             _wiki("Jamal_Murray_2022.jpg"),
    "pascal_siakam":            _wiki("Pascal_Siakam_2022.jpg"),
    "bradley_beal":             _wiki("Bradley_Beal_2020.jpg"),
    "jrue_holiday":             _wiki("Jrue_Holiday_2022.jpg"),
    "zach_lavine":              _wiki("Zach_LaVine_2022.jpg"),
    "kemba_walker":             _wiki("Kemba_Walker_2020.jpg"),
    "john_wall":                _wiki("John_Wall_2018.jpg"),
    "kyle_lowry":               _wiki("Kyle_Lowry_2022.jpg"),
    "deron_williams":           _wiki("Deron_Williams_2016.jpg"),
    "rajon_rondo":              _wiki("Rajon_Rondo_2017.jpg"),
    "marc_gasol":               _wiki("Marc_Gasol_2019.jpg"),
    "demarcus_cousins":         _wiki("DeMarcus_Cousins_2018.jpg"),
    "andre_iguodala":           _wiki("Andre_Iguodala_2016.jpg"),
    "kevin_love":               _wiki("Kevin_Love_2022.jpg"),

    # ── 2000s–2010s Era ───────────────────────────────────────────────────
    "dwyane_wade":              _wiki("Dwyane_Wade_2013.jpg"),
    "carmelo_anthony":          _wiki("Carmelo_Anthony_2019.jpg"),
    "chris_bosh":               _wiki("Chris_Bosh_2013.jpg"),
    "dwight_howard":            _wiki("Dwight_Howard_2019.jpg"),
    "pau_gasol":                _wiki("Pau_Gasol_2013.jpg"),
    "tony_parker":              _wiki("Tony_Parker_2012.jpg"),
    "manu_ginobili":            _wiki("Manu_Gin%C3%B3bili_2018.jpg"),
    "derrick_rose":             _wiki("Derrick_Rose_2011.jpg"),
    "blake_griffin":            _wiki("Blake_Griffin_2019.jpg"),
    "yao_ming":                 _wiki("Yao_Ming_2009.jpg"),
    "chauncey_billups":         _wiki("Chauncey_Billups_2019.jpg"),
    "vince_carter":             _wiki("Vince_Carter_2019.jpg"),
    "tracy_mcgrady":            _wiki("Tracy_McGrady_2019.jpg"),
    "grant_hill":               _wiki("Grant_Hill_%28basketball%29.jpg"),
    "anfernee_hardaway":        _wiki("Anfernee_Hardaway_2019.jpg"),
    "amare_stoudemire":         _wiki("Amar%27e_Stoudemire.jpg"),
    "gilbert_arenas":           _wiki("Gilbert_Arenas.jpg"),
    "stephon_marbury":          _wiki("Stephon_Marbury.jpg"),
    "lamar_odom":               _wiki("Lamar_Odom_2010.jpg"),
    "baron_davis":              _wiki("Baron_Davis_2009.jpg"),
    "shawn_kemp":               _wiki("Shawn_Kemp.jpg"),
    "peja_stojakovic":          _wiki("Peja_Stojakovi%C4%87.jpg"),
    "antawn_jamison":           _wiki("Antawn_Jamison.jpg"),
    "sam_cassell":              _wiki("Sam_Cassell.jpg"),

    # ── 90s Legends ───────────────────────────────────────────────────────
    "allen_iverson":            _wiki("Allen_Iverson_2016.jpg"),
    "ray_allen":                _wiki("Ray_Allen_2012.jpg"),
    "paul_pierce":              _wiki("Paul_Pierce_2012.jpg"),
    "kevin_garnett":            _wiki("Kevin_Garnett_2007.jpg"),
    "dirk_nowitzki":            _wiki("Dirk_Nowitzki_2019.jpg"),
    "steve_nash":               _wiki("Steve_Nash_2009.jpg"),
    "jason_kidd":               _wiki("Jason_Kidd_2012.jpg"),
    "gary_payton":              _wiki("Gary_Payton.jpg"),
    "reggie_miller":            _wiki("Reggie_Miller.jpg"),
    "alonzo_mourning":          _wiki("Alonzo_Mourning.jpg"),
    "scottie_pippen":           _wiki("Scottie_Pippen.jpg"),
    "dennis_rodman":            _wiki("Dennis_Rodman.jpg"),
    "dominique_wilkins":        _wiki("Dominique_Wilkins.jpg"),
    "isiah_thomas":             _wiki("Isiah_Thomas.jpg"),
    "clyde_drexler":            _wiki("Clyde_Drexler.jpg"),
    "david_robinson":           _wiki("David_Robinson_%28basketball%29.jpg"),
    "hakeem_olajuwon":          _wiki("Hakeem_Olajuwon.jpg"),
    "charles_barkley":          _wiki("Charles_Barkley.jpg"),
    "patrick_ewing":            _wiki("Patrick_Ewing.jpg"),
    "john_stockton":            _wiki("John_Stockton.jpg"),
    "karl_malone":              _wiki("Karl_Malone.jpg"),
    "joe_dumars":               _wiki("Joe_Dumars.jpg"),
    "mitch_richmond":           _wiki("Mitch_Richmond.jpg"),
    "latrell_sprewell":         _wiki("Latrell_Sprewell.jpg"),
    "glen_rice":                _wiki("Glen_Rice.jpg"),

    # ── All-Time Legends ──────────────────────────────────────────────────
    "michael_jordan":           _wiki("Michael_Jordan_in_2014.jpg"),
    "kobe_bryant":              _wiki("Kobe_Bryant_2014.jpg"),
    "shaquille_oneal":          _wiki("Shaquille_O%27Neal_2.jpg"),
    "tim_duncan":               _wiki("Tim_Duncan_%282009%29.jpg"),
    "magic_johnson":            _wiki("Magic_Johnson.jpg"),
    "larry_bird":               _wiki("Larry_Bird.jpg"),
    "kareem_abdul_jabbar":      _wiki("Kareem_Abdul-Jabbar_%281974%29.jpg"),
    "julius_erving":            _wiki("Julius_Erving.jpg"),
    "moses_malone":             _wiki("Moses_Malone.jpg"),
    "oscar_robertson":          _wiki("Oscar_Robertson.jpg"),
    "jerry_west":               _wiki("Jerry_West_1963.jpg"),
    "elgin_baylor":             _wiki("Elgin_Baylor_%281971%29.jpg"),
    "bill_russell":             _wiki("Bill_Russell_%28basketball%2C_1956%29.jpg"),
    "wilt_chamberlain":         _wiki("Wilt_Chamberlain.jpg"),
    "pete_maravich":            _wiki("Pete_Maravich.jpg"),
    "george_gervin":            _wiki("George_Gervin.jpg"),
    "nate_archibald":           _wiki("Nate_Archibald.jpg"),
    "bob_mcadoo":               _wiki("Bob_McAdoo.jpg"),
    "elvin_hayes":              _wiki("Elvin_Hayes.jpg"),
    "bob_cousy":                _wiki("Bob_Cousy.jpg"),
    "rick_barry":               _wiki("Rick_Barry.jpg"),
    "dave_cowens":              _wiki("Dave_Cowens.jpg"),
    "bill_walton":              _wiki("Bill_Walton.jpg"),
    "walt_frazier":             _wiki("Walt_Frazier.jpg"),
    "george_mikan":             _wiki("George_Mikan.jpg"),
    "bob_pettit":               _wiki("Bob_Pettit.jpg"),
    "willis_reed":              _wiki("Willis_Reed.jpg"),
    "dan_issel":                _wiki("Dan_Issel.jpg"),
    "artis_gilmore":            _wiki("Artis_Gilmore.jpg"),
}

ROUND_TIME = 20  # seconds per question

# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------

class NBARoster(commands.Cog):
    """Guess the NBA player from their photo — first to reach the target score wins!"""

    def __init__(self, bot: Red):
        self.bot = bot
        self._games: Dict[int, dict] = {}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _image_dir(self) -> Path:
        return cog_data_path(self) / "images"

    def _image_path(self, slug: str) -> Optional[Path]:
        for ext in ("jpg", "jpeg", "png", "webp"):
            p = self._image_dir() / f"{slug}.{ext}"
            if p.exists():
                return p
        return None

    async def _download_image(self, session: aiohttp.ClientSession, url: str, slug: str) -> bool:
        """Download an image from url and save locally.
        Retries on HTTP 429 with Retry-After backoff.
        Rejects non-image responses (HTML error pages, etc.)."""
        url_path = url.split("?")[0]
        ext = url_path.rsplit(".", 1)[-1].lower()
        if ext not in ("jpg", "jpeg", "png", "webp"):
            ext = "jpg"

        dest = self._image_dir() / f"{slug}.{ext}"
        backoff = 5.0
        for attempt in range(4):
            try:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=30),
                    allow_redirects=True,
                ) as resp:
                    if resp.status == 429:
                        retry_after = float(resp.headers.get("Retry-After", backoff))
                        await asyncio.sleep(retry_after)
                        backoff = min(backoff * 2, 60.0)
                        continue
                    if resp.status != 200:
                        return False
                    # Reject anything that isn't an image (e.g. HTML "file not found" pages)
                    content_type = resp.headers.get("Content-Type", "")
                    if "image" not in content_type:
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

    def _available_players(self) -> List[Dict]:
        """Return only players who have a locally cached image."""
        return [p for p in PLAYERS if self._image_path(p["slug"]) is not None]

    # ------------------------------------------------------------------
    # Commands — main group
    # ------------------------------------------------------------------

    @commands.group(name="nba", aliases=["nbag", "nbaplay", "nbaguess"], invoke_without_command=True)
    @commands.guild_only()
    async def nba(self, ctx: commands.Context):
        """NBA Player Photo Quiz commands.
        Run `[p]nba setup` once (admin) to download images, then `[p]nba start` to play."""
        await ctx.send_help(ctx.command)

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    @nba.command(name="setup")
    @commands.admin_or_permissions(administrator=True)
    async def nba_setup(self, ctx: commands.Context):
        """Download all NBA player photos locally (run this once before playing)."""
        img_dir = self._image_dir()
        img_dir.mkdir(parents=True, exist_ok=True)

        total = len(PLAYERS)
        embed = discord.Embed(
            title="📥  Downloading NBA Player Photos",
            description=(
                f"Downloading photos for **{total}** players.\n"
                "This takes **3–6 minutes** — please be patient and don't run it again!"
            ),
            colour=0x1D428A,
        )
        embed.set_footer(text="jaffar21")
        status_msg = await ctx.send(embed=embed)

        ok = 0
        failed = []
        skipped = 0

        connector = aiohttp.TCPConnector(limit=5)
        async with aiohttp.ClientSession(
            connector=connector,
            headers={"User-Agent": "NBAPlayerQuizBot/1.0 (Red-DiscordBot cog by jaffar21)"},
        ) as session:
            for i, player in enumerate(PLAYERS, 1):
                slug = player["slug"]

                if self._image_path(slug) is not None:
                    skipped += 1
                    ok += 1
                    continue

                url = PLAYER_IMAGE_URLS.get(slug)
                if not url:
                    failed.append(player["name"])
                    continue

                success = await self._download_image(session, url, slug)
                if success:
                    ok += 1
                else:
                    failed.append(player["name"])

                if i % 10 == 0:
                    new_embed = discord.Embed(
                        title="📥  Downloading NBA Player Photos",
                        description=(
                            f"Progress: **{i}/{total}**\n"
                            f"✅ Downloaded: {ok - skipped}  |  ❌ Failed: {len(failed)}"
                        ),
                        colour=0x1D428A,
                    )
                    new_embed.set_footer(text="jaffar21")
                    try:
                        await status_msg.edit(embed=new_embed)
                    except discord.HTTPException:
                        pass

                await asyncio.sleep(0.5)

        available = len(self._available_players())
        result_embed = discord.Embed(title="✅  Setup Complete!", colour=0x00CC44)
        result_embed.add_field(
            name="Results",
            value=(
                f"**{available}** player photos ready to play\n"
                f"✅ Downloaded: {ok - skipped}\n"
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
                value="`[p]nba clearimages` then `[p]nba setup` to retry everything fresh.",
                inline=False,
            )
        result_embed.add_field(name="Next Step", value="Use `[p]nba start` to play!", inline=False)
        result_embed.set_footer(text="jaffar21")
        await status_msg.edit(embed=result_embed)

    # ------------------------------------------------------------------
    # Start
    # ------------------------------------------------------------------

    @nba.command(name="start")
    @commands.guild_only()
    async def nba_start(self, ctx: commands.Context, target: int = 10):
        """Start an NBA player photo quiz. First to the target score wins!"""
        guild_id = ctx.guild.id
        if guild_id in self._games:
            await ctx.send("A game is already running! Use `[p]nba stop` to end it.")
            return

        players = self._available_players()
        if len(players) < 5:
            await ctx.send("Not enough player images downloaded. Run `[p]nba setup` first!")
            return

        if target < 1:
            await ctx.send("Target score must be at least 1.")
            return

        random.shuffle(players)
        self._games[guild_id] = {
            "channel_id": ctx.channel.id,
            "pool": players,
            "used_indices": set(),
            "scores": {},
            "target": target,
            "current_player": None,
            "round_task": None,
        }

        embed = discord.Embed(
            title="🏀  NBA Player Photo Quiz",
            description=(
                f"First to **{target} points** wins!\n"
                "Type the player's name — first name, last name, or nickname all work.\n\n"
                "Starting in 3 seconds..."
            ),
            colour=0x1D428A,
        )
        embed.set_footer(text="jaffar21")
        await ctx.send(embed=embed)
        await asyncio.sleep(3)
        await self._next_round(guild_id, ctx.channel)

    # ------------------------------------------------------------------
    # Stop
    # ------------------------------------------------------------------

    @nba.command(name="stop")
    @commands.guild_only()
    async def nba_stop(self, ctx: commands.Context):
        """Stop the current NBA quiz."""
        guild_id = ctx.guild.id
        if guild_id not in self._games:
            await ctx.send("No game is running right now.")
            return
        game = self._games[guild_id]
        if game.get("round_task") and not game["round_task"].done():
            game["round_task"].cancel()
        channel = self.bot.get_channel(game["channel_id"])
        await self._end_game(guild_id, channel, reason="stopped")
        await ctx.send("🛑 Game stopped.")

    # ------------------------------------------------------------------
    # Scores
    # ------------------------------------------------------------------

    @nba.command(name="scores")
    @commands.guild_only()
    async def nba_scores(self, ctx: commands.Context):
        """Show the current scores."""
        guild_id = ctx.guild.id
        if guild_id not in self._games:
            await ctx.send("No game is running right now.")
            return
        await ctx.send(embed=self._build_scoreboard(self._games[guild_id]))

    # ------------------------------------------------------------------
    # Skip
    # ------------------------------------------------------------------

    @nba.command(name="skip")
    @commands.guild_only()
    @commands.mod_or_permissions(manage_messages=True)
    async def nba_skip(self, ctx: commands.Context):
        """Skip the current player (mods only)."""
        guild_id = ctx.guild.id
        game = self._games.get(guild_id)
        if not game:
            await ctx.send("No game is running right now.")
            return
        if not game.get("current_player"):
            await ctx.send("No question is active right now.")
            return

        player_name = game["current_player"]["name"]
        if game.get("round_task") and not game["round_task"].done():
            game["round_task"].cancel()

        channel = self.bot.get_channel(game["channel_id"])
        await channel.send(f"⏩ Skipped! That was **{player_name}**.")
        await asyncio.sleep(1)
        await self._next_round(guild_id, channel)

    # ------------------------------------------------------------------
    # Clear Images
    # ------------------------------------------------------------------

    @nba.command(name="clearimages")
    @commands.admin_or_permissions(administrator=True)
    async def nba_clearimages(self, ctx: commands.Context):
        """Delete all locally cached player images so setup re-downloads them fresh."""
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
            f"🗑️ Cleared **{deleted}** cached player images.\n"
            "Run `[p]nba setup` to re-download everything fresh."
        )

    # ------------------------------------------------------------------
    # Game logic
    # ------------------------------------------------------------------

    def _pick_player(self, game: dict) -> Optional[Dict]:
        pool = game["pool"]
        available = [i for i in range(len(pool)) if i not in game["used_indices"]]
        if not available:
            return None
        idx = random.choice(available)
        game["used_indices"].add(idx)
        return pool[idx]

    def _build_scoreboard(self, game: dict) -> discord.Embed:
        scores = game["scores"]
        embed = discord.Embed(title="🏀  Scoreboard", colour=0x1D428A)
        if not scores:
            embed.description = "No points scored yet!"
        else:
            sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            medals = ["🥇", "🥈", "🥉"]
            lines = [
                f"{medals[r] if r < 3 else f'#{r+1}'} <@{uid}> — **{pts} pt{'s' if pts != 1 else ''}**"
                for r, (uid, pts) in enumerate(sorted_scores)
            ]
            embed.description = "\n".join(lines)
        embed.set_footer(text=f"jaffar21 • First to {game['target']} wins")
        return embed

    async def _next_round(self, guild_id: int, channel: discord.TextChannel):
        game = self._games.get(guild_id)
        if not game:
            return

        player = self._pick_player(game)
        if player is None:
            await channel.send("🏁 All players used! Reshuffling the deck...")
            game["pool"] = self._available_players()
            random.shuffle(game["pool"])
            game["used_indices"] = set()
            player = self._pick_player(game)
            if player is None:
                await channel.send("⚠️ No player images found. Run `[p]nba setup` first.")
                await self._end_game(guild_id, channel, reason="no_images")
                return

        game["current_player"] = player
        img_path = self._image_path(player["slug"])
        suffix = img_path.suffix.lstrip(".")

        embed = discord.Embed(
            title="🏀  Who is this NBA player?",
            description=f"⏱️ **{ROUND_TIME} seconds** — type your answer!",
            colour=0x1D428A,
        )
        embed.set_footer(text="jaffar21")

        try:
            file = discord.File(str(img_path), filename=f"{player['slug']}.{suffix}")
            embed.set_image(url=f"attachment://{player['slug']}.{suffix}")
            await channel.send(file=file, embed=embed)
        except Exception:
            await channel.send("⚠️ Couldn't load that image, skipping...")
            await asyncio.sleep(1)
            await self._next_round(guild_id, channel)
            return

        task = asyncio.get_event_loop().create_task(
            self._round_timer(guild_id, channel, player)
        )
        game["round_task"] = task

    async def _round_timer(self, guild_id: int, channel: discord.TextChannel, player: dict):
        try:
            await asyncio.sleep(ROUND_TIME)
        except asyncio.CancelledError:
            return

        game = self._games.get(guild_id)
        if not game or game.get("current_player") != player:
            return

        await channel.send(f"⏰ Time's up! That was **{player['name']}**.")
        await asyncio.sleep(1.5)
        await self._next_round(guild_id, channel)

    async def _end_game(self, guild_id: int, channel: discord.TextChannel, reason: str = "winner"):
        game = self._games.pop(guild_id, None)
        if not game or reason == "stopped":
            return

        embed = self._build_scoreboard(game)
        embed.title = "🏆  Game Over — Final Scores"
        if reason == "winner" and game["scores"]:
            winner_id = max(game["scores"], key=game["scores"].get)
            pts = game["scores"][winner_id]
            embed.description = (
                f"🎉 <@{winner_id}> wins with **{pts} points**!\n\n"
                + (embed.description or "")
            )
        await channel.send(embed=embed)

    # ------------------------------------------------------------------
    # Message listener
    # ------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        guild_id = message.guild.id
        game = self._games.get(guild_id)
        if not game or message.channel.id != game["channel_id"]:
            return

        player = game.get("current_player")
        if not player:
            return

        if _answers_match(message.content, player["answers"]):
            uid = message.author.id
            game["scores"][uid] = game["scores"].get(uid, 0) + 1
            pts = game["scores"][uid]

            if game.get("round_task") and not game["round_task"].done():
                game["round_task"].cancel()
            game["current_player"] = None

            if pts >= game["target"]:
                await message.channel.send(
                    f"🏆 **{message.author.display_name}** got it — **{player['name']}**! "
                    f"They reach **{pts} points** and WIN! 🎉"
                )
                await self._end_game(guild_id, message.channel, reason="winner")
            else:
                await message.channel.send(
                    f"✅ **{message.author.display_name}** got it — **{player['name']}**! "
                    f"({pts} pt{'s' if pts != 1 else ''} / {game['target']})"
                )
                await asyncio.sleep(1.5)
                await self._next_round(guild_id, message.channel)
