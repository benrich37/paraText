import math


hex_chars = "0123456789ABCDEF"

def str_not(string):
    """ Function which can perform 'not(...)' on strings (because for some reason
           bool(any non-empty string) -> True)
    :param string: Either "True" or "False"
    :return:
    """
    return not(string == "True")


def make_darker(hex_color, dark_fac=2):
    """Function to decrease intensity of each color channel to make darker

    Parameters
    ----------
    hex_color: hex color code as a string (#RRGGBB)

    dark_fac: integer factor to decrease each color channel by
              default value is 2

    Returns
    -------
    new_hex_color
        string with new hex color code
    """
    if hex_color[0] != "#":
        # if it doesn't start with # it's probably not a hex color string
        raise ValueError

    else:
        # split each channel into elements of a list
        hex_i = [hex_color[1:3], hex_color[3:5], hex_color[5:]]

        # hold the channel values in base 10
        dec_i = []
        for he in hex_i:
            dec_i.append(short_hex_to_dec(he))

        # decrease each color channel value by half
        dec_changed = []
        for de in dec_i:
            dec_changed.append(math.floor(de/dark_fac))

        # convert back to base 16
        hex_f = []
        for de in dec_changed:
            num = int(math.floor(de))
            full_hex = hex(num)
            full_hex_str = str(full_hex)
            short_hex = full_hex[full_hex_str.index('x') + 1:]
            hex_f.append(short_hex)

    new_hex_color = "#" + hex_f[0] + hex_f[1] + hex_f[2]

    return new_hex_color


def get_short_hex(num):
    """Function to convert to hex and remove '0x' from hex value

    Parameters
    ----------
    num: number in base 10

    Returns
    -------
    short_hex
        cleaned up number in base 16
    """
    num = int(math.floor(num))
    full_hex = str(hex(num))
    short_hex = full_hex[full_hex.index('x') + 1:]

    return short_hex


def short_hex_to_dec(short_hex):
    """Function to convert hex number to base 10

    Parameters
    ----------
    short_hex: A number in base 16 (hexadecimal)

    Returns
    -------
    return_sum
        the same number in base 10
    """
    # converts a number in hex to its respective number in base 10
    digs = len(short_hex)
    return_sum = 0
    for i in range(digs):
        dig_dec = hex_chars.index(short_hex[i])*(16**(digs-1-i))
        return_sum += dig_dec
    return return_sum


def char_idx_to_ints(char_idx):
    """Returns the integers in a char index string

    Parameters
    ----------
    char_idx: a character index string
              character index string containing the line and column indexes

    Returns
    -------
    line_idx
        integer contained in first position of char_idx

    col_idx
        integer contained in the second position of char_idx
    """
    split = char_idx.index('.')
    line_idx = int(char_idx[0:split])
    col_idx = int(char_idx[split + 1:])
    return line_idx, col_idx


def ints_to_char_idx(line_idx, col_idx):
    """Generates char_idx as a string

    Parameters
    ----------
    line_idx: int for line number

    col_idx: int for column number

    Returns
    -------
    char_idx
        respective char index string
    """
    # just mushes them back together a string for use with tkinter
    char_idx = str(line_idx) + '.' + str(col_idx)
    return char_idx


def add_to_char_idx(char_idx, mod_int, add=True):
    """Add or remove a number to the col idx

    Parameters
    ----------
    char_idx: string for character index

    mod_int: integer to add or subtract from col idx

    add: bool
         True if adding, False if subtracting

    Returns
    -------
    new_char_idx
        string with modified char indx
    """
    line_idx, col_idx = char_idx_to_ints(str(char_idx))
    if add:
        new_col_idx = col_idx + mod_int
    else:
        new_col_idx = col_idx - mod_int
    new_char_idx = ints_to_char_idx(line_idx, new_col_idx)
    return new_char_idx


def del_fn(widg):
    """ Simple function that we can call easily instead of having to construct a bunch of
    lambda functions

    :param (Widget) widg: The widget we wish to delete
    :return         None:
    """
    widg.destroy()


def return_matches(twidget, pattern):
    """
    :param       (Widget) twidget: Text-containing widget we wish to search through
    :param          (Str) pattern: Text-pattern we wish to search for
    :return (list of str) results: A list of char indices where each element is either the beginning
                                    or ending char index of where the pattern appears
    """
    results = []
    over = False
    last_char_idx = '1.0'
    while not over:
        resulti = twidget.search(pattern, last_char_idx, stopindex=twidget.index('end'))
        if len(resulti) == 0:
            over = True
        else:
            last_char_idx = add_to_char_idx(resulti, 1)
            results.append(resulti)
    return results


def get_text_by_tagname(twidget, tagname):
    """
    :param    (Widget) twidget: Text-widget that (hopefully) has some text tagged by the tagname
    :param       (str) tagname: The name of the tag we want to look for
    :return (str) current_text: The text currently under the tag
    """
    bounds = twidget.tag_ranges(tagname)
    if len(bounds) > 2:
        print('only returning first tagged section')
    current_text = twidget.get(bounds[0], bounds[1])
    return current_text


def insert_at_end(twidget, end_char_idx, insert_text):
    """ This function just inserts a word at the end of a word and then deletes
    the final character, ie if we want to insert 'Word' into 'Sentence', the
    end result would be 'SentencWord' - By inserting within the word and THEN
    deleting that last character, tkinter doesn't delete the existing tag


    :param   (Widget) twidget: Text widget we're operating on
    :param (str) end_char_idx: char idx of where we're going to insert the new word
    :param  (str) insert_text: Text we're inserting
    :return              None: (only in-place operations)
    """
    text_len = len(insert_text)
    insert_char_idx = add_to_char_idx(str(end_char_idx), 1, add=False)
    cut_text = twidget.get(insert_char_idx)
    twidget.insert(insert_char_idx, insert_text)
    del_char_idx = add_to_char_idx(str(end_char_idx), text_len - 1, add=True)
    twidget.delete(del_char_idx)
    twidget.insert(insert_char_idx, cut_text)


def insert(twidget, tagname, newtext):
    """
    :param (Widget) twidget: Text widget we're operating on
    :param    (str) tagname: tagname who's text selection we're inserting into
    :param    (str) newtext: text we're inserting
    :return            None:
    """
    init_char_idx_bounds = twidget.tag_ranges(tagname)
    insert_at_end(twidget, init_char_idx_bounds[1], newtext)


def replace(twidget, tagname, newtext):
    """
    :param (Widget) twidget: Text-widget we're operating on
    :param    (str) tagname: tagname who's text we're replacing
    :param    (str) newtext: Text we're replacing with
    :return            None:
    """
    init_char_idx_bounds = twidget.tag_ranges(tagname)
    if len(init_char_idx_bounds) > 2:
        # If this ever gets called, then the tagname convention has failed and it created
        # the same child_rep_tag twice for separate children
        print('too many matches, no replacements done')
        return None
    insert(twidget, tagname, newtext)
    twidget.delete(init_char_idx_bounds[0], init_char_idx_bounds[1])


def append_no_dup(item, list):
    """
    :param  item: Item to add
    :param  list: List to add to
    :return None: (in-place operations only)
    """
    # Simple function to add an item to a list iff its not already in the list
    # (used most commonly for appending options)
    if not item in list:
        list.append(item)
