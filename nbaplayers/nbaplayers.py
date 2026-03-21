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
]

# Strip duplicate slugs
_seen: set = set()
_deduped: List[Dict] = []
for _p in PLAYERS:
    if _p["slug"] not in _seen:
        _seen.add(_p["slug"])
        _deduped.append(_p)
PLAYERS = _deduped

# ---------------------------------------------------------------------------
# Image URLs — all pre-resolved Wikimedia CDN URLs (verified via Wikipedia API)
# ---------------------------------------------------------------------------

PLAYER_IMAGE_URLS: Dict[str, str] = {
    # ── Current Stars ─────────────────────────────────────────────────────
    "lebron_james":             "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7a/LeBron_James_%2851959977144%29_%28cropped2%29.jpg/500px-LeBron_James_%2851959977144%29_%28cropped2%29.jpg",
    "stephen_curry":            "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f1/Steph_Curry_P20230117AS-1347_%28cropped%29.jpg/500px-Steph_Curry_P20230117AS-1347_%28cropped%29.jpg",
    "kevin_durant":             "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Kevin_Durant%2C_Paris_2024_%28cropped%29.jpg/500px-Kevin_Durant%2C_Paris_2024_%28cropped%29.jpg",
    "giannis_antetokounmpo":    "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9c/Giannis_Antetokounmpo_%2851915153421%29_%28cropped%29.jpg/500px-Giannis_Antetokounmpo_%2851915153421%29_%28cropped%29.jpg",
    "kawhi_leonard":            "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a9/Kawhi_Leonard_%287440607%29_%28cropped%29.jpg/500px-Kawhi_Leonard_%287440607%29_%28cropped%29.jpg",
    "james_harden":             "https://upload.wikimedia.org/wikipedia/commons/thumb/6/63/Harden_dribbling_midcourt%2C_Cavaliers_vs_Nets_on_January_17%2C_2022_%28cropped%29.jpg/500px-Harden_dribbling_midcourt%2C_Cavaliers_vs_Nets_on_January_17%2C_2022_%28cropped%29.jpg",
    "russell_westbrook":        "https://upload.wikimedia.org/wikipedia/commons/thumb/b/be/Russell_Westbrook_%28March_21%2C_2022%29_%28cropped%29.jpg/500px-Russell_Westbrook_%28March_21%2C_2022%29_%28cropped%29.jpg",
    "anthony_davis":            "https://upload.wikimedia.org/wikipedia/commons/thumb/3/36/Anthony_Davis_pre-game_%28cropped%29.jpg/500px-Anthony_Davis_pre-game_%28cropped%29.jpg",
    "kyrie_irving":             "https://upload.wikimedia.org/wikipedia/commons/thumb/2/27/Kyrie_Irving_%2851830909437%29_%28cropped%29.jpg/500px-Kyrie_Irving_%2851830909437%29_%28cropped%29.jpg",
    "damian_lillard":           "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8e/Damian_Lillard_%282021%29_%28cropped%29.jpg/500px-Damian_Lillard_%282021%29_%28cropped%29.jpg",
    "joel_embiid":              "https://upload.wikimedia.org/wikipedia/commons/thumb/1/13/Joel_Embiid_2019.jpg/500px-Joel_Embiid_2019.jpg",
    "nikola_jokic":             "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7e/Nikola_Jokic_free_throw_%28cropped%29.jpg/500px-Nikola_Jokic_free_throw_%28cropped%29.jpg",
    "luka_doncic":              "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cd/Luka_Doncic_%2851914951721%29_%28cropped1%29.jpg/500px-Luka_Doncic_%2851914951721%29_%28cropped1%29.jpg",
    "ja_morant":                "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a1/Ja_Morant_2021.jpg/500px-Ja_Morant_2021.jpg",
    "zion_williamson":          "https://upload.wikimedia.org/wikipedia/commons/thumb/5/53/Zion_Williamson_2020_%28cropped%29.jpg/500px-Zion_Williamson_2020_%28cropped%29.jpg",
    "trae_young":               "https://upload.wikimedia.org/wikipedia/commons/thumb/4/42/Trae_Young_%282022_All-Star_Weekend%29_%28cropped%29.jpg/500px-Trae_Young_%282022_All-Star_Weekend%29_%28cropped%29.jpg",
    "devin_booker":             "https://upload.wikimedia.org/wikipedia/commons/thumb/2/22/Devin_Booker%2C_Olympic_Games_2024_%28cropped%29.jpg/500px-Devin_Booker%2C_Olympic_Games_2024_%28cropped%29.jpg",
    "paul_george":              "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d6/Paul_George_Pacers.jpg/500px-Paul_George_Pacers.jpg",
    "jimmy_butler":             "https://upload.wikimedia.org/wikipedia/commons/thumb/f/fc/CES_2026_-_Jimmy_Butler_01_%28cropped%29.jpg/500px-CES_2026_-_Jimmy_Butler_01_%28cropped%29.jpg",
    "jayson_tatum":             "https://upload.wikimedia.org/wikipedia/commons/thumb/8/84/Celtics_at_Wizards_2024-12-044_%28cropped_2%29.jpg/500px-Celtics_at_Wizards_2024-12-044_%28cropped_2%29.jpg",
    "jaylen_brown":             "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a0/Jaylen_Brown_2022.jpg/500px-Jaylen_Brown_2022.jpg",
    "bam_adebayo":              "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7d/Bam_Adebayo_%28cropped%29.jpg/500px-Bam_Adebayo_%28cropped%29.jpg",
    "donovan_mitchell":         "https://upload.wikimedia.org/wikipedia/commons/thumb/3/39/Donovan_Mitchell_Pregame.jpg/500px-Donovan_Mitchell_Pregame.jpg",
    "deaaron_fox":              "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e9/De%27Aaron_Fox.jpg/500px-De%27Aaron_Fox.jpg",
    "shai_gilgeous_alexander":  "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8c/2023-08-09_Deutschland_gegen_Kanada_%28Basketball-L%C3%A4nderspiel%29_by_Sandro_Halank%E2%80%93109.jpg/500px-2023-08-09_Deutschland_gegen_Kanada_%28Basketball-L%C3%A4nderspiel%29_by_Sandro_Halank%E2%80%93109.jpg",
    "karl_anthony_towns":       "https://upload.wikimedia.org/wikipedia/commons/thumb/5/55/Karl-Anthony_Towns_%2851914283512%29_%28cropped%29_%28cropped%29.jpg/500px-Karl-Anthony_Towns_%2851914283512%29_%28cropped%29_%28cropped%29.jpg",
    "draymond_green":           "https://upload.wikimedia.org/wikipedia/commons/thumb/9/99/Draymond_Green_2022.jpg/500px-Draymond_Green_2022.jpg",
    "klay_thompson":            "https://upload.wikimedia.org/wikipedia/commons/thumb/8/81/Klay_Thompson_%28cropped%29.jpg/500px-Klay_Thompson_%28cropped%29.jpg",
    "chris_paul":               "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ad/Chris_Paul_%282022_All-Star_Weekend%29_%28cropped%29.jpg/500px-Chris_Paul_%282022_All-Star_Weekend%29_%28cropped%29.jpg",
    "tyrese_haliburton":        "https://upload.wikimedia.org/wikipedia/commons/thumb/1/16/1_tyrese_haliburton_2025_%28cropped_2%29.jpg/500px-1_tyrese_haliburton_2025_%28cropped_2%29.jpg",
    "lamelo_ball":              "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f9/LaMelo_Ball_%28cropped%29.jpg/500px-LaMelo_Ball_%28cropped%29.jpg",
    "anthony_edwards":          "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7e/Anthony_Edwards_Kentavious_Caldwell-Pope_%2851734745028%29_%28cropped%29_%28cropped%29.jpg/500px-Anthony_Edwards_Kentavious_Caldwell-Pope_%2851734745028%29_%28cropped%29_%28cropped%29.jpg",
    "cade_cunningham":          "https://upload.wikimedia.org/wikipedia/commons/thumb/f/fe/1_cade_cunningham_2024.jpg/500px-1_cade_cunningham_2024.jpg",
    "victor_wembanyama":        "https://upload.wikimedia.org/wikipedia/commons/thumb/6/65/Victor_Wembanyama_San_Antonio_Spurs_2024.jpg/500px-Victor_Wembanyama_San_Antonio_Spurs_2024.jpg",
    "paolo_banchero":           "https://upload.wikimedia.org/wikipedia/commons/thumb/5/54/Paolo_Banchero.png/500px-Paolo_Banchero.png",
    "jaren_jackson_jr":         "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e8/Jaren_Jackson_%2851814052094%29_%28cropped%29.jpg/500px-Jaren_Jackson_%2851814052094%29_%28cropped%29.jpg",
    "brandon_ingram":           "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e0/Brandon_Ingram_2020_%28cropped2%29.jpg/500px-Brandon_Ingram_2020_%28cropped2%29.jpg",
    "julius_randle":            "https://upload.wikimedia.org/wikipedia/commons/thumb/1/17/Julius_Randle_with_Lakers.jpg/500px-Julius_Randle_with_Lakers.jpg",
    "rudy_gobert":              "https://upload.wikimedia.org/wikipedia/commons/thumb/3/31/Rudy_Gobert.jpg/500px-Rudy_Gobert.jpg",
    "jamal_murray":             "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b6/Jamal_Murray_free_throw_%28cropped%29.jpg/500px-Jamal_Murray_free_throw_%28cropped%29.jpg",
    "pascal_siakam":            "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b1/1_pascal_siakam_2025_%28cropped%29.jpg/500px-1_pascal_siakam_2025_%28cropped%29.jpg",
    "bradley_beal":             "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0e/Bradley_Beal_WSH_Wizards_2022_%28croppedface%29.jpg/500px-Bradley_Beal_WSH_Wizards_2022_%28croppedface%29.jpg",
    "jrue_holiday":             "https://upload.wikimedia.org/wikipedia/commons/thumb/b/ba/Celtics_at_Wizards_2024-12-021_%28cropped%29.jpg/500px-Celtics_at_Wizards_2024-12-021_%28cropped%29.jpg",
    "zach_lavine":              "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Zach_LaVine_%282022_All-Star_Weekend%29.jpg/500px-Zach_LaVine_%282022_All-Star_Weekend%29.jpg",
    "kemba_walker":             "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e6/Kemba_Walker_2019.jpg/500px-Kemba_Walker_2019.jpg",
    "john_wall":                "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8c/2019_John_Wall_%2848823815693%29.jpg/500px-2019_John_Wall_%2848823815693%29.jpg",
    "kyle_lowry":               "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ac/Kyle_Lowry_%2826715268738%29_%28cropped%29.jpg/500px-Kyle_Lowry_%2826715268738%29_%28cropped%29.jpg",
    "deron_williams":           "https://upload.wikimedia.org/wikipedia/commons/thumb/5/55/Deron_Williams_Nets_2.jpg/500px-Deron_Williams_Nets_2.jpg",
    "rajon_rondo":              "https://upload.wikimedia.org/wikipedia/commons/thumb/2/28/Rajon_Rondo_%2838294689275%29_%28cropped%29.jpg/500px-Rajon_Rondo_%2838294689275%29_%28cropped%29.jpg",
    "marc_gasol":               "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4a/Marc_Gasol-jul_2018.jpg/500px-Marc_Gasol-jul_2018.jpg",
    "demarcus_cousins":         "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3c/1_demarcus_cousins_2019_%28cropped%29.jpg/500px-1_demarcus_cousins_2019_%28cropped%29.jpg",
    "andre_iguodala":           "https://upload.wikimedia.org/wikipedia/commons/thumb/5/58/Heat_Andre_Iguodala_%28cropped%29.jpg/500px-Heat_Andre_Iguodala_%28cropped%29.jpg",
    "kevin_love":               "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a2/Kevin_Love_2020_%28cropped%29.jpg/500px-Kevin_Love_2020_%28cropped%29.jpg",
    # ── 2000s–2010s Era ───────────────────────────────────────────────────
    "dwyane_wade":              "https://upload.wikimedia.org/wikipedia/commons/thumb/7/73/Dwyane_Wade_e1.jpg/500px-Dwyane_Wade_e1.jpg",
    "carmelo_anthony":          "https://upload.wikimedia.org/wikipedia/commons/thumb/2/27/Carmelo_Anthony_at_2025_NBA_All_Star_Weekend_%28cropped%29.jpg/500px-Carmelo_Anthony_at_2025_NBA_All_Star_Weekend_%28cropped%29.jpg",
    "chris_bosh":               "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5c/Chris_Bosh_Open_Congress_2022.jpg/500px-Chris_Bosh_Open_Congress_2022.jpg",
    "dwight_howard":            "https://upload.wikimedia.org/wikipedia/commons/thumb/4/41/Dwight_Howard_pre-game_%28cropped%29.jpg/500px-Dwight_Howard_pre-game_%28cropped%29.jpg",
    "pau_gasol":                "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a1/PauCaptura.jpg/500px-PauCaptura.jpg",
    "tony_parker":              "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6c/Flamme_olympique_Reims_1525799.jpg/500px-Flamme_olympique_Reims_1525799.jpg",
    "manu_ginobili":            "https://upload.wikimedia.org/wikipedia/commons/thumb/3/33/Manu_Ginobili_Spurs-Magic011_%28cropped%29.jpg/500px-Manu_Ginobili_Spurs-Magic011_%28cropped%29.jpg",
    "derrick_rose":             "https://upload.wikimedia.org/wikipedia/commons/thumb/0/06/Derrick_Rose_03.jpg/500px-Derrick_Rose_03.jpg",
    "blake_griffin":            "https://upload.wikimedia.org/wikipedia/commons/thumb/f/fd/Blake_Griffin_Brooklyn_Nets_2022_%28cropped%29.jpg/500px-Blake_Griffin_Brooklyn_Nets_2022_%28cropped%29.jpg",
    "yao_ming":                 "https://upload.wikimedia.org/wikipedia/commons/thumb/8/89/Yao_Ming_in_2014_%28cropped%29.jpg/500px-Yao_Ming_in_2014_%28cropped%29.jpg",
    "chauncey_billups":         "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Billups_coach_%28cropped%29.jpg/500px-Billups_coach_%28cropped%29.jpg",
    "vince_carter":             "https://upload.wikimedia.org/wikipedia/commons/thumb/9/93/Vince_Carter_2013-03-25_%281%29.jpg/500px-Vince_Carter_2013-03-25_%281%29.jpg",
    "tracy_mcgrady":            "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f9/Tracy_McGrady_1.jpg/500px-Tracy_McGrady_1.jpg",
    "grant_hill":               "https://upload.wikimedia.org/wikipedia/commons/thumb/0/05/Grant_Hill_2007-12-08.jpg/500px-Grant_Hill_2007-12-08.jpg",
    "anfernee_hardaway":        "https://upload.wikimedia.org/wikipedia/commons/thumb/2/25/HBCUAllstarBasketball4223-118_%2852802377149%29_%28cropped%29.jpg/500px-HBCUAllstarBasketball4223-118_%2852802377149%29_%28cropped%29.jpg",
    "amare_stoudemire":         "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8a/Amar%27e_Stoudemire_free_throw.jpg/500px-Amar%27e_Stoudemire_free_throw.jpg",
    "gilbert_arenas":           "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2a/Gilbert_arenas_2008.jpg/500px-Gilbert_arenas_2008.jpg",
    "stephon_marbury":          "https://upload.wikimedia.org/wikipedia/commons/thumb/2/24/Stephon_Marbury_%40_Amazon_Fishbowl_2.jpg/500px-Stephon_Marbury_%40_Amazon_Fishbowl_2.jpg",
    "lamar_odom":               "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8f/Lamar_Odom_%2837%29_%28cropped%29.jpg/500px-Lamar_Odom_%2837%29_%28cropped%29.jpg",
    "baron_davis":              "https://upload.wikimedia.org/wikipedia/commons/thumb/e/ee/Collision_2023_-_RCZ_0560_%2853008986428%29_%28cropped%29.jpg/500px-Collision_2023_-_RCZ_0560_%2853008986428%29_%28cropped%29.jpg",
    "shawn_kemp":               "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b2/Shawn_Kemp_%289523772347%29_%28cropped%29.jpg/500px-Shawn_Kemp_%289523772347%29_%28cropped%29.jpg",
    "peja_stojakovic":          "https://upload.wikimedia.org/wikipedia/commons/thumb/0/02/Peja_Stojakovic_Mavs_cropped.jpg/500px-Peja_Stojakovic_Mavs_cropped.jpg",
    "antawn_jamison":           "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0c/2019_Antawn_Jamison_%2848824316652%29_%28cropped%29.jpg/500px-2019_Antawn_Jamison_%2848824316652%29_%28cropped%29.jpg",
    "sam_cassell":              "https://upload.wikimedia.org/wikipedia/commons/thumb/c/ca/Wizards_Assistant_Coach_Sam_Cassell_%28cropped%29.jpg/500px-Wizards_Assistant_Coach_Sam_Cassell_%28cropped%29.jpg",
    # ── 90s Legends ───────────────────────────────────────────────────────
    "allen_iverson":            "https://upload.wikimedia.org/wikipedia/commons/thumb/2/21/Allen_Iverson_headshot.jpg/500px-Allen_Iverson_headshot.jpg",
    "ray_allen":                "https://upload.wikimedia.org/wikipedia/commons/thumb/d/da/Ray_Allen_161208-A-HE359-046_%2831482070191%29.jpg/500px-Ray_Allen_161208-A-HE359-046_%2831482070191%29.jpg",
    "paul_pierce":              "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e3/Paul_Pierce_2008-01-13_%28cropped%29.jpg/500px-Paul_Pierce_2008-01-13_%28cropped%29.jpg",
    "kevin_garnett":            "https://upload.wikimedia.org/wikipedia/commons/thumb/6/60/Kevin_Garnett_2008-01-13.jpg/500px-Kevin_Garnett_2008-01-13.jpg",
    "dirk_nowitzki":            "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1d/Dirk_Nowitzki_2_%28cropped%29.jpg/500px-Dirk_Nowitzki_2_%28cropped%29.jpg",
    "steve_nash":               "https://upload.wikimedia.org/wikipedia/commons/thumb/9/99/SteveNash2014.jpg/500px-SteveNash2014.jpg",
    "jason_kidd":               "https://upload.wikimedia.org/wikipedia/commons/thumb/8/84/Jason_Kidd_Nets_coach_cropped.jpg/500px-Jason_Kidd_Nets_coach_cropped.jpg",
    "gary_payton":              "https://upload.wikimedia.org/wikipedia/commons/thumb/1/14/Gary_Payton%2C_Miami_Heat_circa_2007_%28cropped%29.jpg/500px-Gary_Payton%2C_Miami_Heat_circa_2007_%28cropped%29.jpg",
    "reggie_miller":            "https://upload.wikimedia.org/wikipedia/commons/c/c0/Reggie_Miller_crop.png",
    "alonzo_mourning":          "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b7/Alonzo_Mourning.jpg/500px-Alonzo_Mourning.jpg",
    "scottie_pippen":           "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5f/Scottie_Pippen_5-2-22_%28cropped%29.jpg/500px-Scottie_Pippen_5-2-22_%28cropped%29.jpg",
    "dennis_rodman":            "https://upload.wikimedia.org/wikipedia/commons/thumb/9/99/Dennis_Rodman_02_%2834649289162%29_%28cropped%29.jpg/500px-Dennis_Rodman_02_%2834649289162%29_%28cropped%29.jpg",
    "dominique_wilkins":        "https://upload.wikimedia.org/wikipedia/commons/thumb/7/76/Dominique_Wilkins_2022.jpg/500px-Dominique_Wilkins_2022.jpg",
    "isiah_thomas":             "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1e/Isiah_Thomas_2007_%28cropped%29.jpg/500px-Isiah_Thomas_2007_%28cropped%29.jpg",
    "clyde_drexler":            "https://upload.wikimedia.org/wikipedia/commons/thumb/6/62/Clyde_Drexler_01.jpg/500px-Clyde_Drexler_01.jpg",
    "david_robinson":           "https://upload.wikimedia.org/wikipedia/commons/thumb/8/85/David_Robinson_2017.jpg/500px-David_Robinson_2017.jpg",
    "hakeem_olajuwon":          "https://upload.wikimedia.org/wikipedia/commons/thumb/8/84/Nigerian_President_Buhari_Stands_With_Secretary_Kerry%2C_U.S._Delegation_After_They_Attended_His_Inauguration_Ceremony_%28cropped%29.jpg/500px-Nigerian_President_Buhari_Stands_With_Secretary_Kerry%2C_U.S._Delegation_After_They_Attended_His_Inauguration_Ceremony_%28cropped%29.jpg",
    "charles_barkley":          "https://upload.wikimedia.org/wikipedia/commons/thumb/8/89/1_charles_barkley_2019_%28cropped%29.jpg/500px-1_charles_barkley_2019_%28cropped%29.jpg",
    "patrick_ewing":            "https://upload.wikimedia.org/wikipedia/commons/thumb/0/05/Patrick_Ewing_2021_%28cropped%29.jpg/500px-Patrick_Ewing_2021_%28cropped%29.jpg",
    "john_stockton":            "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cf/John_Stockton_2022.jpg/500px-John_Stockton_2022.jpg",
    "karl_malone":              "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e5/NBA_HOF%E2%80%99er_Karl_Malone_visits_Barksdale_%289%29_%28cropped%29.jpg/500px-NBA_HOF%E2%80%99er_Karl_Malone_visits_Barksdale_%289%29_%28cropped%29.jpg",
    "joe_dumars":               "https://upload.wikimedia.org/wikipedia/commons/1/1f/Joe_Dumars.jpg",
    "mitch_richmond":           "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d4/Mitch_Richmond_cropped.jpg/500px-Mitch_Richmond_cropped.jpg",
    "glen_rice":                "https://upload.wikimedia.org/wikipedia/commons/1/14/Glen_Rice_2010_%28cropped%29.jpg",
    # ── All-Time Legends ──────────────────────────────────────────────────
    "michael_jordan":           "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ae/Michael_Jordan_in_2014.jpg/500px-Michael_Jordan_in_2014.jpg",
    "kobe_bryant":              "https://upload.wikimedia.org/wikipedia/commons/thumb/3/36/Kobe_Bryant_Dec_2014.jpg/500px-Kobe_Bryant_Dec_2014.jpg",
    "shaquille_oneal":          "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e5/TechCrunch_Disrupt_2023_-_Day_1_%28cropped%29.jpg/500px-TechCrunch_Disrupt_2023_-_Day_1_%28cropped%29.jpg",
    "tim_duncan":               "https://upload.wikimedia.org/wikipedia/commons/thumb/c/cb/Tim_Duncan_Walks_Verizon_Center%27s_Floor_%28cropped%29_%28cropped%29.jpg/500px-Tim_Duncan_Walks_Verizon_Center%27s_Floor_%28cropped%29_%28cropped%29.jpg",
    "magic_johnson":            "https://upload.wikimedia.org/wikipedia/commons/thumb/2/29/Magic_Johnson_at_SXSW_2022_%2851958828669%29_%28cropped%29.jpg/500px-Magic_Johnson_at_SXSW_2022_%2851958828669%29_%28cropped%29.jpg",
    "larry_bird":               "https://upload.wikimedia.org/wikipedia/commons/thumb/b/bb/Larrybird.jpg/500px-Larrybird.jpg",
    "kareem_abdul_jabbar":      "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a0/Kareem_Abdul-Jabbar_May_2014.jpg/500px-Kareem_Abdul-Jabbar_May_2014.jpg",
    "julius_erving":            "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0d/Julius_Erving_2016.jpg/500px-Julius_Erving_2016.jpg",
    "moses_malone":             "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a1/Moses_Malone_cropped_portrait.jpg/500px-Moses_Malone_cropped_portrait.jpg",
    "oscar_robertson":          "https://upload.wikimedia.org/wikipedia/commons/thumb/d/de/Oscar_Robertson_2024.jpg/500px-Oscar_Robertson_2024.jpg",
    "jerry_west":               "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5a/Jerry_West_1972.jpeg/500px-Jerry_West_1972.jpeg",
    "elgin_baylor":             "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e5/Elgin_Baylor_Night_program-%28cropped%29.jpg/500px-Elgin_Baylor_Night_program-%28cropped%29.jpg",
    "bill_russell":             "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Bill_russell_dribbling_%28cropped%29.jpg/500px-Bill_russell_dribbling_%28cropped%29.jpg",
    "wilt_chamberlain":         "https://upload.wikimedia.org/wikipedia/commons/thumb/1/11/Wilt_Chamberlain_1960_%28cropped%29_%28cropped%29.jpg/500px-Wilt_Chamberlain_1960_%28cropped%29_%28cropped%29.jpg",
    "pete_maravich":            "https://upload.wikimedia.org/wikipedia/commons/thumb/2/25/Pete_Maravich_1977.jpeg/500px-Pete_Maravich_1977.jpeg",
    "george_gervin":            "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d1/George_Gervin_ABA.jpeg/500px-George_Gervin_ABA.jpeg",
    "nate_archibald":           "https://upload.wikimedia.org/wikipedia/commons/thumb/7/77/Nate_Archibald_1974.jpeg/500px-Nate_Archibald_1974.jpeg",
    "bob_mcadoo":               "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9f/Mcadoo_1973.jpg/500px-Mcadoo_1973.jpg",
    "elvin_hayes":              "https://upload.wikimedia.org/wikipedia/commons/thumb/4/45/Elvin_Hayes_1975.jpeg/500px-Elvin_Hayes_1975.jpeg",
    "bob_cousy":                "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c5/Bob_Cousy_%281%29.jpeg/500px-Bob_Cousy_%281%29.jpeg",
    "rick_barry":               "https://upload.wikimedia.org/wikipedia/commons/thumb/2/28/Rick_Barry.jpg/500px-Rick_Barry.jpg",
    "dave_cowens":              "https://upload.wikimedia.org/wikipedia/commons/5/5e/Dave_Cowens_-_2005_NBA_Legends_Tour_-_1-21-05.jpg",
    "bill_walton":              "https://upload.wikimedia.org/wikipedia/commons/thumb/5/54/Bill_walton_blazers_photo.jpg/500px-Bill_walton_blazers_photo.jpg",
    "walt_frazier":             "https://upload.wikimedia.org/wikipedia/commons/thumb/0/07/Walt_Frazier_%28cropped%29.jpg/500px-Walt_Frazier_%28cropped%29.jpg",
    "george_mikan":             "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2d/George_Mikan_1945.jpeg/500px-George_Mikan_1945.jpeg",
    "bob_pettit":               "https://upload.wikimedia.org/wikipedia/commons/thumb/8/88/Bob_Pettit_1961.jpeg/500px-Bob_Pettit_1961.jpeg",
    "willis_reed":              "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4f/Willis_Reed_1972_publicity_photo.jpg/500px-Willis_Reed_1972_publicity_photo.jpg",
    "dan_issel":                "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b4/Dan_Issel_%281%29.jpeg/500px-Dan_Issel_%281%29.jpeg",
    "artis_gilmore":            "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d6/Artis_Gilmore.jpg/500px-Artis_Gilmore.jpg",
}

ROUND_TIME = 20

# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------

class NBARoster(commands.Cog):
    """Guess the NBA player from their photo — first to reach the target score wins!"""

    def __init__(self, bot: Red):
        self.bot = bot
        self._games: Dict[int, dict] = {}

    def _image_dir(self) -> Path:
        return cog_data_path(self) / "images"

    def _image_path(self, slug: str) -> Optional[Path]:
        for ext in ("jpg", "jpeg", "png", "webp"):
            p = self._image_dir() / f"{slug}.{ext}"
            if p.exists():
                return p
        return None

    async def _download_image(self, session: aiohttp.ClientSession, url: str, slug: str) -> bool:
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
        return [p for p in PLAYERS if self._image_path(p["slug"]) is not None]

    @commands.group(name="nba", aliases=["nbag", "nbaplay", "nbaguess"], invoke_without_command=True)
    @commands.guild_only()
    async def nba(self, ctx: commands.Context):
        """NBA Player Photo Quiz commands.
        Run `[p]nba setup` once (admin) to download images, then `[p]nba start` to play."""
        await ctx.send_help(ctx.command)

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
                "This takes **3–6 minutes** — please be patient!"
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
            headers={"User-Agent": "Mozilla/5.0 NBAPlayerQuizBot/2.0 (Red-DiscordBot cog by jaffar21)"},
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
        self._games.pop(guild_id, None)
        await ctx.send("🛑 Game stopped.")

    @nba.command(name="scores")
    @commands.guild_only()
    async def nba_scores(self, ctx: commands.Context):
        """Show the current scores."""
        guild_id = ctx.guild.id
        if guild_id not in self._games:
            await ctx.send("No game is running right now.")
            return
        await ctx.send(embed=self._build_scoreboard(self._games[guild_id]))

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
                self._games.pop(guild_id, None)
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
                await self._end_game(guild_id, message.channel)
            else:
                await message.channel.send(
                    f"✅ **{message.author.display_name}** got it — **{player['name']}**! "
                    f"({pts} pt{'s' if pts != 1 else ''} / {game['target']})"
                )
                await asyncio.sleep(1.5)
                await self._next_round(guild_id, message.channel)

    async def _end_game(self, guild_id: int, channel: discord.TextChannel):
        game = self._games.pop(guild_id, None)
        if not game:
            return
        embed = self._build_scoreboard(game)
        embed.title = "🏆  Game Over — Final Scores"
        if game["scores"]:
            winner_id = max(game["scores"], key=game["scores"].get)
            pts = game["scores"][winner_id]
            embed.description = (
                f"🎉 <@{winner_id}> wins with **{pts} points**!\n\n"
                + (embed.description or "")
            )
        await channel.send(embed=embed)
