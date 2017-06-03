# coding=utf-8
# Author: Nic Wolfe <nic@wolfeden.ca>
#
# This file is part of Medusa.
#
# Medusa is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Medusa is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Medusa. If not, see <http://www.gnu.org/licenses/>.

import fnmatch
import os
import re

from six import string_types

from medusa import app, logger

from medusa.name_parser.parser import InvalidNameException, InvalidShowException, NameParser


resultFilters = [
    "(dir|sub|nfo)fix",
    "(?<!shomin.)sample",
    "(dvd)?extras",
]

if hasattr('General', 'ignore_und_subs') and app.IGNORE_UND_SUBS:
    resultFilters.append("sub(bed|ed|pack|s)")

if hasattr('General', 'ignored_subs_list') and app.IGNORED_SUBS_LIST:
    resultFilters.append("(" + app.IGNORED_SUBS_LIST.replace(",", "|") + ")sub(bed|ed|s)?")


def contains_words(item, words, strict=True):
    """
    Yield words that are contained in an item.

    :param item: item to search for words
    :param words: iterable of words to search for in item
    :param strict: exclude substring matches
      If strict find exact existence of a word in the item but exclude matches
      where the word is part of a substring.  For example `word` would not
      match 'words' or 'word1'.
    """
    def _strict(_word):
        # Use a regex to make sure the match is not part of a substring
        pattern = r'(^|[\W_]){word}($|[\W_])'.format(word=_word)
        return re.search(pattern, item, re.I)

    def _lenient(_word):
        # Use string.__contains__ for a quick lenient test
        return _word in item

    # select strict or lenient method for the test
    item_contains = _strict if strict else _lenient

    for word in words:
        if item_contains(word):
                yield word


def contains_at_least_one_word(name, words):
    """
    Filter out results based on filter_words.

    :param name: name to check
    :param words: string of words separated by a ',' or list of words
    :return: False if the name doesn't contain any word of words list, or the found word from the list.
    """
    if not (name and words):
        return False

    if isinstance(words, string_types):
        words = words.split(',')
    items = [(re.compile(r'(^|[\W_])%s($|[\W_])' % word.strip(), re.I), word.strip()) for word in words]
    for regexp, word in items:
        if regexp.search(name):
            # subs_words = '.dub.' or '.dksub.' or else
            subs_word = regexp.search(name).group(0)
            # If word is a regex like "dub(bed)?" or "sub(bed|ed|pack|s)"
            # then return just the matched word: "dub" and not full regex
            if word in resultFilters:
                return subs_word.replace(".", "")
            else:
                return word

    return False


def filter_bad_releases(name, parse=True):
    """
    Filter out non-english and just all-around stupid releases by comparing them
    to the resultFilters contents.

    :param name: the release name to check
    :return: True if the release name is OK, False if it's bad.
    """
    try:
        if parse:
            NameParser().parse(name)
    except InvalidNameException as error:
        logger.log(u"{}".format(error), logger.DEBUG)
        return False
    except InvalidShowException:
        pass

    # if any of the bad strings are in the name then say no
    word = contains_at_least_one_word(name, resultFilters)
    if word:
        logger.log(u"Unwanted scene release: {0}. Contains unwanted word: {1}. Ignoring it".format(name, word), logger.DEBUG)
        return False
    return True


def determine_release_name(dir_name=None, nzb_name=None):
    """Determine a release name from an nzb and/or folder name."""

    if nzb_name is not None:
        logger.log(u"Using nzb_name for release name.")
        return nzb_name.rpartition('.')[0]

    if dir_name is None:
        return None

    # try to get the release name from nzb/nfo
    file_types = ["*.nzb", "*.nfo"]

    for search in file_types:

        reg_expr = re.compile(fnmatch.translate(search), re.IGNORECASE)
        files = [file_name for file_name in os.listdir(dir_name) if
                 os.path.isfile(os.path.join(dir_name, file_name))]

        results = [f for f in files if reg_expr.search(f)]

        if len(results) == 1:
            found_file = os.path.basename(results[0])
            found_file = found_file.rpartition('.')[0]
            if filter_bad_releases(found_file):
                logger.log(u"Release name (" + found_file + ") found from file (" + results[0] + ")")
                return found_file.rpartition('.')[0]

    # If that fails, we try the folder
    folder = os.path.basename(dir_name)
    if filter_bad_releases(folder):
        # NOTE: Multiple failed downloads will change the folder name.
        # (e.g., appending #s)
        # Should we handle that?
        logger.log(u"Folder name (" + folder + ") appears to be a valid release name. Using it.", logger.DEBUG)
        return folder

    return None
