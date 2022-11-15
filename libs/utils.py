import math

hex_chars = "0123456789ABCDEF"

def make_darker(hex_color, dark_fac=2):
    """

    :param hex_color: A string signifying a hex color (#RRGGBB, where RR/GG/BB hold 0 -> 256 in base 16)
    :param dark_fac:
    :return:
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
    return "#" + hex_f[0] + hex_f[1] + hex_f[2]

def get_short_hex(num):
    # the built in hex function for some reason has a '0x' at the beginning of the string
    # (ie hex(1) returns '0x1' and hex(255) returns '0xff') so this truncates off the
    # '0x' to get just the actual hex number (ie '1' or 'ff')
    full_hex = str(hex(math.floor(num)))
    short_hex = full_hex[full_hex.index('x') + 1:]
    return short_hex

def short_hex_to_dec(short_hex):
    # converts a number in hex to its respective number in base 10
    digs = len(short_hex)
    return_sum = 0
    for i in range(digs):
        dig_dec = hex_chars.index(short_hex[i])*(16**(digs-1-i))
        return_sum += dig_dec
    return return_sum

def index_to_ints(index):
    # converts a char idx (line number,character number) into invidiual ints from each part
    split = index.index('.')
    line_idx = int(index[0:split])
    col_idx = int(index[split + 1:])
    return line_idx, col_idx

def ints_to_index(line_idx, col_idx):
    return str(line_idx) + '.' + str(col_idx)

def add_to_idx(index, mod_int, add=True):
    line_idx, col_idx = index_to_ints(str(index))
    if add:
        new_col_idx = col_idx + mod_int
    else:
        new_col_idx = col_idx - mod_int
    new_index = ints_to_index(line_idx, new_col_idx)
    return new_index

def del_fn(widg):
    widg.destroy()

def return_matches(twidget, pattern):
    results = []
    over = False
    last_idx = '1.0'
    while not over:
        resulti = twidget.search(pattern, last_idx, stopindex=twidget.index('end'))
        if len(resulti) == 0:
            over = True
        else:
            last_idx = add_to_idx(resulti, 1)
            results.append(resulti)
    return results

def get_text_by_tagname(twidget, tagname):
    bounds = twidget.tag_ranges(tagname)
    if len(bounds) > 2:
        print('only returning first tagged section')
    return twidget.get(bounds[0], bounds[1])

def insert_at_end(twidget, tagname, end_index, insert_text):
    text_len = len(insert_text)
    insert_index = add_to_idx(str(end_index), 1, add=False)
    cut_text = twidget.get(insert_index)
    twidget.insert(insert_index, insert_text)
    del_index = add_to_idx(str(end_index), text_len - 1, add=True)
    twidget.delete(del_index)
    twidget.insert(insert_index, cut_text)

def insert(twidget, tagname, newtext):
    init_bounds = twidget.tag_ranges(tagname)
    insert_at_end(twidget, tagname, init_bounds[1], newtext)
    new_bounds = twidget.tag_ranges(tagname)

def replace(twidget, tagname, newtext):
    init_bounds = twidget.tag_ranges(tagname)
    if len(init_bounds) > 2:
        print('too many matches, no replacements done')
        return None
    insert(twidget, tagname, newtext)
    twidget.delete(init_bounds[0], init_bounds[1])

def append_no_dup(item, list):
    if not item in list:
        list.append(item)