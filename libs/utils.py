import math

hex_chars = "0123456789ABCDEF"

def make_darker(hex_color, dark_fac=2):
    if hex_color[0] != "#":
        raise ValueError
    else:
        hex_i = [hex_color[1:3],hex_color[3:5],hex_color[5:]]
        dec_i = []
        for he in hex_i:
            dec_i.append(int(short_hex_to_dec(he)))
        dec_changes = []
        for de in dec_i:
            dec_changes.append(math.floor(de/dark_fac))
        dec_f = []
        for i in [0,1,2]:
            dec_f.append(dec_i[i] - dec_changes[i])
        hex_f = []
        for de in dec_f:
            hex_f.append(get_short_hex(de))
    return "#" + hex_f[0] + hex_f[1] + hex_f[2]

def get_short_hex(num):
    full_hex = str(hex(math.floor(num)))
    short_hex = full_hex[full_hex.index('x') + 1:]
    return short_hex

def short_hex_to_dec(short_hex):
    digs = len(short_hex)
    return_sum = 0
    for i in range(digs):
        dig_dec = hex_chars.index(short_hex[i])*(16**(digs-1-i))
        return_sum += dig_dec
    return return_sum

def index_to_ints(index):
    split = index.index('.')
    line_idx = int(index[0:split])
    char_idx = int(index[split + 1:])
    return line_idx, char_idx

def ints_to_index(line_idx, char_idx):
    return str(line_idx) + '.' + str(char_idx)

def add_to_idx(index, mod_int, add=True):
    line_idx, char_idx = index_to_ints(str(index))
    if add:
        new_char_idx = char_idx + mod_int
    else:
        new_char_idx = char_idx - mod_int
    new_index = ints_to_index(line_idx, new_char_idx)
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