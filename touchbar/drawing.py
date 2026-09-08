"""Cairo drawing at the Touch Bar's native aspect ratio; uses installed fonts."""
import math
import cairo

BG = (0.0, 0.0, 0.0)
PLATE = (0.12, 0.14, 0.18)
FG = (0.91, 0.94, 0.98)
ACCENT = (0.40, 0.68, 0.98)


def text(c, value, x, y, size=25, font='sans-serif', color=FG):
    c.select_font_face(font, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    c.set_font_size(size)
    c.set_source_rgb(*color)
    ext = c.text_extents(value)
    c.move_to(x - ext.width / 2 - ext.x_bearing, y - ext.height / 2 - ext.y_bearing)
    c.show_text(value)


def rounded(c, x, y, width, height, radius=8):
    c.new_sub_path()
    for cx, cy, start in [(x+width-radius,y+radius,-math.pi/2),
                          (x+width-radius,y+height-radius,0),
                          (x+radius,y+height-radius,math.pi/2),
                          (x+radius,y+radius,math.pi)]:
        c.arc(cx, cy, radius, start, start + math.pi/2)
    c.close_path()


def icon(c, name, x, y, size=34):
    if name == 'omarchy':
        text(c, '\ue900', x, y, 41, 'omarchy', ACCENT)
        return
    c.save()
    c.translate(x, y)
    c.scale(size / 32, size / 32)
    c.set_source_rgb(*FG)
    c.set_line_width(2.4)
    c.set_line_cap(cairo.LINE_CAP_ROUND)
    c.set_line_join(cairo.LINE_JOIN_ROUND)
    if name == 'volume':
        c.move_to(-13,-5); c.line_to(-7,-5); c.line_to(0,-11); c.line_to(0,11)
        c.line_to(-7,5); c.line_to(-13,5); c.close_path(); c.stroke()
        for radius in (7,13):
            c.arc(0,0,radius,-0.8,0.8); c.stroke()
    elif name == 'brightness':
        c.arc(0,0,6,0,2*math.pi); c.stroke()
        for n in range(8):
            a=n*math.pi/4
            c.move_to(10*math.cos(a),10*math.sin(a)); c.line_to(14*math.cos(a),14*math.sin(a)); c.stroke()
    elif name == 'keyboard':
        rounded(c,-15,-9,30,19,3); c.stroke()
        for row in (-4,1):
            for col in (-9,-3,3,9):
                c.rectangle(col-1,row-1,2,2); c.fill()
        c.move_to(-7,6); c.line_to(7,6); c.stroke()
    elif name == 'workspaces':
        for x1 in (-12,2):
            for y1 in (-12,2):
                rounded(c,x1,y1,10,10,2); c.stroke()
    elif name == 'camera':
        c.move_to(-14,-7); c.line_to(-6,-7); c.line_to(-3,-12); c.line_to(6,-12)
        c.line_to(9,-7); c.line_to(14,-7); c.line_to(14,11); c.line_to(-14,11); c.close_path(); c.stroke()
        c.arc(0,1,6,0,2*math.pi); c.stroke()
    elif name == 'bell':
        c.move_to(-12,8); c.line_to(-8,3); c.line_to(-8,-4)
        c.curve_to(-8,-17,8,-17,8,-4); c.line_to(8,3); c.line_to(12,8); c.close_path(); c.stroke()
        c.arc(0,10,4,0,math.pi); c.stroke()
    elif name in ('previous','next','play'):
        if name == 'previous': c.scale(-1,1)
        if name == 'play':
            # Combined play/pause glyph is honest without a player-state query.
            c.move_to(-13,-11); c.line_to(1,0); c.line_to(-13,11); c.close_path(); c.fill()
            c.rectangle(5,-10,3,20); c.rectangle(11,-10,3,20); c.fill()
        else:
            c.move_to(-10,-11); c.line_to(7,0); c.line_to(-10,11); c.close_path(); c.fill()
            c.move_to(12,-11); c.line_to(12,11); c.stroke()
    elif name == 'back':
        c.move_to(9,-9); c.line_to(-2,-9); c.line_to(-11,0); c.line_to(-2,9)
        c.move_to(-11,0); c.line_to(4,0); c.curve_to(16,0,16,13,5,13); c.stroke()
    c.restore()


def render(layout, width=2170, height=60):
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, width, height)
    c = cairo.Context(surface)
    c.scale(width / 2170, height / 60)
    c.set_source_rgb(*BG); c.paint()
    for item in layout.items():
        if item.action == 'spacer':
            continue
        active = item.action == layout.pressed or item.action == f"workspace:{layout.state['workspace']}"
        c.set_source_rgb(*(tuple(v * 1.5 for v in PLATE) if active else PLATE))
        rounded(c, item.x, 2, item.width, 56); c.fill()
        if item.action == 'slider':
            level = layout.state[layout.page]
            start, end = item.x + 34, item.x + item.width - 100
            c.set_line_width(8); c.set_line_cap(cairo.LINE_CAP_ROUND)
            c.set_source_rgb(0.28,0.31,0.36)
            c.move_to(start,30); c.line_to(end,30); c.stroke()
            if level is not None:
                point = start + (end - start) * level / 100
                c.set_source_rgb(*ACCENT); c.move_to(start,30); c.line_to(point,30); c.stroke()
                c.set_source_rgb(*FG); c.arc(point,30,12,0,2*math.pi); c.fill()
            text(c,item.label,item.x+item.width-48,30,24)
        elif item.icon and item.label:
            center = item.x + item.width/2
            size, icon_width, gap = 23, 30, 16
            c.select_font_face('sans-serif',cairo.FONT_SLANT_NORMAL,cairo.FONT_WEIGHT_BOLD)
            c.set_font_size(size)
            label_width = c.text_extents(item.label).width
            if label_width + icon_width + gap > item.width - 24:
                size = max(15, size * (item.width - 24 - icon_width - gap) / max(1,label_width))
                c.set_font_size(size)
                label_width = c.text_extents(item.label).width
            left = center - (icon_width + gap + label_width)/2
            icon(c,item.icon,left+icon_width/2,30,icon_width)
            text(c,item.label,left+icon_width+gap+label_width/2,30,size)
        elif item.icon:
            icon(c,item.icon,item.x+item.width/2,30)
        else:
            text(c,item.label,item.x+item.width/2,30,26)
    surface.flush()
    return surface
