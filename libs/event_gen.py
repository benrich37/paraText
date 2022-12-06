def right_click_coord(ex, coords):
    ex.event_generate('<Motion>', x=coords[0], y=coords[1])
    ex.event_generate('<Button-2>', x=coords[0], y=coords[1])
    ex.event_generate('<ButtonRelease-2>', x=coords[0], y=coords[1])


def left_click_coord(ex, coords):
    ex.event_generate('<Motion>', x=coords[0], y=coords[1])
    ex.event_generate('<Button-1>', x=coords[0], y=coords[1])
    ex.event_generate('<ButtonRelease-1>', x=coords[0], y=coords[1])


def shift_right_click_coord(ex, coords):
    ex.event_generate('<Motion>', x=coords[0], y=coords[1])
    ex.event_generate('<Shift-Button-2>', x=coords[0], y=coords[1])
    ex.event_generate('<Shift-ButtonRelease-2>', x=coords[0], y=coords[1])


def shift_left_click_coord(ex, coords):
    ex.event_generate('<Motion>', x=coords[0], y=coords[1])
    ex.event_generate('<Shift-Button-1>', x=coords[0], y=coords[1])
    ex.event_generate('<Shift-ButtonRelease-1>', x=coords[0], y=coords[1])


def click_char(ex, char_idx, click_fn):
    coords = ex.bbox(char_idx)
    click_fn(ex, coords)
