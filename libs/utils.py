import math

hex_chars = "0123456789ABCDEF"

def make_darker(hex_color, dark_fac=2):
    """ Function which decreases intensity of each color channel to make dark
    :param hex_color: A string signifying a hex color (#RRGGBB, where RR/GG/BB hold 0 -> 256 in base 16)
    :param dark_fac: Factor to decrease each color channel by (ie for dark_fac=2, #101010 turns into #050505")
    :return new_hex_color: String for new hex color
    """
    if hex_color[0] != "#":
        # if it doesn't start with # it's probably not a hex color string
        raise ValueError
    else:
        # split the channels into elements of a list
        hex_i = [hex_color[1:3],hex_color[3:5],hex_color[5:]]
        dec_i = []
        for he in hex_i:
            # hold the channel values in base 10
            dec_i.append(int(short_hex_to_dec(he)))
        dec_changes = []
        for de in dec_i:
            # decrease each color channel by half of the current channel value
            dec_changes.append(math.floor(de/dark_fac))
        dec_f = []
        for i in [0,1,2]:
            # perform the subtraction
            dec_f.append(dec_i[i] - dec_changes[i])
        hex_f = []
        for de in dec_f:
            # convert back to base 16
            hex_f.append(get_short_hex(de))
    new_hex_color = "#" + hex_f[0] + hex_f[1] + hex_f[2]
    return new_hex_color

def get_short_hex(num):
    """
    :param num: a number in base 10
    :return short_hex: a cleaned up number in base 16
    """
    # the built in hex function for some reason has a '0x' at the beginning of the string
    # (ie hex(1) returns '0x1' and hex(255) returns '0xff') so this truncates off the
    # '0x' to get just the actual hex number (ie '1' or 'ff')
    full_hex = str(hex(math.floor(num)))
    short_hex = full_hex[full_hex.index('x') + 1:]
    return short_hex

def short_hex_to_dec(short_hex):
    """
    :param short_hex: A number in base 16
    :return return_sum: The same number in base 10
    """
    # converts a number in hex to its respective number in base 10
    digs = len(short_hex)
    return_sum = 0
    for i in range(digs):
        dig_dec = hex_chars.index(short_hex[i])*(16**(digs-1-i))
        return_sum += dig_dec
    return return_sum

def char_idx_to_ints(char_idx):
    """
    :param char_idx: A character index string
    :return line_idx, col_idx: The integers contained in the char_idx
    """
    # converts a char idx (line number,character number) into invidiual ints from each part
    split = char_idx.index('.')
    line_idx = int(char_idx[0:split])
    col_idx = int(char_idx[split + 1:])
    return line_idx, col_idx

def ints_to_char_idx(line_idx, col_idx):
    """
    :param line_idx: Int for line number
    :param col_idx: Int for column number
    :return char_idx: Respective char index string
    """
    # just mushes them back together a string for use with tkinter
    char_idx = str(line_idx) + '.' + str(col_idx)
    return char_idx

def add_to_char_idx(char_idx, mod_int, add=True):
    """
    :param char_idx: String for character index
    :param mod_int:
    :param add:
    :return:
    """
    # I don't know why I wrote it like this, but this function just adds/subtracts a number from the col idx
    # of a char idx
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

    :param widg: The widget we wish to delete
    :return None:
    """
    widg.destroy()

def return_matches(twidget, pattern):
    """
    :param twidget: Text-containing widget we wish to search through
    :param pattern: Text-pattern we wish to search for
    :return results: A list of char indices where each element is either the beginning
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
    :param twidget: Text-widget that (hopefully) has some text tagged by the tagname
    :param tagname: The name of the tag we want to look for
    :return current_text: The text currently under the tag
    """
    bounds = twidget.tag_ranges(tagname)
    if len(bounds) > 2:
        print('only returning first tagged section')
    current_text = twidget.get(bounds[0], bounds[1])
    return current_text

def insert_at_end(twidget, end_char_idx, insert_text):
    text_len = len(insert_text)
    insert_char_idx = add_to_char_idx(str(end_char_idx), 1, add=False)
    cut_text = twidget.get(insert_char_idx)
    twidget.insert(insert_char_idx, insert_text)
    del_char_idx = add_to_char_idx(str(end_char_idx), text_len - 1, add=True)
    twidget.delete(del_char_idx)
    twidget.insert(insert_char_idx, cut_text)

def insert(twidget, tagname, newtext):
    init_char_idx_bounds = twidget.tag_ranges(tagname)
    insert_at_end(twidget, init_char_idx_bounds[1], newtext)
    new_bounds = twidget.tag_ranges(tagname)

def replace(twidget, tagname, newtext):
    init_char_idx_bounds = twidget.tag_ranges(tagname)
    if len(init_char_idx_bounds) > 2:
        print('too many matches, no replacements done')
        return None
    insert(twidget, tagname, newtext)
    twidget.delete(init_char_idx_bounds[0], init_char_idx_bounds[1])

def append_no_dup(item, list):
    if not item in list:
        list.append(item)