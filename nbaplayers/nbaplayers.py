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
        if norm_input == _normalize(ans):
            return True
    return False


# ---------------------------------------------------------------------------
# Player roster  (name, slug, accepted answers)
# ---------------------------------------------------------------------------

PLAYERS: List[Dict] = [
    # ── Current/Recent Stars ──────────────────────────────────────────────
    {"slug": "lebron_james",            "name": "LeBron James",            "answers": ["lebron", "lebron james", "king james", "lbj", "the king", "king"]},
    {"slug": "stephen_curry",           "name": "Stephen Curry",           "answers": ["steph", "curry", "stephen curry", "steph curry", "chef curry"]},
    {"slug": "kevin_durant",            "name": "Kevin Durant",            "answers": ["durant", "kd", "kevin durant", "slim reaper"]},
    {"slug": "giannis_antetokounmpo",   "name": "Giannis Antetokounmpo",   "answers": ["giannis", "greek freak", "giannis antetokounmpo", "antetokounmpo"]},
    {"slug": "kawhi_leonard",           "name": "Kawhi Leonard",           "answers": ["kawhi", "leonard", "the claw", "kawhi leonard"]},
    {"slug": "james_harden",            "name": "James Harden",            "answers": ["harden", "james harden", "the beard"]},
    {"slug": "russell_westbrook",       "name": "Russell Westbrook",       "answers": ["westbrook", "russ", "russell westbrook", "brodie"]},
    {"slug": "anthony_davis",           "name": "Anthony Davis",           "answers": ["anthony davis", "ad", "davis", "the brow", "unibrow"]},
    {"slug": "kyrie_irving",            "name": "Kyrie Irving",            "answers": ["kyrie", "irving", "kyrie irving", "uncle drew"]},
    {"slug": "damian_lillard",          "name": "Damian Lillard",          "answers": ["lillard", "dame", "damian lillard", "dame dolla"]},
    {"slug": "joel_embiid",             "name": "Joel Embiid",             "answers": ["embiid", "joel embiid", "the process", "jojo", "joel"]},
    {"slug": "nikola_jokic",            "name": "Nikola Jokić",            "answers": ["jokic", "nikola jokic", "the joker", "nikola"]},
    {"slug": "luka_doncic",             "name": "Luka Dončić",             "answers": ["luka", "doncic", "luka doncic", "luka magic"]},
    {"slug": "ja_morant",               "name": "Ja Morant",               "answers": ["ja", "morant", "ja morant"]},
    {"slug": "zion_williamson",         "name": "Zion Williamson",         "answers": ["zion", "williamson", "zion williamson"]},
    {"slug": "trae_young",              "name": "Trae Young",              "answers": ["trae", "trae young", "ice trae", "young"]},
    {"slug": "devin_booker",            "name": "Devin Booker",            "answers": ["booker", "book", "devin booker", "devin"]},
    {"slug": "paul_george",             "name": "Paul George",             "answers": ["paul george", "pg", "pg13", "george"]},
    {"slug": "jimmy_butler",            "name": "Jimmy Butler",            "answers": ["butler", "jimmy butler", "jimmy buckets", "jimmy"]},
    {"slug": "jayson_tatum",            "name": "Jayson Tatum",            "answers": ["tatum", "jayson tatum", "jt"]},
    {"slug": "jaylen_brown",            "name": "Jaylen Brown",            "answers": ["jaylen brown", "jaylen", "brown", "jb"]},
    {"slug": "bam_adebayo",             "name": "Bam Adebayo",             "answers": ["bam", "adebayo", "bam adebayo"]},
    {"slug": "donovan_mitchell",        "name": "Donovan Mitchell",        "answers": ["donovan mitchell", "mitchell", "spida", "donovan"]},
    {"slug": "deaaron_fox",             "name": "De'Aaron Fox",            "answers": ["fox", "de'aaron fox", "deaaron fox", "swipa"]},
    {"slug": "darius_garland",          "name": "Darius Garland",          "answers": ["garland", "darius garland", "darius"]},
    {"slug": "tyler_herro",             "name": "Tyler Herro",             "answers": ["herro", "tyler herro", "tyler"]},
    {"slug": "shai_gilgeous_alexander", "name": "Shai Gilgeous-Alexander", "answers": ["sga", "shai", "gilgeous-alexander", "shai gilgeous-alexander", "shai gilgeous alexander"]},
    {"slug": "karl_anthony_towns",      "name": "Karl-Anthony Towns",      "answers": ["kat", "towns", "karl-anthony towns", "karl anthony towns"]},
    {"slug": "julius_randle",           "name": "Julius Randle",           "answers": ["randle", "julius randle", "julius"]},
    {"slug": "rudy_gobert",             "name": "Rudy Gobert",             "answers": ["gobert", "rudy gobert", "rudy", "stifle tower"]},
    {"slug": "draymond_green",          "name": "Draymond Green",          "answers": ["draymond", "green", "draymond green"]},
    {"slug": "klay_thompson",           "name": "Klay Thompson",           "answers": ["klay", "thompson", "klay thompson"]},
    {"slug": "chris_paul",              "name": "Chris Paul",              "answers": ["chris paul", "cp3", "paul", "point god"]},
    {"slug": "bradley_beal",            "name": "Bradley Beal",            "answers": ["beal", "bradley beal", "bb3", "bradley"]},
    {"slug": "cj_mccollum",             "name": "CJ McCollum",             "answers": ["mccollum", "cj mccollum", "cj"]},
    {"slug": "pascal_siakam",           "name": "Pascal Siakam",           "answers": ["siakam", "pascal siakam", "spicy p", "pascal"]},
    {"slug": "andrew_wiggins",          "name": "Andrew Wiggins",          "answers": ["wiggins", "andrew wiggins", "wiggs"]},
    {"slug": "jrue_holiday",            "name": "Jrue Holiday",            "answers": ["holiday", "jrue holiday", "jrue"]},
    {"slug": "zach_lavine",             "name": "Zach LaVine",             "answers": ["lavine", "zach lavine", "zach"]},
    {"slug": "ben_simmons",             "name": "Ben Simmons",             "answers": ["simmons", "ben simmons", "ben"]},
    {"slug": "anthony_edwards",         "name": "Anthony Edwards",         "answers": ["ant", "anthony edwards", "edwards", "ant man"]},
    {"slug": "cade_cunningham",         "name": "Cade Cunningham",         "answers": ["cade", "cunningham", "cade cunningham"]},
    {"slug": "evan_mobley",             "name": "Evan Mobley",             "answers": ["mobley", "evan mobley", "evan"]},
    {"slug": "scottie_barnes",          "name": "Scottie Barnes",          "answers": ["scottie barnes", "barnes", "scottie"]},
    {"slug": "franz_wagner",            "name": "Franz Wagner",            "answers": ["franz", "wagner", "franz wagner"]},
    {"slug": "jaren_jackson_jr",        "name": "Jaren Jackson Jr.",       "answers": ["jaren jackson", "jjj", "jaren jackson jr", "jaren"]},
    {"slug": "brandon_ingram",          "name": "Brandon Ingram",          "answers": ["ingram", "brandon ingram", "bi", "brandon"]},
    {"slug": "lonzo_ball",              "name": "Lonzo Ball",              "answers": ["lonzo", "ball", "lonzo ball"]},
    {"slug": "khris_middleton",         "name": "Khris Middleton",         "answers": ["middleton", "khris middleton", "khris"]},
    {"slug": "victor_wembanyama",       "name": "Victor Wembanyama",       "answers": ["wemby", "wembanyama", "victor wembanyama", "victor"]},
    {"slug": "paolo_banchero",          "name": "Paolo Banchero",          "answers": ["banchero", "paolo banchero", "paolo"]},

    # ── 2000s–2010s Era ───────────────────────────────────────────────────
    {"slug": "dwyane_wade",             "name": "Dwyane Wade",             "answers": ["wade", "dwyane wade", "d wade", "flash", "dwyane"]},
    {"slug": "carmelo_anthony",         "name": "Carmelo Anthony",         "answers": ["carmelo", "melo", "carmelo anthony"]},
    {"slug": "chris_bosh",              "name": "Chris Bosh",              "answers": ["bosh", "chris bosh"]},
    {"slug": "dwight_howard",           "name": "Dwight Howard",           "answers": ["dwight", "howard", "dwight howard", "superman", "d12"]},
    {"slug": "pau_gasol",               "name": "Pau Gasol",               "answers": ["pau", "gasol", "pau gasol"]},
    {"slug": "tony_parker",             "name": "Tony Parker",             "answers": ["tony parker", "parker", "tp"]},
    {"slug": "manu_ginobili",           "name": "Manu Ginóbili",           "answers": ["manu", "ginobili", "manu ginobili"]},
    {"slug": "derrick_rose",            "name": "Derrick Rose",            "answers": ["rose", "derrick rose", "d rose"]},
    {"slug": "blake_griffin",           "name": "Blake Griffin",           "answers": ["blake", "griffin", "blake griffin"]},
    {"slug": "yao_ming",                "name": "Yao Ming",                "answers": ["yao", "yao ming"]},
    {"slug": "chauncey_billups",        "name": "Chauncey Billups",        "answers": ["billups", "chauncey", "mr big shot", "chauncey billups"]},
    {"slug": "vince_carter",            "name": "Vince Carter",            "answers": ["vince", "carter", "vince carter", "vinsanity", "vc"]},
    {"slug": "tracy_mcgrady",           "name": "Tracy McGrady",           "answers": ["tmac", "tracy mcgrady", "mcgrady", "tracy"]},
    {"slug": "grant_hill",              "name": "Grant Hill",              "answers": ["grant hill", "hill", "grant"]},
    {"slug": "anfernee_hardaway",       "name": "Anfernee Hardaway",       "answers": ["penny", "hardaway", "penny hardaway", "anfernee hardaway", "anfernee"]},
    {"slug": "amare_stoudemire",        "name": "Amar'e Stoudemire",       "answers": ["amare", "stoudemire", "amar'e stoudemire", "stat"]},
    {"slug": "gilbert_arenas",          "name": "Gilbert Arenas",          "answers": ["arenas", "gilbert arenas", "agent zero", "hibachi", "gilbert"]},
    {"slug": "lamar_odom",              "name": "Lamar Odom",              "answers": ["lamar", "odom", "lamar odom"]},
    {"slug": "stephon_marbury",         "name": "Stephon Marbury",         "answers": ["marbury", "starbury", "stephon marbury", "stephon"]},
    {"slug": "peja_stojakovic",         "name": "Peja Stojaković",         "answers": ["peja", "stojakovic", "peja stojakovic"]},
    {"slug": "shawn_kemp",              "name": "Shawn Kemp",              "answers": ["kemp", "shawn kemp", "reign man"]},
    {"slug": "baron_davis",             "name": "Baron Davis",             "answers": ["baron davis", "bd", "boom dizzle", "baron"]},
    {"slug": "mitch_richmond",          "name": "Mitch Richmond",          "answers": ["richmond", "mitch richmond", "the rock", "mitch"]},
    {"slug": "latrell_sprewell",        "name": "Latrell Sprewell",        "answers": ["sprewell", "latrell sprewell", "spree", "latrell"]},
    {"slug": "allan_houston",           "name": "Allan Houston",           "answers": ["houston", "allan houston", "allan"]},
    {"slug": "gary_payton",             "name": "Gary Payton",             "answers": ["gary payton", "payton", "the glove", "gp"]},
    {"slug": "reggie_miller",           "name": "Reggie Miller",           "answers": ["reggie miller", "miller", "reggie"]},
    {"slug": "alonzo_mourning",         "name": "Alonzo Mourning",         "answers": ["mourning", "alonzo mourning", "zo"]},
    {"slug": "jason_kidd",              "name": "Jason Kidd",              "answers": ["kidd", "jason kidd"]},
    {"slug": "steve_nash",              "name": "Steve Nash",              "answers": ["nash", "steve nash"]},
    {"slug": "rasheed_wallace",         "name": "Rasheed Wallace",         "answers": ["rasheed", "rasheed wallace", "sheed"]},
    {"slug": "ben_wallace",             "name": "Ben Wallace",             "answers": ["ben wallace", "ben", "big ben"]},
    {"slug": "richard_hamilton",        "name": "Richard Hamilton",        "answers": ["rip hamilton", "hamilton", "richard hamilton", "rip"]},
    {"slug": "mike_bibby",              "name": "Mike Bibby",              "answers": ["bibby", "mike bibby", "mike"]},
    {"slug": "elton_brand",             "name": "Elton Brand",             "answers": ["brand", "elton brand", "elton"]},
    {"slug": "caron_butler",            "name": "Caron Butler",            "answers": ["butler", "caron butler", "caron", "tuff juice"]},
    {"slug": "antawn_jamison",          "name": "Antawn Jamison",          "answers": ["jamison", "antawn jamison", "antawn"]},
    {"slug": "jermaine_oneal",          "name": "Jermaine O'Neal",         "answers": ["jermaine oneal", "jermaine o'neal", "jermaine"]},
    {"slug": "damon_stoudamire",        "name": "Damon Stoudamire",        "answers": ["stoudamire", "damon stoudamire", "mighty mouse", "damon"]},
    {"slug": "glen_rice",               "name": "Glen Rice",               "answers": ["glen rice", "rice", "glen"]},

    # ── 90s Legends ───────────────────────────────────────────────────────
    {"slug": "michael_jordan",          "name": "Michael Jordan",          "answers": ["jordan", "mj", "michael jordan", "air jordan", "his airness"]},
    {"slug": "kobe_bryant",             "name": "Kobe Bryant",             "answers": ["kobe", "bryant", "kobe bryant", "black mamba", "mamba"]},
    {"slug": "shaquille_oneal",         "name": "Shaquille O'Neal",        "answers": ["shaq", "shaquille oneal", "shaquille o'neal", "diesel", "big diesel", "shaquille"]},
    {"slug": "tim_duncan",              "name": "Tim Duncan",              "answers": ["tim duncan", "duncan", "big fundamental"]},
    {"slug": "kevin_garnett",           "name": "Kevin Garnett",           "answers": ["garnett", "kg", "kevin garnett", "the big ticket"]},
    {"slug": "ray_allen",               "name": "Ray Allen",               "answers": ["ray allen", "allen", "jesus shuttlesworth"]},
    {"slug": "paul_pierce",             "name": "Paul Pierce",             "answers": ["paul pierce", "pierce", "the truth"]},
    {"slug": "allen_iverson",           "name": "Allen Iverson",           "answers": ["iverson", "ai", "allen iverson", "the answer"]},
    {"slug": "dirk_nowitzki",           "name": "Dirk Nowitzki",           "answers": ["dirk", "nowitzki", "dirk nowitzki"]},
    {"slug": "dwyane_wade_legend",      "name": "Dwyane Wade",             "answers": []},
    {"slug": "scottie_pippen",          "name": "Scottie Pippen",          "answers": ["pippen", "scottie pippen", "scottie"]},
    {"slug": "dennis_rodman",           "name": "Dennis Rodman",           "answers": ["rodman", "dennis rodman", "the worm", "worm"]},
    {"slug": "dominique_wilkins",       "name": "Dominique Wilkins",       "answers": ["dominique", "wilkins", "dominique wilkins", "human highlight"]},
    {"slug": "isiah_thomas",            "name": "Isiah Thomas",            "answers": ["isiah", "isiah thomas", "zeke"]},
    {"slug": "clyde_drexler",           "name": "Clyde Drexler",           "answers": ["drexler", "clyde drexler", "clyde the glide", "clyde"]},
    {"slug": "david_robinson",          "name": "David Robinson",          "answers": ["robinson", "david robinson", "the admiral"]},
    {"slug": "hakeem_olajuwon",         "name": "Hakeem Olajuwon",         "answers": ["hakeem", "olajuwon", "hakeem olajuwon", "the dream", "akeem"]},
    {"slug": "charles_barkley",         "name": "Charles Barkley",         "answers": ["barkley", "charles barkley", "sir charles"]},
    {"slug": "patrick_ewing",           "name": "Patrick Ewing",           "answers": ["ewing", "patrick ewing"]},
    {"slug": "john_stockton",           "name": "John Stockton",           "answers": ["stockton", "john stockton"]},
    {"slug": "karl_malone",             "name": "Karl Malone",             "answers": ["karl malone", "malone", "the mailman", "mailman"]},
    {"slug": "alonzo_mourning_legend",  "name": "Alonzo Mourning",         "answers": []},
    {"slug": "joe_dumars",              "name": "Joe Dumars",              "answers": ["dumars", "joe dumars", "joe"]},

    # ── 70s–80s Legends ───────────────────────────────────────────────────
    {"slug": "magic_johnson",           "name": "Magic Johnson",           "answers": ["magic", "magic johnson", "johnson", "earvin johnson"]},
    {"slug": "larry_bird",              "name": "Larry Bird",              "answers": ["bird", "larry bird", "larry legend", "larry"]},
    {"slug": "kareem_abdul_jabbar",     "name": "Kareem Abdul-Jabbar",     "answers": ["kareem", "jabbar", "kareem abdul jabbar", "kareem abdul-jabbar"]},
    {"slug": "julius_erving",           "name": "Julius Erving",           "answers": ["dr j", "julius erving", "erving", "julius", "the doctor", "doc"]},
    {"slug": "moses_malone",            "name": "Moses Malone",            "answers": ["moses", "malone", "moses malone"]},
    {"slug": "oscar_robertson",         "name": "Oscar Robertson",         "answers": ["oscar", "robertson", "oscar robertson", "the big o"]},
    {"slug": "jerry_west",              "name": "Jerry West",              "answers": ["jerry west", "west", "the logo"]},
    {"slug": "elgin_baylor",            "name": "Elgin Baylor",            "answers": ["baylor", "elgin baylor", "elgin"]},
    {"slug": "bill_russell",            "name": "Bill Russell",            "answers": ["bill russell", "russell"]},
    {"slug": "wilt_chamberlain",        "name": "Wilt Chamberlain",        "answers": ["wilt", "chamberlain", "wilt chamberlain", "wilt the stilt", "the big dipper"]},
    {"slug": "pete_maravich",           "name": "Pete Maravich",           "answers": ["maravich", "pistol pete", "pete maravich", "pistol"]},
    {"slug": "george_gervin",           "name": "George Gervin",           "answers": ["gervin", "george gervin", "the iceman", "iceman"]},
    {"slug": "nate_archibald",          "name": "Nate Archibald",          "answers": ["archibald", "nate archibald", "tiny archibald", "tiny"]},
    {"slug": "bob_mcadoo",              "name": "Bob McAdoo",              "answers": ["mcadoo", "bob mcadoo"]},
    {"slug": "elvin_hayes",             "name": "Elvin Hayes",             "answers": ["hayes", "elvin hayes", "the big e"]},
    {"slug": "dan_issel",               "name": "Dan Issel",               "answers": ["issel", "dan issel", "the horse"]},
    {"slug": "artis_gilmore",           "name": "Artis Gilmore",           "answers": ["gilmore", "artis gilmore", "a-train"]},
    {"slug": "dave_cowens",             "name": "Dave Cowens",             "answers": ["cowens", "dave cowens"]},
    {"slug": "bill_walton",             "name": "Bill Walton",             "answers": ["walton", "bill walton"]},
    {"slug": "rick_barry",              "name": "Rick Barry",              "answers": ["barry", "rick barry"]},
    {"slug": "bob_pettit",              "name": "Bob Pettit",              "answers": ["pettit", "bob pettit"]},
    {"slug": "walt_frazier",            "name": "Walt Frazier",            "answers": ["frazier", "clyde frazier", "walt frazier"]},
    {"slug": "willis_reed",             "name": "Willis Reed",             "answers": ["reed", "willis reed"]},
    {"slug": "dave_debusschere",        "name": "Dave DeBusschere",        "answers": ["debusschere", "dave debusschere"]},
    {"slug": "billy_cunningham",        "name": "Billy Cunningham",        "answers": ["cunningham", "billy cunningham", "the kangaroo kid"]},
    {"slug": "spencer_haywood",         "name": "Spencer Haywood",         "answers": ["haywood", "spencer haywood", "spencer"]},
    {"slug": "gail_goodrich",           "name": "Gail Goodrich",           "answers": ["goodrich", "gail goodrich"]},
    {"slug": "hal_greer",               "name": "Hal Greer",               "answers": ["greer", "hal greer"]},
    {"slug": "jack_sikma",              "name": "Jack Sikma",              "answers": ["sikma", "jack sikma"]},
    {"slug": "sid_moncrief",            "name": "Sidney Moncrief",         "answers": ["moncrief", "sid moncrief", "sidney moncrief", "sid"]},
    {"slug": "calvin_murphy",           "name": "Calvin Murphy",           "answers": ["murphy", "calvin murphy", "calvin"]},

    # ── 50s–60s Legends ───────────────────────────────────────────────────
    {"slug": "bob_cousy",               "name": "Bob Cousy",               "answers": ["cousy", "bob cousy", "the cooz"]},
    {"slug": "bill_sharman",            "name": "Bill Sharman",            "answers": ["sharman", "bill sharman"]},
    {"slug": "dolph_schayes",           "name": "Dolph Schayes",           "answers": ["schayes", "dolph schayes"]},
    {"slug": "george_mikan",            "name": "George Mikan",            "answers": ["mikan", "george mikan", "mr basketball"]},
    {"slug": "bob_lanier",              "name": "Bob Lanier",              "answers": ["lanier", "bob lanier"]},
    {"slug": "paul_arizin",             "name": "Paul Arizin",             "answers": ["arizin", "paul arizin"]},
    {"slug": "tom_heinsohn",            "name": "Tom Heinsohn",            "answers": ["heinsohn", "tom heinsohn"]},
    {"slug": "lenny_wilkens",           "name": "Lenny Wilkens",           "answers": ["wilkens", "lenny wilkens"]},

    # ── Additional Modern Players ─────────────────────────────────────────
    {"slug": "lebron_james_young",      "name": "LeBron James",            "answers": []},
    {"slug": "kevin_johnson",           "name": "Kevin Johnson",           "answers": ["kevin johnson", "kj"]},
    {"slug": "vin_baker",               "name": "Vin Baker",               "answers": ["baker", "vin baker", "vin"]},
    {"slug": "antonio_mcdyess",         "name": "Antonio McDyess",         "answers": ["mcdyess", "antonio mcdyess", "dice"]},
    {"slug": "jerry_stackhouse",        "name": "Jerry Stackhouse",        "answers": ["stackhouse", "jerry stackhouse", "stack"]},
    {"slug": "steve_francis",           "name": "Steve Francis",           "answers": ["francis", "steve francis", "stevie franchise"]},
    {"slug": "cuttino_mobley",          "name": "Cuttino Mobley",          "answers": ["mobley", "cuttino mobley", "cat"]},
    {"slug": "shareef_abdur_rahim",     "name": "Shareef Abdur-Rahim",     "answers": ["abdur-rahim", "shareef abdur-rahim", "shareef"]},
    {"slug": "david_wesley",            "name": "David Wesley",            "answers": ["wesley", "david wesley"]},
    {"slug": "jason_williams",          "name": "Jason Williams",          "answers": ["jason williams", "white chocolate", "j-will"]},
    {"slug": "wally_szczerbiak",        "name": "Wally Szczerbiak",        "answers": ["szczerbiak", "wally szczerbiak", "wally"]},
    {"slug": "mike_miller",             "name": "Mike Miller",             "answers": ["mike miller", "miller"]},
    {"slug": "pao_gasol2",              "name": "Marc Gasol",              "answers": ["marc gasol", "marc", "gasol"]},
    {"slug": "marc_gasol",              "name": "Marc Gasol",              "answers": ["marc gasol", "marc", "big spain"]},
    {"slug": "jose_calderon",           "name": "José Calderón",           "answers": ["calderon", "jose calderon"]},
    {"slug": "luol_deng",               "name": "Luol Deng",               "answers": ["deng", "luol deng", "luol"]},
    {"slug": "joakim_noah",             "name": "Joakim Noah",             "answers": ["noah", "joakim noah", "jo"]},
    {"slug": "nikola_vucevic",          "name": "Nikola Vučević",          "answers": ["vucevic", "nikola vucevic", "vuc"]},
    {"slug": "serge_ibaka",             "name": "Serge Ibaka",             "answers": ["ibaka", "serge ibaka", "serge"]},
    {"slug": "lou_williams",            "name": "Lou Williams",            "answers": ["lou will", "lou williams", "williams", "sweet lou"]},
    {"slug": "jamal_murray",            "name": "Jamal Murray",            "answers": ["murray", "jamal murray", "jamal", "blue arrow"]},
    {"slug": "michael_porter_jr",       "name": "Michael Porter Jr.",      "answers": ["mpj", "michael porter jr", "michael porter", "porter"]},
    {"slug": "nikola_jokic2",           "name": "Nikola Jokić",            "answers": []},
    {"slug": "domantas_sabonis",        "name": "Domantas Sabonis",        "answers": ["sabonis", "domantas sabonis", "domantas"]},
    {"slug": "myles_turner",            "name": "Myles Turner",            "answers": ["turner", "myles turner", "myles"]},
    {"slug": "al_horford",              "name": "Al Horford",              "answers": ["horford", "al horford", "al"]},
    {"slug": "kyle_lowry",              "name": "Kyle Lowry",              "answers": ["lowry", "kyle lowry", "kyle"]},
    {"slug": "dillon_brooks",           "name": "Dillon Brooks",           "answers": ["brooks", "dillon brooks", "dillon"]},
    {"slug": "terry_rozier",            "name": "Terry Rozier",            "answers": ["rozier", "terry rozier", "scary terry", "terry"]},
    {"slug": "mikal_bridges",           "name": "Mikal Bridges",           "answers": ["mikal bridges", "bridges", "mikal"]},
    {"slug": "nic_claxton",             "name": "Nic Claxton",             "answers": ["claxton", "nic claxton", "nic"]},
    {"slug": "alperen_sengun",          "name": "Alperen Şengün",          "answers": ["sengun", "alperen sengun", "alperen"]},
    {"slug": "lamelo_ball",             "name": "LaMelo Ball",             "answers": ["lamelo", "lamelo ball", "melo ball"]},
    {"slug": "josh_giddey",             "name": "Josh Giddey",             "answers": ["giddey", "josh giddey", "josh"]},
    {"slug": "herbert_jones",           "name": "Herbert Jones",           "answers": ["herb jones", "jones", "herb"]},
    {"slug": "isaiah_thomas_modern",    "name": "Isaiah Thomas",           "answers": ["isaiah thomas", "it", "isaiah"]},
    {"slug": "kemba_walker",            "name": "Kemba Walker",            "answers": ["kemba", "walker", "kemba walker"]},
    {"slug": "john_wall",               "name": "John Wall",               "answers": ["wall", "john wall"]},
    {"slug": "deron_williams",          "name": "Deron Williams",          "answers": ["deron williams", "deron", "d-will"]},
    {"slug": "rajon_rondo",             "name": "Rajon Rondo",             "answers": ["rondo", "rajon rondo", "rondo"]},
    {"slug": "paul_millsap",            "name": "Paul Millsap",            "answers": ["millsap", "paul millsap", "paul"]},
    {"slug": "andre_iguodala",          "name": "Andre Iguodala",          "answers": ["iguodala", "andre iguodala", "iggy", "andre"]},
    {"slug": "josh_smith",              "name": "Josh Smith",              "answers": ["josh smith", "j smoove", "smith"]},
    {"slug": "rudy_gay",                "name": "Rudy Gay",                "answers": ["rudy gay", "gay", "rudy"]},
    {"slug": "demarcus_cousins",        "name": "DeMarcus Cousins",        "answers": ["cousins", "demarcus cousins", "boogie", "boogie cousins"]},
    {"slug": "goran_dragic",            "name": "Goran Dragić",            "answers": ["dragic", "goran dragic", "the dragon", "goran"]},
    {"slug": "nikola_mirotic",          "name": "Nikola Mirotić",          "answers": ["mirotic", "nikola mirotic"]},
    {"slug": "larry_nance_jr",          "name": "Larry Nance Jr.",         "answers": ["larry nance jr", "larry nance", "nance"]},
    {"slug": "danilo_gallinari",        "name": "Danilo Gallinari",        "answers": ["gallinari", "danilo gallinari", "gallo"]},
    {"slug": "tobias_harris",           "name": "Tobias Harris",           "answers": ["tobias harris", "harris", "tobias"]},
    {"slug": "marcus_smart",            "name": "Marcus Smart",            "answers": ["smart", "marcus smart", "marcus"]},
    {"slug": "brook_lopez",             "name": "Brook Lopez",             "answers": ["lopez", "brook lopez", "brook"]},
    {"slug": "tristan_thompson",        "name": "Tristan Thompson",        "answers": ["tristan thompson", "thompson", "tristan", "tt"]},
    {"slug": "kevin_love",              "name": "Kevin Love",              "answers": ["love", "kevin love"]},
    {"slug": "nikola_vucevic2",         "name": "Nikola Vučević",          "answers": []},
    {"slug": "taj_gibson",              "name": "Taj Gibson",              "answers": ["taj gibson", "gibson", "taj"]},
    {"slug": "reggie_jackson",          "name": "Reggie Jackson",          "answers": ["reggie jackson", "jackson"]},
    {"slug": "michael_beasley",         "name": "Michael Beasley",         "answers": ["beasley", "michael beasley", "b-easy"]},
    {"slug": "ron_artest",              "name": "Ron Artest",              "answers": ["ron artest", "artest", "metta world peace", "metta"]},
    {"slug": "caron_butler_legend",     "name": "Caron Butler",            "answers": []},
    {"slug": "sam_cassell",             "name": "Sam Cassell",             "answers": ["cassell", "sam cassell", "sam"]},
    {"slug": "cj_watson",               "name": "C.J. Watson",             "answers": ["cj watson", "watson"]},
    {"slug": "nene",                    "name": "Nenê",                    "answers": ["nene"]},
]

# De-duplicate by slug, keeping first occurrence; also strip entries with empty answer lists that are intentional fillers
_seen_slugs: set = set()
_deduped: List[Dict] = []
for _p in PLAYERS:
    if _p["slug"] not in _seen_slugs and _p["answers"]:
        _seen_slugs.add(_p["slug"])
        _deduped.append(_p)
PLAYERS = _deduped

# ---------------------------------------------------------------------------
# Image URLs  (NBA.com CDN for modern; Wikipedia Special:FilePath for legends)
# NBA.com: https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png
# Wikipedia: https://en.wikipedia.org/wiki/Special:FilePath/{filename}
# ---------------------------------------------------------------------------

def _nba(player_id: int) -> str:
    return f"https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png"

def _wiki(filename: str) -> str:
    return f"https://en.wikipedia.org/wiki/Special:FilePath/{filename}"

PLAYER_IMAGE_URLS: Dict[str, str] = {
    # ── Current/Recent Stars (NBA.com CDN) ───────────────────────────────
    "lebron_james":             _nba(2544),
    "stephen_curry":            _nba(201939),
    "kevin_durant":             _nba(201142),
    "giannis_antetokounmpo":    _nba(203507),
    "kawhi_leonard":            _nba(202695),
    "james_harden":             _nba(201935),
    "russell_westbrook":        _nba(201566),
    "anthony_davis":            _nba(203076),
    "kyrie_irving":             _nba(202681),
    "damian_lillard":           _nba(203081),
    "joel_embiid":              _nba(203954),
    "nikola_jokic":             _nba(203999),
    "luka_doncic":              _nba(1629029),
    "ja_morant":                _nba(1629630),
    "zion_williamson":          _nba(1629627),
    "trae_young":               _nba(1630169),
    "devin_booker":             _nba(1626164),
    "paul_george":              _nba(202331),
    "jimmy_butler":             _nba(202710),
    "jayson_tatum":             _nba(1628369),
    "jaylen_brown":             _nba(1627759),
    "bam_adebayo":              _nba(1628389),
    "donovan_mitchell":         _nba(1628378),
    "deaaron_fox":              _nba(1628368),
    "darius_garland":           _nba(1629636),
    "tyler_herro":              _nba(1629625),
    "shai_gilgeous_alexander":  _nba(1628983),
    "karl_anthony_towns":       _nba(1626157),
    "julius_randle":            _nba(203944),
    "rudy_gobert":              _nba(203497),
    "draymond_green":           _nba(203110),
    "klay_thompson":            _nba(202691),
    "chris_paul":               _nba(101108),
    "bradley_beal":             _nba(203078),
    "cj_mccollum":              _nba(203468),
    "pascal_siakam":            _nba(1627783),
    "andrew_wiggins":           _nba(203952),
    "jrue_holiday":             _nba(201950),
    "zach_lavine":              _nba(203897),
    "ben_simmons":              _nba(1627732),
    "anthony_edwards":          _nba(1630162),
    "cade_cunningham":          _nba(1630595),
    "evan_mobley":              _nba(1630596),
    "scottie_barnes":           _nba(1630567),
    "franz_wagner":             _nba(1630532),
    "jaren_jackson_jr":         _nba(1628991),
    "brandon_ingram":           _nba(1627742),
    "lonzo_ball":               _nba(1628366),
    "khris_middleton":          _nba(203114),
    "victor_wembanyama":        _nba(1641705),
    "paolo_banchero":           _nba(1631094),

    # ── 2000s–2010s Era (NBA.com CDN) ────────────────────────────────────
    "dwyane_wade":              _nba(2548),
    "carmelo_anthony":          _nba(2546),
    "chris_bosh":               _nba(2547),
    "dwight_howard":            _nba(2730),
    "pau_gasol":                _nba(2200),
    "tony_parker":              _nba(2225),
    "manu_ginobili":            _nba(1938),
    "derrick_rose":             _nba(201565),
    "blake_griffin":            _nba(201933),
    "yao_ming":                 _nba(2397),
    "chauncey_billups":         _wiki("Chauncey_Billups.jpg"),
    "vince_carter":             _nba(1713),
    "tracy_mcgrady":            _nba(1736),
    "grant_hill":               _nba(1680),
    "anfernee_hardaway":        _nba(1748),
    "amare_stoudemire":         _nba(2405),
    "gilbert_arenas":           _nba(2772),
    "lamar_odom":               _nba(2403),
    "stephon_marbury":          _nba(1715),
    "peja_stojakovic":          _nba(2208),
    "shawn_kemp":               _nba(874),
    "baron_davis":              _nba(1884),
    "mitch_richmond":           _wiki("Mitch_Richmond.jpg"),
    "latrell_sprewell":         _nba(818),
    "allan_houston":            _nba(960),
    "gary_payton":              _nba(756),
    "reggie_miller":            _nba(670),
    "alonzo_mourning":          _nba(766),
    "jason_kidd":               _nba(786),
    "steve_nash":               _nba(959),
    "rasheed_wallace":          _nba(955),
    "ben_wallace":              _nba(2216),
    "richard_hamilton":         _nba(2054),
    "mike_bibby":               _nba(1717),
    "dirk_nowitzki":            _wiki("Dirk_Nowitzki.jpg"),
    "elton_brand":              _nba(1726),
    "caron_butler":             _nba(2404),
    "antawn_jamison":           _nba(1714),
    "jermaine_oneal":           _nba(952),
    "damon_stoudamire":         _nba(932),
    "glen_rice":                _nba(668),
    "allen_iverson":            _nba(947),
    "ray_allen":                _nba(951),
    "paul_pierce":              _nba(1718),
    "kevin_garnett":            _nba(708),
    "scottie_pippen":           _nba(966),
    "dennis_rodman":            _nba(953),
    "dominique_wilkins":        _nba(369),
    "isiah_thomas":             _nba(267),
    "clyde_drexler":            _nba(184),
    "david_robinson":           _nba(400),
    "hakeem_olajuwon":          _nba(165),
    "charles_barkley":          _nba(787),
    "patrick_ewing":            _nba(121),
    "john_stockton":            _nba(304),
    "karl_malone":              _nba(252),
    "joe_dumars":               _nba(120),
    "sam_cassell":              _nba(789),
    "kevin_johnson":            _nba(536),
    "vin_baker":                _nba(892),
    "antonio_mcdyess":          _nba(1019),
    "jerry_stackhouse":         _wiki("Jerry_Stackhouse.jpg"),
    "steve_francis":            _wiki("Steve_Francis.jpg"),
    "jason_williams":           _nba(1732),
    "luol_deng":                _nba(2736),
    "joakim_noah":              _nba(201149),
    "nikola_vucevic":           _nba(202696),
    "serge_ibaka":              _nba(201586),
    "lou_williams":             _nba(2595),
    "jamal_murray":             _nba(1627750),
    "michael_porter_jr":        _nba(1629008),
    "domantas_sabonis":         _nba(1627734),
    "myles_turner":             _nba(1626167),
    "al_horford":               _nba(201143),
    "kyle_lowry":               _nba(200768),
    "demarcus_cousins":         _nba(202326),
    "goran_dragic":             _nba(201609),
    "danilo_gallinari":         _nba(201568),
    "tobias_harris":            _nba(202699),
    "marcus_smart":             _nba(203935),
    "brook_lopez":              _nba(201572),
    "tristan_thompson":         _nba(202684),
    "kevin_love":               _nba(201567),
    "deron_williams":           _nba(101114),
    "rajon_rondo":              _nba(200765),
    "paul_millsap":             _nba(200794),
    "andre_iguodala":           _nba(2738),
    "rudy_gay":                 _nba(200752),
    "ron_artest":               _nba(2183),
    "marc_gasol":               _nba(201188),
    "isaiah_thomas_modern":     _nba(202738),
    "kemba_walker":             _nba(202689),
    "john_wall":                _nba(202322),
    "dillon_brooks":            _nba(1628415),
    "terry_rozier":             _nba(1626179),
    "mikal_bridges":            _nba(1628969),
    "lamelo_ball":              _nba(1630163),
    "josh_giddey":              _nba(1630581),
    "alperen_sengun":           _nba(1630578),
    "nic_claxton":              _nba(1629651),
    "herbert_jones":            _nba(1630560),
    "nikola_mirotic":           _nba(1626196),
    "reggie_jackson":           _nba(203490),
    "jose_calderon":            _nba(101181),
    "josh_smith":               _nba(2748),
    "taj_gibson":               _nba(201971),
    "michael_beasley":          _nba(201166),
    "larry_nance_jr":           _nba(1626204),
    "nene":                     _nba(2413),
    "shareef_abdur_rahim":      _nba(973),
    "cuttino_mobley":           _nba(1888),
    "wally_szczerbiak":         _nba(1896),
    "mike_miller":              _nba(2038),
    "pao_gasol2":               _wiki("Marc_Gasol.jpg"),

    # ── 70s–80s & All-Time Legends (Wikipedia) ───────────────────────────
    "michael_jordan":           _wiki("Michael_Jordan_in_2014.jpg"),
    "kobe_bryant":              _wiki("Kobe_Bryant_2014.jpg"),
    "shaquille_oneal":          _wiki("Shaquille_O%27Neal_2.jpg"),
    "tim_duncan":               _wiki("Tim_Duncan.jpg"),
    "magic_johnson":            _wiki("Magic_johnson_2.jpg"),
    "larry_bird":               _wiki("Larry_Bird.jpg"),
    "kareem_abdul_jabbar":      _wiki("Kareem_Abdul-Jabbar.jpg"),
    "julius_erving":            _wiki("Julius_Erving.jpg"),
    "moses_malone":             _wiki("Moses_Malone.jpg"),
    "oscar_robertson":          _wiki("Oscar_Robertson.jpg"),
    "jerry_west":               _wiki("Jerry_West.jpg"),
    "elgin_baylor":             _wiki("Elgin_Baylor.jpg"),
    "bill_russell":             _wiki("Bill_Russell.jpg"),
    "wilt_chamberlain":         _wiki("Wilt_Chamberlain.jpg"),
    "pete_maravich":            _wiki("Pete_Maravich.jpg"),
    "george_gervin":            _wiki("George_Gervin.jpg"),
    "nate_archibald":           _wiki("Nate_Archibald.jpg"),
    "bob_mcadoo":               _wiki("Bob_McAdoo.jpg"),
    "elvin_hayes":              _wiki("Elvin_Hayes.jpg"),
    "dan_issel":                _wiki("Dan_Issel.jpg"),
    "artis_gilmore":            _wiki("Artis_Gilmore.jpg"),
    "dave_cowens":              _wiki("Dave_Cowens.jpg"),
    "bill_walton":              _wiki("Bill_Walton.jpg"),
    "rick_barry":               _wiki("Rick_Barry.jpg"),
    "bob_pettit":               _wiki("Bob_Pettit.jpg"),
    "walt_frazier":             _wiki("Walt_Frazier.jpg"),
    "willis_reed":              _wiki("Willis_Reed.jpg"),
    "dave_debusschere":         _wiki("Dave_DeBusschere.jpg"),
    "billy_cunningham":         _wiki("Billy_Cunningham.jpg"),
    "spencer_haywood":          _wiki("Spencer_Haywood.jpg"),
    "gail_goodrich":            _wiki("Gail_Goodrich.jpg"),
    "hal_greer":                _wiki("Hal_Greer.jpg"),
    "jack_sikma":               _wiki("Jack_Sikma.jpg"),
    "sid_moncrief":             _wiki("Sidney_Moncrief.jpg"),
    "calvin_murphy":            _wiki("Calvin_Murphy.jpg"),
    "bob_cousy":                _wiki("Bob_Cousy.jpg"),
    "bill_sharman":             _wiki("Bill_Sharman.jpg"),
    "dolph_schayes":            _wiki("Dolph_Schayes.jpg"),
    "george_mikan":             _wiki("George_Mikan.jpg"),
    "bob_lanier":               _wiki("Bob_Lanier.jpg"),
    "paul_arizin":              _wiki("Paul_Arizin.jpg"),
    "tom_heinsohn":             _wiki("Tom_Heinsohn.jpg"),
    "lenny_wilkens":            _wiki("Lenny_Wilkens.jpg"),
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
        Retries on HTTP 429 with Retry-After backoff."""
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
    # Setup — download all images
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

        connector = aiohttp.TCPConnector(limit=10)
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
                            f"✅ Downloaded: {ok}  |  ❌ Failed: {len(failed)}"
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
        result_embed = discord.Embed(
            title="✅  Setup Complete!",
            colour=0x00CC44,
        )
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
                value=(
                    "To wipe everything and retry from scratch: "
                    "`[p]nba clearimages` then `[p]nba setup`."
                ),
                inline=False,
            )
        result_embed.add_field(
            name="Next Step",
            value="Use `[p]nba start` to start a game!",
            inline=False,
        )
        result_embed.set_footer(text="jaffar21")
        await status_msg.edit(embed=result_embed)

    # ------------------------------------------------------------------
    # Start
    # ------------------------------------------------------------------

    @nba.command(name="start")
    @commands.guild_only()
    async def nba_start(self, ctx: commands.Context, target: int = 10):
        """Start an NBA player photo quiz. First to the target score wins!

        Optional: set a custom target (default is 10).
        Example: `[p]nba start 15`
        """
        guild_id = ctx.guild.id

        if guild_id in self._games:
            await ctx.send("A game is already running! Use `[p]nba stop` to end it.")
            return

        players = self._available_players()
        if len(players) < 5:
            await ctx.send(
                "Not enough player images downloaded. Run `[p]nba setup` first!"
            )
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
                "Type the player's name to score — first name, last name, or nickname all work.\n\n"
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
        game = self._games[guild_id]
        embed = self._build_scoreboard(game)
        await ctx.send(embed=embed)

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
        """Delete all locally cached player images so setup re-downloads them fresh.

        Use this followed by `[p]nba setup` to get a clean install.
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
            f"🗑️ Cleared **{deleted}** cached player images.\n"
            f"Run `[p]nba setup` to re-download everything fresh."
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
            lines = []
            medals = ["🥇", "🥈", "🥉"]
            for rank, (uid, pts) in enumerate(sorted_scores):
                medal = medals[rank] if rank < 3 else f"#{rank+1}"
                lines.append(f"{medal} <@{uid}> — **{pts} pt{'s' if pts != 1 else ''}**")
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

        embed = discord.Embed(
            title="🏀  Who is this NBA player?",
            description=f"⏱️ **{ROUND_TIME} seconds** — type your answer!",
            colour=0x1D428A,
        )
        embed.set_footer(text="jaffar21")

        try:
            file = discord.File(str(img_path), filename=f"{player['slug']}.{img_path.suffix.lstrip('.')}")
            embed.set_image(url=f"attachment://{player['slug']}.{img_path.suffix.lstrip('.')}")
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
        if not game:
            return

        if reason == "stopped":
            return

        embed = self._build_scoreboard(game)
        embed.title = "🏆  Game Over — Final Scores"
        if reason == "winner":
            scores = game["scores"]
            if scores:
                winner_id = max(scores, key=scores.get)
                embed.description = (
                    f"🎉 <@{winner_id}> wins with **{scores[winner_id]} points**!\n\n"
                    + (embed.description or "")
                )
        await channel.send(embed=embed)

    # ------------------------------------------------------------------
    # Message listener
    # ------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if not message.guild:
            return

        guild_id = message.guild.id
        game = self._games.get(guild_id)
        if not game:
            return
        if message.channel.id != game["channel_id"]:
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
