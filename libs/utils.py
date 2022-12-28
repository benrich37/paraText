import math
before = 'before'
after = 'after'
same = 'same'


def str_not(string):
    """Performs 'not(...)' on strings
    :param (str) string: either 'True' or 'False'
    :return (bool)):
    """
    return not (string == "True")


def make_darker(hex_color, dark_fac=2):
    """Function to decrease intensity of each color channel to make darker
    :param (str) hex_color: hex color code as a string (#RRGGBB)
    :param (int) dark_fac: integer factor to decrease each color channel by
                     default value is 2
    :return (str) new_hex_color: string with new hex color code
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
            dec_changed.append(math.floor(de / dark_fac))

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
    :param (float or int) num: number in base 10
    :return (str) short_hex: cleaned up number in base 16
    """
    num = int(math.floor(num))
    full_hex = str(hex(num))
    short_hex = full_hex[full_hex.index('x') + 1:]

    return short_hex


def short_hex_to_dec(short_hex):
    """Function to convert hex number to base 10
    :param (str) short_hex: A number in base 16 (hexadecimal)
    :return (float) return_sum: the same number in base 10
    """
    hex_chars = "0123456789ABCDEF"

    # converts a number in hex to its respective number in base 10
    digs = len(short_hex)
    return_sum = 0
    for i in range(digs):
        dig_dec = hex_chars.index(short_hex[i]) * (16 ** (digs - 1 - i))
        return_sum += dig_dec
    return return_sum

def compare_car_idcs_step2(c1, c2):
    if c1 == c2:
        return same
    elif c1 < c2:
        return after
    else:
        return before

def compare_car_idcs_step1(car_1, car_2):
    l1, c1 = char_idx_to_ints(car_1)
    l2, c2 = char_idx_to_ints(car_2)
    if l1 == l2:
        return compare_car_idcs_step2(c1, c2)
    else:
        if l1 < l2:
            return after
        else:
            return before

def compare_care_idcs(car_1, car_2):
    # Add error handling or whatever
    return compare_car_idcs_step1(car_1, car_2)

def conflict_bounds(cars_1, cars_2):
    compare_first = compare_care_idcs(cars_1[0], cars_2[0])
    compare_last = compare_care_idcs(cars_1[1], cars_2[1])
    if compare_first == before:
        if compare_last == after:
            return True
        else:
            return False
    if compare_first == same:
        return True
    if compare_first == after:
        if compare_last == after:
            return False
        else:
            return True





def char_idx_to_ints(char_idx):
    """Returns the integers in a char index string
    :param (str) char_idx: a character index string containing line and col indexes
    :return (int) line_idx: integer contained in first position of char_idx
    :return (int) col_idx: integer contained in the second position of char_idx
    """
    split = char_idx.index('.')
    line_idx = int(char_idx[0:split])
    col_idx = int(char_idx[split + 1:])
    return line_idx, col_idx


def ints_to_char_idx(line_idx, col_idx):
    """Generates char_idx as a string
    :param (int) line_idx: int for line number
    :param (int) col_idx: int for column number
    :return (int) char_idx: respective char index string
    """
    # just mushes them back together a string for use with tkinter
    char_idx = str(line_idx) + '.' + str(col_idx)
    return char_idx


def add_to_char_idx(char_idx, mod_int, add=True):
    """Add or remove a number to the col idx
    :param (str) char_idx: string for character index
    :param (int) mod_int: integer to add or subtract from col idx
    :param (bool) add: True if adding, False if subtracting
    :return (str) new_char_idx: string with modified char indx
    """
    line_idx, col_idx = char_idx_to_ints(str(char_idx))
    if add:
        new_col_idx = col_idx + mod_int
    else:
        new_col_idx = col_idx - mod_int
    new_char_idx = ints_to_char_idx(line_idx, new_col_idx)
    return new_char_idx


def del_fn(widg):
    """Function that destroys a desired widget
    :param (tkinter.Widget) widg: the widget you wish to delete
    :return None:
    """
    widg.destroy()


def return_matches(twidget, pattern):
    """Search for a text pattern in a text-containing widget
    :param (tkinter.Widget) twidget: text-containing widget to search through
    :param (str) pattern: str text pattern to search for
    :return (list[str]) results: list of char indices as strings
                     specifying position of search term
    """
    results = []
    over = False
    last_char_idx = '1.0'
    while not over:
        resulti = twidget.search(pattern, last_char_idx,
                                 stopindex=twidget.index('end'))
        if len(resulti) == 0:
            over = True
        else:
            last_char_idx = add_to_char_idx(resulti, 1)
            results.append(resulti)
    return results


def get_text_by_tagname(twidget, tagname):
    """Search for a family_name name to find text under family_name
    :param (tkinter.Widget) twidget: text-widget that has some text tagged by the tagname
    :param (str) tagname: str name of the family_name you want to look for
    :return (str) current_text: the text currently under the family_name
    """
    bounds = twidget.tag_ranges(tagname)
    if len(bounds) > 2:
        print('only returning first tagged section')
    current_text = twidget.get(bounds[0], bounds[1])
    return current_text


def insert_at_end(twidget, end_char_idx, insert_text):
    """Inserts a word at the end of a word and deletes the final character
    ex: if you want to insert 'Word' into 'Sentence', the end result would be
    'SentencWord' - this way, tkinter doesn't delete the existing family_name
    :param (tkinter.Widget) twidget: text widget you're operating on
    :param (str) end_char_idx: str char idx of where new word will be inserted
    :param (str) insert_text: text you're inserting as an str
    :return None:
    """
    text_len = len(insert_text)
    insert_char_idx = add_to_char_idx(str(end_char_idx), 1, add=False)
    cut_text = twidget.get(insert_char_idx)
    twidget.insert(insert_char_idx, insert_text)
    del_char_idx = add_to_char_idx(str(end_char_idx), text_len - 1, add=True)
    twidget.delete(del_char_idx)
    twidget.insert(insert_char_idx, cut_text)


def insert(twidget, tagname, newtext):
    """Inserts new text into a specific family_name name
    :param (tkinter.Widget) twidget: text widget you're operating on
    :param (str) tagname: tagname whose text selection to insert into as an str
    :param (str) newtext: text to insert as an str
    :return None:
    """
    init_char_idx_bounds = twidget.tag_ranges(tagname)
    insert_at_end(twidget, init_char_idx_bounds[1], newtext)


def replace(twidget, tagname, newtext):
    """Replaces text in a specific family_name name
    :param (tkinter.Widget) twidget: text widget you're operating on
    :param (str) tagname: tagname whose text you're replacing
    :param (str) newtext: text you want to replace with
    :return None:
    """
    init_char_idx_bounds = twidget.tag_ranges(tagname)
    if len(init_char_idx_bounds) > 2:
        # If this ever gets called, then the tagname convention has failed and
        # it created the same child_rep_tag twice for separate children
        print('too many matches, no replacements done')
        return None
    insert(twidget, tagname, newtext)
    twidget.delete(init_char_idx_bounds[0], init_char_idx_bounds[1])


def append_no_dup(item, list):
    """Appends items to a list if item is not already in the list
    :param (any) item: item to add
    :param (list[any]) list: list to add to
    :return None:
    """
    # (used most commonly for appending options)
    if item not in list:
        list.append(item)

def get_bounds_as_strs(bounds):
    output = []
    for i in range(len(bounds)):
        output.append(bounds[i].string)
    return output


def dict_pretty(dict):
    if type(dict) == 'dict':
        return dict_pretty(dict.items())
    # elif type(dict) != 'dict_items':
    #     raise ValueError
    return dict_pretty_handler(dict)

def dict_pretty_handler(dict_items):
    output = ''
    indent = ''
    aslist = list(dict_items)
    for p in aslist:
        return_str, indent = dict_pretty_printer(p, indent)
        output += return_str
    return output

def dict_pretty_printer(item, indent):
    tab = '  '
    if type(item) == str:
        return_str = indent + item + '\n'
    else:
        return_str = indent + '(list)' + '\n'
        indent += tab
        for i in item:
            temp_return_str, temp_indent = dict_pretty_printer(i, indent)
            return_str += temp_indent + temp_return_str
    return return_str, indent



