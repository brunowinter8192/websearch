# INFRASTRUCTURE
import re

STOPWORDS = {
    "a","about","above","after","again","all","also","although","among","an","and","any",
    "are","as","at","be","because","been","before","being","between","both","but","by",
    "can","could","did","do","does","doing","during","each","even","ever","for","from",
    "get","got","had","has","have","having","he","her","here","him","his","how","if",
    "in","into","is","it","its","itself","just","like","may","me","might","more","most",
    "much","my","nor","not","now","of","off","on","or","other","our","out","own","per",
    "s","shall","she","should","since","so","some","such","t","than","that","the","their",
    "them","then","there","these","they","this","those","through","to","too","under","up",
    "us","very","was","we","were","what","when","where","which","while","who","will",
    "with","would","you","your","re","ve","ll","d","m","no","use",
    "aber","alle","allem","allen","aller","alles","als","also","am","an","ander","andere",
    "anderen","anderer","anderes","auf","aus","bei","bin","bis","bist","da","damit","dann",
    "das","dass","dem","den","denn","der","des","dessen","die","dies","diese","diesem",
    "diesen","dieser","dieses","doch","dort","du","durch","ein","eine","einem","einen",
    "einer","eines","er","es","etwas","fur","gegen","gibt","hat","hatte","haben","hier",
    "hin","hinter","ich","im","in","ist","ja","jede","jedem","jeden","jeder","jedes",
    "jetzt","kann","kein","keine","konnte","mal","man","mehr","mein","mit","nach","nicht",
    "noch","nun","nur","ob","oder","ohne","schon","sehr","seit","sich","sie","sind","so",
    "soll","sondern","uber","um","und","uns","unter","viel","vom","von","vor","war","was",
    "weil","wenn","werden","wie","will","wir","wird","wo","wurde","zum","zur","zu",
}

_BLOAT = [
    ("B1_url_breadcrumb",   re.compile(r'›')),
    ("B2_read_more",        re.compile(r'\bRead more\b')),
    ("B3_web_results",      re.compile(r'^Web results')),
    ("B4_featured_snippet", re.compile(r'^Featured snippet from the web')),
    ("B5_social_proof",     re.compile(r'\d[\d,.]*[Kk]?\+? *(likes|comments|answers|posts) *·')),
    ("B6_scholar_ellipsis", re.compile(r'^…\s|\s…\s|…$')),
    ("B7_mojeek_nav_dump",  re.compile(r'^\.\.\. .{5,150} \.\.\.$')),
    ("B8_meta_html_entity", re.compile(r'&[a-z]+;|&#\d+;')),
    ("B9_meta_tag_noise",   re.compile(r'Tagged with [\w, ]+\.?$')),
    ("B10_jats_xml",        re.compile(r'<jats:|<ns\d+:')),
]


# FUNCTIONS

def detect_bloat(text: str) -> set[str]:
    return {name for name, pat in _BLOAT if pat.search(text)}


def _strip_doubled_prefix(text: str) -> str:
    if len(text) < 60:
        return text
    head = text[:300]
    best_cut = 0
    for L in (100, 70, 50, 30):
        if len(head) < 2 * L:
            continue
        for start in range(0, min(len(head) - 2 * L, 100)):
            chunk = head[start:start + L]
            second = head.find(chunk, start + L)
            if 0 < second and second + L <= len(head):
                cut = second + L
                if cut > best_cut:
                    best_cut = cut
    return text[best_cut:] if best_cut else text


def strip_bloat(text: str) -> str:
    text = _strip_doubled_prefix(text)
    text = re.sub(r'^Web results', '', text)
    text = re.sub(r'^Featured snippet from the web', '', text)
    text = re.sub(r'^\s*·\s*Translate this page', '', text)
    text = re.sub(r'\bRead more.*', '', text)
    text = re.sub(r'\d[\d,.]*[Kk]?\+? *(likes|comments|answers|posts) *·[^\n]*', '', text)
    text = re.sub(r'\S*›\S*', '', text)
    text = re.sub(r'\d{1,2} \w{3,9} \d{4} — ', '', text)
    text = re.sub(r'&[a-z]+;|&#\d+;', '', text)
    text = re.sub(r'Tagged with [\w, ]+\.?$', '', text)
    text = re.sub(r'<[^>]+>', ' ', text)
    return ' '.join(text.split())


def lexical_density(text: str) -> float:
    words = re.findall(r'\b[a-zA-ZäöüÄÖÜßé]{3,}\b', text.lower())
    if not words:
        return 0.0
    unique_content = {w for w in words if w not in STOPWORDS}
    return len(unique_content) / len(words)
