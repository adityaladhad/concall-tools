import re
from collections import namedtuple

import fitz
import nltk

from .stop_words import STOP_WORDS

Speaker = namedtuple("Speaker", ["name", "firm"])


def _get_fingerprint(name):
    """
    returns a generic name without prefixes
    it helps match: "Mr. Praveen Arora" and "Praveen Arora"
    it does by return a normalized version: praveenarora
    """
    original_name = name.replace("\n", " ").strip()
    NON_WORD = re.compile(r"[\W]+")
    name = NON_WORD.sub(" ", original_name).lower()

    removals = [
        r"^the ",
        r" and ",
        r"^mr ",
        r"^mrs ",
        r"^ms ",
    ]
    for removal in removals:
        name = re.sub(removal, "", name)

    # join everything
    name = name.replace(" ", "")
    return name


def _extract_name(subjtext):
    """
    the extract_rels function returns a string with the POS tags in it
    this function extracts the name from the string
    """
    return " ".join(
        nltk.tag.str2tuple(word)[0] for word in subjtext.split(" ")
    )


def _get_relations(named_tags, subjclass, objclass):
    """
    Extract relations between two named entities
    """
    FROM = re.compile(r".*\bfrom\b.*")
    relations = nltk.sem.extract_rels(
        subjclass, objclass, named_tags, pattern=FROM
    )
    speaker_firm = {}
    for relation in relations:
        speaker = _get_fingerprint(_extract_name(relation["subjtext"]))
        firm = _extract_name(relation["objtext"])
        if speaker not in speaker_firm:
            speaker_firm[speaker] = firm
    return speaker_firm


def _extract_relations(named_tags):
    """
    Extract name fo firm from which the speaker is associated
    """
    # Relationship are in form of PERSON from ORGANIZATION
    speaker_firm = _get_relations(named_tags, "PERSON", "ORGANIZATION")
    # sometimes, the named entity tags ORGANIZATION as PERSON
    # thus try PERSON from PERSON if not available
    for speaker, firm in _get_relations(
        named_tags, "PERSON", "PERSON"
    ).items():
        if speaker not in speaker_firm:
            speaker_firm[speaker] = firm
    return speaker_firm


def _print_portion(named_tags, substr):
    conll_tags = nltk.chunk.util.tree2conlltags(named_tags)
    all_tokens = [w for w, _t, _iob in conll_tags]
    look_tokens = nltk.word_tokenize(substr)

    for i in range(len(all_tokens) - len(look_tokens) + 1):
        portion = all_tokens[i : i + len(look_tokens)]
        if portion == look_tokens:
            print("PORTION:", conll_tags[i : i + len(look_tokens)])
            return


def _extract_speakers_two(doc):
    text = ""
    for i, page in enumerate(doc):
        page_text = page.get_text("text")
        # a transcript page would have at-least 100 words
        word_count = len(page_text.split())
        if word_count < 150 and (i != len(doc) - 1):
            continue
        text += "\n" + page_text

    # tokenize the text and recognize named entities
    named_tags = nltk.ne_chunk(nltk.pos_tag(nltk.word_tokenize(text)))

    speaker_firm = _extract_relations(named_tags)

    # extract all speakers
    # by looping over all named entities
    # an entity is a speaker
    # if their name is the first word of any line
    people = []
    for entity in named_tags:
        if isinstance(entity, nltk.tree.Tree) and entity.label() == "PERSON":
            person = " ".join(leaf[0] for leaf in entity.leaves())
            if person.lower() in STOP_WORDS:
                continue
            if person not in people:
                people.append(person)

    speakers = []
    lines = nltk.tokenize.sent_tokenize(text)
    for person in people:
        speaker_lines = [line for line in lines if line.startswith(person)]
        if speaker_lines:
            print("PERSON:", person)
            _print_portion(named_tags, speaker_lines[0])
            fp = _get_fingerprint(person)
            speaker = Speaker(name=person, firm=speaker_firm.get(fp, None))
            speakers.append(speaker)
    return speakers


def extract_speakers(pdf_name):
    doc = fitz.open(pdf_name)
    speakers = _extract_speakers_two(doc)
    return speakers
